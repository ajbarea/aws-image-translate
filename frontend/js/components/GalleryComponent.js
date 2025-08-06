import { BaseComponent } from "./BaseComponent.js";
import { FlipModalComponent } from "./FlipModalComponent.js";
const { AWS_CONFIG } = window;

// Fallback images used only if the API call fails
const FB_BASE = "resources/images";
const fallbackImages = [
  { id: 1, src: `${FB_BASE}/es1.png`, alt: "Spanish Sign 1" },
  { id: 2, src: `${FB_BASE}/es2.jpg`, alt: "Spanish Sign 2" },
  { id: 3, src: `${FB_BASE}/es3.png`, alt: "Spanish Sign 3" },
  { id: 4, src: `${FB_BASE}/es4.png`, alt: "Spanish Sign 4" },
  { id: 5, src: `${FB_BASE}/es5.png`, alt: "Spanish Sign 5" },
  { id: 6, src: `${FB_BASE}/lenslate-transparent.png`, alt: "Lenslate Logo" },
  { id: 7, src: `${FB_BASE}/nice to meet you.png`, alt: "Nice to Meet You" },
  { id: 8, src: `${FB_BASE}/restroom.png`, alt: "Restroom Sign" },
  { id: 9, src: `${FB_BASE}/stop.png`, alt: "Stop Sign" }
];

export class GalleryComponent extends BaseComponent {
  constructor(placeholderId) {
    super(placeholderId);
    this.name = "GalleryComponent";
    this.flipModal = null;
    this.galleryGrid = null;
    this.images = [];
    this.previousImageCount = 0;
    this.refreshInterval = null;
    this.lastImageCount = 0;
    this.refreshButton = null;
  }

  async initialize() {
    await super.initialize();

    // Find the gallery grid element
    this.galleryGrid = this.container.querySelector("#gallery-grid");
    if (!this.galleryGrid) {
      console.error(`❌ ${this.name}: Gallery grid not found!`);
      return;
    }

    // Add refresh controls
    this.addRefreshControls();

    // Initialize flip modal component
    await this.initializeFlipModal();

    // Load images from API then render
    await this.loadImages();
    this.render();

    // Start auto-refresh every 2 minutes to catch new Reddit images
    this.startAutoRefresh();

    console.log(`✅ ${this.name}: Initialized with auto-refresh enabled`);
  }

  async initializeFlipModal() {
    try {
      // Find the flip modal in the same container
      const flipModalElement = this.container.querySelector("#flip-modal");
      if (flipModalElement) {
        // Pass the flip modal element directly instead of the ID
        this.flipModal = new FlipModalComponent("flip-modal");
        await this.flipModal.initialize();
        console.log(`✅ ${this.name}: Flip modal initialized`);
      } else {
        console.warn(
          `⚠️ ${this.name}: Flip modal element not found in container`
        );
        // Try to find it in the document
        const globalFlipModal = document.querySelector("#flip-modal");
        if (globalFlipModal) {
          this.flipModal = new FlipModalComponent("flip-modal");
          await this.flipModal.initialize();
          console.log(
            `✅ ${this.name}: Flip modal initialized (found globally)`
          );
        } else {
          console.warn(
            `⚠️ ${this.name}: Flip modal element not found globally either`
          );
        }
      }
    } catch (error) {
      console.error(`❌ ${this.name}: Failed to initialize flip modal:`, error);
    }
  }

  async loadImages() {
    const apiUrl = `${AWS_CONFIG.apiGatewayUrl}/gallery`;
    console.log(`🌐 ${this.name}: Fetching images from`, apiUrl);

    try {
      const response = await fetch(apiUrl, {
        method: "GET",
        headers: {
          "Content-Type": "application/json"
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      if (data && Array.isArray(data.images)) {
        this.images = data.images;
        console.log(`✅ ${this.name}: Loaded ${this.images.length} images`);
      } else {
        console.warn(
          `⚠️ ${this.name}: Unexpected API response, using fallback images`
        );
        this.images = fallbackImages;
      }
    } catch (error) {
      console.error(`❌ ${this.name}: Failed to load images:`, error);
      this.images = fallbackImages;
    }
  }

  addRefreshControls() {
    // Add refresh button to the gallery header
    const galleryHeader = this.container.querySelector(".gallery-header") ||
      this.container.querySelector("h2") ||
      this.container.querySelector(".dashboard-section h3");

    if (galleryHeader) {
      const refreshContainer = document.createElement("div");
      refreshContainer.className = "gallery-refresh-controls";
      refreshContainer.innerHTML = `
        <button id="refresh-gallery-btn" class="btn-secondary" title="Refresh gallery">
          🔄 Refresh
        </button>
        <span id="gallery-status" class="gallery-status">
          Auto-refresh: ON
        </span>
      `;

      // Insert after the header
      galleryHeader.parentNode.insertBefore(refreshContainer, galleryHeader.nextSibling);

      // Add event listener
      this.refreshButton = refreshContainer.querySelector("#refresh-gallery-btn");
      this.refreshButton.addEventListener("click", () => this.manualRefresh());
    }
  }

  async manualRefresh() {
    if (this.refreshButton) {
      this.refreshButton.innerHTML = "⏳ Refreshing...";
      this.refreshButton.disabled = true;
    }

    await this.loadImages();
    this.render();
    this.checkForNewImages();

    if (this.refreshButton) {
      this.refreshButton.innerHTML = "🔄 Refresh";
      this.refreshButton.disabled = false;
    }
  }

  startAutoRefresh() {
    // Refresh every 2 minutes (120000ms) to catch new Reddit images
    this.refreshInterval = setInterval(async () => {
      console.log(`🔄 ${this.name}: Auto-refreshing gallery...`);
      await this.loadImages();
      this.checkForNewImages();
    }, 120000); // 2 minutes

    console.log(`✅ ${this.name}: Auto-refresh started (every 2 minutes)`);
  }

  stopAutoRefresh() {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
      this.refreshInterval = null;
      console.log(`🛑 ${this.name}: Auto-refresh stopped`);
    }
  }

  checkForNewImages() {
    const currentCount = this.images.length;
    if (currentCount > this.lastImageCount) {
      const newImages = currentCount - this.lastImageCount;
      this.showNewImageNotification(newImages);
      this.render(); // Re-render to show new images
    }
    this.lastImageCount = currentCount;
  }

  showNewImageNotification(count) {
    // Create a subtle notification
    const notification = document.createElement("div");
    notification.className = "new-images-notification";
    notification.innerHTML = `
      <span>🎉 ${count} new image${count > 1 ? "s" : ""} from Reddit!</span>
    `;

    // Add to top of gallery
    this.galleryGrid.parentNode.insertBefore(notification, this.galleryGrid);

    // Remove after 5 seconds
    setTimeout(() => {
      if (notification.parentNode) {
        notification.remove();
      }
    }, 5000);

    console.log(`🎉 ${this.name}: ${count} new images detected!`);
  }

  isImageNew(image) {
    // Check if image was uploaded in the last hour
    if (!image.timestamp) { return false; }

    const now = Date.now() / 1000; // Current time in seconds
    const imageTime = image.timestamp;
    const hoursSinceUpload = (now - imageTime) / 3600;

    return hoursSinceUpload < 1; // Less than 1 hour old
  }

  refresh() {
    this.render();
  }

  // Clean up when component is destroyed
  destroy() {
    this.stopAutoRefresh();
    super.destroy && super.destroy();
  }

  render() {
    console.log(`🎨 ${this.name}: Starting render, container:`, this.container);
    if (!this.galleryGrid) {
      console.error(`❌ ${this.name}: Gallery grid not found!`);
      return;
    }

    // Clear existing content
    this.galleryGrid.innerHTML = "";

    this.images.forEach((image) => {
      const card = this.createImageCard(image);
      this.galleryGrid.appendChild(card);
    });

    console.log(`✅ ${this.name}: Rendered ${this.images.length} images`);
  }

  createImageCard(image) {
    const card = document.createElement("div");
    card.className = "gallery-item";

    // Check if image is new (less than 1 hour old)
    const isNew = this.isImageNew(image);
    if (isNew) {
      card.classList.add("gallery-item-new");
    }

    const img = document.createElement("img");
    img.src = image.src;
    img.alt = image.alt;
    img.loading = "lazy";

    // Add error handling for images
    img.addEventListener("error", () => {
      img.style.display = "none";
      card.innerHTML = `
        <div style="display: flex; align-items: center; justify-content: center; height: 200px; color: #666; background: #f5f5f5; border-radius: 8px;">
          <span>Image not found</span>
        </div>
      `;
    });

    card.appendChild(img);

    // Add "NEW" badge for recent images
    if (isNew) {
      const newBadge = document.createElement("div");
      newBadge.className = "gallery-new-badge";
      newBadge.textContent = "NEW";
      card.appendChild(newBadge);
    }

    // Add click handler to open flip modal
    card.addEventListener("click", () => {
      console.log("Image clicked:", image.alt); // Debug log
      if (this.flipModal) {
        this.flipModal.open(image);
      } else {
        console.warn(
          `${this.name}: Flip modal not available, falling back to simple modal`
        );
        this.openSimpleModal(image);
      }
    });

    return card;
  }

  // Fallback simple modal for when flip modal isn't available
  openSimpleModal(image) {
    // Create modal backdrop
    const modal = document.createElement("div");
    modal.className = "image-modal-backdrop";
    modal.innerHTML = `
      <div class="image-modal-content">
        <div class="image-modal-header">
          <h3 class="image-modal-title">${image.alt}</h3>
          <button class="image-modal-close" type="button">×</button>
        </div>
        <div class="image-modal-body">
          <img src="${image.src}" alt="${image.alt}" class="image-modal-img">
        </div>
      </div>
    `;

    // Add event listeners
    const closeBtn = modal.querySelector(".image-modal-close");
    closeBtn.addEventListener("click", () => modal.remove());

    modal.addEventListener("click", (e) => {
      if (e.target === modal) {
        modal.remove();
      }
    });

    // Add to DOM
    document.body.appendChild(modal);
  }
}
