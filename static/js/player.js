// WebMusic Player JavaScript

class WebMusicPlayer {
    constructor() {
        this.audio = document.getElementById('audio-player');
        this.currentTrackElement = document.getElementById('current-track');
        this.playPauseButton = document.getElementById('play-pause');
        
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        // Play/pause button
        this.playPauseButton.addEventListener('click', () => {
            if (this.audio.paused) {
                this.audio.play();
            } else {
                this.audio.pause();
            }
        });
        
        // Audio events
        this.audio.addEventListener('play', () => {
            this.playPauseButton.textContent = '⏸';
        });
        
        this.audio.addEventListener('pause', () => {
            this.playPauseButton.textContent = '▶';
        });
        
        this.audio.addEventListener('ended', () => {
            this.playPauseButton.textContent = '▶';
            this.currentTrackElement.textContent = 'No track playing';
        });
        
        this.audio.addEventListener('error', (e) => {
            console.error('Audio error:', e);
            this.currentTrackElement.textContent = 'Error playing track';
        });
    }
    
    playTrack(trackId, title, artist) {
        this.audio.src = `/stream/${trackId}`;
        this.audio.play();
        this.currentTrackElement.textContent = `${artist} - ${title}`;
    }
}

// Initialize player when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.player = new WebMusicPlayer();
});

// Global function for playing tracks (used by templates)
function playTrack(trackId, title, artist) {
    if (window.player) {
        window.player.playTrack(trackId, title, artist);
    }
}
