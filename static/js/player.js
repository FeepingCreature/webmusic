// WebMusic Player JavaScript

class WebMusicPlayer {
    constructor() {
        this.audio = document.getElementById('audio-player');
        this.currentTrackElement = document.getElementById('current-track');
        this.currentAlbumElement = document.getElementById('current-album');
        this.playPauseButton = document.getElementById('play-pause');
        this.prevButton = document.getElementById('prev-track');
        this.nextButton = document.getElementById('next-track');
        this.albumArtMini = document.getElementById('album-art-mini');
        this.albumArtImg = document.getElementById('album-art-img');
        this.musicIcon = document.getElementById('music-icon');
        this.contentElement = document.querySelector('.content');
        
        // Playback bar elements
        this.currentTimeElement = document.getElementById('current-time');
        this.durationElement = document.getElementById('duration');
        this.progressContainer = document.getElementById('progress-container');
        this.progressBar = document.getElementById('progress-bar');
        this.progressHandle = document.getElementById('progress-handle');
        
        // Album playback state
        this.albumContext = null;
        this.currentTrackIndex = -1;
        this.currentTrackId = null;
        this.currentTrackDuration = 0;
        this.seeking = false;
        this.seekOffset = 0;
        
        this.setupEventListeners();
        this.setupLinkHijacking();
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
            if (this.albumContext && this.currentTrackIndex < this.albumContext.tracks.length - 1) {
                // Auto-advance to next track in album
                this.playNextTrack();
            } else {
                // End of album or single track
                this.playPauseButton.textContent = '▶';
                if (!this.albumContext) {
                    this.currentTrackElement.textContent = 'No track playing';
                    this.clearAlbumMode();
                }
            }
        });
        
        // Previous/Next track controls
        this.prevButton.addEventListener('click', () => {
            this.playPreviousTrack();
        });
        
        this.nextButton.addEventListener('click', () => {
            this.playNextTrack();
        });
        
        this.audio.addEventListener('error', (e) => {
            console.error('Audio error:', e);
            this.currentTrackElement.textContent = 'Error playing track';
        });
        
        // Progress bar updates
        this.audio.addEventListener('timeupdate', () => {
            if (!this.seeking) {
                this.updateProgressBar();
            }
        });
        
        this.audio.addEventListener('loadedmetadata', () => {
            this.updateDuration();
        });
        
        this.audio.addEventListener('durationchange', () => {
            this.updateDuration();
        });
        
        // Progress bar seeking
        this.progressContainer.addEventListener('click', (e) => {
            this.handleSeek(e);
        });
        
        this.progressContainer.addEventListener('mousedown', (e) => {
            this.seeking = true;
            this.handleSeek(e);
            
            const handleMouseMove = (e) => {
                this.handleSeek(e);
            };
            
            const handleMouseUp = () => {
                this.seeking = false;
                document.removeEventListener('mousemove', handleMouseMove);
                document.removeEventListener('mouseup', handleMouseUp);
            };
            
            document.addEventListener('mousemove', handleMouseMove);
            document.addEventListener('mouseup', handleMouseUp);
        });
    }
    
    setupLinkHijacking() {
        // Intercept clicks on internal links
        document.addEventListener('click', (e) => {
            const link = e.target.closest('a');
            if (!link) return;
            
            const href = link.getAttribute('href');
            if (!href || href.startsWith('http') || href.startsWith('#')) return;
            
            const basePath = window.BASE_PATH || '';
            
            // Check if this is an internal link (starts with base path or is relative)
            const isInternalLink = href.startsWith('/') || (basePath && href.startsWith(basePath));
            if (!isInternalLink) return;
            
            // Prevent default navigation
            e.preventDefault();
            
            // Strip base path from href for internal routing
            let internalHref = href;
            if (basePath && href.startsWith(basePath)) {
                internalHref = href.substring(basePath.length) || '/';
            }
            
            // Load content via AJAX
            this.loadPage(internalHref);
            
            // Update browser history with full URL
            history.pushState(null, '', href);
        });
        
        // Handle browser back/forward buttons
        window.addEventListener('popstate', () => {
            const basePath = window.BASE_PATH || '';
            const currentPath = location.pathname;
            
            // Check if this is an internal URL (starts with base path or is relative)
            const isInternalUrl = currentPath.startsWith('/') || (basePath && currentPath.startsWith(basePath));
            
            if (isInternalUrl) {
                // Strip base path from URL for internal routing
                let internalPath = currentPath;
                if (basePath && currentPath.startsWith(basePath)) {
                    internalPath = currentPath.substring(basePath.length) || '/';
                }
                
                this.loadPage(internalPath);
            } else {
                // External URL - do full page reload
                location.reload();
            }
        });
    }
    
    async loadPage(url) {
        try {
            // Add loading indicator
            this.contentElement.style.opacity = '0.5';
            
            // Prepend base path if it exists and URL is relative
            const basePath = window.BASE_PATH || '';
            const fullUrl = url.startsWith('/') && basePath ? basePath + url : url;
            
            const response = await fetch(fullUrl, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const html = await response.text();
            
            // Extract content from response
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newContent = doc.querySelector('.content');
            
            if (newContent) {
                // Replace content
                this.contentElement.innerHTML = newContent.innerHTML;
            
                // Execute any scripts in the new content
                const scripts = this.contentElement.querySelectorAll('script');
                scripts.forEach(script => {
                    const newScript = document.createElement('script');
                    if (script.src) {
                        newScript.src = script.src;
                    } else {
                        newScript.textContent = script.textContent;
                    }
                    document.head.appendChild(newScript);
                    document.head.removeChild(newScript);
                });
            
                // Update page title
                const newTitle = doc.querySelector('title');
                if (newTitle) {
                    document.title = newTitle.textContent;
                }
            
                // Update active nav link
                this.updateActiveNavLink(url);
            
                // Re-attach event listeners for new content
                this.attachContentEventListeners();
            }
            
        } catch (error) {
            console.error('Failed to load page:', error);
            // Fallback to normal navigation
            location.href = url;
        } finally {
            // Remove loading indicator
            this.contentElement.style.opacity = '1';
        }
    }
    
    updateActiveNavLink(url) {
        // Remove active class from all nav links
        document.querySelectorAll('.nav-menu a').forEach(link => {
            link.classList.remove('active');
        });
        
        // Add active class to current page link
        const currentLink = document.querySelector(`.nav-menu a[href="${url}"]`);
        if (currentLink) {
            currentLink.classList.add('active');
        }
    }
    
    attachContentEventListeners() {
        // Re-attach any event listeners needed for new content
        // This is called after content is dynamically loaded
        
        // Re-attach lazy loading for any new images
        const imageObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    const src = img.dataset.src;
                    if (src) {
                        img.src = src;
                        img.removeAttribute('data-src');
                        imageObserver.unobserve(img);
                    }
                }
            });
        }, {
            rootMargin: '50px'
        });
        
        document.querySelectorAll('.lazy-load').forEach(img => {
            if (img.dataset.src) {
                imageObserver.observe(img);
            }
        });
        
        // Example: Re-attach play button listeners
        document.querySelectorAll('.play-button').forEach(button => {
            button.addEventListener('click', (e) => {
                e.stopPropagation();
                // Play button functionality is handled by onclick attributes
            });
        });
        
        // Re-attach filter input handlers
        const albumFilter = document.getElementById('album-filter');
        if (albumFilter) {
            albumFilter.addEventListener('input', function() {
                const query = this.value.toLowerCase().trim();
                const albumCards = document.querySelectorAll('.album-card');
                
                albumCards.forEach(card => {
                    const title = card.querySelector('.album-title').textContent.toLowerCase();
                    const artist = card.querySelector('.album-artist').textContent.toLowerCase();
                    
                    if (title.includes(query) || artist.includes(query)) {
                        card.style.display = 'block';
                    } else {
                        card.style.display = 'none';
                    }
                });
            });
        }
        
        const artistFilter = document.getElementById('artist-filter');
        if (artistFilter) {
            artistFilter.addEventListener('input', function() {
                const query = this.value.toLowerCase().trim();
                const artistItems = document.querySelectorAll('.artist-item');
                
                artistItems.forEach(item => {
                    const artistName = item.querySelector('.artist-name').textContent.toLowerCase();
                    const albumNames = Array.from(item.querySelectorAll('.artist-album a'))
                        .map(link => link.textContent.toLowerCase())
                        .join(' ');
                    
                    if (artistName.includes(query) || albumNames.includes(query)) {
                        item.style.display = 'block';
                    } else {
                        item.style.display = 'none';
                    }
                });
            });
        }
    }
    
    playTrack(trackId) {
        // Read album context from DOM
        const trackListElement = document.querySelector('.track-list');
        if (!trackListElement) {
            console.error('No track list found');
            return;
        }
        
        const albumContext = JSON.parse(trackListElement.dataset.albumContext);
        if (!albumContext) {
            console.error('No album context found');
            return;
        }
        
        // Find the track in the album context
        const track = albumContext.tracks.find(t => t.id === trackId);
        if (!track) {
            console.error('Track not found in album context');
            return;
        }
        
        const basePath = window.BASE_PATH || '';
        this.currentTrackId = trackId;
        this.seekOffset = 0; // Reset seek offset for new track
        this.audio.src = `${basePath}/stream/${trackId}`;
        this.audio.play();
        
        const artist = track.artist || albumContext.album.artist || 'Unknown Artist';
        const title = track.title;
        this.currentTrackElement.textContent = `${artist} - ${title}`;
        
        // Set track duration from metadata
        this.currentTrackDuration = track.duration || 0;
        this.setAlbumContext(albumContext, trackId);
        
        this.updateDuration();
    }
    
    updateProgressBar() {
        const duration = this.currentTrackDuration || this.audio.duration || 0;
        if (duration > 0) {
            // Calculate actual current time in the original track
            const actualCurrentTime = this.seekOffset + (this.audio.currentTime || 0);
            const progress = (actualCurrentTime / duration) * 100;
            this.progressBar.style.width = `${progress}%`;
            this.progressHandle.style.left = `${progress}%`;
            this.currentTimeElement.textContent = this.formatTime(actualCurrentTime);
        }
    }
    
    updateDuration() {
        const duration = this.currentTrackDuration || this.audio.duration || 0;
        if (duration > 0) {
            this.durationElement.textContent = this.formatTime(duration);
        }
    }
    
    formatTime(seconds) {
        if (!seconds || isNaN(seconds)) return '0:00';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }
    
    handleSeek(e) {
        const duration = this.currentTrackDuration || this.audio.duration || 0;
        if (!duration || !this.currentTrackId) return;
        
        const rect = this.progressContainer.getBoundingClientRect();
        const clickX = e.clientX - rect.left;
        const progress = Math.max(0, Math.min(1, clickX / rect.width));
        const seekTime = progress * duration;
        
        // Update UI immediately for responsiveness
        this.progressBar.style.width = `${progress * 100}%`;
        this.progressHandle.style.left = `${progress * 100}%`;
        this.currentTimeElement.textContent = this.formatTime(seekTime);
        
        // Make seek request to backend
        this.seekToPosition(seekTime);
    }
    
    seekToPosition(seekTime) {
        const basePath = window.BASE_PATH || '';
        const seekUrl = `${basePath}/stream/${this.currentTrackId}?seek=${seekTime}`;
        
        // Store the seek offset for progress calculations
        this.seekOffset = seekTime;
        
        // Replace current audio source with seek URL
        this.audio.src = seekUrl;
        this.audio.play();
    }
    
    setAlbumContext(albumContext, currentTrackId) {
        this.albumContext = albumContext;
        this.currentTrackIndex = albumContext.tracks.findIndex(track => track.id === currentTrackId);
        
        // Update track display to include track number
        if (this.currentTrackIndex >= 0) {
            const currentTrack = albumContext.tracks[this.currentTrackIndex];
            const trackNumber = currentTrack.track_number || (this.currentTrackIndex + 1);
            const artist = currentTrack.artist || albumContext.album.artist || 'Unknown Artist';
            this.currentTrackElement.textContent = `${trackNumber}. ${artist} - ${currentTrack.title}`;
        }
        
        // Show album info in header
        this.currentAlbumElement.textContent = `${albumContext.album.artist || 'Unknown Artist'} - ${albumContext.album.name}`;
        this.currentAlbumElement.classList.remove('hidden');
        
        // Show album art if available
        if (albumContext.album.art_path) {
            const basePath = window.BASE_PATH || '';
            this.albumArtImg.src = `${basePath}/art/${albumContext.album.id}`;
            this.albumArtMini.classList.remove('hidden');
            this.musicIcon.classList.add('hidden');
        }
        
        // Show/hide prev/next buttons
        this.prevButton.classList.remove('hidden');
        this.nextButton.classList.remove('hidden');
        this.updateNavigationButtons();
    }
    
    clearAlbumMode() {
        this.albumContext = null;
        this.currentTrackIndex = -1;
        
        // Hide album info
        this.currentAlbumElement.classList.add('hidden');
        this.albumArtMini.classList.add('hidden');
        this.musicIcon.classList.remove('hidden');
        
        // Hide prev/next buttons
        this.prevButton.classList.add('hidden');
        this.nextButton.classList.add('hidden');
    }
    
    updateNavigationButtons() {
        if (!this.albumContext) return;
        
        this.prevButton.disabled = this.currentTrackIndex <= 0;
        this.nextButton.disabled = this.currentTrackIndex >= this.albumContext.tracks.length - 1;
    }
    
    playPreviousTrack() {
        if (!this.albumContext || this.currentTrackIndex <= 0) return;
        
        const prevTrack = this.albumContext.tracks[this.currentTrackIndex - 1];
        this.playTrack(prevTrack.id);
    }
    
    playNextTrack() {
        if (!this.albumContext || this.currentTrackIndex >= this.albumContext.tracks.length - 1) return;
        
        const nextTrack = this.albumContext.tracks[this.currentTrackIndex + 1];
        this.playTrack(nextTrack.id);
    }
}

// Initialize player when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.player = new WebMusicPlayer();
});

