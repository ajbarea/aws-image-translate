import { BaseComponent } from "./BaseComponent.js";

/**
 * Upload queue component managing the list of files to be processed
 */
export class UploadQueueComponent extends BaseComponent {
  constructor(containerId, options = {}) {
    super(containerId, options);
    this.uploadQueue = [];
    this.nextId = 1;
  }

  async onInit() {
    this.uploadList = this.querySelector("#uploadList");
    if (!this.uploadList) {
      throw new Error("Upload list element not found");
    }
  }

  setupEventListeners() {
    // Listen for remove button clicks
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
      addedAt: new Date(),
    };

    this.uploadQueue.push(item);
    this.createUploadListItem(item);
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
      this.emit("queue:updated", { queue: this.uploadQueue });
    }
  }

  createUploadListItem(item) {
    const li = document.createElement("li");
    li.className = "upload-item";
    li.id = item.id;

    // Create placeholder content first
    li.innerHTML = `
      <div class="upload-item-image">
        <div class="image-placeholder">Loading...</div>
      </div>
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
        <button class="remove-file-btn" data-item-id="${
          item.id
        }" title="Remove file">×</button>
      </div>
    `;

    // Create thumbnail asynchronously
    this.createThumbnail(item.file)
      .then((thumbnailSrc) => {
        const imageContainer = li.querySelector(".upload-item-image");
        if (imageContainer && thumbnailSrc) {
          imageContainer.innerHTML = `<img src="${thumbnailSrc}" alt="${item.file.name}">`;
        }
      })
      .catch((error) => {
        console.warn(
          `⚠️ UploadQueue: Could not create thumbnail for ${item.file.name}:`,
          error
        );
        const imageContainer = li.querySelector(".upload-item-image");
        if (imageContainer) {
          imageContainer.innerHTML = `<div class="image-placeholder">📷</div>`;
        }
      });

    this.uploadList.appendChild(li);
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
      }
    }

    this.emit("queue:itemUpdated", { item });
  }

  getStatusDisplayText(status) {
    const statusMap = {
      pending: "Pending",
      uploading: "Uploading...",
      processing: "Processing...",
      complete: "Complete",
      error: "Error",
    };
    return statusMap[status] || status;
  }

  formatFileSize(bytes) {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
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

  clearQueue() {
    this.uploadQueue = [];
    this.uploadList.innerHTML = "";
    this.emit("queue:updated", { queue: this.uploadQueue });
  }

  clearCompleted() {
    const completedItems = this.getCompletedItems();
    for (const item of completedItems) {
      this.removeFromQueue(item.id);
    }
  }

  isEmpty() {
    return this.uploadQueue.length === 0;
  }

  hasError() {
    return this.uploadQueue.some((item) => item.status === "error");
  }

  hasPending() {
    return this.uploadQueue.some((item) => item.status === "pending");
  }
}
