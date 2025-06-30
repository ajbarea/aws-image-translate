import { AWS_CONFIG } from "./config.js";
import { AuthManager } from "./auth.js";

class ImageProcessor {
  constructor() {
    this.auth = new AuthManager(AWS_CONFIG);
    this.s3 = new AWS.S3();
    this.uploadQueue = [];
    this.setupUI();
  }

  setupUI() {
    this.dropZone = document.getElementById("dropZone");
    this.fileInput = document.getElementById("fileInput");
    this.uploadList = document.getElementById("uploadList");
    this.processBtn = document.getElementById("processBtn");
    this.resultsDiv = document.getElementById("results");

    // Setup event listeners
    this.setupDragAndDrop();
    this.setupFileInput();
    this.setupProcessButton();
  }

  setupDragAndDrop() {
    this.dropZone.addEventListener("dragover", (e) => {
      e.preventDefault();
      this.dropZone.classList.add("drag-over");
    });

    this.dropZone.addEventListener("dragleave", () => {
      this.dropZone.classList.remove("drag-over");
    });

    this.dropZone.addEventListener("drop", (e) => {
      e.preventDefault();
      this.dropZone.classList.remove("drag-over");
      this.handleFiles(e.dataTransfer.files);
    });

    this.dropZone.addEventListener("click", () => {
      this.fileInput.click();
    });
  }

  setupFileInput() {
    this.fileInput.addEventListener("change", (e) => {
      this.handleFiles(e.target.files);
    });
  }

  setupProcessButton() {
    this.processBtn.addEventListener("click", async () => {
      this.processBtn.disabled = true;
      await this.processQueue();
      this.resultsDiv.style.display = "block";
    });
  }

  handleFiles(files) {
    for (const file of files) {
      if (file.type.startsWith("image/")) {
        this.addToUploadQueue(file);
      }
    }
    if (this.uploadQueue.length > 0) {
      this.processBtn.style.display = "block";
    }
  }

  addToUploadQueue(file) {
    const item = {
      file,
      id: `upload-${Date.now()}-${crypto.randomUUID()}`,
      status: "pending",
    };

    this.uploadQueue.push(item);
    this.createUploadListItem(item);
  }

  createUploadListItem(item) {
    const li = document.createElement("li");
    li.className = "upload-item";
    li.id = item.id;

    // Create thumbnail
    const reader = new FileReader();
    reader.onload = (e) => {
      li.innerHTML = `
                <img src="${e.target.result}" alt="${item.file.name}">
                <div class="details">
                    <div>${item.file.name}</div>
                    <div class="progress">
                        <div class="progress-bar" style="width: 0%"></div>
                    </div>
                </div>
                <div class="status">Pending</div>
            `;
    };
    reader.readAsDataURL(item.file);

    this.uploadList.appendChild(li);
  }

  async processQueue() {
    for (const item of this.uploadQueue) {
      if (item.status === "pending") {
        await this.uploadAndProcess(item);
      }
    }
  }

  async uploadAndProcess(item) {
    const li = document.getElementById(item.id);
    const statusDiv = li.querySelector(".status");
    const progressBar = li.querySelector(".progress-bar");

    try {
      // Update status to uploading
      statusDiv.textContent = "Uploading...";

      // Upload to S3
      const params = {
        Bucket: AWS_CONFIG.bucketName,
        Key: `uploads/${item.file.name}`,
        Body: item.file,
        ContentType: item.file.type,
      };

      const upload = this.s3.upload(params);

      upload.on("httpUploadProgress", (progress) => {
        const percentage = ((progress.loaded / progress.total) * 100).toFixed(
          0
        );
        progressBar.style.width = `${percentage}%`;
      });

      await upload.promise();

      // Update status to processing
      statusDiv.textContent = "Processing...";

      // Here we would call our AWS Lambda function to process the image
      // For now, we'll simulate the process
      await new Promise((resolve) => setTimeout(resolve, 2000));

      // Update status to complete
      statusDiv.textContent = "Complete";
      item.status = "complete";

      this.showResults(item);
    } catch (error) {
      statusDiv.textContent = "Error";
      console.error("Error processing file:", error);
      item.status = "error";
    }
  }

  showResults(item) {
    const result = document.createElement("div");
    result.innerHTML = `
            <h3>${item.file.name}</h3>
            <p>Detected Text: Sample text detected</p>
            <p>Translation: Sample translation</p>
            <hr>
        `;
    this.resultsDiv.appendChild(result);
  }
}

// Initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
  new ImageProcessor();
});
