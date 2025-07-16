# WebMusic

Lightweight web-based music server.

## AI Notice

This repo was vibecoded in an afternoon by Claude Sonnet 4. Good job, Claude Sonnet.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run server
python app.py --library /path/to/music --port 8080

# Or deploy as systemd service
./deploy.sh
```

## Features

- Folder with music files in (taglib)
- CUE/TTA support

That's 'bout it.

## Requirements

- Python 3.10+
- ffmpeg (for transcoding)
- SQLite3
- Taglib
