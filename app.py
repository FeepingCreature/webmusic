"""Main Flask application for WebMusic."""

import argparse
import os
import threading
from pathlib import Path
from flask import Flask, render_template, request, jsonify, abort, Response as FlaskResponse
from flask.wrappers import Response
from typing import Any, Dict, List
import mimetypes

from database import Database
from scanner import MusicScanner
from transcoder import AudioTranscoder


def send_file_bytes(file_path: Path) -> Response:
    """Send a file using raw bytes path to handle non-UTF-8 filenames."""
    assert file_path.exists(), f"File not found: {file_path}"
    
    # Determine MIME type
    mime_type, _ = mimetypes.guess_type(str(file_path))
    if not mime_type:
        mime_type = 'application/octet-stream'
    
    # Get file size
    file_size = file_path.stat().st_size
    
    # Open and read file in binary mode
    with open(file_path, 'rb') as f:
        file_data = f.read()
    
    # Create response with proper headers
    response = FlaskResponse(
        file_data,
        mimetype=mime_type,
        headers={
            'Content-Length': str(file_size),
            'Cache-Control': 'public, max-age=3600'
        }
    )
    
    return response


def create_app(library_path: str, auth_enabled: bool = False, base_path: str = '') -> Flask:
    """Create and configure Flask application."""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.urandom(24)
    
    # Configure base path for reverse proxy support
    base_path_clean = base_path.rstrip('/')
    app.config['BASE_PATH'] = base_path_clean
    
    # Custom template function to generate URLs with base path
    @app.template_global()
    def url_for_with_base(endpoint, **values):
        url = app.url_for(endpoint, **values)
        if base_path_clean and url.startswith('/'):
            url = base_path_clean + url
        return url
    
    # Initialize database, scanner, and transcoder
    db = Database()
    scanner = MusicScanner(library_path, db)
    transcoder = AudioTranscoder()
    
    # Store in app context
    app.db = db
    app.scanner = scanner
    app.transcoder = transcoder
    app.library_path = Path(library_path)
    app.auth_enabled = auth_enabled
    
    @app.route('/')
    def index() -> str:
        """Main page - redirect to albums."""
        return albums()
    
    @app.route('/albums')
    def albums() -> str:
        """Albums page."""
        albums_list = app.db.get_albums()
        return render_template('albums.html', albums=albums_list)
    
    @app.route('/album/<int:album_id>')
    def album_detail(album_id: int) -> str:
        """Album detail page."""
        try:
            album = app.db.get_album_by_id(album_id)
            tracks = app.db.get_tracks_by_album(album_id)
            
            # Convert bytes fields to strings for JSON serialization
            if album['art_path']:
                album['art_path'] = os.fsdecode(album['art_path'])
            
            return render_template('album_detail.html', album=album, tracks=tracks)
        except AssertionError:
            abort(404)
    
    @app.route('/artists')
    def artists() -> str:
        """Artists page."""
        # Get unique artists from albums
        albums_list = app.db.get_albums()
        artists_dict: Dict[str, List[Dict[str, Any]]] = {}
        
        for album in albums_list:
            artist = album['artist'] or 'Unknown Artist'
            if artist not in artists_dict:
                artists_dict[artist] = []
            artists_dict[artist].append(album)
        
        artists_list = [
            {'name': name, 'albums': albums, 'album_count': len(albums)}
            for name, albums in sorted(artists_dict.items())
        ]
        
        return render_template('artists.html', artists=artists_list)
    
    
    @app.route('/api/scan')
    def api_scan() -> Response:
        """Trigger library scan."""
        if app.scanner.scanning:
            return jsonify({'status': 'already_scanning'})
        
        # Start scan in background
        def scan_thread() -> None:
            stats = app.scanner.scan_library()
            print(f"Scan completed: {stats}")
        
        threading.Thread(target=scan_thread, daemon=True).start()
        return jsonify({'status': 'scan_started'})
    
    @app.route('/api/scan/status')
    def api_scan_status() -> Response:
        """Get scan status."""
        return jsonify({'scanning': app.scanner.scanning})
    
    @app.route('/api/profiles')
    def api_profiles() -> Response:
        """Get available transcoding profiles."""
        from transcoder import TRANSCODING_PROFILES
        profiles = {
            name: {
                'name': profile.name,
                'codec': profile.codec,
                'bitrate': profile.bitrate,
                'format': profile.format
            }
            for name, profile in TRANSCODING_PROFILES.items()
        }
        return jsonify(profiles)
    
    @app.route('/stream/<int:track_id>')
    def stream_track(track_id: int) -> FlaskResponse:
        """Stream audio file with optional transcoding."""
        # Get track from database
        with app.db.get_connection() as conn:
            track = conn.execute(
                "SELECT * FROM tracks WHERE id = ?", (track_id,)
            ).fetchone()
        
        assert track, f"Track not found: {track_id}"
        
        # Convert bytes path back to filesystem path
        track_path = Path(os.fsdecode(track['path']))
        assert track_path.exists(), f"Track file not found: {track_path}"
        
        # Increment play count
        app.db.increment_play_count(track_id)
        
        # Get transcoding profile from query parameter
        profile = request.args.get('profile', 'raw')
        
        # Check if this is a CUE track (has cue_start)
        if track['cue_start'] is not None:
            # Stream CUE track segment
            start_time = track['cue_start']
            duration = None
            if track['cue_end'] is not None:
                duration = track['cue_end'] - track['cue_start']
            
            def generate():
                for chunk in app.transcoder.stream_audio(track_path, profile, start_time, duration):
                    yield chunk
            
            content_type = app.transcoder.get_content_type(profile)
            return FlaskResponse(generate(), mimetype=content_type)
        
        else:
            # Regular audio file
            if profile == 'raw':
                # Serve file directly for raw profile
                return send_file_bytes(track_path)
            else:
                # Transcode entire file
                def generate():
                    for chunk in app.transcoder.stream_audio(track_path, profile):
                        yield chunk
                
                content_type = app.transcoder.get_content_type(profile)
                return FlaskResponse(generate(), mimetype=content_type)
    
    @app.route('/art/<int:album_id>')
    def album_art(album_id: int) -> Response:
        """Serve album art."""
        try:
            album = app.db.get_album_by_id(album_id)
            assert album['art_path'], f"No art path for album: {album_id}"
            
            # Convert bytes path back to filesystem path
            art_path = Path(os.fsdecode(album['art_path']))
            assert art_path.exists(), f"Art file not found: {art_path}"
            
            return send_file_bytes(art_path)
        except AssertionError:
            abort(404)
    
    return app


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description='WebMusic - Lightweight music server')
    parser.add_argument('--library', required=True, help='Path to music library')
    parser.add_argument('--port', type=int, default=8080, help='Port to run on')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--auth', choices=['required', 'optional', 'disabled'], 
                       default='disabled', help='Authentication mode')
    parser.add_argument('--scan-interval', type=int, default=300, 
                       help='Background scan interval in seconds')
    parser.add_argument('--base-path', default='', 
                       help='Base path for reverse proxy (e.g., /webmusic)')
    
    args = parser.parse_args()
    
    assert os.path.exists(args.library), f"Library path does not exist: {args.library}"
    
    # Create Flask app
    auth_enabled = args.auth in ['required', 'optional']
    app = create_app(args.library, auth_enabled, args.base_path)
    
    # Start background scanner
    if args.scan_interval > 0:
        print(f"Starting background scanner (interval: {args.scan_interval}s)")
        app.scanner.scan_library_background(args.scan_interval)
    
    print(f"Starting WebMusic on http://{args.host}:{args.port}")
    print(f"Library: {args.library}")
    
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == '__main__':
    main()
