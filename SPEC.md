# WebMusic Specification

WebMusic is a lightweight, web-based music library frontend designed as a simpler alternative to Navidrome. The goal is to provide most essential features with a fraction of the code complexity.

## Core Philosophy

- **Simplicity First**: Leverage Python standard library and system tools (ffmpeg, sqlite3)
- **Progressive Enhancement**: Standard web app that works without JavaScript, enhanced with minimal JS
- **Filesystem-Centric**: Music library is organized in folders, minimal database overhead
- **Streaming Focus**: Dynamic transcoding via ffmpeg for various quality levels

## Architecture Overview

### Backend
- **Language**: Python (standard library preferred)
- **Database**: SQLite3 for metadata and statistics
- **Audio Processing**: ffmpeg for transcoding and streaming
- **Web Framework**: Flask or similar lightweight framework

### Frontend
- **Progressive Web App**: Uninterrupted playback during navigation
- **Minimal JavaScript**: Only for link hijacking and playback continuity
- **Responsive Design**: Works on desktop and mobile

## Core Features

### Music Library Management
- **Single Root Folder**: Configurable via command line
- **Album Organization**: One leaf folder = one album
- **Background Scanning**: Periodic filesystem scanning based on folder modification dates
- **Supported Formats**: 
  - Standard tagged audio files (MP3, FLAC, OGG, etc.)
  - CUE/TTA disk images
- **Metadata Storage**: Track info, album art paths, statistics

### Database Schema
```sql
-- Core tables for music metadata
albums (id, path, name, artist, last_modified, date_added, art_path)
tracks (id, album_id, path, title, artist, duration, track_number, cue_start, cue_end)
stats (track_id, play_count, last_played, date_added)
sessions (id, user_id, token, expires)
users (id, username, password_hash, created)
```

### Audio Streaming & Transcoding
- **Dynamic Transcoding**: Real-time conversion via ffmpeg
- **Quality Levels**: Configurable presets (e.g., "raw", "320k mp3", "128k ogg")
- **CUE Support**: Extract segments from disk images using ffmpeg
- **Streaming Protocol**: HTTP range requests for seeking

### Web Interface

#### Layout
```
┌─────────────────────────────────────────┐
│ [♪] Now Playing: Artist - Song    [⏸] │ ← Persistent header
├─────────────────────────────────────────┤
│ Sidebar │ Main Content Area             │
│ Albums  │                               │
│ Artists │ [Search: ____________]        │
│ Genres  │                               │
│ Playlists│ Album Grid / List View       │
│ Search  │                               │
└─────────────────────────────────────────┘
```

#### Pages
- **Albums**: Grid/list view with cover art
- **Artists**: Artist list with album counts
- **Genres**: Genre-based browsing
- **Search**: Real-time search across all metadata
- **Now Playing**: Current queue and playback controls

### Progressive Web App Features
- **Uninterrupted Playback**: Navigation doesn't stop music
- **Link Hijacking**: JavaScript intercepts internal links
- **History Management**: Proper browser back/forward support
- **Offline Capability**: Basic caching for UI assets

### Authentication System
- **Optional Authentication**: Can run without login
- **Session Management**: Token-based sessions
- **Extensible**: Abstract auth interface for future providers
- **Default**: Simple username/password

## Technical Implementation

### File Organization
```
webmusic/
├── app.py              # Main Flask application
├── scanner.py          # Background library scanner
├── transcoder.py       # ffmpeg transcoding wrapper
├── auth.py             # Authentication system
├── database.py         # SQLite operations
├── static/
│   ├── css/
│   ├── js/
│   └── icons/
└── templates/
    ├── base.html
    ├── albums.html
    ├── artists.html
    └── player.html
```

### Command Line Interface
```bash
webmusic --library /path/to/music --port 8080 --auth optional
```

### Configuration
- **Library Path**: Root music directory
- **Transcoding Presets**: Quality/format combinations
- **Scan Interval**: Background scan frequency
- **Authentication**: Enable/disable user system

### Dependencies
- **Core**: Python 3.8+, SQLite3, ffmpeg
- **Python Packages**: Flask, mutagen (for metadata), bcrypt (for auth)
- **Frontend**: Minimal vanilla JavaScript, modern CSS

## Development Phases

### Phase 1: Core Backend
- [ ] Basic Flask app structure
- [ ] SQLite database schema
- [ ] Filesystem scanner
- [ ] Basic audio streaming

### Phase 2: Web Interface
- [ ] HTML templates and CSS
- [ ] Album/artist browsing
- [ ] Search functionality
- [ ] Basic audio player

### Phase 3: Advanced Features
- [ ] Dynamic transcoding
- [ ] CUE/TTA support
- [ ] Progressive Web App features
- [ ] Authentication system

### Phase 4: Polish
- [ ] Performance optimization
- [ ] Mobile responsiveness
- [ ] Error handling
- [ ] Documentation

## Non-Goals
- **Complex Playlists**: Keep playlist functionality minimal
- **Social Features**: No sharing, comments, or social integration
- **Advanced DSP**: No equalizer, effects, or audio processing
- **Multi-User Libraries**: Single library per instance
- **Complex Metadata**: Stick to basic ID3/Vorbis tags

## Success Metrics
- **Codebase Size**: <2000 lines of Python
- **Memory Usage**: <100MB for 10k+ track libraries
- **Startup Time**: <5 seconds for initial scan
- **Response Time**: <200ms for page loads, <1s for transcoding start
