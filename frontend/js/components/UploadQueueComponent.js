import { BaseComponent } from "./BaseComponent.js";

/**
 * Upload queue component managing the list of files to be processed
 */
export class UploadQueueComponent extends BaseComponent {
  constructor(containerId, options = {}) {
    super(containerId, options);
    this.uploadQueue = [];
    this.nextId = 1;

    // Configuration options
    this.options = {
      autoClearCompleted: true,
      autoClearDelay: 30000, // 30 seconds
      autoCollapseCompleted: true,
      maxCompletedItems: 20,
      ...options
    };

    // Timer for auto-clearing completed items
    this.autoClearTimer = null;
  }

  async onInit() {
    // Get the new organized upload sections
    this.activeUploadList = this.querySelector("#activeUploadList");
    this.completedUploadList = this.querySelector("#completedUploadList");
    this.failedUploadList = this.querySelector("#failedUploadList");

    this.activeSection = this.querySelector("#activeUploadsSection");
    this.completedSection = this.querySelector("#completedUploadsSection");
    this.failedSection = this.querySelector("#failedUploadsSection");

    this.activeCount = this.querySelector("#activeCount");
    this.completedCount = this.querySelector("#completedCount");
    this.failedCount = this.querySelector("#failedCount");

    if (!this.activeUploadList) {
      throw new Error("Active upload list element not found");
    }

    // Set up completed section toggle
    const completedToggle = this.querySelector("#completedToggle");
    if (completedToggle) {
      this.addEventListener(completedToggle, "click", this.toggleCompletedSection.bind(this));
    }

    // Set up retry all button
    const retryAllBtn = this.querySelector("#retry-all-btn");
    if (retryAllBtn) {
      this.addEventListener(retryAllBtn, "click", this.retryAllFailed.bind(this));
    }

    // Set up clear completed button
    const clearCompletedBtn = this.querySelector("#clear-completed-btn");
    if (clearCompletedBtn) {
      this.addEventListener(clearCompletedBtn, "click", (e) => {
        e.stopPropagation(); // Prevent toggling the section
        this.clearCompletedOnly();
      });
    }
  }

  setupEventListeners() {
    // Listen for remove button clicks and image preview clicks
    this.addEventListener(
      this.container,
      "click",
      this.handleButtonClick.bind(this)
    );
  }

  handleButtonClick(e) {
    if (e.target.matches(".remove-file-btn")) {
      const itemId = e.target.dataset.itemId;
      this.removeFromQueue(itemId);
    } else if (e.target.matches(".retry-item-btn")) {
      const itemId = e.target.dataset.itemId;
      this.retryItem(itemId);
    } else if (
      e.target.matches(".upload-image-preview") ||
      e.target.closest(".upload-image-preview")
    ) {
      const button = e.target.closest(".upload-image-preview") || e.target;
      const imageUrl = button.dataset.imageUrl;
      const imageName = button.dataset.imageName;
      if (imageUrl && imageName) {
        this.openImageModal(imageUrl, imageName);
      }
    }
  }

  addFiles(files) {
    for (const file of files) {
      this.addToQueue(file);
    }
    this.emit("queue:updated", { queue: this.uploadQueue });
  }

  addToQueue(file) {
    const item = {
      id: `upload-${this.nextId++}`,
      file,
      status: "pending",
      progress: 0,
      error: null,
      s3Key: null,
      s3Location: null,
      processingResults: null,
      addedAt: new Date()
    };

    this.uploadQueue.push(item);
    this.createUploadListItem(item);
    this.updateSectionCounts();
    console.log(`📁 UploadQueue: Added ${file.name} to queue`);
  }

  removeFromQueue(itemId) {
    const index = this.uploadQueue.findIndex((item) => item.id === itemId);
    if (index !== -1) {
      const item = this.uploadQueue[index];
      this.uploadQueue.splice(index, 1);

      // Remove from DOM
      const listItem = document.getElementById(itemId);
      if (listItem) {
        listItem.remove();
      }

      console.log(`🗑️ UploadQueue: Removed ${item.file.name} from queue`);
      this.updateSectionCounts();
      this.emit("queue:updated", { queue: this.uploadQueue });
    }
  }

  /**
   * Update section counts and visibility
   */
  updateSectionCounts() {
    const activeItems = this.uploadQueue.filter(item =>
      item.status === "pending" || item.status === "uploading" || item.status === "processing"
    );
    const completedItems = this.uploadQueue.filter(item => item.status === "complete");
    const failedItems = this.uploadQueue.filter(item => item.status === "error");

    // Update counts
    if (this.activeCount) {
      this.activeCount.textContent = `(${activeItems.length} items)`;
    }
    if (this.completedCount) {
      this.completedCount.textContent = `(${completedItems.length} items)`;
    }
    if (this.failedCount) {
      this.failedCount.textContent = `(${failedItems.length} items)`;
    }

    // Show/hide sections based on content
    if (this.activeSection) {
      this.activeSection.classList.toggle("hidden", activeItems.length === 0);
    }
    if (this.completedSection) {
      this.completedSection.classList.toggle("hidden", completedItems.length === 0);
    }
    if (this.failedSection) {
      this.failedSection.classList.toggle("hidden", failedItems.length === 0);
    }
  }

  /**
   * Toggle the completed section collapsed state
   */
  toggleCompletedSection() {
    if (this.completedSection) {
      this.completedSection.classList.toggle("collapsed");
    }
  }

  /**
   * Retry all failed uploads
   */
  retryAllFailed() {
    const failedItems = this.uploadQueue.filter(item => item.status === "error");
    for (const item of failedItems) {
      this.retryItem(item.id);
    }
  }

  /**
   * Retry a specific item
   */
  retryItem(itemId) {
    const item = this.uploadQueue.find(item => item.id === itemId);
    if (item && item.status === "error") {
      item.status = "pending";
      item.progress = 0;
      item.error = null;

      // Move item back to active section
      this.moveItemToSection(item, "active");
      this.updateSectionCounts();

      this.emit("queue:itemUpdated", { item });
      this.emit("queue:updated", { queue: this.uploadQueue });
    }
  }

  createUploadListItem(item) {
    const li = document.createElement("li");
    li.className = "upload-item";
    li.id = item.id;

    // Create placeholder content first
    li.innerHTML = `
      <button class="upload-item-image upload-image-preview" data-image-url="" data-image-name="${this.escapeHtml(
    item.file.name
  )}" title="View image">
        <div class="image-placeholder">Loading...</div>
      </button>
      <div class="upload-item-details">
        <div class="upload-item-name">${item.file.name}</div>
        <div class="upload-item-size">${this.formatFileSize(
    item.file.size
  )}</div>
        <div class="upload-item-progress">
          <div class="progress-bar" style="width: 0%"></div>
        </div>
      </div>
      <div class="upload-item-status">
        <span class="status-text">Pending</span>
        <button class="remove-file-btn" data-item-id="${item.id
}" title="Remove file">×</button>
      </div>
    `;

    // Add to the appropriate section (new items start in active)
    this.activeUploadList.appendChild(li);

    // Create thumbnail asynchronously
    this.createThumbnail(item.file)
      .then((thumbnailSrc) => {
        const imageContainer = li.querySelector(".upload-item-image");
        if (imageContainer && thumbnailSrc) {
          imageContainer.innerHTML = `<img src="${thumbnailSrc}" alt="${item.file.name}">`;
          imageContainer.dataset.imageUrl = thumbnailSrc;
        }
      })
      .catch((error) => {
        console.warn(
          `⚠️ UploadQueue: Could not create thumbnail for ${item.file.name}:`,
          error
        );
        const imageContainer = li.querySelector(".upload-item-image");
        if (imageContainer) {
          imageContainer.innerHTML = "<div class=\"image-placeholder\">📷</div>";
        }
      });
  }

  async createThumbnail(file) {
    return new Promise((resolve, reject) => {
      if (!file.type.startsWith("image/")) {
        reject(new Error("Not an image file"));
        return;
      }

      const reader = new FileReader();
      reader.onload = (e) => {
        resolve(e.target.result);
      };
      reader.onerror = () => {
        reject(new Error("Failed to read file"));
      };
      reader.readAsDataURL(file);
    });
  }

  updateItemStatus(itemId, status, progress = null, error = null) {
    const item = this.uploadQueue.find((item) => item.id === itemId);
    if (!item) {
      console.warn(
        `⚠️ UploadQueue: Item ${itemId} not found for status update`
      );
      return;
    }

    const previousStatus = item.status;
    item.status = status;
    if (progress !== null) {
      item.progress = progress;
    }
    if (error !== null) {
      item.error = error;
    }

    // Update DOM
    const listItem = document.getElementById(itemId);
    if (listItem) {
      const statusText = listItem.querySelector(".status-text");
      const progressBar = listItem.querySelector(".progress-bar");

      if (statusText) {
        statusText.textContent = this.getStatusDisplayText(status);
        statusText.className = `status-text status-${status}`;
      }

      if (progressBar && progress !== null) {
        progressBar.style.width = `${progress}%`;
      }

      // Add error display if needed
      if (error && status === "error") {
        let errorDiv = listItem.querySelector(".upload-item-error");
        if (!errorDiv) {
          errorDiv = document.createElement("div");
          errorDiv.className = "upload-item-error";
          listItem.appendChild(errorDiv);
        }
        errorDiv.textContent = error;

        // Add retry button for failed items
        const statusDiv = listItem.querySelector(".upload-item-status");
        let retryBtn = statusDiv.querySelector(".retry-item-btn");
        if (!retryBtn) {
          retryBtn = document.createElement("button");
          retryBtn.className = "retry-item-btn";
          retryBtn.dataset.itemId = itemId;
          retryBtn.title = "Retry upload";
          retryBtn.innerHTML = "🔄";
          statusDiv.insertBefore(retryBtn, statusDiv.querySelector(".remove-file-btn"));
        }
      } else {
        // Remove retry button if not in error state
        const retryBtn = listItem.querySelector(".retry-item-btn");
        if (retryBtn) {
          retryBtn.remove();
        }
      }

      // Handle section movement based on status changes
      if (status === "complete" && previousStatus !== "complete") {
        // Add success animation
        listItem.classList.add("just-completed");

        // Move to completed section after a brief delay for user feedback
        setTimeout(() => {
          this.moveItemToSection(item, "completed");
          listItem.classList.remove("just-completed");

          // Auto-collapse completed section if configured
          if (this.options.autoCollapseCompleted && this.completedSection) {
            setTimeout(() => {
              this.completedSection.classList.add("collapsed");
            }, 1000);
          }

          // Schedule auto-clear if all processing is complete
          this.scheduleAutoClear();
        }, 2000);
      } else if (status === "error" && previousStatus !== "error") {
        this.moveItemToSection(item, "failed");
      }
    }

    // Update section counts
    this.updateSectionCounts();
    this.emit("queue:itemUpdated", { item });
  }

  /**
   * Move an item to the appropriate section
   */
  moveItemToSection(item, section) {
    const listItem = document.getElementById(item.id);
    if (!listItem) {return;}

    let targetList;
    switch (section) {
      case "active":
        targetList = this.activeUploadList;
        break;
      case "completed":
        targetList = this.completedUploadList;
        break;
      case "failed":
        targetList = this.failedUploadList;
        break;
      default:
        return;
    }

    // Remove from current location and add to new section
    listItem.remove();
    targetList.appendChild(listItem);

    // Update section counts after moving
    this.updateSectionCounts();
  }

  /**
   * Schedule auto-clear of completed items if all processing is done
   */
  scheduleAutoClear() {
    if (!this.options.autoClearCompleted) {return;}

    // Clear any existing timer
    if (this.autoClearTimer) {
      clearTimeout(this.autoClearTimer);
    }

    // Check if there are any active items still processing
    const activeItems = this.uploadQueue.filter(item =>
      item.status === "pending" || item.status === "uploading" || item.status === "processing"
    );

    // Only schedule auto-clear if no items are still processing
    if (activeItems.length === 0) {
      this.autoClearTimer = setTimeout(() => {
        const completedItems = this.uploadQueue.filter(item => item.status === "complete");

        // Only auto-clear if we have too many completed items or user isn't interacting
        if (completedItems.length > this.options.maxCompletedItems) {
          console.log(`🧹 UploadQueue: Auto-clearing ${completedItems.length} completed items`);
          this.clearCompletedOnly();

          // Show a subtle notification
          this.showAutoClearNotification(completedItems.length);
        }
      }, this.options.autoClearDelay);
    }
  }

  /**
   * Show a subtle notification about auto-clearing
   */
  showAutoClearNotification(count) {
    // You could emit an event here for the main app to show a toast
    this.emit("queue:autoCleared", { count });
  }

  getStatusDisplayText(status) {
    const statusMap = {
      pending: "Pending",
      uploading: "Uploading...",
      processing: "Processing...",
      complete: "Complete",
      error: "Error"
    };
    return statusMap[status] || status;
  }

  formatFileSize(bytes) {
    if (bytes === 0) {return "0 Bytes";}
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))  } ${  sizes[i]}`;
  }

  getQueue() {
    return [...this.uploadQueue];
  }

  getPendingItems() {
    return this.uploadQueue.filter((item) => item.status === "pending");
  }

  getCompletedItems() {
    return this.uploadQueue.filter((item) => item.status === "complete");
  }

  getErrorItems() {
    return this.uploadQueue.filter((item) => item.status === "error");
  }

  hasPending() {
    return this.uploadQueue.some((item) => item.status === "pending");
  }

  clearQueue() {
    this.uploadQueue = [];

    // Clear all section lists
    if (this.activeUploadList) {this.activeUploadList.innerHTML = "";}
    if (this.completedUploadList) {this.completedUploadList.innerHTML = "";}
    if (this.failedUploadList) {this.failedUploadList.innerHTML = "";}

    this.updateSectionCounts();
    this.emit("queue:updated", { queue: this.uploadQueue });
  }

  clearCompleted() {
    const completedItems = this.getCompletedItems();
    for (const item of completedItems) {
      this.removeFromQueue(item.id);
    }
  }

  /**
   * Clear only completed items (useful for cleaning up after processing)
   */
  clearCompletedOnly() {
    const completedItems = [...this.uploadQueue.filter(item => item.status === "complete")];

    for (const item of completedItems) {
      const index = this.uploadQueue.findIndex(i => i.id === item.id);
      if (index !== -1) {
        this.uploadQueue.splice(index, 1);

        // Remove from DOM
        const listItem = document.getElementById(item.id);
        if (listItem) {
          listItem.remove();
        }
      }
    }

    this.updateSectionCounts();
    this.emit("queue:updated", { queue: this.uploadQueue });
  }

  isEmpty() {
    return this.uploadQueue.length === 0;
  }

  openImageModal(imageUrl, imageName) {
    // Remove existing modal if present
    this.closeImageModal();

    // Prevent background scrolling
    document.body.style.overflow = "hidden";

    // Create modal backdrop
    const modalBackdrop = document.createElement("div");
    modalBackdrop.className = "image-modal-backdrop";
    modalBackdrop.id = "imageModal";

    // Create modal content
    modalBackdrop.innerHTML = `
      <div class="image-modal-content">
        <div class="image-modal-header">
          <h3 class="image-modal-title">${this.escapeHtml(imageName)}</h3>
          <button class="image-modal-close" title="Close">&times;</button>
        </div>
        <div class="image-modal-body">
          <img src="${imageUrl}" alt="${this.escapeHtml(
  imageName
)}" class="image-modal-img" />
        </div>
      </div>
    `;

    // Add to document
    document.body.appendChild(modalBackdrop);

    // Add event listeners
    const closeBtn = modalBackdrop.querySelector(".image-modal-close");
    closeBtn.addEventListener("click", () => this.closeImageModal());

    // Close on backdrop click
    modalBackdrop.addEventListener("click", (e) => {
      if (e.target === modalBackdrop) {
        this.closeImageModal();
      }
    });

    // Prevent wheel events from bubbling to document when scrolling in modal
    const modalBody = modalBackdrop.querySelector(".image-modal-body");
    const handleWheel = (e) => {
      e.stopPropagation();
    };
    modalBody.addEventListener("wheel", handleWheel);

    // Close on Escape key
    const handleEscape = (e) => {
      if (e.key === "Escape") {
        this.closeImageModal();
        document.removeEventListener("keydown", handleEscape);
      }
    };
    document.addEventListener("keydown", handleEscape);

    // Store event handlers for cleanup
    modalBackdrop._escapeHandler = handleEscape;
    modalBackdrop._wheelHandler = handleWheel;
    modalBackdrop._modalBody = modalBody;
  }

  closeImageModal() {
    const modal = document.getElementById("imageModal");
    if (modal) {
      // Clean up escape key listener
      if (modal._escapeHandler) {
        document.removeEventListener("keydown", modal._escapeHandler);
      }

      // Clean up wheel event listener
      if (modal._wheelHandler && modal._modalBody) {
        modal._modalBody.removeEventListener("wheel", modal._wheelHandler);
      }

      modal.remove();

      // Restore background scrolling
      document.body.style.overflow = "";
    }
  }

  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }
}
