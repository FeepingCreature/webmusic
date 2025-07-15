"""Main Flask application for WebMusic."""

import argparse
import os
import threading
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, abort
from flask.wrappers import Response
from typing import Any, Dict, List

from database import Database
from scanner import MusicScanner


def create_app(library_path: str, auth_enabled: bool = False) -> Flask:
    """Create and configure Flask application."""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.urandom(24)
    
    # Initialize database and scanner
    db = Database()
    scanner = MusicScanner(library_path, db)
    
    # Store in app context
    app.db = db
    app.scanner = scanner
    app.library_path = Path(library_path)
    app.auth_enabled = auth_enabled
    
    @app.route('/')
    def index() -> str:
        """Main page - redirect to albums."""
        return albums()
    
    @app.route('/albums')
    def albums() -> str:
        """Albums page."""
        page = request.args.get('page', 1, type=int)
        limit = 50
        offset = (page - 1) * limit
        
        albums_list = app.db.get_albums(limit=limit, offset=offset)
        
        # Check if this is an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Return just the content for AJAX requests
            return render_template('albums.html', albums=albums_list, page=page)
        
        return render_template('albums.html', albums=albums_list, page=page)
    
    @app.route('/album/<int:album_id>')
    def album_detail(album_id: int) -> str:
        """Album detail page."""
        try:
            album = app.db.get_album_by_id(album_id)
            tracks = app.db.get_tracks_by_album(album_id)
            
            # Check if this is an AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return render_template('album_detail.html', album=album, tracks=tracks)
            
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
        
        # Check if this is an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return render_template('artists.html', artists=artists_list)
        
        return render_template('artists.html', artists=artists_list)
    
    @app.route('/search')
    def search() -> str:
        """Search page."""
        query = request.args.get('q', '').strip()
        results: Dict[str, List[Dict[str, Any]]] = {'albums': [], 'tracks': []}
        
        if query:
            results['albums'] = app.db.search_albums(query)
            results['tracks'] = app.db.search_tracks(query)
        
        # Check if this is an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return render_template('search.html', query=query, results=results)
        
        return render_template('search.html', query=query, results=results)
    
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
    
    @app.route('/stream/<int:track_id>')
    def stream_track(track_id: int) -> Response:
        """Stream audio file."""
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
        
        # For now, serve file directly (transcoding will be added later)
        return send_file(track_path, as_attachment=False)
    
    @app.route('/art/<int:album_id>')
    def album_art(album_id: int) -> Response:
        """Serve album art."""
        try:
            album = app.db.get_album_by_id(album_id)
            assert album['art_path'], f"No art path for album: {album_id}"
            
            # Convert bytes path back to filesystem path
            art_path = Path(os.fsdecode(album['art_path']))
            assert art_path.exists(), f"Art file not found: {art_path}"
            
            return send_file(art_path)
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
    
    args = parser.parse_args()
    
    assert os.path.exists(args.library), f"Library path does not exist: {args.library}"
    
    # Create Flask app
    auth_enabled = args.auth in ['required', 'optional']
    app = create_app(args.library, auth_enabled)
    
    # Initial scan
    print("Performing initial library scan...")
    stats = app.scanner.scan_library()
    print(f"Initial scan complete: {stats}")
    
    # Start background scanner
    if args.scan_interval > 0:
        print(f"Starting background scanner (interval: {args.scan_interval}s)")
        app.scanner.scan_library_background(args.scan_interval)
    
    print(f"Starting WebMusic on http://{args.host}:{args.port}")
    print(f"Library: {args.library}")
    
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == '__main__':
    main()
