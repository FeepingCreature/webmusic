"""Filesystem scanner for WebMusic."""

import os
import threading
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import mutagen
from mutagen.id3 import ID3NoHeaderError

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
        self._stop_scan = False
    
    def find_album_art(self, album_path: Path) -> Optional[str]:
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
        try:
            audio_file = mutagen.File(str(file_path))
            if not audio_file:
                return {}
            
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
            
        except (ID3NoHeaderError, Exception):
            # Fallback to filename
            return {
                'title': file_path.stem,
                'artist': None,
                'album': None,
                'track_number': None,
                'duration': 0
            }
    
    def _get_tag(self, audio_file, tag_names: List[str]) -> Optional[str]:
        """Get tag value from audio file, trying multiple tag formats."""
        for tag_name in tag_names:
            if tag_name in audio_file:
                value = audio_file[tag_name]
                if isinstance(value, list) and value:
                    return str(value[0])
                elif value:
                    return str(value)
        return None
    
    def _get_track_number(self, audio_file) -> Optional[int]:
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
        if not album_path.is_dir():
            return False
        
        # Check if album needs updating
        last_modified = album_path.stat().st_mtime
        if not self.db.album_needs_update(str(album_path), last_modified):
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
        
        # Add album to database
        album_id = self.db.add_album(
            path=str(album_path),
            name=album_name,
            artist=album_artist,
            last_modified=last_modified,
            art_path=art_path
        )
        
        # Add tracks
        for audio_file in audio_files:
            metadata = self.extract_metadata(audio_file)
            self.db.add_track(
                album_id=album_id,
                path=str(audio_file),
                title=metadata['title'],
                artist=metadata['artist'],
                duration=metadata['duration'],
                track_number=metadata['track_number']
            )
        
        return True
    
    def scan_library(self) -> Dict[str, int]:
        """Scan the entire music library."""
        if self.scanning:
            return {'error': 'Scan already in progress'}
        
        self.scanning = True
        self._stop_scan = False
        stats = {'albums_scanned': 0, 'albums_updated': 0}
        
        try:
            for root, dirs, files in os.walk(self.library_path, followlinks=True):
                if self._stop_scan:
                    break
                
                root_path = Path(root)
                
                # Check if this directory contains audio files (leaf directory)
                has_audio = any(
                    Path(root, f).suffix.lower() in self.AUDIO_EXTENSIONS 
                    for f in files
                )
                
                if has_audio:
                    if self.scan_album(root_path):
                        stats['albums_updated'] += 1
                    stats['albums_scanned'] += 1
        
        finally:
            self.scanning = False
        
        return stats
    
    def scan_library_background(self, interval: int = 300):
        """Run library scan in background thread."""
        def scan_loop():
            while not self._stop_scan:
                print("Starting background library scan...")
                stats = self.scan_library()
                print(f"Scan complete: {stats}")
                
                # Wait for next scan
                for _ in range(interval):
                    if self._stop_scan:
                        break
                    time.sleep(1)
        
        thread = threading.Thread(target=scan_loop, daemon=True)
        thread.start()
        return thread
    
    def stop_scanning(self):
        """Stop background scanning."""
        self._stop_scan = True
        self.scanning = False
