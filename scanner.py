"""Filesystem scanner for WebMusic."""

import os
import threading
import time
from pathlib import Path
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import mutagen

from database import Database
from cue_parser import parse_cue_file, CueSheet


class MusicScanner:
    """Scans filesystem for music files and updates database."""
    
    AUDIO_EXTENSIONS = {'.mp3', '.flac', '.ogg', '.m4a', '.wav', '.tta'}
    CUE_EXTENSIONS = {'.cue'}
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
            'albumartist': self._get_tag(audio_file, ['TPE2', 'ALBUMARTIST', 'aART']),
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
        # Debug: print all available tags
        print(f"    Available tags: {list(audio_file.keys())}")
        
        # Comprehensive list of track number tag names across formats
        track_tags = [
            'TRCK',        # ID3v2 (MP3)
            'TRACKNUMBER', # Vorbis Comment (OGG, FLAC)
            'TRACK',       # Alternative Vorbis Comment
            'trkn',        # MP4/M4A
            'TPE1',        # Sometimes misused
            'TN',          # ID3v1
        ]
        
        for tag_name in track_tags:
            if tag_name in audio_file:
                value = audio_file[tag_name]
                print(f"    Found tag {tag_name}: {repr(value)}")
                
                if isinstance(value, list) and value:
                    value = value[0]
                
                # Handle "track/total" format
                if isinstance(value, str) and '/' in value:
                    value = value.split('/')[0]
                
                try:
                    track_num = int(str(value))
                    print(f"    Extracted track number: {track_num}")
                    return track_num
                except (ValueError, TypeError):
                    print(f"    Failed to convert {repr(value)} to int")
                    continue
        
        print(f"    No track number found")
        return None
    
    def scan_album(self, album_path: Path) -> bool:
        """Scan a single album directory."""
        try:
            # Use repr() to safely handle non-UTF-8 paths
            rel_path = repr(str(album_path.relative_to(self.library_path)))
            print(f"  → Starting scan of: {rel_path}")
            
            assert album_path.is_dir(), f"Path is not a directory: {album_path}"
            
            # Convert to bytes for database operations
            album_path_bytes = os.fsencode(album_path)
            
            # Check if album needs updating
            last_modified = album_path.stat().st_mtime
            if not self.db.album_needs_update(album_path_bytes, last_modified):
                rel_path = repr(str(album_path.relative_to(self.library_path)))
                print(f"  → Album up to date: {rel_path}")
                return False
            
            rel_path = repr(str(album_path.relative_to(self.library_path)))
            print(f"  → Album needs update: {rel_path}")
            
            # Look for CUE files first
            cue_files = [f for f in album_path.iterdir() if f.suffix.lower() in self.CUE_EXTENSIONS]
            
            if cue_files:
                print(f"  → Processing CUE album: {cue_files[0].name}")
                # Process CUE/TTA album
                result = self.scan_cue_album(album_path, cue_files[0])
                print(f"  → CUE scan result: {result}")
                return result
            else:
                print(f"  → Processing regular audio album")
                # Process regular audio files
                result = self.scan_regular_album(album_path)
                print(f"  → Regular scan result: {result}")
                return result
        except Exception as e:
            # Use repr() to safely handle non-UTF-8 paths
            path_repr = repr(str(album_path))
            print(f"  → Exception in scan_album for {path_repr}: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def scan_regular_album(self, album_path: Path) -> bool:
        """Scan an album with individual audio files."""
        album_path_bytes = os.fsencode(album_path)
        last_modified = album_path.stat().st_mtime
        
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
        album_albumartist = first_file_meta.get('albumartist')
        
        # Find album art
        art_path = self.find_album_art(album_path)
        art_path_bytes = os.fsencode(art_path) if art_path else None
        
        # Add album to database (without updating timestamp yet, clear existing tracks)
        album_id = self.db.add_album(
            path=album_path_bytes,
            name=album_name,
            artist=album_artist,
            albumartist=album_albumartist,
            art_path=art_path_bytes,
            update_timestamp=False,
            clear_tracks=True
        )
        
        # Add tracks
        for audio_file in audio_files:
            metadata = self.extract_metadata(audio_file)
            print(f"  → Adding track: {metadata['title']}, track_number: {metadata['track_number']}")
            self.db.add_track(
                album_id=album_id,
                path=os.fsencode(audio_file),
                title=metadata['title'],
                artist=metadata['artist'],
                duration=metadata['duration'],
                track_number=metadata['track_number']
            )
        
        # Only update timestamp after successful completion
        self.db.update_album_timestamp(album_path_bytes, last_modified)
        
        return True
    
    def scan_cue_album(self, album_path: Path, cue_file: Path) -> bool:
        """Scan an album with CUE file."""
        album_path_bytes = os.fsencode(album_path)
        last_modified = album_path.stat().st_mtime
        
        # Parse CUE file
        print(f"  → Parsing CUE file: {cue_file.name}")
        cue_sheet = parse_cue_file(cue_file)
        if not cue_sheet or not cue_sheet.tracks:
            print(f"  → Failed to parse CUE file or no tracks found")
            return False
        
        print(f"  → Found {len(cue_sheet.tracks)} tracks in CUE file")
        
        # Verify audio file exists
        audio_file_path = cue_sheet.get_audio_file_path()
        if not audio_file_path:
            print(f"  → Audio file not found: {cue_sheet.audio_file}")
            return False
        
        print(f"  → Audio file: {audio_file_path.name}")
        
        # Use CUE metadata for album info
        album_name = cue_sheet.album_title or album_path.name
        album_artist = cue_sheet.album_performer
        
        print(f"  → Album: {album_name} by {album_artist or 'Unknown Artist'}")
        
        # Find album art
        art_path = self.find_album_art(album_path)
        art_path_bytes = os.fsencode(art_path) if art_path else None
        if art_path:
            print(f"  → Found album art: {Path(art_path).name}")
        
        # Add album to database (without updating timestamp yet, clear existing tracks)
        album_id = self.db.add_album(
            path=album_path_bytes,
            name=album_name,
            artist=album_artist,
            albumartist=album_artist,  # For CUE albums, album artist is the performer
            art_path=art_path_bytes,
            update_timestamp=False,
            clear_tracks=True
        )
        
        # Add tracks from CUE
        for i, track in enumerate(cue_sheet.tracks):
            duration = None
            if track.end_time is not None:
                duration = track.end_time - track.start_time
            
            end_time_str = f"{track.end_time:.2f}s" if track.end_time else "end"
            print(f"  → Adding track {track.number}: {track.title} ({track.start_time:.2f}s - {end_time_str})")
            print(f"  → Track number from CUE: {track.number}")
            
            track_id = self.db.add_track(
                album_id=album_id,
                path=os.fsencode(audio_file_path),
                title=track.title,
                artist=track.performer or album_artist,
                duration=duration,
                track_number=track.number,
                cue_start=track.start_time,
                cue_end=track.end_time
            )
            
            print(f"  → Track added with ID: {track_id}")
        
        # Only update timestamp after successful completion
        self.db.update_album_timestamp(album_path_bytes, last_modified)
        
        print(f"  → Successfully added {len(cue_sheet.tracks)} tracks")
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
                
                # Check if this directory contains audio files or CUE files (leaf directory)
                has_audio = any(
                    Path(os.fsdecode(root), os.fsdecode(f)).suffix.lower() in self.AUDIO_EXTENSIONS 
                    for f in files
                )
                has_cue = any(
                    Path(os.fsdecode(root), os.fsdecode(f)).suffix.lower() in self.CUE_EXTENSIONS
                    for f in files
                )
                
                if has_audio or has_cue:
                    album_dirs.append(root_path)
            
            print(f"Found {len(album_dirs)} album directories")
        
            # Second pass: scan albums in parallel
            print(f"Starting parallel scan with ThreadPoolExecutor (4 workers)...")
            with ThreadPoolExecutor(max_workers=4) as executor:
                print(f"Submitting {len(album_dirs)} scan jobs to executor...")
            
                # Submit all scan jobs
                future_to_path = {
                    executor.submit(self.scan_album, album_path): album_path 
                    for album_path in album_dirs
                }
            
                print(f"All {len(future_to_path)} jobs submitted, waiting for completion...")
            
                # Process completed scans
                completed_count = 0
                for future in as_completed(future_to_path):
                    completed_count += 1
                
                    if self._stop_event.is_set():
                        print("Scan stopped by user request")
                        break
                
                    album_path = future_to_path[future]
                    try:
                        # Use repr() to safely handle non-UTF-8 paths
                        rel_path = repr(str(album_path.relative_to(self.library_path)))
                        print(f"Processing result for: {rel_path}")
                        was_updated = future.result()
                        stats['albums_scanned'] += 1
                        if was_updated:
                            stats['albums_updated'] += 1
                    
                        print(f"Scanned album: {rel_path} {'(updated)' if was_updated else '(up to date)'}")
                    
                        # Progress update every 10 albums
                        if stats['albums_scanned'] % 10 == 0:
                            print(f"Progress: {stats['albums_scanned']}/{len(album_dirs)} albums scanned, {stats['albums_updated']} updated")
                
                    except Exception as e:
                        # Use repr() to safely handle non-UTF-8 paths
                        rel_path = repr(str(album_path.relative_to(self.library_path)))
                        print(f"Error scanning {rel_path}: {e}")
                        print(f"Exception type: {type(e).__name__}")
                        import traceback
                        traceback.print_exc()
                        stats['albums_scanned'] += 1
            
                print(f"Completed processing {completed_count} futures out of {len(future_to_path)} submitted")
        
        finally:
            self.scanning = False
            print(f"Library scan complete: {stats['albums_scanned']} albums scanned, {stats['albums_updated']} updated")
        
        return stats
    
    def scan_library_background(self, interval: int = 300) -> threading.Thread:
        """Run library scan in background thread."""
        def scan_loop() -> None:
            while not self._stop_event.is_set():
                print(f"Starting background library scan... (interval: {interval}s)")
                try:
                    stats = self.scan_library()
                    print(f"Background scan complete: {stats}")
                except Exception as e:
                    print(f"Background scan failed: {e}")
                    import traceback
                    traceback.print_exc()
                
                # Wait for next scan or stop event
                print(f"Waiting {interval} seconds until next scan...")
                if self._stop_event.wait(timeout=interval):
                    print("Background scanner stopped by stop event")
                    break
        
        thread = threading.Thread(target=scan_loop, daemon=True)
        thread.start()
        print(f"Background scanner thread started (daemon=True)")
        return thread
    
    def stop_scanning(self) -> None:
        """Stop background scanning."""
        self._stop_event.set()
        self.scanning = False
