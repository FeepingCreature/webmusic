"""Database operations for WebMusic."""

import sqlite3
import os
import time
import random
from datetime import datetime
from typing import List, Dict, Any, Callable, TypeVar

T = TypeVar('T')


class Database:
    """SQLite database wrapper for WebMusic."""
    
    def __init__(self, db_path: str = "webmusic.db"):
        self.db_path = db_path
        self.init_db()
    
    def _retry_on_lock(self, func: Callable[[], T], max_retries: int = 5) -> T:
        """Retry a database operation if it fails due to database lock."""
        for attempt in range(max_retries):
            try:
                return func()
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    # Exponential backoff with jitter
                    delay = (2 ** attempt) * 0.1 + random.uniform(0, 0.1)
                    print(f"Database locked, retrying in {delay:.2f}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    continue
                else:
                    # Re-raise if not a lock error or we've exhausted retries
                    raise
        
        # This should never be reached, but just in case
        raise RuntimeError(f"Failed to execute database operation after {max_retries} attempts")
    
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
                    albumartist TEXT,
                    last_modified REAL NOT NULL,
                    date_added REAL NOT NULL,
                    art_path TEXT
                );
                
                CREATE TABLE IF NOT EXISTS tracks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    album_id INTEGER NOT NULL,
                    path TEXT NOT NULL,
                    title TEXT NOT NULL,
                    artist TEXT,
                    duration REAL,
                    track_number INTEGER,
                    cue_start REAL,
                    cue_end REAL,
                    FOREIGN KEY (album_id) REFERENCES albums (id),
                    UNIQUE(album_id, path, cue_start)
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
                CREATE INDEX IF NOT EXISTS idx_tracks_cue ON tracks(album_id, path, cue_start);
                CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
            """)
    
    def add_album(self, path: bytes, name: str, artist: str | None = None, 
                  albumartist: str | None = None, last_modified: float | None = None, 
                  art_path: bytes | None = None, update_timestamp: bool = True, 
                  clear_tracks: bool = False) -> int:
        """Add or update an album in the database."""
        def _add_album_impl() -> int:
            now = datetime.now().timestamp()
            
            with self.get_connection() as conn:
                # Check if album already exists
                existing = conn.execute("SELECT id, last_modified FROM albums WHERE path = ?", (path,)).fetchone()
                
                if existing:
                    album_id = existing['id']
                    
                    # Clear existing tracks if requested (for rescanning)
                    if clear_tracks:
                        conn.execute("DELETE FROM tracks WHERE album_id = ?", (album_id,))
                    
                    # Update existing album
                    final_last_modified = last_modified
                    if update_timestamp and final_last_modified is None:
                        final_last_modified = os.path.getmtime(path)
                    elif not update_timestamp:
                        # Keep existing timestamp
                        final_last_modified = existing['last_modified']
                    elif final_last_modified is None:
                        final_last_modified = existing['last_modified']
                    
                    conn.execute("""
                        UPDATE albums 
                        SET name = ?, artist = ?, albumartist = ?, last_modified = ?, art_path = ?
                        WHERE id = ?
                    """, (name, artist, albumartist, final_last_modified, art_path, album_id))
                    return album_id
                else:
                    # Create new album
                    final_last_modified = last_modified
                    if final_last_modified is None:
                        final_last_modified = 0 if not update_timestamp else os.path.getmtime(path)
                    
                    cursor = conn.execute("""
                        INSERT INTO albums 
                        (path, name, artist, albumartist, last_modified, date_added, art_path)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (path, name, artist, albumartist, final_last_modified, now, art_path))
                    assert cursor.lastrowid is not None
                    return cursor.lastrowid
        
        return self._retry_on_lock(_add_album_impl)
    
    def add_track(self, album_id: int, path: bytes, title: str, 
                  artist: str | None = None, duration: float | None = None,
                  track_number: int | None = None, cue_start: float | None = None,
                  cue_end: float | None = None) -> int:
        """Add or update a track in the database."""
        def _add_track_impl() -> int:
            with self.get_connection() as conn:
                # For CUE tracks, we need to handle the case where multiple tracks
                # have the same file path but different cue_start times
                if cue_start is not None:
                    # Check if this exact CUE track already exists
                    existing = conn.execute("""
                        SELECT id FROM tracks 
                        WHERE album_id = ? AND path = ? AND cue_start = ?
                    """, (album_id, path, cue_start)).fetchone()
                    
                    if existing:
                        # Update existing CUE track
                        track_id = existing['id']
                        conn.execute("""
                            UPDATE tracks 
                            SET title = ?, artist = ?, duration = ?, track_number = ?, cue_end = ?
                            WHERE id = ?
                        """, (title, artist, duration, track_number, cue_end, track_id))
                    else:
                        # Insert new CUE track
                        cursor = conn.execute("""
                            INSERT INTO tracks 
                            (album_id, path, title, artist, duration, track_number, cue_start, cue_end)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (album_id, path, title, artist, duration, track_number, cue_start, cue_end))
                        assert cursor.lastrowid is not None
                        track_id = cursor.lastrowid
                else:
                    # Regular track - use INSERT OR REPLACE
                    cursor = conn.execute("""
                        INSERT OR REPLACE INTO tracks 
                        (album_id, path, title, artist, duration, track_number, cue_start, cue_end)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (album_id, path, title, artist, duration, track_number, cue_start, cue_end))
                    assert cursor.lastrowid is not None
                    track_id = cursor.lastrowid
                
                # Initialize stats for new track
                now = datetime.now().timestamp()
                conn.execute("""
                    INSERT OR IGNORE INTO stats (track_id, date_added)
                    VALUES (?, ?)
                """, (track_id, now))
                
                return track_id
        
        return self._retry_on_lock(_add_track_impl)
    
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
    
    def album_needs_update(self, path: bytes, last_modified: float) -> bool:
        """Check if an album needs to be rescanned based on modification time."""
        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT last_modified FROM albums WHERE path = ?
            """, (path,)).fetchone()
            
            if not row:
                return True  # New album
            
            return bool(row['last_modified'] < last_modified)
    
    def update_album_timestamp(self, path: bytes, last_modified: float) -> None:
        """Update an album's last_modified timestamp after successful scan."""
        def _update_timestamp_impl() -> None:
            with self.get_connection() as conn:
                conn.execute("""
                    UPDATE albums SET last_modified = ? WHERE path = ?
                """, (last_modified, path))
        
        self._retry_on_lock(_update_timestamp_impl)
