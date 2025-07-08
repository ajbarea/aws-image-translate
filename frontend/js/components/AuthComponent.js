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

    // Show login form by default
    this.showLoginForm();

    // Ensure other forms are hidden initially
    this.registerFormContainer.classList.add("hidden");
    this.confirmationFormContainer.classList.add("hidden");
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

    if (target.matches("#goToRegisterBtn")) {
      this.showRegisterForm();
    } else if (target.matches("#backToLoginFromRegister")) {
      this.showLoginForm();
    } else if (target.matches("#resendCodeBtn")) {
      this.handleResendConfirmationCode();
    } else if (target.matches("#backToLoginBtn")) {
      this.showLoginForm();
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
      this.showError(error.message || "Registration failed. Please try again.");
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

    const resendBtn = this.querySelector("#resendCodeBtn");
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
}
