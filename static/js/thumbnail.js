/**
 * Sistema di thumbnail hover per PDF
 * Mostra un'anteprima del PDF al passaggio del mouse
 */
class ThumbnailHover {
    constructor(options = {}) {
        this.tooltip = null;
        this.cache = new Map();
        this.loadingTimeout = null;
        this.selector = options.selector || '.pdf-thumbnail-trigger';
        this.apiEndpoint = options.apiEndpoint || '/api/thumbnail/';
        this.delay = options.delay || 300;
        this.init();
    }

    init() {
        // Aggiungi event listeners a tutti gli elementi con la classe specificata
        document.querySelectorAll(this.selector).forEach(element => {
            element.addEventListener('mouseenter', (e) => this.showThumbnail(e));
            element.addEventListener('mouseleave', () => this.hideThumbnail());
            element.addEventListener('mousemove', (e) => this.positionTooltip(e));
        });
    }

    /**
     * Ricarica i listener per elementi aggiunti dinamicamente
     */
    refresh() {
        this.init();
    }

    showThumbnail(event) {
        const element = event.target.closest(this.selector);
        if (!element) return;

        // Ottieni il filename dall'attributo data-filename o dal testo
        const filename = element.dataset.filename || element.textContent.trim();
        if (!filename) return;

        // Clear existing timeout
        if (this.loadingTimeout) {
            clearTimeout(this.loadingTimeout);
        }

        // Delay per evitare flickering su mouse veloce
        this.loadingTimeout = setTimeout(() => {
            this.createTooltip();
            this.loadThumbnail(filename);
            this.positionTooltip(event);
        }, this.delay);
    }

    hideThumbnail() {
        if (this.loadingTimeout) {
            clearTimeout(this.loadingTimeout);
            this.loadingTimeout = null;
        }

        if (this.tooltip) {
            this.tooltip.remove();
            this.tooltip = null;
        }
    }

    createTooltip() {
        if (this.tooltip) return;

        this.tooltip = document.createElement('div');
        this.tooltip.className = 'thumbnail-tooltip';
        document.body.appendChild(this.tooltip);
    }

    async loadThumbnail(filename) {
        // Check cache first
        if (this.cache.has(filename)) {
            this.showThumbnailImage(this.cache.get(filename));
            return;
        }

        // Show loading state
        this.tooltip.innerHTML = '<div class="thumbnail-loading">📸 Caricamento...</div>';

        try {
            const response = await fetch(`${this.apiEndpoint}${encodeURIComponent(filename)}`);
            const data = await response.json();

            if (data.success && data.thumbnail) {
                // Cache the result
                this.cache.set(filename, data.thumbnail);
                this.showThumbnailImage(data.thumbnail);
            } else {
                this.showError();
            }
        } catch (error) {
            console.error('Errore caricamento thumbnail:', error);
            this.showError();
        }
    }

    showThumbnailImage(thumbnail) {
        if (!this.tooltip) return;
        this.tooltip.innerHTML = `<img src="${thumbnail}" alt="PDF Preview">`;
    }

    showError() {
        if (!this.tooltip) return;
        this.tooltip.innerHTML = '<div class="thumbnail-error">❌ Anteprima non disponibile</div>';
    }

    positionTooltip(event) {
        if (!this.tooltip) return;

        const x = event.pageX + 15;
        const y = event.pageY + 15;

        // Check viewport boundaries
        const rect = this.tooltip.getBoundingClientRect();
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;

        let finalX = x;
        let finalY = y;

        // Adjust horizontal position if needed
        if (x + rect.width > viewportWidth) {
            finalX = event.pageX - rect.width - 15;
        }

        // Adjust vertical position if needed
        if (y + rect.height > viewportHeight + window.scrollY) {
            finalY = event.pageY - rect.height - 15;
        }

        this.tooltip.style.left = `${finalX}px`;
        this.tooltip.style.top = `${finalY}px`;
    }

    /**
     * Pulisce la cache dei thumbnail
     */
    clearCache() {
        this.cache.clear();
    }
}

// Istanza globale (opzionale, può essere inizializzata manualmente)
let thumbnailHoverInstance = null;

// Funzione helper per inizializzare automaticamente
function initThumbnailHover(options = {}) {
    thumbnailHoverInstance = new ThumbnailHover(options);
    return thumbnailHoverInstance;
}
