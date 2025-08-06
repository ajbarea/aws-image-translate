import { BaseComponent } from "./BaseComponent.js";

/**
 * Profile settings component for account linking and user settings
 * Can be used both as a standalone component and as a modal
 */
export class ProfileComponent extends BaseComponent {
  constructor(containerId, authManager, options = {}) {
    super(containerId, options);
    this.auth = authManager;
    this.currentUser = null;
    this.isGoogleLinked = false;
    this.isModal = options.isModal || false; // Flag to indicate modal mode
  }

  async onInit() {
    // Load current user information
    await this.loadUserInfo();

    // Render the profile interface
    this.renderProfileInterface();
  }

  async loadUserInfo() {
    try {
      this.currentUser = await this.auth.getCurrentUser();

      // Check if Google account is already linked by examining the identities array
      const identities = this.currentUser.identities || [];
      this.isGoogleLinked = identities.some(id => id.providerName === "Google");

      console.log("👤 ProfileComponent: User info loaded:", {
        username: this.currentUser.username,
        email: this.currentUser.attributes?.email,
        googleLinked: this.isGoogleLinked,
        identities: identities,
        identitiesCount: identities.length
      });
    } catch (_error) {
      console.log("ℹ️ ProfileComponent: No user info to load; user is not authenticated.");
    }
  }



  renderProfileInterface() {
    if (!this.container) {return;}

    const headerTitle = this.isModal ? "Account Settings" : "Profile Settings";

    this.container.innerHTML = `
      <div class="profile-container">
        <div class="profile-header">
          <h2>${headerTitle}</h2>
          <button id="close-profile-btn" class="close-button" aria-label="Close ${headerTitle}">×</button>
        </div>
        
        <div class="profile-content">
          <div class="profile-section">
            <h3>Account Information</h3>
            <div class="profile-info">
              <div class="info-item">
                <label>Email:</label>
                <span>${this.currentUser?.attributes?.email || "Not available"}</span>
              </div>
              <div class="info-item">
                <label>Username:</label>
                <span>${this.currentUser?.username || "Not available"}</span>
              </div>
            </div>
          </div>

          <div class="profile-section">
            <h3>Account Linking</h3>
            <div class="account-linking">
              <div class="linking-option">
                <div class="provider-info">
                  <div class="provider-logo google-logo"></div>
                  <div class="provider-details">
                    <h4>Google Account</h4>
                    <p class="provider-status">
                      ${this.isGoogleLinked ?
    '<span class="status-linked">✓ Linked</span>' :
    '<span class="status-not-linked">Not linked</span>'
}
                    </p>
                  </div>
                </div>
                <div class="provider-actions">
                  ${this.isGoogleLinked ? `
                    <button id="unlink-google-btn" class="btn-secondary">
                      Unlink Google Account
                    </button>
                  ` : `
                    <button id="link-google-btn" class="btn-primary">
                      Link Google Account
                    </button>
                  `}
                </div>
              </div>
            </div>
            
            <div class="linking-info">
              <p class="info-text">
                ${this.isGoogleLinked ?
    "You can sign in using either your email/password or Google account." :
    "Link your Google account to sign in with Google in addition to your email/password."
}
              </p>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  setupEventListeners() {
    // Close profile button
    this.addEventListener(
      this.container,
      "click",
      this.handleButtonClick.bind(this)
    );

    // Listen for successful account linking
    this.on("profile:googleLinked", this.handleGoogleLinked.bind(this));
    this.on("profile:googleUnlinked", this.handleGoogleUnlinked.bind(this));
  }

  handleButtonClick(e) {
    const target = e.target;

    if (target.matches("#close-profile-btn")) {
      this.closeProfile();
    } else if (target.matches("#link-google-btn")) {
      this.linkGoogleAccount();
    } else if (target.matches("#unlink-google-btn")) {
      this.unlinkGoogleAccount();
    }
  }

  async linkGoogleAccount() {
    try {
      console.log("🔗 ProfileComponent: Initiating Google account linking...");

      // Show loading state
      const linkBtn = this.querySelector("#link-google-btn");
      const originalText = linkBtn.textContent;
      linkBtn.textContent = "Linking...";
      linkBtn.disabled = true;

      // Validate that user is authenticated
      if (!this.currentUser) {
        throw new Error("User not authenticated");
      }

      // Check if Google SSO is available
      if (!this.auth.isGoogleSSOAvailable()) {
        throw new Error("Google SSO is not configured");
      }

      // Pre-validate user email exists
      if (!this.currentUser.attributes?.email) {
        throw new Error("Your account must have a verified email address to link with Google");
      }

      // Check if user is already linked (this should have been caught earlier)
      if (this.isGoogleLinked) {
        console.log("✅ ProfileComponent: User already has Google account linked");
        this.showSuccess("Your Google account is already linked!");
        linkBtn.textContent = originalText;
        linkBtn.disabled = false;
        return;
      }

      // Show confirmation dialog with email validation info
      const userEmail = this.currentUser.attributes.email;
      const confirmed = confirm(
        "You are about to link your Google account to this account.\n\n" +
        `Important: Your Google account email must match your current account email (${userEmail}).\n\n` +
        "Do you want to continue?"
      );

      if (!confirmed) {
        console.log("🔗 ProfileComponent: Account linking cancelled by user");
        // Reset button state
        linkBtn.textContent = originalText;
        linkBtn.disabled = false;
        return;
      }

      // Generate state parameter for linking
      const state = this.auth.generateRandomState();
      sessionStorage.setItem("oauth_state", state);
      sessionStorage.setItem("oauth_action", "link_account");

      // Construct linking URL
      const linkingUrl = `${this.auth.config.cognitoDomainUrl}/oauth2/authorize?` +
        "identity_provider=Google&" +
        `redirect_uri=${encodeURIComponent(`${window.location.origin  }/`)}&` +
        "response_type=code&" +
        `client_id=${this.auth.config.userPoolWebClientId}&` +
        "scope=openid%20profile%20email&" +
        `state=${state}`;

      console.log("🔗 ProfileComponent: Redirecting to Google for account linking");
      window.location.href = linkingUrl;

    } catch (error) {
      console.error("❌ ProfileComponent: Failed to initiate Google account linking:", error);
      this.showError(`Failed to link Google account: ${  error.message}`);

      // Reset button state
      const linkBtn = this.querySelector("#link-google-btn");
      if (linkBtn) {
        linkBtn.textContent = "Link Google Account";
        linkBtn.disabled = false;
      }
    }
  }

  async unlinkGoogleAccount() {
    try {
      console.log("🔗 ProfileComponent: Initiating Google account unlinking...");

      // Show loading state
      const unlinkBtn = this.querySelector("#unlink-google-btn");
      const originalText = unlinkBtn.textContent;
      unlinkBtn.textContent = "Checking...";
      unlinkBtn.disabled = true;

      // First, try to unlink to see if password is required
      try {
        const result = await this.auth.unlinkGoogleAccount();

        if (result.success) {
          // Success - refresh and update UI
          await this.loadUserInfo();
          this.renderProfileInterface();
          this.setupEventListeners();
          this.showSuccess("Google account unlinked successfully");
          this.emit("profile:googleUnlinked", { userId: this.currentUser.username });
          console.log("✅ ProfileComponent: Google account unlinked successfully");
          return;
        }
      } catch (error) {
        // Check if this is a password required error
        if (error.message.includes("428") || error.message.includes("password")) {
          console.log("🔐 ProfileComponent: Password required for unlinking");

          // Reset button state
          unlinkBtn.textContent = originalText;
          unlinkBtn.disabled = false;

          // Show password setup modal
          this.showPasswordSetupModal();
          return;
        }

        // Other errors - rethrow to be handled below
        throw error;
      }

    } catch (error) {
      console.error("❌ ProfileComponent: Failed to unlink Google account:", error);

      // Provide user-friendly error messages
      let errorMessage = "Failed to unlink Google account";

      if (error.message.includes("No Google account is currently linked")) {
        errorMessage = "No Google account is currently linked to this user";
        // Refresh user info in case the state is out of sync
        await this.loadUserInfo();
        this.renderProfileInterface();
        this.setupEventListeners();
      } else if (error.message.includes("Authentication")) {
        errorMessage = "Authentication error. Please sign in again.";
      } else if (error.message.includes("Network") || error.message.includes("fetch")) {
        errorMessage = "Network error. Please check your connection and try again.";
      } else {
        errorMessage = error.message || errorMessage;
      }

      this.showError(errorMessage);

      // Reset button state
      const unlinkBtn = this.querySelector("#unlink-google-btn");
      if (unlinkBtn) {
        unlinkBtn.textContent = "Unlink Google Account";
        unlinkBtn.disabled = false;
      }
    }
  }

  showPasswordSetupModal() {
    console.log("🔐 ProfileComponent: Showing password setup modal");

    // Create modal overlay
    const modalOverlay = document.createElement("div");
    modalOverlay.className = "password-setup-modal-overlay";
    modalOverlay.innerHTML = `
      <div class="password-setup-modal">
        <div class="modal-header">
          <h3>Set Up Password</h3>
          <button id="closePasswordModal" class="close-button" aria-label="Close">×</button>
        </div>
        <div class="modal-content">
          <p class="modal-message">
            To unlink your Google account, you must first set up a password to ensure you can still access your account.
          </p>
          <form id="passwordSetupForm">
            <div class="form-group">
              <label for="newPassword">New Password:</label>
              <input type="password" id="newPassword" required 
                     placeholder="Enter a secure password"
                     minlength="8">
              <small class="password-requirements">
                Password must be at least 8 characters with uppercase, lowercase, and numbers
              </small>
            </div>
            <div class="form-group">
              <label for="confirmPassword">Confirm Password:</label>
              <input type="password" id="confirmPassword" required 
                     placeholder="Confirm your password">
            </div>
            <div class="form-actions">
              <button type="button" id="cancelPasswordSetup" class="btn-secondary">
                Cancel
              </button>
              <button type="submit" id="set-password-btn" class="btn-primary">
                Set Password
              </button>
            </div>
          </form>
        </div>
      </div>
    `;

    // Add to page
    document.body.appendChild(modalOverlay);

    // Set up event listeners
    const closeModal = () => {
      document.body.removeChild(modalOverlay);
    };

    modalOverlay.querySelector("#closePasswordModal").addEventListener("click", closeModal);
    modalOverlay.querySelector("#cancelPasswordSetup").addEventListener("click", closeModal);

    // Close on overlay click
    modalOverlay.addEventListener("click", (e) => {
      if (e.target === modalOverlay) {
        closeModal();
      }
    });

    // Handle form submission
    modalOverlay.querySelector("#passwordSetupForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      await this.handlePasswordSetup(modalOverlay, closeModal);
    });

    // Focus on password field
    modalOverlay.querySelector("#newPassword").focus();
  }

  async handlePasswordSetup(modalOverlay, closeModal) {
    const newPassword = modalOverlay.querySelector("#newPassword").value;
    const confirmPassword = modalOverlay.querySelector("#confirmPassword").value;
    const setPasswordBtn = modalOverlay.querySelector("#set-password-btn");
    const originalBtnText = setPasswordBtn.textContent;

    try {
      // Validate passwords match
      if (newPassword !== confirmPassword) {
        this.showModalError(modalOverlay, "Passwords do not match");
        return;
      }

      // Validate password strength (basic client-side validation)
      const passwordError = this.auth.validatePassword(newPassword);
      if (passwordError) {
        this.showModalError(modalOverlay, passwordError);
        return;
      }

      // Show loading state
      setPasswordBtn.textContent = "Setting Password...";
      setPasswordBtn.disabled = true;

      // Set the password
      const result = await this.auth.setUserPassword(newPassword);

      if (result.success) {
        console.log("✅ ProfileComponent: Password set successfully");

        // Close modal
        closeModal();

        // Show success message
        this.showSuccess("Password set successfully! You can now unlink your Google account.");

        // Now show confirmation for unlinking
        setTimeout(() => {
          this.confirmAndUnlinkGoogle();
        }, 1000);

      } else {
        throw new Error(result.message || "Failed to set password");
      }

    } catch (error) {
      console.error("❌ ProfileComponent: Failed to set password:", error);

      let errorMessage = "Failed to set password";
      if (error.message.includes("Password does not meet requirements")) {
        errorMessage = "Password does not meet security requirements";
      } else if (error.message.includes("Authentication")) {
        errorMessage = "Authentication error. Please sign in again.";
      } else {
        errorMessage = error.message || errorMessage;
      }

      this.showModalError(modalOverlay, errorMessage);

      // Reset button state
      setPasswordBtn.textContent = originalBtnText;
      setPasswordBtn.disabled = false;
    }
  }

  showModalError(modalOverlay, message) {
    // Remove existing error messages
    const existingErrors = modalOverlay.querySelectorAll(".modal-error");
    existingErrors.forEach(error => error.remove());

    // Create new error message
    const errorDiv = document.createElement("div");
    errorDiv.className = "modal-error";
    errorDiv.textContent = message;

    // Insert after the modal message
    const modalContent = modalOverlay.querySelector(".modal-content");
    const modalMessage = modalOverlay.querySelector(".modal-message");
    modalContent.insertBefore(errorDiv, modalMessage.nextSibling);
  }

  async confirmAndUnlinkGoogle() {
    const confirmed = confirm(
      "Your password has been set up successfully. " +
      "Are you sure you want to unlink your Google account? " +
      "You will still be able to sign in with your email and password."
    );

    if (!confirmed) {
      console.log("🔗 ProfileComponent: Google account unlinking cancelled by user after password setup");
      return;
    }

    // Show loading state
    const unlinkBtn = this.querySelector("#unlink-google-btn");
    let originalText = "";
    if (unlinkBtn) {
      originalText = unlinkBtn.textContent;
      unlinkBtn.textContent = "Unlinking...";
      unlinkBtn.disabled = true;
    }

    try {
      // Now unlink should work since password is set
      const result = await this.auth.unlinkGoogleAccount();

      if (result.success) {
        // Refresh user info to get updated identities
        await this.loadUserInfo();

        // Update UI
        this.renderProfileInterface();
        this.setupEventListeners();

        this.showSuccess("Google account unlinked successfully! You can now sign in with your email and password.");
        this.emit("profile:googleUnlinked", { userId: this.currentUser.username });

        console.log("✅ ProfileComponent: Google account unlinked successfully after password setup");
      } else {
        throw new Error(result.message || "Failed to unlink Google account");
      }

    } catch (error) {
      console.error("❌ ProfileComponent: Failed to unlink Google account after password setup:", error);
      this.showError(`Failed to unlink Google account: ${  error.message || "Unknown error"}`);

      // Reset button state
      const unlinkBtn = this.querySelector("#unlink-google-btn");
      if (unlinkBtn) {
        unlinkBtn.textContent = originalText || "Unlink Google Account";
        unlinkBtn.disabled = false;
      }
    }
  }



  handleGoogleLinked(_event) {
    console.log("🎉 ProfileComponent: Google account linked successfully");
    this.isGoogleLinked = true;
    this.renderProfileInterface();
    this.setupEventListeners();
    this.showSuccess("Google account linked successfully! You can now sign in with Google.");
  }

  handleGoogleUnlinked(_event) {
    console.log("🎉 ProfileComponent: Google account unlinked successfully");
    this.isGoogleLinked = false;
    this.renderProfileInterface();
    this.setupEventListeners();
  }

  closeProfile() {
    console.log("🚪 ProfileComponent: Closing profile");
    if (this.isModal) {
      this.emit("settings:closed");
    } else {
      this.emit("profile:closed");
    }
    this.hide();
  }

  async refresh() {
    console.log("🔄 ProfileComponent: Refreshing profile data");
    await this.loadUserInfo();
    this.renderProfileInterface();
    this.setupEventListeners();
  }

  show() {
    super.show();
    this.refresh(); // Refresh data when showing
  }

  showSuccess(message) {
    // Create or update success message
    this.showMessage(message, "success");
  }

  showError(message) {
    // Create or update error message
    this.showMessage(message, "error");
  }

  showMessage(message, type) {
    // Remove existing messages
    const existingMessages = this.container.querySelectorAll(".profile-message");
    existingMessages.forEach(msg => msg.remove());

    // Create new message
    const messageDiv = document.createElement("div");
    messageDiv.className = `profile-message profile-message-${type}`;
    messageDiv.textContent = message;

    // Insert at top of profile content
    const profileContent = this.container.querySelector(".profile-content");
    if (profileContent) {
      profileContent.insertBefore(messageDiv, profileContent.firstChild);
    }

    // Auto-hide after 5 seconds
    setTimeout(() => {
      if (messageDiv.parentNode) {
        messageDiv.remove();
      }
    }, 5000);
  }
}
