"""Filesystem scanner for WebMusic."""

import os
import threading
import time
from pathlib import Path
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import mutagen

from database import Database


class MusicScanner:
    """Scans filesystem for music files and updates database."""
    
    AUDIO_EXTENSIONS = {'.mp3', '.flac', '.ogg', '.m4a', '.wav', '.tta'}
    ART_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp'}
    ART_FILENAMES = {'cover', 'folder', 'album', 'front'}
    
    def __init__(self, library_path: str, db: Database):
        self.library_path = Path(library_path)
        self.db = db
        self.scanning = False
        self._stop_event = threading.Event()
    
    def find_album_art(self, album_path: Path) -> str | None:
        """Find album art in the album directory."""
        for filename in self.ART_FILENAMES:
            for ext in self.ART_EXTENSIONS:
                art_file = album_path / f"{filename}{ext}"
                if art_file.exists():
                    return str(art_file)
        
        # Look for any image file
        for file in album_path.iterdir():
            if file.suffix.lower() in self.ART_EXTENSIONS:
                return str(file)
        
        return None
    
    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Extract metadata from audio file."""
        audio_file = mutagen.File(str(file_path))
        
        # Handle files that mutagen can't read
        if not audio_file:
            return {
                'title': file_path.stem,
                'artist': None,
                'album': None,
                'track_number': None,
                'duration': 0
            }
        
        metadata = {
            'title': self._get_tag(audio_file, ['TIT2', 'TITLE', '\xa9nam']),
            'artist': self._get_tag(audio_file, ['TPE1', 'ARTIST', '\xa9ART']),
            'album': self._get_tag(audio_file, ['TALB', 'ALBUM', '\xa9alb']),
            'track_number': self._get_track_number(audio_file),
            'duration': getattr(audio_file.info, 'length', 0)
        }
        
        # Use filename as title if not found in tags
        if not metadata['title']:
            metadata['title'] = file_path.stem
        
        return metadata
    
    def _get_tag(self, audio_file: mutagen.FileType, tag_names: List[str]) -> str | None:
        """Get tag value from audio file, trying multiple tag formats."""
        for tag_name in tag_names:
            try:
                if tag_name in audio_file:
                    value = audio_file[tag_name]
                    if isinstance(value, list) and value:
                        return str(value[0])
                    elif value:
                        return str(value)
            except (ValueError, KeyError):
                # Some audio files raise ValueError when checking tag existence
                continue
        return None
    
    def _get_track_number(self, audio_file: mutagen.FileType) -> int | None:
        """Extract track number from various tag formats."""
        track_tags = ['TRCK', 'TRACKNUMBER', 'trkn']
        for tag_name in track_tags:
            if tag_name in audio_file:
                value = audio_file[tag_name]
                if isinstance(value, list) and value:
                    value = value[0]
                
                # Handle "track/total" format
                if isinstance(value, str) and '/' in value:
                    value = value.split('/')[0]
                
                try:
                    return int(str(value))
                except (ValueError, TypeError):
                    continue
        
        return None
    
    def scan_album(self, album_path: Path) -> bool:
        """Scan a single album directory."""
        assert album_path.is_dir(), f"Path is not a directory: {album_path}"
        
        # Convert to bytes for database operations
        album_path_bytes = os.fsencode(album_path)
        
        # Check if album needs updating
        last_modified = album_path.stat().st_mtime
        if not self.db.album_needs_update(album_path_bytes, last_modified):
            return False
        
        # Find audio files
        audio_files = []
        for file in album_path.iterdir():
            if file.suffix.lower() in self.AUDIO_EXTENSIONS:
                audio_files.append(file)
        
        if not audio_files:
            return False
        
        # Extract album metadata from first audio file
        first_file_meta = self.extract_metadata(audio_files[0])
        album_name = first_file_meta.get('album') or album_path.name
        album_artist = first_file_meta.get('artist')
        
        # Find album art
        art_path = self.find_album_art(album_path)
        art_path_bytes = os.fsencode(art_path) if art_path else None
        
        # Add album to database
        album_id = self.db.add_album(
            path=album_path_bytes,
            name=album_name,
            artist=album_artist,
            last_modified=last_modified,
            art_path=art_path_bytes
        )
        
        # Add tracks
        for audio_file in audio_files:
            metadata = self.extract_metadata(audio_file)
            self.db.add_track(
                album_id=album_id,
                path=os.fsencode(audio_file),
                title=metadata['title'],
                artist=metadata['artist'],
                duration=metadata['duration'],
                track_number=metadata['track_number']
            )
        
        return True
    
    def scan_library(self) -> Dict[str, int]:
        """Scan the entire music library."""
        assert not self.scanning, "Scan already in progress"
        
        self.scanning = True
        self._stop_event.clear()
        stats = {'albums_scanned': 0, 'albums_updated': 0}
        
        print(f"Starting library scan of: {self.library_path}")
        
        try:
            # First pass: collect all album directories
            album_dirs = []
            for root, dirs, files in os.walk(os.fsencode(self.library_path), followlinks=True):
                if self._stop_event.is_set():
                    print("Scan stopped by user request")
                    break
                
                root_path = Path(os.fsdecode(root))
                
                # Check if this directory contains audio files (leaf directory)
                has_audio = any(
                    Path(os.fsdecode(root), os.fsdecode(f)).suffix.lower() in self.AUDIO_EXTENSIONS 
                    for f in files
                )
                
                if has_audio:
                    album_dirs.append(root_path)
            
            print(f"Found {len(album_dirs)} album directories")
            
            # Second pass: scan albums in parallel
            with ThreadPoolExecutor(max_workers=4) as executor:
                # Submit all scan jobs
                future_to_path = {
                    executor.submit(self.scan_album, album_path): album_path 
                    for album_path in album_dirs
                }
                
                # Process completed scans
                for future in as_completed(future_to_path):
                    if self._stop_event.is_set():
                        print("Scan stopped by user request")
                        break
                    
                    album_path = future_to_path[future]
                    try:
                        was_updated = future.result()
                        stats['albums_scanned'] += 1
                        if was_updated:
                            stats['albums_updated'] += 1
                        
                        print(f"Scanned album: {album_path.relative_to(self.library_path)} {'(updated)' if was_updated else '(up to date)'}")
                        
                        # Progress update every 10 albums
                        if stats['albums_scanned'] % 10 == 0:
                            print(f"Progress: {stats['albums_scanned']}/{len(album_dirs)} albums scanned, {stats['albums_updated']} updated")
                    
                    except Exception as e:
                        print(f"Error scanning {album_path.relative_to(self.library_path)}: {e}")
                        stats['albums_scanned'] += 1
        
        finally:
            self.scanning = False
            print(f"Library scan complete: {stats['albums_scanned']} albums scanned, {stats['albums_updated']} updated")
        
        return stats
    
    def scan_library_background(self, interval: int = 300) -> threading.Thread:
        """Run library scan in background thread."""
        def scan_loop() -> None:
            while not self._stop_event.is_set():
                print("Starting background library scan...")
                stats = self.scan_library()
                print(f"Scan complete: {stats}")
                
                # Wait for next scan or stop event
                if self._stop_event.wait(timeout=interval):
                    break
        
        thread = threading.Thread(target=scan_loop, daemon=True)
        thread.start()
        return thread
    
    def stop_scanning(self) -> None:
        """Stop background scanning."""
        self._stop_event.set()
        self.scanning = False
