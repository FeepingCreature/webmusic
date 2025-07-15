"""CUE file parser for WebMusic."""

import re
from pathlib import Path
from typing import List, Dict, Any, Tuple


class CueTrack:
    """Represents a single track from a CUE file."""
    
    def __init__(self, number: int, title: str, performer: str | None = None, 
                 start_time: float = 0.0, end_time: float | None = None):
        self.number = number
        self.title = title
        self.performer = performer
        self.start_time = start_time
        self.end_time = end_time


class CueSheet:
    """Represents a parsed CUE file."""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.audio_file: str | None = None
        self.album_title: str | None = None
        self.album_performer: str | None = None
        self.genre: str | None = None
        self.date: str | None = None
        self.tracks: List[CueTrack] = []
    
    def get_audio_file_path(self) -> Path | None:
        """Get the full path to the audio file referenced by this CUE."""
        if not self.audio_file:
            return None
        
        # Audio file path is relative to CUE file location
        audio_path = self.file_path.parent / self.audio_file
        return audio_path if audio_path.exists() else None


def parse_time(time_str: str) -> float:
    """Parse CUE time format (MM:SS:FF) to seconds."""
    parts = time_str.split(':')
    if len(parts) != 3:
        return 0.0
    
    try:
        minutes = int(parts[0])
        seconds = int(parts[1])
        frames = int(parts[2])
        
        # 75 frames per second in CD audio
        return minutes * 60 + seconds + frames / 75.0
    except ValueError:
        return 0.0


def parse_cue_file(cue_path: Path) -> CueSheet | None:
    """Parse a CUE file and return a CueSheet object."""
    if not cue_path.exists() or cue_path.suffix.lower() != '.cue':
        return None
    
    cue_sheet = CueSheet(cue_path)
    current_track: CueTrack | None = None
    
    try:
        with open(cue_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('REM COMMENT'):
                    continue
                
                # Parse global metadata
                if line.startswith('TITLE '):
                    title = _extract_quoted_value(line)
                    if current_track:
                        current_track.title = title
                    else:
                        cue_sheet.album_title = title
                
                elif line.startswith('PERFORMER '):
                    performer = _extract_quoted_value(line)
                    if current_track:
                        current_track.performer = performer
                    else:
                        cue_sheet.album_performer = performer
                
                elif line.startswith('FILE '):
                    # Extract filename (remove quotes and WAVE/BINARY suffix)
                    match = re.match(r'FILE\s+"([^"]+)"\s+\w+', line)
                    if match:
                        cue_sheet.audio_file = match.group(1)
                
                elif line.startswith('REM GENRE '):
                    cue_sheet.genre = line[10:].strip()
                
                elif line.startswith('REM DATE '):
                    cue_sheet.date = line[9:].strip()
                
                elif line.startswith('TRACK '):
                    # Finalize previous track
                    if current_track:
                        cue_sheet.tracks.append(current_track)
                    
                    # Start new track
                    match = re.match(r'TRACK\s+(\d+)\s+AUDIO', line)
                    if match:
                        track_number = int(match.group(1))
                        current_track = CueTrack(track_number, "")
                
                elif line.startswith('INDEX 01 ') and current_track:
                    # Parse track start time
                    time_str = line[9:].strip()
                    current_track.start_time = parse_time(time_str)
        
        # Add the last track
        if current_track:
            cue_sheet.tracks.append(current_track)
        
        # Calculate end times for tracks
        for i, track in enumerate(cue_sheet.tracks):
            if i < len(cue_sheet.tracks) - 1:
                track.end_time = cue_sheet.tracks[i + 1].start_time
            # Last track end time will remain None (play to end of file)
        
        return cue_sheet if cue_sheet.tracks else None
    
    except Exception:
        # Let parsing errors bubble up for debugging
        raise


def _extract_quoted_value(line: str) -> str:
    """Extract quoted value from a CUE line."""
    match = re.search(r'"([^"]*)"', line)
    return match.group(1) if match else ""
