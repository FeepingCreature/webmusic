"""Audio transcoding for WebMusic using ffmpeg."""

import subprocess
import shlex
from pathlib import Path
from typing import Dict, Any, Iterator


class TranscodingProfile:
    """Represents an audio transcoding profile."""
    
    def __init__(self, name: str, codec: str, bitrate: str | None = None, 
                 format: str | None = None, extra_args: list[str] | None = None):
        self.name = name
        self.codec = codec
        self.bitrate = bitrate
        self.format = format
        self.extra_args = extra_args or []


# Predefined transcoding profiles
TRANSCODING_PROFILES: Dict[str, TranscodingProfile] = {
    'raw': TranscodingProfile('raw', 'copy'),
    'mp3_320': TranscodingProfile('mp3_320', 'libmp3lame', '320k', 'mp3'),
    'mp3_192': TranscodingProfile('mp3_192', 'libmp3lame', '192k', 'mp3'),
    'mp3_128': TranscodingProfile('mp3_128', 'libmp3lame', '128k', 'mp3'),
    'ogg_256': TranscodingProfile('ogg_256', 'libvorbis', '256k', 'ogg'),
    'ogg_128': TranscodingProfile('ogg_128', 'libvorbis', '128k', 'ogg'),
}


class AudioTranscoder:
    """Handles audio transcoding using ffmpeg."""
    
    def __init__(self):
        self.ffmpeg_path = 'ffmpeg'
    
    def stream_audio(self, input_path: Path, profile_name: str = 'raw',
                     start_time: float | None = None, duration: float | None = None) -> Iterator[bytes]:
        """Stream transcoded audio data."""
        profile = TRANSCODING_PROFILES.get(profile_name, TRANSCODING_PROFILES['raw'])
        
        # Build ffmpeg command
        cmd = [self.ffmpeg_path]
        
        # Input options
        if start_time is not None:
            cmd.extend(['-ss', str(start_time)])
        
        cmd.extend(['-i', str(input_path)])
        
        # Duration limit
        if duration is not None:
            cmd.extend(['-t', str(duration)])
        
        # Output options
        if profile.codec != 'copy':
            cmd.extend(['-acodec', profile.codec])
            
            if profile.bitrate:
                cmd.extend(['-ab', profile.bitrate])
        else:
            cmd.extend(['-c', 'copy'])
        
        # Format
        if profile.format:
            cmd.extend(['-f', profile.format])
        else:
            cmd.extend(['-f', 'wav'])  # Default to WAV for raw
        
        # Extra arguments
        cmd.extend(profile.extra_args)
        
        # Output to stdout
        cmd.extend(['-'])
        
        # Start ffmpeg process
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            
            # Stream data in chunks
            chunk_size = 8192
            while True:
                chunk = process.stdout.read(chunk_size)
                if not chunk:
                    break
                yield chunk
            
            # Wait for process to complete
            process.wait()
            
            if process.returncode != 0:
                stderr = process.stderr.read().decode('utf-8', errors='ignore')
                raise RuntimeError(f"ffmpeg failed with code {process.returncode}: {stderr}")
        
        except FileNotFoundError:
            raise RuntimeError("ffmpeg not found. Please install ffmpeg.")
    
    def get_audio_info(self, input_path: Path) -> Dict[str, Any]:
        """Get audio file information using ffprobe."""
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            str(input_path)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            import json
            return json.loads(result.stdout)
        except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def get_content_type(self, profile_name: str) -> str:
        """Get HTTP content type for a transcoding profile."""
        profile = TRANSCODING_PROFILES.get(profile_name, TRANSCODING_PROFILES['raw'])
        
        content_types = {
            'mp3': 'audio/mpeg',
            'ogg': 'audio/ogg',
            'wav': 'audio/wav',
            'flac': 'audio/flac',
        }
        
        return content_types.get(profile.format or 'wav', 'audio/wav')
