import { BaseComponent } from "./BaseComponent.js";

/**
 * File upload component handling drag-and-drop and file selection
 */
export class FileUploadComponent extends BaseComponent {
  constructor(containerId, options = {}) {
    super(containerId, options);
    this.acceptedTypes = options.acceptedTypes || ["image/*"];
    this.maxFileSize = options.maxFileSize || 10 * 1024 * 1024; // 10MB default
    this.maxFiles = options.maxFiles || 10;
    this.isProcessingFiles = false;
  }

  async onInit() {
    this.dropZone = this.querySelector("#dropZone");
    this.fileInput = this.querySelector("#fileInput");

    if (!this.dropZone || !this.fileInput) {
      throw new Error("Drop zone or file input not found");
    }

    // Set up file input attributes
    this.fileInput.setAttribute("accept", this.acceptedTypes.join(","));
    this.fileInput.setAttribute("multiple", "");
  }

  setupEventListeners() {
    // File input change
    this.addEventListener(
      this.fileInput,
      "change",
      this.handleFileInputChange.bind(this)
    );

    // Drop zone click
    this.addEventListener(
      this.dropZone,
      "click",
      this.handleDropZoneClick.bind(this)
    );

    // Drag and drop events
    this.addEventListener(
      this.dropZone,
      "dragover",
      this.handleDragOver.bind(this)
    );
    this.addEventListener(
      this.dropZone,
      "dragleave",
      this.handleDragLeave.bind(this)
    );
    this.addEventListener(this.dropZone, "drop", this.handleDrop.bind(this));

    // Prevent default drag behaviors on document
    this.addEventListener(document, "dragover", (e) => e.preventDefault());
    this.addEventListener(document, "drop", (e) => e.preventDefault());
  }

  handleFileInputChange(e) {
    const files = Array.from(e.target.files);
    this.processFiles(files);
  }

  handleDropZoneClick(e) {
    // Don't trigger if clicking on the actual file input
    if (e.target !== this.fileInput) {
      e.preventDefault();
      this.fileInput.click();
    }
  }

  handleDragOver(e) {
    e.preventDefault();
    this.dropZone.classList.add("drag-over");
  }

  handleDragLeave(e) {
    // Only remove the class if we're leaving the drop zone entirely
    if (!this.dropZone.contains(e.relatedTarget)) {
      this.dropZone.classList.remove("drag-over");
    }
  }

  handleDrop(e) {
    e.preventDefault();
    this.dropZone.classList.remove("drag-over");

    const files = Array.from(e.dataTransfer.files);
    this.processFiles(files);
  }

  async processFiles(files) {
    if (files.length === 0 || this.isProcessingFiles) {
      return;
    }

    // Set processing flag to prevent duplicate processing
    this.isProcessingFiles = true;

    try {
      const validFiles = [];
      const errors = [];

      // Validate each file
      for (const file of files) {
        const validation = await this.validateFile(file);
        if (validation.valid) {
          validFiles.push(file);
        } else {
          errors.push(`${file.name}: ${validation.error}`);
        }
      }

      // Check total file count
      if (validFiles.length > this.maxFiles) {
        errors.push(
          `Maximum ${this.maxFiles} files allowed. ${validFiles.length} files selected.`
        );
        validFiles.splice(this.maxFiles);
      }

      // Show errors if any
      if (errors.length > 0) {
        this.showError(errors.join("\n"));
      }

      // Emit files if any are valid
      if (validFiles.length > 0) {
        this.emit("files:selected", { files: validFiles });
        this.showSuccess(`${validFiles.length} file(s) selected for upload`);
      }

      // Clear the file input
      this.fileInput.value = "";
    } finally {
      // Reset processing flag after a short delay to allow for any pending events
      setTimeout(() => {
        this.isProcessingFiles = false;
      }, 100);
    }
  }

  validateFile(file) {
    // Check file type
    const isValidType = this.acceptedTypes.some((type) => {
      if (type.endsWith("/*")) {
        const category = type.slice(0, -2);
        return file.type.startsWith(category + "/");
      }
      return file.type === type;
    });

    if (!isValidType) {
      return {
        valid: false,
        error: `Invalid file type. Accepted types: ${this.acceptedTypes.join(
          ", "
        )}`,
      };
    }

    // Check file size
    if (file.size > this.maxFileSize) {
      const sizeMB = Math.round(this.maxFileSize / 1024 / 1024);
      return {
        valid: false,
        error: `File too large. Maximum size: ${sizeMB}MB`,
      };
    }

    // Check if it's actually an image by trying to create an image element
    return new Promise((resolve) => {
      if (file.type.startsWith("image/")) {
        const img = new Image();
        img.onload = () => {
          URL.revokeObjectURL(img.src);
          resolve({ valid: true });
        };
        img.onerror = () => {
          URL.revokeObjectURL(img.src);
          resolve({ valid: false, error: "Invalid or corrupted image file" });
        };
        img.src = URL.createObjectURL(file);
      } else {
        resolve({ valid: true });
      }
    });
  }

  /**
   * Update drop zone state
   */
  setEnabled(enabled) {
    if (enabled) {
      this.enable();
      this.dropZone.classList.remove("disabled");
    } else {
      this.disable();
      this.dropZone.classList.add("disabled");
    }
  }

  /**
   * Update drop zone text
   */
  setDropZoneText(text) {
    const textElement = this.dropZone.querySelector("p");
    if (textElement) {
      textElement.textContent = text;
    }
  }

  /**
   * Get current files from file input
   */
  getCurrentFiles() {
    return Array.from(this.fileInput.files);
  }

  /**
   * Clear selected files
   */
  clearFiles() {
    this.fileInput.value = "";
    this.clearMessages();
  }
}
