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
        
        // Album playback state
        this.albumContext = null;
        this.currentTrackIndex = -1;
        
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
            this.loadPage(location.pathname);
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
    
    playTrack(trackId, title, artist, albumContext = null) {
        const basePath = window.BASE_PATH || '';
        this.audio.src = `${basePath}/stream/${trackId}`;
        this.audio.play();
        this.currentTrackElement.textContent = `${artist} - ${title}`;
        
        if (albumContext) {
            this.setAlbumContext(albumContext, trackId);
        } else {
            this.clearAlbumMode();
        }
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
        this.playTrack(prevTrack.id, prevTrack.title, prevTrack.artist || this.albumContext.album.artist, this.albumContext);
    }
    
    playNextTrack() {
        if (!this.albumContext || this.currentTrackIndex >= this.albumContext.tracks.length - 1) return;
        
        const nextTrack = this.albumContext.tracks[this.currentTrackIndex + 1];
        this.playTrack(nextTrack.id, nextTrack.title, nextTrack.artist || this.albumContext.album.artist, this.albumContext);
    }
}

// Initialize player when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.player = new WebMusicPlayer();
});

