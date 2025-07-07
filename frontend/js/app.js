import { AWS_CONFIG } from "./config.js";
import { AuthManager } from "./auth.js";

// Import components
import { AuthComponent } from "./components/AuthComponent.js";
import { FileUploadComponent } from "./components/FileUploadComponent.js";
import { UploadQueueComponent } from "./components/UploadQueueComponent.js";
import { LanguageSelectionComponent } from "./components/LanguageSelectionComponent.js";
import { ResultsComponent } from "./components/ResultsComponent.js";

/**
 * Main application class orchestrating all components
 */
class ImageProcessor {
  constructor() {
    console.log("🚀 ImageProcessor: Initializing application...");

    // Core services
    this.auth = new AuthManager(AWS_CONFIG);
    this.s3 = null;
    this.isAuthenticated = false;

    // Components
    this.components = {
      auth: null,
      fileUpload: null,
      uploadQueue: null,
      languageSelection: null,
      results: null,
    };

    // UI sections
    this.loginSection = null;
    this.appSection = null;
    this.processBtn = null;

    console.log(
      "✅ ImageProcessor: Application structure initialized. Waiting for components."
    );
  }

  async initialize() {
    // Listen for components loaded event
    document.addEventListener("componentsLoaded", async () => {
      console.log(
        "🔧 ImageProcessor: 'componentsLoaded' event received. Initializing UI and Auth."
      );
      await this.initializeComponents();
      await this.checkInitialAuthState();
    });

    document.addEventListener("componentsLoadFailed", (e) => {
      console.error(
        "❌ ImageProcessor: 'componentsLoadFailed' event received.",
        e.detail
      );
      this.showCriticalError(
        "Failed to load essential parts of the application. Please refresh the page or try again later."
      );
    });
  }

  async initializeComponents() {
    try {
      // Cache main UI sections
      this.loginSection = document.getElementById("loginSection");
      this.appSection = document.getElementById("appSection");
      this.processBtn = document.getElementById("processBtn");

      if (!this.loginSection || !this.appSection) {
        throw new Error("Critical UI sections not found");
      }

      // Initialize components
      this.components.auth = new AuthComponent("loginSection", this.auth);
      this.components.fileUpload = new FileUploadComponent(
        "file-upload-placeholder",
        {
          acceptedTypes: ["image/*"],
          maxFileSize: 10 * 1024 * 1024, // 10MB
          maxFiles: 10,
        }
      );
      this.components.uploadQueue = new UploadQueueComponent(
        "upload-list-placeholder"
      );
      this.components.languageSelection = new LanguageSelectionComponent(
        "language-selection-placeholder",
        {
          defaultLanguage: "en",
        }
      );
      this.components.results = new ResultsComponent("results-placeholder");

      // Initialize all components
      for (const [name, component] of Object.entries(this.components)) {
        if (component) {
          await component.initialize();
          console.log(`✅ ImageProcessor: ${name} component initialized`);
        }
      }

      // Setup inter-component communication
      this.setupEventHandlers();

      // Setup process button
      this.setupProcessButton();

      console.log("✅ ImageProcessor: All components initialized successfully");
    } catch (error) {
      console.error(
        "❌ ImageProcessor: Failed to initialize components:",
        error
      );
      this.showCriticalError("Failed to initialize application components");
    }
  }

  setupEventHandlers() {
    // Authentication events
    document.addEventListener("auth:loginSuccess", async (e) => {
      await this.handleSuccessfulAuth(e.detail.userInfo);
    });

    // Queue events
    document.addEventListener("queue:updated", (e) => {
      this.updateProcessButtonVisibility();
    });

    // File upload events
    document.addEventListener("files:selected", (e) => {
      if (this.components.uploadQueue) {
        this.components.uploadQueue.addFiles(e.detail.files);
      }
    });

    // Translation request events
    document.addEventListener("result:retranslateRequest", async (e) => {
      const { item, targetLanguage, callback } = e.detail;
      try {
        const translationResult = await this.translateText(
          item.processingResults.detectedText,
          item.processingResults.detectedLanguage || "en",
          targetLanguage,
          item.s3Key
        );
        callback(translationResult);
      } catch (error) {
        console.error("Translation request failed:", error);
      }
    });
  }

  setupProcessButton() {
    if (this.processBtn) {
      this.processBtn.addEventListener("click", async () => {
        this.processBtn.disabled = true;
        await this.processQueue();
        this.processBtn.disabled = false;
      });
    }
  }

  updateProcessButtonVisibility() {
    if (this.processBtn && this.components.uploadQueue) {
      const hasPending = this.components.uploadQueue.hasPending();
      this.processBtn.style.display =
        hasPending && this.isAuthenticated ? "block" : "none";
    }
  }

  async checkInitialAuthState() {
    if (!this.auth || !this.loginSection || !this.appSection) {
      console.warn(
        "⚠️ ImageProcessor: Auth or core sections not ready for checkInitialAuthState"
      );
      return;
    }

    console.log("🔍 ImageProcessor: Checking initial authentication state...");
    try {
      const isAuth = await this.auth.isAuthenticated();
      if (isAuth) {
        console.log("✅ ImageProcessor: User is already authenticated");
        const userInfo = await this.auth.getCurrentUser();
        await this.handleSuccessfulAuth(userInfo);
      } else {
        console.log("❌ ImageProcessor: User is not authenticated");
        this.showLoginSection();
      }
    } catch (error) {
      console.error("❌ ImageProcessor: Error checking auth state:", error);
      this.showLoginSection();
    }
  }

  showLoginSection() {
    console.log("🔐 ImageProcessor: Showing login section");
    this.loginSection.style.display = "block";
    this.appSection.style.display = "none";
    this.isAuthenticated = false;
    this.updateProcessButtonVisibility();
  }

  async handleSuccessfulAuth(userInfo) {
    console.log("🎉 ImageProcessor: Handling successful authentication");

    // Store authentication state
    this.isAuthenticated = true;

    // Initialize S3 client with authenticated credentials
    this.s3 = new AWS.S3({
      region: AWS_CONFIG.region,
    });

    // Update UI to show authenticated app
    this.loginSection.style.display = "none";
    this.appSection.style.display = "block";

    // Add user info to UI
    this.addUserInfoToUI(userInfo);

    // Enable components
    if (this.components.fileUpload) this.components.fileUpload.enable();
    if (this.components.languageSelection)
      this.components.languageSelection.enable();

    // Update process button visibility
    this.updateProcessButtonVisibility();

    // Show success message
    this.showGlobalMessage(
      "✅ Login successful! You can now upload images for translation.",
      "success"
    );

    console.log("✅ ImageProcessor: Authentication UI updated");
  }

  addUserInfoToUI(userInfo) {
    // Remove existing user info if present
    const existingUserInfo = document.getElementById("userInfo");
    if (existingUserInfo) {
      existingUserInfo.remove();
    }

    // Create user info element
    const userInfoDiv = document.createElement("div");
    userInfoDiv.id = "userInfo";
    userInfoDiv.innerHTML = `
      <div class="user-info-bar">
        <div class="user-info-welcome">
          Welcome, ${userInfo.attributes?.email || userInfo.username}!
        </div>
        <button id="logoutBtn" class="logout-button">
          Logout
        </button>
      </div>
    `;

    this.appSection.insertBefore(userInfoDiv, this.appSection.firstChild);

    // Setup logout handler
    const logoutBtn = userInfoDiv.querySelector("#logoutBtn");
    if (logoutBtn) {
      logoutBtn.addEventListener("click", () => this.handleLogout());
    }
  }

  async handleLogout() {
    console.log("🚪 ImageProcessor: Handling logout");
    try {
      // Sign out from Cognito
      await this.auth.signOut();

      // Clear application state
      this.isAuthenticated = false;
      this.s3 = null;

      // Clear components
      if (this.components.uploadQueue) this.components.uploadQueue.clearQueue();
      if (this.components.results) this.components.results.clearResults();

      // Disable components
      if (this.components.fileUpload) this.components.fileUpload.disable();
      if (this.components.languageSelection)
        this.components.languageSelection.disable();

      // Remove user info from UI
      const existingUserInfo = document.getElementById("userInfo");
      if (existingUserInfo) {
        existingUserInfo.remove();
      }

      // Show login section
      this.showLoginSection();

      // Show success message
      this.showGlobalMessage(
        "You have been successfully logged out.",
        "success"
      );

      console.log("✅ ImageProcessor: Logout successful");
    } catch (error) {
      console.error("❌ ImageProcessor: Logout error:", error);
      this.showGlobalMessage("Logout failed. Please try again.", "error");
    }
  }

  async processQueue() {
    if (!this.isAuthenticated || !this.s3) {
      console.error("❌ ImageProcessor: Not authenticated for processing");
      this.showGlobalMessage(
        "Authentication error. Please log in again.",
        "error"
      );
      return;
    }

    const pendingItems = this.components.uploadQueue.getPendingItems();
    if (pendingItems.length === 0) {
      console.log("📝 ImageProcessor: No pending items to process");
      return;
    }

    console.log(`🚀 ImageProcessor: Processing ${pendingItems.length} items`);

    for (const item of pendingItems) {
      await this.uploadAndProcess(item);
    }
  }

  async uploadAndProcess(item) {
    try {
      console.log(`📤 ImageProcessor: Processing ${item.file.name}`);

      // Update status to uploading
      this.components.uploadQueue.updateItemStatus(item.id, "uploading", 0);

      // Upload to S3
      const s3Key = `uploads/${Date.now()}-${item.file.name}`;
      const uploadParams = {
        Bucket: AWS_CONFIG.bucketName,
        Key: s3Key,
        Body: item.file,
        ContentType: item.file.type,
        Metadata: {
          "original-name": item.file.name,
          "upload-time": new Date().toISOString(),
        },
      };

      const upload = this.s3.upload(uploadParams);

      // Track upload progress
      upload.on("httpUploadProgress", (progress) => {
        const percentage = Math.round((progress.loaded / progress.total) * 100);
        this.components.uploadQueue.updateItemStatus(
          item.id,
          "uploading",
          percentage
        );
      });

      const uploadResult = await upload.promise();
      console.log("✅ ImageProcessor: Upload successful:", uploadResult);

      // Update status to processing
      this.components.uploadQueue.updateItemStatus(item.id, "processing", 100);

      // Process the image
      const processingResult = await this.processImage(s3Key);

      // Update item with results
      item.s3Key = s3Key;
      item.s3Location = uploadResult.Location;
      item.processingResults = processingResult;

      // Update status to complete
      this.components.uploadQueue.updateItemStatus(item.id, "complete");

      console.log(
        `🎉 ImageProcessor: Successfully processed ${item.file.name}`
      );
    } catch (error) {
      console.error(
        `❌ ImageProcessor: Error processing ${item.file.name}:`,
        error
      );
      this.components.uploadQueue.updateItemStatus(
        item.id,
        "error",
        null,
        error.message
      );
    }
  }

  async processImage(s3Key) {
    console.log(`🚀 ImageProcessor: Processing image ${s3Key}`);

    const targetLanguage =
      this.components.languageSelection.getSelectedLanguage();

    const response = await fetch(`${AWS_CONFIG.apiGatewayUrl}/process`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        bucket: AWS_CONFIG.bucketName,
        key: s3Key,
        targetLanguage: targetLanguage,
      }),
    });

    if (!response.ok) {
      let errorMessage = `Processing failed: ${response.status} ${response.statusText}`;
      try {
        const errorBody = await response.text();
        errorMessage += ` - ${errorBody}`;
      } catch (e) {
        console.warn("Failed to read error response body:", e);
        errorMessage += " - Could not read error details";
      }
      throw new Error(errorMessage);
    }

    return await response.json();
  }

  async translateText(text, sourceLanguage, targetLanguage, s3Key) {
    console.log(`🔄 ImageProcessor: Translating text to ${targetLanguage}`);

    const response = await fetch(`${AWS_CONFIG.apiGatewayUrl}/process`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        bucket: AWS_CONFIG.bucketName,
        key: s3Key,
        targetLanguage: targetLanguage,
        detectedText: text,
        detectedLanguage: sourceLanguage,
      }),
    });

    if (!response.ok) {
      throw new Error(
        `Translation failed: ${response.status} ${response.statusText}`
      );
    }

    return await response.json();
  }

  showGlobalMessage(message, type = "info", duration = 5000) {
    // Remove existing global messages
    const existingMessages = document.querySelectorAll(".global-message");
    existingMessages.forEach((msg) => msg.remove());

    // Create message element
    const messageDiv = document.createElement("div");
    messageDiv.className = `global-message global-message-${type}`;
    messageDiv.textContent = message;

    // Insert at top of page
    const container = document.querySelector(".container");
    if (container) {
      container.insertBefore(messageDiv, container.firstChild);
    } else {
      document.body.insertBefore(messageDiv, document.body.firstChild);
    }

    // Auto-hide after duration
    if (duration > 0) {
      setTimeout(() => {
        if (messageDiv.parentNode) {
          messageDiv.remove();
        }
      }, duration);
    }
  }

  showCriticalError(message) {
    const body = document.body;
    const errorDiv = document.createElement("div");
    errorDiv.className = "critical-error";
    errorDiv.innerHTML = `<p>${message}</p>`;

    if (body.firstChild) {
      body.insertBefore(errorDiv, body.firstChild);
    } else {
      body.appendChild(errorDiv);
    }

    // Hide other major sections
    if (this.loginSection) this.loginSection.style.display = "none";
    if (this.appSection) this.appSection.style.display = "none";
  }
}

// Initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", async () => {
  const processor = new ImageProcessor();
  await processor.initialize();
});
