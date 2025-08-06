const { AWS_CONFIG } = window;
import { AuthManager } from "./auth.js";
import { AuthComponent } from "./components/AuthComponent.js";
import { FileUploadComponent } from "./components/FileUploadComponent.js";
import { UploadQueueComponent } from "./components/UploadQueueComponent.js";
import { LanguageSelectionComponent } from "./components/LanguageSelectionComponent.js";
import { ResultsComponent } from "./components/ResultsComponent.js";
import { GalleryComponent } from "./components/GalleryComponent.js";
import { DashboardComponent } from "./components/DashboardComponent.js";
import { initPerformanceMonitor } from "./performance.js";

// Main application class orchestrating all components
class ImageProcessor {
  constructor() {
    console.log("🚀 ImageProcessor: Initializing application...");

    // Core services
    this.auth = new AuthManager(AWS_CONFIG);
    this.s3 = null;
    this.isAuthenticated = false;
    this.oauthCompleted = false; // Track if OAuth was completed
    this.forceAuthCheck = false; // Force auth check when components load
    this.pendingAuthData = null; // Store auth data if DOM isn't ready

    // Components
    this.components = {
      auth: null,
      fileUpload: null,
      uploadQueue: null,
      languageSelection: null,
      results: null,
      gallery: null,
      dashboard: null
    };

    // UI sections
    this.loadingSection = null;
    this.loginSection = null;
    this.appSection = null;
    this.processButton = null;
    this.clearAllButton = null;
    this.tabsContainer = null;
    this.uploadView = null;
    this.galleryView = null;
    this.dashboardView = null;
    this.uploadTab = null;
    this.galleryTab = null;
    this.dashboardTab = null;

    console.log(
      "✅ ImageProcessor: Application structure initialized. Waiting for components."
    );
  }

  async initialize() {
    // Start performance monitoring as early as possible
    initPerformanceMonitor();

    // Quick synchronous auth check to prevent login screen flash
    this.performQuickAuthCheck();

    // Setup event handlers FIRST - before anything else
    this.setupEventHandlers();

    // Setup URL-based routing for maintaining tab state on refresh
    this.setupURLRouting();

    // Listen for components loaded event SECOND - before OAuth processing
    document.addEventListener("componentsLoaded", async () => {
      console.log(
        "🔧 ImageProcessor: 'componentsLoaded' event received. Initializing UI and Auth."
      );
      await this.initializeComponents();

      // Setup processing status handlers after components are ready
      this.setupProcessingStatusHandlers();

      // Always check auth state, but prioritize OAuth completion
      if (this.oauthCompleted || this.forceAuthCheck) {
        console.log("🔄 ImageProcessor: OAuth was completed or force auth check requested, checking auth state immediately");
        await this.checkInitialAuthState();
      } else {
        console.log("🔄 ImageProcessor: No OAuth completion detected, checking normal auth state");
        await this.checkInitialAuthState();
      }
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

    // Check for OAuth callback THIRD - after event handlers are set up
    await this.handleOAuthCallback();
  }

  async initializeComponents() {
    try {
      // Cache main UI sections
      this.loadingSection = document.getElementById("loadingSection");
      this.loginSection = document.getElementById("loginSection");
      this.appSection = document.getElementById("appSection");
      this.processButton = document.getElementById("process-btn");
      this.clearAllButton = document.getElementById("clear-all-btn");
      this.tabsContainer = document.getElementById("tabs-container");
      this.uploadView = document.getElementById("upload-view");
      this.galleryView = document.getElementById("gallery-view");
      this.dashboardView = document.getElementById("dashboard-view");
      this.uploadTab = document.getElementById("upload-tab");
      this.galleryTab = document.getElementById("gallery-tab");
      this.dashboardTab = document.getElementById("dashboard-tab");
      this.processingStatus = document.getElementById("processing-status");

      if (!this.loginSection || !this.appSection) {
        throw new Error("Critical UI sections not found");
      }

      console.log("✅ ImageProcessor: DOM elements cached successfully");

      // Initialize components
      this.components.auth = new AuthComponent("loginSection", this.auth);
      this.components.fileUpload = new FileUploadComponent(
        "file-upload-placeholder",
        {
          acceptedTypes: ["image/jpeg", "image/jpg", "image/png"],
          maxFileSize: 15 * 1024 * 1024, // 15MB (AWS Rekognition limit)
          maxFiles: 10
        }
      );
      this.components.uploadQueue = new UploadQueueComponent(
        "upload-list-placeholder"
      );
      this.components.languageSelection = new LanguageSelectionComponent(
        "language-selection-placeholder",
        {
          defaultLanguage: "en"
        }
      );
      this.components.results = new ResultsComponent("results-placeholder");
      this.components.gallery = new GalleryComponent("gallery-placeholder");
      this.components.dashboard = new DashboardComponent("dashboard-placeholder", this.auth);

      // Initialize all components
      for (const [name, component] of Object.entries(this.components)) {
        if (component) {
          await component.initialize();
          console.log(`✅ ImageProcessor: ${name} component initialized`);
        }
      }

      // Setup process button
      this.setupProcessButton();

      // Handle any pending auth data
      if (this.pendingAuthData) {
        console.log("🔄 ImageProcessor: Processing pending auth data from successful authentication");
        await this.handleSuccessfulAuth(this.pendingAuthData, true); // This is from a new login
        this.pendingAuthData = null;
      } else if (this.oauthCompleted) {
        // If OAuth was completed but no pending data, force auth check
        console.log("🔄 ImageProcessor: OAuth completed but no pending data, forcing auth check");
        await this.checkInitialAuthState();
      }

      console.log("✅ ImageProcessor: All components initialized successfully");
    } catch (error) {
      console.error(
        "❌ ImageProcessor: Failed to initialize components:",
        error
      );

      // Don't show critical error if it's just a timing issue with auth components
      if (error.message.includes("Auth form containers not found")) {
        console.log("⏳ ImageProcessor: Auth components not ready yet, will retry when componentsLoaded fires");
        return;
      }

      this.showCriticalError("Failed to initialize application components");
    }
  }

  setupEventHandlers() {
    // Authentication events
    document.addEventListener("auth:loginSuccess", async (e) => {
      console.log("🎯 ImageProcessor: auth:loginSuccess event received!");
      try {
        // If DOM elements aren't ready yet, wait for components to load
        if (!this.loginSection || !this.appSection) {
          console.log("⏳ ImageProcessor: DOM not ready, storing auth data for later");
          this.pendingAuthData = e.detail.userInfo;

          // Set up a one-time listener for when components are loaded
          const handleComponentsLoaded = async () => {
            console.log("🔄 ImageProcessor: Components loaded, processing stored auth data");
            if (this.pendingAuthData) {
              await this.handleSuccessfulAuth(this.pendingAuthData, true); // This is from a new login
              this.pendingAuthData = null;
            }
            document.removeEventListener("componentsLoaded", handleComponentsLoaded);
          };

          document.addEventListener("componentsLoaded", handleComponentsLoaded);
          return;
        }

        console.log("🔄 ImageProcessor: DOM is ready, processing auth immediately");
        await this.handleSuccessfulAuth(e.detail.userInfo, true); // This is from auth:loginSuccess event
      } catch (error) {
        console.error("❌ ImageProcessor: Error in handleSuccessfulAuth:", error);
      }
    });

    // Queue events
    document.addEventListener("queue:updated", (_e) => {
      this.updateProcessButtonVisibility();
      this.updateProcessingStatus();
    });

    // Results events
    document.addEventListener("result:removed", (_e) => {
      this.updateProcessButtonVisibility();
    });

    // Listen for new results to update counter
    document.addEventListener("result:added", (_e) => {
      this.updateResultsCounter();
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
        callback(null, translationResult);
      } catch (error) {
        console.error("Translation request failed:", error);
        callback(error, null);
      }
    });

    document.addEventListener("flipmodal:translateRequest", async (e) => {
      const { imageData, targetLanguage, currentResults, callback } = e.detail;
      try {
        const detectedText = currentResults ? currentResults.detectedText : null;
        const detectedLanguage = currentResults ? currentResults.detectedLanguage : null;

        const translationResult = await this.translateText(
          detectedText,
          detectedLanguage,
          targetLanguage,
          imageData.key
        );
        callback(null, translationResult);
      } catch (error) {
        console.error("Flip modal translation request failed:", error);
        callback(error, null);
      }
    });
  }

  setupProcessButton() {
    if (this.processButton) {
      this.processButton.addEventListener("click", async () => {
        this.processButton.disabled = true;
        await this.processQueue();
        this.processButton.disabled = false;
      });
    }

    if (this.clearAllButton) {
      this.clearAllButton.addEventListener("click", () => {
        this.clearAllData();
      });
    }
  }

  updateProcessButtonVisibility() {
    if (this.processButton && this.components.uploadQueue) {
      const hasPending = this.components.uploadQueue.hasPending();
      this.processButton.style.display =
        hasPending && this.isAuthenticated ? "block" : "none";
    }

    // Show clear button if there are uploads or results
    if (this.clearAllButton && this.isAuthenticated) {
      const hasUploads =
        this.components.uploadQueue && !this.components.uploadQueue.isEmpty();
      const hasResults = this.components.results?.hasResults();
      this.clearAllButton.style.display =
        hasUploads || hasResults ? "block" : "none";
    }
  }

  async handleOAuthCallback() {
    // Check if current URL contains OAuth callback parameters
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get("code");
    const error = urlParams.get("error");

    if (code || error) {
      console.log("🔄 ImageProcessor: OAuth callback detected");

      try {
        if (error) {
          console.error("❌ ImageProcessor: OAuth error:", error);
          this.showGlobalMessage(`Google sign-in failed: ${error}`, "error");
        } else {
          // Check if this is an account linking callback
          const oauthAction = sessionStorage.getItem("oauth_action");

          if (oauthAction === "link_account") {
            console.log("🔗 ImageProcessor: Account linking callback detected");

            // Handle account linking
            const tokens = await this.auth.handleOAuthCallback();
            console.log("🎉 ImageProcessor: Account linking successful");

            // Clear OAuth action
            sessionStorage.removeItem("oauth_action");

            // Clear URL parameters
            window.history.replaceState({}, document.title, window.location.pathname);

            // Emit account linking success event
            document.dispatchEvent(new CustomEvent("profile:googleLinked", {
              detail: { tokens }
            }));

            // Show success message
            this.showGlobalMessage("✅ Google account linked successfully!", "success");

            // Switch to profile view to show the updated status
            if (this.isAuthenticated) {
              this.showView("profile");
            }
          } else {
            // Handle regular OAuth sign-in
            await this.auth.handleOAuthCallback();
            console.log("🎉 ImageProcessor: OAuth callback successful");

            // Clear URL parameters
            window.history.replaceState({}, document.title, window.location.pathname);

            // Mark OAuth as completed
            this.oauthCompleted = true;

            // Get user info and emit login success event
            try {
              const userInfo = await this.auth.getCurrentUser();
              console.log("👤 ImageProcessor: Retrieved user info after Google OAuth - user authenticated successfully");

              // Small delay to ensure DOM is ready
              await new Promise(resolve => setTimeout(resolve, 100));

              // Emit the auth:loginSuccess event to trigger UI transition
              document.dispatchEvent(new CustomEvent("auth:loginSuccess", {
                detail: { userInfo }
              }));

              console.log("🎉 ImageProcessor: Google OAuth login success event emitted");

            } catch (userInfoError) {
              console.error("❌ ImageProcessor: Failed to get user info after OAuth:", userInfoError);
              console.error("🔍 ImageProcessor: Error details:", userInfoError.message);

              // Better fallback: Try to get user info using isAuthenticated check
              console.log("🔄 ImageProcessor: Attempting fallback user info retrieval...");

              try {
                // Wait a bit for the auth state to settle
                await new Promise(resolve => setTimeout(resolve, 100));

                const isAuth = await this.auth.isAuthenticated();
                if (isAuth) {
                  console.log("✅ ImageProcessor: User is authenticated, trying getCurrentUser again...");
                  const retryUserInfo = await this.auth.getCurrentUser();

                  // Emit the auth:loginSuccess event to trigger UI transition
                  document.dispatchEvent(new CustomEvent("auth:loginSuccess", {
                    detail: { userInfo: retryUserInfo }
                  }));

                  console.log("🎉 ImageProcessor: Google OAuth login success event emitted (retry)");
                } else {
                  console.error("❌ ImageProcessor: User not authenticated in fallback check");
                  throw new Error("Authentication state check failed");
                }
              } catch (fallbackError) {
                console.error("❌ ImageProcessor: Fallback user info retrieval also failed:", fallbackError);

                // Final fallback: Check authentication state to trigger redirect to main app
                if (this.components.auth && this.loginSection && this.appSection) {
                  console.log("🔄 ImageProcessor: Using final fallback - checkInitialAuthState");
                  await this.checkInitialAuthState();
                } else {
                  console.log("🔄 ImageProcessor: Components not ready, auth will be checked when components load");
                  // Set a flag to force auth check when components load
                  this.forceAuthCheck = true;
                }
              }
            }
          }
        }
      } catch (error) {
        console.error("❌ ImageProcessor: OAuth callback handling failed:", error);

        // Clear OAuth action on error
        sessionStorage.removeItem("oauth_action");

        const oauthAction = sessionStorage.getItem("oauth_action");
        const errorMessage = oauthAction === "link_account"
          ? "Google account linking failed. Please try again."
          : "Google sign-in failed. Please try again.";

        this.showGlobalMessage(errorMessage, "error");

        // Clear URL parameters even on error
        window.history.replaceState({}, document.title, window.location.pathname);
      }
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
      console.log("🔍 ImageProcessor: Authentication check result:", isAuth);

      if (isAuth) {
        console.log("✅ ImageProcessor: User is authenticated, getting user info...");
        try {
          const userInfo = await this.auth.getCurrentUser();
          console.log("👤 ImageProcessor: User info retrieved successfully");
          await this.handleSuccessfulAuth(userInfo, false); // This is session restoration, not new login
        } catch (userInfoError) {
          console.error("❌ ImageProcessor: Failed to get user info despite being authenticated:", userInfoError);
          console.log("🔄 ImageProcessor: Creating fallback user info for authenticated OAuth user");

          // Create fallback user info for OAuth users
          const fallbackUserInfo = {
            username: "oauth_user",
            attributes: {
              email: "oauth_user@google.oauth",
              email_verified: "true",
              name: "OAuth User"
            }
          };

          console.log("👤 ImageProcessor: Using fallback user info for OAuth user");
          await this.handleSuccessfulAuth(fallbackUserInfo, false); // This is session restoration, not new login
        }
      } else {
        console.log("❌ ImageProcessor: User is not authenticated");
        // Clear any URL hash since user needs to login first
        if (window.location.hash) {
          window.history.replaceState(null, null, window.location.pathname);
        }
        this.showLoginSection();
      }
    } catch (error) {
      console.error("❌ ImageProcessor: Error checking auth state:", error);
      this.showLoginSection();
    }
  }

  showLoginSection() {
    console.log("🔐 ImageProcessor: Showing login section");
    if (this.loadingSection) { this.loadingSection.style.display = "none"; }
    if (this.loginSection) { this.loginSection.style.display = "block"; }
    if (this.appSection) { this.appSection.style.display = "none"; }
    this.isAuthenticated = false;
    this.updateProcessButtonVisibility();
  }

  async handleSuccessfulAuth(userInfo, isNewLogin = false) {
    console.log("🎉 ImageProcessor: Handling successful authentication", { isNewLogin });
    console.log("👤 ImageProcessor: UserInfo received successfully");
    console.log("🔍 ImageProcessor: Current DOM elements:", {
      loginSection: !!this.loginSection,
      appSection: !!this.appSection,
      tabsContainer: !!this.tabsContainer
    });

    // Ensure DOM elements are available
    if (!this.loginSection || !this.appSection) {
      console.error("❌ ImageProcessor: Critical DOM elements not available in handleSuccessfulAuth");
      console.log("🔄 ImageProcessor: Storing auth data as pending and will retry");
      this.pendingAuthData = userInfo;
      return;
    }

    console.log("🔄 ImageProcessor: Starting authentication UI transition...");

    // Store authentication state
    this.isAuthenticated = true;

    // Initialize S3 client with authenticated credentials if available
    // For OAuth users, we need to wait for credentials to be set up
    const maxRetries = 10;
    let retryCount = 0;

    const initializeS3Client = async () => {
      try {
        // Check if AWS credentials are available
        if (AWS.config.credentials && AWS.config.credentials.accessKeyId) {
          this.s3 = new AWS.S3({
            region: AWS_CONFIG.region
          });
          console.log("✅ ImageProcessor: S3 client initialized with credentials");
          console.log("🔑 ImageProcessor: AWS credentials available:", {
            hasCredentials: !!AWS.config.credentials,
            hasAccessKey: !!AWS.config.credentials?.accessKeyId,
            region: AWS_CONFIG.region
          });
          return;
        }

        // If no credentials yet and we haven't exceeded retries, wait and try again
        if (retryCount < maxRetries) {
          retryCount++;
          console.log(`🔄 ImageProcessor: Waiting for AWS credentials (attempt ${retryCount}/${maxRetries})...`);
          setTimeout(initializeS3Client, 500); // Wait 500ms and try again
          return;
        }

        // Fallback: create S3 client without explicit credentials (rely on global config)
        this.s3 = new AWS.S3({
          region: AWS_CONFIG.region
        });
        console.log("⚠️ ImageProcessor: S3 client initialized without explicit credentials check");

      } catch (s3Error) {
        console.warn("⚠️ ImageProcessor: S3 client initialization failed - uploads may not work:", s3Error.message);
        this.s3 = null;
      }
    };

    // Start S3 client initialization
    initializeS3Client();

    // Update UI to show authenticated app
    console.log("🔄 ImageProcessor: About to update UI - hiding loading/login, showing app");
    console.log("🔍 ImageProcessor: Before UI update - loadingSection display:", this.loadingSection?.style.display);
    console.log("🔍 ImageProcessor: Before UI update - loginSection display:", this.loginSection?.style.display);
    console.log("🔍 ImageProcessor: Before UI update - appSection display:", this.appSection?.style.display);

    if (this.loadingSection) { this.loadingSection.style.display = "none"; }
    if (this.loginSection) { this.loginSection.style.display = "none"; }
    if (this.appSection) { this.appSection.style.display = "block"; }
    if (this.tabsContainer) { this.tabsContainer.style.display = "flex"; }

    console.log("🔍 ImageProcessor: After UI update - loadingSection display:", this.loadingSection?.style.display);
    console.log("🔍 ImageProcessor: After UI update - loginSection display:", this.loginSection?.style.display);
    console.log("🔍 ImageProcessor: After UI update - appSection display:", this.appSection?.style.display);
    console.log("✅ ImageProcessor: UI visibility updated");

    // Add user info to UI
    this.addUserInfoToUI(userInfo);

    // Enable components
    if (this.components.fileUpload) { this.components.fileUpload.enable(); }
    if (this.components.languageSelection) { this.components.languageSelection.enable(); }

    // Setup tab listeners
    this.uploadTab.addEventListener("click", () => this.showView("upload"));
    this.galleryTab.addEventListener("click", () => this.showView("gallery"));
    this.dashboardTab.addEventListener("click", () => this.showView("dashboard"));

    // Set initial view - check URL hash first, fallback to upload
    const initialView = this.getViewFromURL() || "upload";
    console.log(`🎯 Setting initial view to: ${initialView}`);
    this.showView(initialView);

    // Update process button visibility
    this.updateProcessButtonVisibility();

    // Show success message only for new logins, not session restoration
    if (isNewLogin) {
      this.showGlobalMessage(
        "✅ Login successful! You can now upload images for translation.",
        "success"
      );
    }

    console.log("✅ ImageProcessor: Authentication UI updated");
  }

  showView(viewName) {
    console.log(`📱 Switching to ${viewName} view`);

    // Hide all views first
    this.uploadView.style.display = "none";
    this.galleryView.style.display = "none";
    this.dashboardView.style.display = "none";

    // Remove active class from all tabs
    this.uploadTab.classList.remove("active");
    this.galleryTab.classList.remove("active");
    this.dashboardTab.classList.remove("active");

    // Update URL hash to reflect current view
    this.updateURL(viewName);

    if (viewName === "upload") {
      this.uploadView.style.display = "block";
      this.uploadTab.classList.add("active");
      // Clear counter when viewing upload tab (where results are shown)
      this.clearResultsCounter();
    } else if (viewName === "gallery") {
      this.galleryView.style.display = "block";
      this.galleryTab.classList.add("active");

      // Initialize gallery component if it exists
      if (this.components.gallery) {
        this.components.gallery.refresh();
      }
    } else if (viewName === "dashboard") {
      this.dashboardView.style.display = "block";
      this.dashboardTab.classList.add("active");

      // Initialize dashboard component if it exists
      if (this.components.dashboard) {
        this.components.dashboard.refresh();
      }
    }

    console.log(`✅ Successfully switched to ${viewName} view`);
  }

  updateResultsCounter() {
    // Only show counter if we're not currently on the upload tab
    if (!this.uploadTab.classList.contains("active")) {
      const currentCount = parseInt(this.uploadTab.dataset.resultCount || "0") + 1;
      this.uploadTab.dataset.resultCount = currentCount;

      // Update or create counter badge
      let badge = this.uploadTab.querySelector(".tab-counter");
      if (!badge) {
        badge = document.createElement("span");
        badge.className = "tab-counter";
        this.uploadTab.appendChild(badge);
      }
      badge.textContent = currentCount;
    }
  }

  clearResultsCounter() {
    const badge = this.uploadTab.querySelector(".tab-counter");
    if (badge) {
      badge.remove();
    }
    this.uploadTab.dataset.resultCount = "0";
  }

  // URL-based routing methods for maintaining tab state on refresh
  getViewFromURL() {
    const hash = window.location.hash.substring(1); // Remove the # symbol
    const validViews = ["upload", "gallery", "dashboard"];
    console.log(`🔗 URL Hash: "${hash}", Valid: ${validViews.includes(hash)}`);
    return validViews.includes(hash) ? hash : null;
  }

  updateURL(viewName) {
    // Update URL hash without triggering page reload
    const newHash = `#${viewName}`;
    if (window.location.hash !== newHash) {
      console.log(`🔗 Updating URL hash to: ${newHash}`);
      window.history.replaceState(null, null, newHash);
    }
  }

  setupURLRouting() {
    // Listen for hash changes (back/forward button navigation)
    window.addEventListener("hashchange", () => {
      console.log("🔗 Hash changed, checking authentication...");
      const viewName = this.getViewFromURL();
      if (viewName && this.isAuthenticated) {
        console.log(`🔗 Navigating to ${viewName} via hash change`);
        this.showView(viewName);
      } else if (!this.isAuthenticated) {
        console.log("🔗 User not authenticated, clearing hash");
        window.history.replaceState(null, null, window.location.pathname);
      }
    });

    console.log("🔗 URL routing setup complete");
  }

  performQuickAuthCheck() {
    console.log("⚡ Performing quick auth check...");

    try {
      // Check for OAuth token in localStorage
      const oauthToken = localStorage.getItem("oauth_id_token");
      let validOAuthToken = false;

      if (oauthToken) {
        try {
          // Quick token expiration check
          const tokenParts = oauthToken.split(".");
          if (tokenParts.length === 3) {
            const payload = JSON.parse(atob(tokenParts[1]));
            const currentTime = Math.floor(Date.now() / 1000);
            validOAuthToken = payload.exp && payload.exp > currentTime;
          }
        } catch (_e) {
          console.log("⚡ Could not validate OAuth token format");
        }
      }

      // Check for Cognito session (synchronously from localStorage)
      let hasCognitoSession = false;
      try {
        const cognitoKeys = Object.keys(localStorage).filter(key =>
          key.includes("CognitoIdentityServiceProvider") &&
          key.includes("accessToken")
        );
        hasCognitoSession = cognitoKeys.length > 0;
      } catch (_e) {
        console.log("⚡ Could not check Cognito session synchronously");
      }

      const likelyAuthenticated = validOAuthToken || hasCognitoSession;

      console.log(`⚡ Quick auth check result: ${likelyAuthenticated ? "likely authenticated" : "likely not authenticated"} (OAuth: ${validOAuthToken}, Cognito: ${hasCognitoSession})`);

      if (likelyAuthenticated) {
        // Hide loading and show app immediately, auth check will confirm later
        if (this.loadingSection) { this.loadingSection.style.display = "none"; }
        if (this.appSection) { this.appSection.style.display = "block"; }
        console.log("⚡ Showing app immediately based on quick check");
      } else {
        // Hide loading and show login
        if (this.loadingSection) { this.loadingSection.style.display = "none"; }
        if (this.loginSection) { this.loginSection.style.display = "block"; }
        console.log("⚡ Showing login immediately based on quick check");
      }
    } catch (error) {
      console.error("⚡ Quick auth check failed:", error);
      // Fallback to showing loading
      console.log("⚡ Fallback: keeping loading screen visible");
    }
  }

  updateProcessingStatus(completed = 0, total = 0) {
    if (!this.processingStatus) { return; }

    if (total === 0) {
      // Hide status bar when no processing
      this.processingStatus.classList.add("hidden");
      return;
    }

    // Show and update status bar
    this.processingStatus.classList.remove("hidden");

    const statusText = this.processingStatus.querySelector(".processing-status-text");
    const statusCount = this.processingStatus.querySelector(".processing-status-count");
    const statusBar = this.processingStatus.querySelector(".processing-status-bar");
    const toggleBtn = this.processingStatus.querySelector(".processing-status-toggle");

    if (completed >= total) {
      statusText.textContent = "✅ Processing complete!";
      statusCount.textContent = `${completed} results ready`;
      statusBar.style.width = "100%";
      toggleBtn.textContent = "📍 View Results";

      // Auto-hide after 3 seconds when complete
      setTimeout(() => {
        this.processingStatus.classList.add("hidden");
      }, 3000);
    } else {
      statusText.textContent = "Processing images...";
      statusCount.textContent = `${completed} of ${total} completed`;
      statusBar.style.width = `${(completed / total) * 100}%`;
      toggleBtn.textContent = "📍 View Latest";
    }
  }

  setupProcessingStatusHandlers() {
    if (!this.processingStatus) { return; }

    const toggleBtn = this.processingStatus.querySelector(".processing-status-toggle");
    if (toggleBtn) {
      toggleBtn.addEventListener("click", () => {
        // Scroll to the latest result
        if (this.components.results) {
          const latestResult = this.components.results.getLatestResult();
          if (latestResult) {
            this.components.results.scrollToResult(latestResult);
          }
        }
      });
    }
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
        <button id="logout-btn" class="logout-button">
          Logout
        </button>
      </div>
    `;

    this.appSection.insertBefore(userInfoDiv, this.appSection.firstChild);

    // Setup logout handler
    const logoutBtn = userInfoDiv.querySelector("#logout-btn");
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
      if (this.components.uploadQueue) { this.components.uploadQueue.clearQueue(); }
      if (this.components.results) { this.components.results.clearResults(); }

      // Disable components
      if (this.components.fileUpload) { this.components.fileUpload.disable(); }
      if (this.components.languageSelection) { this.components.languageSelection.disable(); }

      // Remove user info from UI
      const existingUserInfo = document.getElementById("userInfo");
      if (existingUserInfo) {
        existingUserInfo.remove();
      }

      // Hide tabs
      this.tabsContainer.style.display = "none";

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
    if (!this.isAuthenticated) {
      console.error("❌ ImageProcessor: Not authenticated");
      this.showGlobalMessage(
        "Authentication error. Please log in again.",
        "error"
      );
      return;
    }

    if (!this.s3) {
      console.error("❌ ImageProcessor: S3 client not available");
      this.showGlobalMessage(
        "Upload functionality is temporarily unavailable. AWS credentials could not be established.",
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

    // Initialize processing status
    let completedItems = 0;
    const totalItems = pendingItems.length;
    this.updateProcessingStatus(completedItems, totalItems);

    for (const item of pendingItems) {
      await this.uploadAndProcess(item);
      completedItems++;
      this.updateProcessingStatus(completedItems, totalItems);
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
          "upload-time": new Date().toISOString()
        }
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
        Authorization: `Bearer ${this.auth.idToken}`
      },
      body: JSON.stringify({
        bucket: AWS_CONFIG.bucketName,
        key: s3Key,
        targetLanguage: targetLanguage
      })
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
        Authorization: `Bearer ${this.auth.idToken}`
      },
      body: JSON.stringify({
        bucket: AWS_CONFIG.bucketName,
        key: s3Key,
        targetLanguage: targetLanguage,
        detectedText: text,
        detectedLanguage: sourceLanguage
      })
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
    if (this.loginSection) { this.loginSection.style.display = "none"; }
    if (this.appSection) { this.appSection.style.display = "none"; }
  }

  clearAllData() {
    console.log("🗑️ ImageProcessor: Clearing all data");

    // Clear upload queue
    if (this.components.uploadQueue) {
      this.components.uploadQueue.clearQueue();
    }

    // Clear results
    if (this.components.results) {
      this.components.results.clearResults();
    }

    // Update button visibility
    this.updateProcessButtonVisibility();

    console.log("✅ ImageProcessor: All data cleared");
  }

  // Debug method to test UI transition manually
  testUITransition() {
    console.log("🧪 ImageProcessor: Testing UI transition manually");
    console.log("🔍 ImageProcessor: Current DOM elements:", {
      loginSection: !!this.loginSection,
      appSection: !!this.appSection,
      tabsContainer: !!this.tabsContainer
    });

    if (this.loginSection && this.appSection) {
      console.log("🔄 ImageProcessor: Forcing UI transition for testing");
      this.loginSection.style.display = "none";
      this.appSection.style.display = "block";
      if (this.tabsContainer) {
        this.tabsContainer.style.display = "flex";
      }
      console.log("✅ ImageProcessor: Test UI transition completed");
    } else {
      console.error("❌ ImageProcessor: Cannot test UI transition - DOM elements not available");
    }
  }
}

// Initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", async () => {
  const processor = new ImageProcessor();
  await processor.initialize();

  // Make processor globally accessible for debugging
  window.imageProcessor = processor;
  console.log("🔧 ImageProcessor: Made globally accessible as window.imageProcessor");
});
