import { AWS_CONFIG } from "./config.js";
import { AuthManager } from "./auth.js";

class ImageProcessor {
  constructor() {
    console.log("🚀 ImageProcessor: Initializing application...");
    this.auth = new AuthManager(AWS_CONFIG);
    this.s3 = null; // Initialize after authentication
    this.uploadQueue = [];
    this.isAuthenticated = false;

    this.setupUI();
    this.setupAuth();
    console.log("✅ ImageProcessor: Application initialized");
  }

  async initialize() {
    await this.checkInitialAuthState();
  }

  async checkInitialAuthState() {
    console.log("🔍 ImageProcessor: Checking initial authentication state...");
    try {
      const isAuth = await this.auth.isAuthenticated();
      if (isAuth) {
        console.log("✅ ImageProcessor: User is already authenticated");
        await this.handleSuccessfulAuth();

        // Get user information and add to UI for existing session
        try {
          const userInfo = await this.auth.getCurrentUser();
          this.addUserInfoToUI(userInfo);
          console.log(
            "✅ ImageProcessor: User info added to UI for existing session"
          );
        } catch (userInfoError) {
          console.warn(
            "⚠️ ImageProcessor: Could not get user info for existing session:",
            userInfoError
          );
        }
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
  }

  async handleSuccessfulAuth() {
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

    // Show success message
    this.showSuccess(
      "✅ Login successful! You can now upload images for translation."
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
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding: 10px; background: #ffffff; border: 1px solid #ddd; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
        <div style="color: #000000 !important; font-weight: bold;">
          Welcome, ${userInfo.attributes.email || userInfo.username}!
        </div>
        <button id="logoutBtn" style="background: #dc3545; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; transition: background-color 0.2s; font-weight: bold;" onmouseover="this.style.backgroundColor='#c82333'" onmouseout="this.style.backgroundColor='#dc3545'">
          Logout
        </button>
      </div>
    `;

    this.appSection.insertBefore(userInfoDiv, this.appSection.firstChild);

    // Add logout functionality
    document.getElementById("logoutBtn").addEventListener("click", () => {
      this.handleLogout();
    });
  }

  async handleLogout() {
    console.log("🚪 ImageProcessor: Handling logout");
    try {
      // Sign out from Cognito
      await this.auth.signOut();

      // Clear application state
      this.isAuthenticated = false;
      this.s3 = null;
      this.uploadQueue = [];

      // Remove user info from UI
      const existingUserInfo = document.getElementById("userInfo");
      if (existingUserInfo) {
        existingUserInfo.remove();
        console.log("✅ ImageProcessor: User info removed from UI");
      }

      // Clear UI state
      this.clearUploadQueue();
      this.clearSuccess();
      this.clearError();

      // Show login section
      this.showLoginSection();

      // Show success message to confirm logout
      this.showSuccess("You have been successfully logged out.");

      console.log("✅ ImageProcessor: Logout successful");
    } catch (error) {
      console.error("❌ ImageProcessor: Logout error:", error);
      this.showError("Logout failed. Please try again.");
    }
  }

  clearUploadQueue() {
    this.uploadQueue = [];
    this.uploadList.innerHTML = "";
    this.processBtn.style.display = "none";
    this.resultsDiv.style.display = "none";
    this.resultsDiv.innerHTML = "";
  }

  setupAuth() {
    console.log("🔐 ImageProcessor: Setting up authentication handlers...");

    // Cache DOM elements
    const loginFormContainer = document.getElementById("loginFormContainer");
    const registerFormContainer = document.getElementById(
      "registerFormContainer"
    );
    const confirmationFormContainer = document.getElementById(
      "confirmationFormContainer"
    );
    const loginForm = document.getElementById("loginForm");
    const registerForm = document.getElementById("registerForm");
    const confirmationForm = document.getElementById("confirmationForm");
    const goToRegisterBtn = document.getElementById("goToRegisterBtn");
    const backToLoginFromRegister = document.getElementById(
      "backToLoginFromRegister"
    );

    if (!loginForm || !registerForm || !confirmationForm) {
      console.error("❌ ImageProcessor: Required form elements not found");
      return;
    }

    // Form navigation buttons
    goToRegisterBtn.addEventListener("click", () => {
      loginFormContainer.style.display = "none";
      registerFormContainer.style.display = "block";
      confirmationFormContainer.style.display = "none";
    });

    backToLoginFromRegister.addEventListener("click", () => {
      loginFormContainer.style.display = "block";
      registerFormContainer.style.display = "none";
      confirmationFormContainer.style.display = "none";
    });

    // Login form handler
    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      console.log("📝 ImageProcessor: Login form submitted");

      const username = document.getElementById("username").value;
      const password = document.getElementById("password").value;

      console.log("👤 ImageProcessor: Username from form:", username);
      console.log(
        "🔒 ImageProcessor: Password length from form:",
        password ? password.length : 0
      );

      await this.handleLogin(
        username,
        password,
        loginForm.querySelector('button[type="submit"]')
      );
    });

    // Registration form handler
    registerForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      console.log("📝 ImageProcessor: Registration form submitted");

      const email = document.getElementById("registerEmail").value;
      const password = document.getElementById("registerPassword").value;
      const confirmPassword = document.getElementById("confirmPassword").value;

      console.log("👤 ImageProcessor: Registration email:", email);
      console.log(
        "🔒 ImageProcessor: Password length:",
        password ? password.length : 0
      );

      await this.handleRegistration(
        email,
        password,
        confirmPassword,
        registerForm.querySelector('button[type="submit"]')
      );
    });

    // Confirmation form handler
    confirmationForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      console.log("📝 ImageProcessor: Confirmation form submitted");

      const email = document.getElementById("confirmationEmail").value;
      const confirmationCode =
        document.getElementById("confirmationCode").value;

      await this.handleEmailConfirmation(
        email,
        confirmationCode,
        confirmationForm.querySelector('button[type="submit"]')
      );
    });

    // Resend confirmation code handler
    document
      .getElementById("resendCodeBtn")
      .addEventListener("click", async () => {
        const email = document.getElementById("confirmationEmail").value;
        await this.handleResendConfirmationCode(email);
      });

    // Back to login handler
    document.getElementById("backToLoginBtn").addEventListener("click", () => {
      this.switchToLoginTab();
    });

    console.log("✅ ImageProcessor: Authentication handlers set up");
  }

  async handleLogin(username, password, submitButton) {
    // Validate inputs
    if (!username || !password) {
      this.showError("Please enter both email and password");
      return;
    }

    // Show loading state
    const originalButtonText = submitButton.textContent;
    submitButton.textContent = "Signing in...";
    submitButton.disabled = true;

    // Clear any previous errors
    this.clearError();

    try {
      console.log("🚀 ImageProcessor: Attempting login...");
      await this.auth.signIn(username, password);
      console.log("🎉 ImageProcessor: Login successful!");

      // Handle successful authentication
      await this.handleSuccessfulAuth();

      // Get user information and add to UI
      try {
        const userInfo = await this.auth.getCurrentUser();
        this.addUserInfoToUI(userInfo);
        console.log("✅ ImageProcessor: User info added to UI");
      } catch (userInfoError) {
        console.warn(
          "⚠️ ImageProcessor: Could not get user info:",
          userInfoError
        );
        // Continue without user info display
      }

      // Clear form
      document.getElementById("loginForm").reset();

      console.log("✅ ImageProcessor: Login process completed");
    } catch (error) {
      console.error("❌ ImageProcessor: Login failed:", error);

      // Check if it's an unconfirmed user error
      if (
        error.originalError &&
        error.originalError.code === "UserNotConfirmedException"
      ) {
        // Show confirmation form for unconfirmed users
        this.showConfirmationForm(username);
        this.showError(
          "Please confirm your email address. We've shown the confirmation form below."
        );
      } else {
        this.showError(error.message || "Login failed. Please try again.");
      }
    } finally {
      // Reset button state
      submitButton.textContent = originalButtonText;
      submitButton.disabled = false;
    }
  }

  async handleRegistration(email, password, confirmPassword, submitButton) {
    // Validate inputs
    if (!email || !password || !confirmPassword) {
      this.showError("Please fill in all fields");
      return;
    }

    if (password !== confirmPassword) {
      this.showError("Passwords do not match");
      return;
    }

    // Show loading state
    const originalButtonText = submitButton.textContent;
    submitButton.textContent = "Creating Account...";
    submitButton.disabled = true;

    // Clear any previous errors
    this.clearError();

    try {
      console.log("🚀 ImageProcessor: Attempting registration...");
      const result = await this.auth.signUp(email, password);
      console.log("🎉 ImageProcessor: Registration successful!");

      if (result.userConfirmed) {
        // User is automatically confirmed (unlikely with email verification)
        this.showSuccess("Account created successfully! You can now log in.");
        this.switchToLoginTab();
      } else {
        // User needs to confirm email - show confirmation form
        this.showConfirmationForm(email);
        this.showSuccess(
          `Account created! Please check your email (${email}) for a confirmation code.`
        );
      }

      // Clear the registration form
      document.getElementById("registerEmail").value = "";
      document.getElementById("registerPassword").value = "";
      document.getElementById("confirmPassword").value = "";

      console.log("✅ ImageProcessor: Registration process completed");
    } catch (error) {
      console.error("❌ ImageProcessor: Registration failed:", error);
      this.showError(error.message || "Registration failed. Please try again.");
    } finally {
      // Reset button state
      submitButton.textContent = originalButtonText;
      submitButton.disabled = false;
    }
  }

  showConfirmationForm(email) {
    console.log("📧 ImageProcessor: Showing confirmation form for:", email);

    // Hide other forms and show confirmation form
    document.getElementById("loginFormContainer").style.display = "none";
    document.getElementById("registerFormContainer").style.display = "none";
    document.getElementById("confirmationFormContainer").style.display =
      "block";

    // Pre-fill email
    document.getElementById("confirmationEmail").value = email;

    // Focus on confirmation code input
    document.getElementById("confirmationCode").focus();
  }

  async handleEmailConfirmation(email, confirmationCode, submitButton) {
    // Validate inputs
    if (!email || !confirmationCode) {
      this.showError("Please enter the confirmation code");
      return;
    }

    if (confirmationCode.length !== 6 || !/^\d{6}$/.test(confirmationCode)) {
      this.showError("Confirmation code must be 6 digits");
      return;
    }

    // Show loading state
    const originalButtonText = submitButton.textContent;
    submitButton.textContent = "Confirming...";
    submitButton.disabled = true;

    // Clear any previous errors
    this.clearError();

    try {
      console.log("🚀 ImageProcessor: Attempting email confirmation...");
      await this.auth.confirmSignUp(email, confirmationCode);
      console.log("🎉 ImageProcessor: Email confirmation successful!");

      // Show success message and switch to login
      this.showSuccess("Email confirmed successfully! You can now log in.");
      this.switchToLoginTab();

      // Clear the confirmation form
      document.getElementById("confirmationCode").value = "";

      console.log("✅ ImageProcessor: Confirmation process completed");
    } catch (error) {
      console.error("❌ ImageProcessor: Confirmation failed:", error);
      this.showError(error.message || "Confirmation failed. Please try again.");
    } finally {
      // Reset button state
      submitButton.textContent = originalButtonText;
      submitButton.disabled = false;
    }
  }

  async handleResendConfirmationCode(email) {
    const resendBtn = document.getElementById("resendCodeBtn");
    const originalText = resendBtn.textContent;

    try {
      resendBtn.textContent = "Sending...";
      resendBtn.disabled = true;

      console.log("📧 ImageProcessor: Resending confirmation code...");
      await this.auth.resendConfirmationCode(email);

      this.showSuccess("Confirmation code sent! Please check your email.");

      // Start countdown
      let countdown = 60;
      const countdownInterval = setInterval(() => {
        resendBtn.textContent = `Resend Code (${countdown}s)`;
        countdown--;

        if (countdown < 0) {
          clearInterval(countdownInterval);
          resendBtn.textContent = originalText;
          resendBtn.disabled = false;
        }
      }, 1000);
    } catch (error) {
      console.error(
        "❌ ImageProcessor: Failed to resend confirmation code:",
        error
      );
      this.showError("Failed to send confirmation code. Please try again.");
      resendBtn.textContent = originalText;
      resendBtn.disabled = false;
    }
  }

  switchToLoginTab() {
    // Show login form, hide others
    document.getElementById("loginFormContainer").style.display = "block";
    document.getElementById("registerFormContainer").style.display = "none";
    document.getElementById("confirmationFormContainer").style.display = "none";
  }

  showError(message) {
    console.error("🚨 ImageProcessor: Showing error:", message);

    // Remove existing error
    this.clearError();

    // Create error element
    const errorDiv = document.createElement("div");
    errorDiv.id = "loginError";
    errorDiv.style.cssText = `
      background: #f8d7da;
      color: #721c24;
      padding: 12px;
      border-radius: 4px;
      margin-bottom: 16px;
      border: 1px solid #f5c6cb;
    `;
    errorDiv.textContent = message;

    // Insert error before the form
    const loginForm = document.getElementById("loginForm");
    loginForm.parentNode.insertBefore(errorDiv, loginForm);
  }

  clearError() {
    const existingError = document.getElementById("loginError");
    if (existingError) {
      existingError.remove();
    }
  }

  showSuccess(message) {
    console.log("🎉 ImageProcessor: Showing success:", message);

    // Remove existing messages
    this.clearError();
    this.clearSuccess();

    // Create success element
    const successDiv = document.createElement("div");
    successDiv.id = "loginSuccess";
    successDiv.style.cssText = `
      background: #d4edda;
      color: #155724;
      padding: 12px;
      border-radius: 4px;
      margin-bottom: 16px;
      border: 1px solid #c3e6cb;
    `;
    successDiv.textContent = message;

    // Insert in the most appropriate location based on current view
    if (this.loginSection.style.display !== "none") {
      // If login section is visible, insert before it
      this.loginSection.parentNode.insertBefore(successDiv, this.loginSection);
    } else {
      // If app section is visible, insert before it
      this.appSection.parentNode.insertBefore(successDiv, this.appSection);
    }

    // Auto-hide after 5 seconds
    setTimeout(() => {
      this.clearSuccess();
    }, 5000);
  }

  clearSuccess() {
    const existingSuccess = document.getElementById("loginSuccess");
    if (existingSuccess) {
      existingSuccess.remove();
    }
  }

  setupUI() {
    // Cache DOM elements for performance
    this.loginSection = document.getElementById("loginSection");
    this.appSection = document.getElementById("appSection");
    this.dropZone = document.getElementById("dropZone");
    this.fileInput = document.getElementById("fileInput");
    this.uploadList = document.getElementById("uploadList");
    this.processBtn = document.getElementById("processBtn");
    this.resultsDiv = document.getElementById("results");
    this.targetLanguageSelect = document.getElementById("targetLanguage");

    // Setup event listeners
    this.setupDragAndDrop();
    this.setupFileInput();
    this.setupProcessButton();
    this.setupLanguageSelection();
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

  setupLanguageSelection() {
    if (this.targetLanguageSelect) {
      this.targetLanguageSelect.addEventListener("change", async (e) => {
        const selectedLanguage = e.target.value;
        console.log(`🌍 ImageProcessor: Language changed to: ${selectedLanguage}`);

        // Re-translate all existing results
        console.log("🔄 ImageProcessor: Re-translating all results to:", selectedLanguage);
        await this.retranslateAllResults(selectedLanguage);
      });
    }
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
      const result = e.target.result;
      const imageSrc = typeof result === "string" ? result : "";
      li.innerHTML = `
        <img src="${imageSrc}" alt="${item.file.name}">
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

  async retranslateAllResults(targetLanguage) {
    console.log("📝 ImageProcessor: Starting re-translation process...");

    // Find all completed items that have processing results
    const completedItems = this.uploadQueue.filter(item =>
      item.status === "complete" && item.processingResults
    );

    if (completedItems.length === 0) {
      console.log("📝 ImageProcessor: No processed items to re-translate");
      return;
    }

    console.log(`📝 ImageProcessor: Re-translating ${completedItems.length} items`);

    // Re-translate each item
    for (const item of completedItems) {
      await this.retranslateItem(item, targetLanguage);
    }
  }

  async retranslateItem(item, targetLanguage) {
    if (!item.processingResults || !item.processingResults.detectedText) {
      console.log(`📝 ImageProcessor: No detected text to translate for ${item.file.name}`);
      return;
    }

    try {
      console.log(`🔄 ImageProcessor: Re-translating ${item.file.name} to ${targetLanguage}`);

      // Call the translation API
      const response = await fetch(`${AWS_CONFIG.apiGatewayUrl}/translate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          text: item.processingResults.detectedText,
          sourceLanguage: item.processingResults.detectedLanguage || "auto",
          targetLanguage: targetLanguage,
        }),
      });

      if (!response.ok) {
        throw new Error(`Translation failed: ${response.status} ${response.statusText}`);
      }

      const translationResult = await response.json();
      console.log("✅ ImageProcessor: Translation result:", translationResult);

      // Update the item's processing results
      item.processingResults.translatedText = translationResult.translatedText;
      item.processingResults.targetLanguage = targetLanguage;

      // Update the UI
      this.updateResultDisplay(item);

    } catch (error) {
      console.error(`❌ ImageProcessor: Translation error for ${item.file.name}:`, error);
    }
  }

  updateResultDisplay(item) {
    // Find the existing result element and update it
    const resultElements = this.resultsDiv.querySelectorAll('.result-item');
    for (const resultElement of resultElements) {
      const title = resultElement.querySelector('h3');
      if (title && title.textContent === item.file.name) {
        // Remove the old result and add the new one
        resultElement.remove();
        this.showResults(item);
        break;
      }
    }
  }

  getLanguageName(languageCode) {
    const languageMap = {
      'en': 'English',
      'es': 'Spanish',
      'fr': 'French',
      'de': 'German',
      'it': 'Italian',
      'pt': 'Portuguese',
      'ru': 'Russian',
      'ja': 'Japanese',
      'ko': 'Korean',
      'zh': 'Chinese (Simplified)',
      'zh-TW': 'Chinese (Traditional)',
      'ar': 'Arabic',
      'hi': 'Hindi',
      'th': 'Thai',
      'vi': 'Vietnamese',
      'nl': 'Dutch',
      'pl': 'Polish',
      'tr': 'Turkish',
      'sv': 'Swedish',
      'da': 'Danish',
      'no': 'Norwegian',
      'fi': 'Finnish',
      'cs': 'Czech',
      'hu': 'Hungarian',
      'ro': 'Romanian',
      'bg': 'Bulgarian',
      'hr': 'Croatian',
      'sk': 'Slovak',
      'sl': 'Slovenian',
      'et': 'Estonian',
      'lv': 'Latvian',
      'lt': 'Lithuanian',
      'mt': 'Maltese',
      'ga': 'Irish',
      'cy': 'Welsh'
    };
    return languageMap[languageCode] || languageCode;
  }

  async processQueue() {
    for (const item of this.uploadQueue) {
      if (item.status === "pending") {
        await this.uploadAndProcess(item);
      }
    }
  }

  async uploadAndProcess(item) {
    // Check authentication before processing
    if (!this.isAuthenticated || !this.s3) {
      console.error("❌ ImageProcessor: Not authenticated for upload");
      const li = document.getElementById(item.id);
      const statusDiv = li.querySelector(".status");
      statusDiv.textContent = "Authentication Error";
      item.status = "error";
      return;
    }

    const li = document.getElementById(item.id);
    const statusDiv = li.querySelector(".status");
    const progressBar = li.querySelector(".progress-bar");

    try {
      // Update status to uploading
      statusDiv.textContent = "Uploading...";
      console.log(`📤 ImageProcessor: Uploading ${item.file.name} to S3...`);

      // Upload to S3 with proper error handling
      const params = {
        Bucket: AWS_CONFIG.bucketName,
        Key: `uploads/${Date.now()}-${item.file.name}`, // Add timestamp to avoid conflicts
        Body: item.file,
        ContentType: item.file.type,
        Metadata: {
          "original-name": item.file.name,
          "upload-time": new Date().toISOString(),
        },
      };

      console.log("📋 ImageProcessor: Upload parameters:", {
        Bucket: params.Bucket,
        Key: params.Key,
        ContentType: params.ContentType,
      });

      const upload = this.s3.upload(params);

      upload.on("httpUploadProgress", (progress) => {
        const percentage = ((progress.loaded / progress.total) * 100).toFixed(
          0
        );
        progressBar.style.width = `${percentage}%`;
        console.log(
          `📊 ImageProcessor: Upload progress for ${item.file.name}: ${percentage}%`
        );
      });

      const uploadResult = await upload.promise();
      console.log("✅ ImageProcessor: Upload successful:", uploadResult);

      // Update status to processing
      statusDiv.textContent = "Processing...";
      progressBar.style.width = "100%";

      // Call Lambda function to process the image
      await this.callLambdaProcessor(params.Key, item);

      // Update status to complete
      statusDiv.textContent = "Complete";
      item.status = "complete";
      item.s3Key = params.Key;
      item.s3Location = uploadResult.Location;

      console.log(
        `🎉 ImageProcessor: Successfully processed ${item.file.name}`
      );
    } catch (error) {
      console.error(
        `❌ ImageProcessor: Error processing ${item.file.name}:`,
        error
      );
      statusDiv.textContent = "Error";
      item.status = "error";
      item.error = error.message;

      // Show user-friendly error message
      this.showUploadError(item, error);
    }
  }

  async callLambdaProcessor(s3Key, item) {
    console.log(`🚀 ImageProcessor: Calling Lambda to process ${s3Key}`);

    try {
      // Get the selected target language
      const targetLanguage = this.targetLanguageSelect ? this.targetLanguageSelect.value : 'en';

      // Call the API Gateway endpoint
      const response = await fetch(`${AWS_CONFIG.apiGatewayUrl}/process`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          bucket: AWS_CONFIG.bucketName,
          key: s3Key,
          targetLanguage: targetLanguage
        }),
      });

      if (!response.ok) {
        // Get the actual error response
        let errorMessage = `Lambda processing failed: ${response.status} ${response.statusText}`;
        try {
          const errorBody = await response.text();
          console.error("❌ ImageProcessor: Lambda error response:", errorBody);
          errorMessage += ` - ${errorBody}`;
        } catch (e) {
          console.error("❌ ImageProcessor: Could not read error response body");
        }
        throw new Error(errorMessage);
      }

      const result = await response.json();
      console.log("✅ ImageProcessor: Lambda processing result:", result);

      // Store the processing results
      item.processingResults = result;

      // Show results in UI
      this.showResults(item);

      return result;
    } catch (error) {
      console.error("❌ ImageProcessor: Lambda processing error:", error);
      throw error;
    }
  }

  showUploadError(item, error) {
    const errorDiv = document.createElement("div");
    errorDiv.style.cssText = `
      background: #f8d7da;
      color: #721c24;
      padding: 8px;
      border-radius: 4px;
      margin-top: 8px;
      font-size: 12px;
    `;
    errorDiv.textContent = `Error: ${error.message}`;

    const li = document.getElementById(item.id);
    li.appendChild(errorDiv);
  }

  showResults(item) {
    console.log(`📊 ImageProcessor: Showing results for ${item.file.name}`);

    const result = document.createElement("div");
    result.className = "result-item";
    result.style.cssText = `
      border: 1px solid #ddd;
      padding: 16px;
      margin-bottom: 16px;
      border-radius: 8px;
      background: #f9f9f9;
    `;

    let resultHTML = `<h3>${item.file.name}</h3>`;

    if (item.processingResults) {
      const results =
        typeof item.processingResults === "string"
          ? JSON.parse(item.processingResults)
          : item.processingResults;

      if (results.detectedText) {
        resultHTML += `
          <div style="margin-bottom: 12px;">
            <strong>🔍 Detected Text:</strong>
            <div style="background: white; padding: 8px; border-radius: 4px; margin-top: 4px;">
              ${results.detectedText || "No text detected"}
            </div>
          </div>
        `;
      }

      if (results.detectedLanguage) {
        resultHTML += `
          <div style="margin-bottom: 12px;">
            <strong>🌍 Detected Language:</strong>
            <span style="background: #e3f2fd; padding: 2px 8px; border-radius: 12px;">
              ${results.detectedLanguage}
            </span>
          </div>
        `;
      }

      if (
        results.translatedText &&
        results.translatedText !== results.detectedText
      ) {
        const targetLang = results.targetLanguage || this.targetLanguageSelect?.value || 'en';
        const targetLangName = this.getLanguageName(targetLang);
        resultHTML += `
          <div style="margin-bottom: 12px;">
            <strong>🔄 Translation (${targetLangName}):</strong>
            <div style="background: white; padding: 8px; border-radius: 4px; margin-top: 4px; border-left: 4px solid #4caf50;">
              ${results.translatedText}
            </div>
          </div>
        `;
      }

      if (results.bucket && results.key) {
        resultHTML += `
          <div style="margin-top: 12px; font-size: 12px; color: #666;">
            📁 S3 Location: s3://${results.bucket}/${results.key}
          </div>
        `;
      }
    } else {
      resultHTML += `
        <p style="color: #666; font-style: italic;">
          Processing completed but no detailed results available.
        </p>
      `;
    }

    if (item.error) {
      resultHTML += `
        <div style="background: #ffebee; color: #c62828; padding: 8px; border-radius: 4px; margin-top: 8px;">
          ❌ Error: ${item.error}
        </div>
      `;
    }

    result.innerHTML = resultHTML;
    this.resultsDiv.appendChild(result);
  }
}

// Initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", async () => {
  const processor = new ImageProcessor();
  await processor.initialize();
});
