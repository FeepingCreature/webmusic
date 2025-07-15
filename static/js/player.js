// WebMusic Player JavaScript

class WebMusicPlayer {
    constructor() {
        this.audio = document.getElementById('audio-player');
        this.currentTrackElement = document.getElementById('current-track');
        this.playPauseButton = document.getElementById('play-pause');
        this.contentElement = document.querySelector('.content');
        
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
            this.playPauseButton.textContent = '▶';
            this.currentTrackElement.textContent = 'No track playing';
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
            
            // Prevent default navigation
            e.preventDefault();
            
            // Load content via AJAX
            this.loadPage(href);
            
            // Update browser history
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
            
            const response = await fetch(url, {
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
