import { BaseComponent } from "./BaseComponent.js";

/**
 * Authentication component handling login, registration, and email confirmation
 */
export class AuthComponent extends BaseComponent {
  constructor(containerId, authManager, options = {}) {
    super(containerId, options);
    this.auth = authManager;
    this.currentForm = "login"; // 'login', 'register', 'confirmation'
    this.pendingConfirmationEmail = null;
  }

  async onInit() {
    // Cache form containers
    this.loginFormContainer = this.querySelector("#loginFormContainer");
    this.registerFormContainer = this.querySelector("#registerFormContainer");
    this.confirmationFormContainer = this.querySelector(
      "#confirmationFormContainer"
    );

    if (
      !this.loginFormContainer ||
      !this.registerFormContainer ||
      !this.confirmationFormContainer
    ) {
      throw new Error("Auth form containers not found");
    }

    // Configure Google OAuth button visibility
    this.configureGoogleOAuthButton();

    // Show login form by default
    this.showLoginForm();

    // Ensure other forms are hidden initially
    this.registerFormContainer.classList.add("hidden");
    this.confirmationFormContainer.classList.add("hidden");
  }

  configureGoogleOAuthButton() {
    const googleAuthBtn = this.querySelector("#google-auth-btn");
    const oauthDivider = this.querySelector(".oauth-divider");

    if (googleAuthBtn && oauthDivider) {
      // Check if Google OAuth is available
      if (!this.auth.isGoogleSSOAvailable()) {
        // Hide Google button and divider when OAuth is not configured
        googleAuthBtn.style.display = "none";
        oauthDivider.style.display = "none";
        console.log("AuthComponent: Google OAuth not configured, hiding Google sign-in button");
      } else {
        // Ensure button and divider are visible when OAuth is configured
        googleAuthBtn.style.display = "block";
        oauthDivider.style.display = "flex";
        console.log("AuthComponent: Google OAuth configured, showing Google sign-in button");
      }
    }
  }

  setupEventListeners() {
    // Form submissions
    this.addEventListener(
      this.container,
      "submit",
      this.handleFormSubmit.bind(this)
    );

    // Button clicks
    this.addEventListener(
      this.container,
      "click",
      this.handleButtonClick.bind(this)
    );
  }

  async handleFormSubmit(e) {
    e.preventDefault();
    const form = e.target;

    if (form.matches("#loginForm")) {
      await this.handleLogin(form);
    } else if (form.matches("#registerForm")) {
      await this.handleRegistration(form);
    } else if (form.matches("#confirmationForm")) {
      await this.handleEmailConfirmation(form);
    }
  }

  handleButtonClick(e) {
    const target = e.target;

    if (target.matches("#go-to-register-btn")) {
      this.showRegisterForm();
    } else if (target.matches("#backToLoginFromRegister")) {
      this.showLoginForm();
    } else if (target.matches("#resend-code-btn")) {
      this.handleResendConfirmationCode();
    } else if (target.matches("#back-to-login-btn")) {
      this.showLoginForm();
    } else if (target.matches("#google-auth-btn")) {
      this.handleGoogleAuth();
    }
  }

  async handleLogin(form) {
    const usernameInput = form.querySelector("#username");
    const passwordInput = form.querySelector("#password");
    const submitButton = form.querySelector('button[type="submit"]');

    if (!usernameInput?.value || !passwordInput?.value) {
      this.showError("Please enter both email and password");
      return;
    }

    const originalButtonText = submitButton.textContent;
    submitButton.textContent = "Signing in...";
    submitButton.disabled = true;

    try {
      await this.auth.signIn(usernameInput.value, passwordInput.value);

      // Get user info for the event
      const userInfo = await this.auth.getCurrentUser();

      // Emit success event
      this.emit("auth:loginSuccess", { userInfo });

      // Clear form
      form.reset();
    } catch (error) {
      console.error("Login failed:", error);

      if (error.originalError?.code === "UserNotConfirmedException") {
        this.showConfirmationForm(usernameInput.value);
        this.showError(
          "Please confirm your email address. We've shown the confirmation form below."
        );
      } else {
        this.showError(error.message || "Login failed. Please try again.");
      }
    } finally {
      submitButton.textContent = originalButtonText;
      submitButton.disabled = false;
    }
  }

  async handleRegistration(form) {
    const emailInput = form.querySelector("#registerEmail");
    const passwordInput = form.querySelector("#registerPassword");
    const confirmPasswordInput = form.querySelector("#confirmPassword");
    const submitButton = form.querySelector('button[type="submit"]');

    if (
      !emailInput?.value ||
      !passwordInput?.value ||
      !confirmPasswordInput?.value
    ) {
      this.showError("Please fill in all fields");
      return;
    }

    if (passwordInput.value !== confirmPasswordInput.value) {
      this.showError("Passwords do not match");
      return;
    }

    const originalButtonText = submitButton.textContent;
    submitButton.textContent = "Creating Account...";
    submitButton.disabled = true;

    try {
      const result = await this.auth.signUp(
        emailInput.value,
        passwordInput.value
      );

      if (result.userConfirmed) {
        this.showSuccess("Account created successfully! You can now log in.");
        this.showLoginForm();
      } else {
        this.showConfirmationForm(emailInput.value);
        this.showSuccess(
          `Account created! Please check your email (${emailInput.value}) for a confirmation code.`
        );
      }

      form.reset();
    } catch (error) {
      console.error("Registration failed:", error);

      // Check if this is an existing account
      if (
        error.originalError &&
        error.originalError.code === "UsernameExistsException"
      ) {
        // Try to determine if the account is confirmed or not
        await this.handleExistingUser(emailInput.value);
      } else if (
        error.message &&
        error.message.includes("already exists and is verified")
      ) {
        // Handle the new Lambda error message for verified users
        this.showLoginForm();
        this.showError(
          "An account with this email already exists and is verified. Please use the login form to sign in."
        );
      } else {
        this.showError(
          error.message || "Registration failed. Please try again."
        );
      }
    } finally {
      submitButton.textContent = originalButtonText;
      submitButton.disabled = false;
    }
  }

  async handleEmailConfirmation(form) {
    const emailInput = form.querySelector("#confirmationEmail");
    const confirmationCodeInput = form.querySelector("#confirmationCode");
    const submitButton = form.querySelector('button[type="submit"]');

    if (!emailInput?.value || !confirmationCodeInput?.value) {
      this.showError("Please enter the confirmation code");
      return;
    }

    if (
      confirmationCodeInput.value.length !== 6 ||
      !/^\d{6}$/.test(confirmationCodeInput.value)
    ) {
      this.showError("Confirmation code must be 6 digits");
      return;
    }

    const originalButtonText = submitButton.textContent;
    submitButton.textContent = "Confirming...";
    submitButton.disabled = true;

    try {
      await this.auth.confirmSignUp(
        emailInput.value,
        confirmationCodeInput.value
      );
      this.showSuccess("Email confirmed successfully! You can now log in.");
      this.showLoginForm();
      confirmationCodeInput.value = "";
    } catch (error) {
      console.error("Confirmation failed:", error);
      this.showError(error.message || "Confirmation failed. Please try again.");
    } finally {
      submitButton.textContent = originalButtonText;
      submitButton.disabled = false;
    }
  }

  async handleResendConfirmationCode() {
    const emailInput = this.querySelector("#confirmationEmail");
    if (!emailInput?.value) {
      this.showError("Please enter your email address");
      return;
    }

    const resendBtn = this.querySelector("#resend-code-btn");
    const originalText = resendBtn.textContent;

    try {
      resendBtn.textContent = "Sending...";
      resendBtn.disabled = true;

      await this.auth.resendConfirmationCode(emailInput.value);
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
      console.error("Failed to resend confirmation code:", error);
      this.showError("Failed to send confirmation code. Please try again.");
      resendBtn.textContent = originalText;
      resendBtn.disabled = false;
    }
  }

  async handleExistingUser(email) {
    try {
      // Check user status directly
      const userStatus = await this.auth.checkUserStatus(email);
      console.log("User status check completed");

      if (userStatus.status === "CONFIRMED" && userStatus.verified) {
        // User is already confirmed - direct them to login
        this.showLoginForm();
        this.showError(
          "An account with this email already exists and is verified. Please use the login form to sign in."
        );
      } else if (userStatus.status === "UNCONFIRMED") {
        // User exists but not confirmed - try to resend confirmation code
        try {
          await this.auth.resendConfirmationCode(email);
          this.showConfirmationForm(email);
          this.showSuccess(
            `This account already exists but is not yet confirmed. We've sent a confirmation code to your email (${email}). Please enter it below to complete your registration.`
          );
        } catch (resendError) {
          console.log("Resend failed:", resendError);
          // If resend fails, still show confirmation form as fallback
          this.showConfirmationForm(email);
          this.showSuccess(
            `This account already exists. Please check your email (${email}) for a confirmation code, or click "Resend Code" below.`
          );
        }
      } else {
        // Unknown status - show confirmation form as fallback
        this.showConfirmationForm(email);
        this.showSuccess(
          `This account already exists. Please check your email (${email}) for a confirmation code, or click "Resend Code" below.`
        );
      }
    } catch (error) {
      console.error("Error checking user status:", error);
      // Fallback to previous logic if status check fails
      try {
        await this.auth.resendConfirmationCode(email);
        this.showConfirmationForm(email);
        this.showSuccess(
          `This account already exists but is not yet confirmed. We've sent a confirmation code to your email (${email}). Please enter it below to complete your registration.`
        );
      } catch (resendError) {
        console.log("Resend confirmation code failed:", resendError);
        if (
          resendError.originalError?.code === "InvalidParameterException" ||
          resendError.originalError?.code === "NotAuthorizedException" ||
          resendError.message?.includes("already confirmed")
        ) {
          this.showLoginForm();
          this.showError(
            "An account with this email already exists and is verified. Please use the login form to sign in."
          );
        } else {
          this.showConfirmationForm(email);
          this.showSuccess(
            `This account already exists. Please check your email (${email}) for a confirmation code, or click "Resend Code" below.`
          );
        }
      }
    }
  }

  showLoginForm() {
    this.currentForm = "login";
    this.loginFormContainer.classList.remove("hidden");
    this.registerFormContainer.classList.add("hidden");
    this.confirmationFormContainer.classList.add("hidden");
    this.clearMessages();
  }

  showRegisterForm() {
    this.currentForm = "register";
    this.loginFormContainer.classList.add("hidden");
    this.registerFormContainer.classList.remove("hidden");
    this.confirmationFormContainer.classList.add("hidden");
    this.clearMessages();
  }

  showConfirmationForm(email) {
    this.currentForm = "confirmation";
    this.pendingConfirmationEmail = email;
    this.loginFormContainer.classList.add("hidden");
    this.registerFormContainer.classList.add("hidden");
    this.confirmationFormContainer.classList.remove("hidden");

    // Pre-fill email
    const emailInput = this.querySelector("#confirmationEmail");
    if (emailInput) {
      emailInput.value = email;
    }

    // Focus on confirmation code input
    const codeInput = this.querySelector("#confirmationCode");
    if (codeInput) {
      codeInput.focus();
    }

    this.clearMessages();
  }

  getCurrentForm() {
    return this.currentForm;
  }

  getPendingConfirmationEmail() {
    return this.pendingConfirmationEmail;
  }

  async handleGoogleAuth() {
    try {
      // Check if Google OAuth is available before attempting sign-in
      if (!this.auth.isGoogleSSOAvailable()) {
        this.showError("Google sign-in is not configured. Please use email/password authentication.");
        return;
      }

      this.showLoading("Redirecting to Google...");
      await this.auth.signInWithGoogle();
    } catch (error) {
      console.error("Google authentication failed:", error);
      this.showError("Failed to authenticate with Google. Please try again.");
    }
  }
}
