"""Database operations for WebMusic."""

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any


class Database:
    """SQLite database wrapper for WebMusic."""
    
    def __init__(self, db_path: str = "webmusic.db"):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self) -> None:
        """Initialize database with required tables."""
        with self.get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS albums (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    artist TEXT,
                    last_modified REAL NOT NULL,
                    date_added REAL NOT NULL,
                    art_path TEXT
                );
                
                CREATE TABLE IF NOT EXISTS tracks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    album_id INTEGER NOT NULL,
                    path TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    artist TEXT,
                    duration REAL,
                    track_number INTEGER,
                    cue_start REAL,
                    cue_end REAL,
                    FOREIGN KEY (album_id) REFERENCES albums (id)
                );
                
                CREATE TABLE IF NOT EXISTS stats (
                    track_id INTEGER PRIMARY KEY,
                    play_count INTEGER DEFAULT 0,
                    last_played REAL,
                    date_added REAL NOT NULL,
                    FOREIGN KEY (track_id) REFERENCES tracks (id)
                );
                
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created REAL NOT NULL
                );
                
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    token TEXT UNIQUE NOT NULL,
                    expires REAL NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_albums_path ON albums(path);
                CREATE INDEX IF NOT EXISTS idx_tracks_album ON tracks(album_id);
                CREATE INDEX IF NOT EXISTS idx_tracks_path ON tracks(path);
                CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
            """)
    
    def add_album(self, path: str, name: str, artist: str | None = None, 
                  last_modified: float | None = None, art_path: str | None = None) -> int:
        """Add or update an album in the database."""
        if last_modified is None:
            last_modified = os.path.getmtime(path)
        
        now = datetime.now().timestamp()
        
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT OR REPLACE INTO albums 
                (path, name, artist, last_modified, date_added, art_path)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (path, name, artist, last_modified, now, art_path))
            return cursor.lastrowid
    
    def add_track(self, album_id: int, path: str, title: str, 
                  artist: str | None = None, duration: float | None = None,
                  track_number: int | None = None, cue_start: float | None = None,
                  cue_end: float | None = None) -> int:
        """Add or update a track in the database."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT OR REPLACE INTO tracks 
                (album_id, path, title, artist, duration, track_number, cue_start, cue_end)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (album_id, path, title, artist, duration, track_number, cue_start, cue_end))
            
            # Initialize stats for new track
            track_id = cursor.lastrowid
            now = datetime.now().timestamp()
            conn.execute("""
                INSERT OR IGNORE INTO stats (track_id, date_added)
                VALUES (?, ?)
            """, (track_id, now))
            
            return track_id
    
    def get_albums(self, limit: int | None = None, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all albums with optional pagination."""
        query = "SELECT * FROM albums ORDER BY name"
        params = []
        
        if limit:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        
        with self.get_connection() as conn:
            return [dict(row) for row in conn.execute(query, params)]
    
    def get_album_by_id(self, album_id: int) -> Dict[str, Any]:
        """Get a specific album by ID."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM albums WHERE id = ?", (album_id,)).fetchone()
            assert row, f"Album not found: {album_id}"
            return dict(row)
    
    def get_tracks_by_album(self, album_id: int) -> List[Dict[str, Any]]:
        """Get all tracks for a specific album."""
        with self.get_connection() as conn:
            return [dict(row) for row in conn.execute("""
                SELECT t.*, s.play_count, s.last_played 
                FROM tracks t 
                LEFT JOIN stats s ON t.id = s.track_id 
                WHERE t.album_id = ? 
                ORDER BY t.track_number, t.title
            """, (album_id,))]
    
    def search_albums(self, query: str) -> List[Dict[str, Any]]:
        """Search albums by name or artist."""
        search_term = f"%{query}%"
        with self.get_connection() as conn:
            return [dict(row) for row in conn.execute("""
                SELECT * FROM albums 
                WHERE name LIKE ? OR artist LIKE ?
                ORDER BY name
            """, (search_term, search_term))]
    
    def search_tracks(self, query: str) -> List[Dict[str, Any]]:
        """Search tracks by title or artist."""
        search_term = f"%{query}%"
        with self.get_connection() as conn:
            return [dict(row) for row in conn.execute("""
                SELECT t.*, a.name as album_name, a.artist as album_artist
                FROM tracks t
                JOIN albums a ON t.album_id = a.id
                WHERE t.title LIKE ? OR t.artist LIKE ?
                ORDER BY t.title
            """, (search_term, search_term))]
    
    def increment_play_count(self, track_id: int) -> None:
        """Increment play count and update last played time."""
        now = datetime.now().timestamp()
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE stats 
                SET play_count = play_count + 1, last_played = ?
                WHERE track_id = ?
            """, (now, track_id))
    
    def album_needs_update(self, path: str, last_modified: float) -> bool:
        """Check if an album needs to be rescanned based on modification time."""
        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT last_modified FROM albums WHERE path = ?
            """, (path,)).fetchone()
            
            if not row:
                return True  # New album
            
            return row['last_modified'] < last_modified
