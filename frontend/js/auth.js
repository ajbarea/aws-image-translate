class AuthManager {
  constructor(config) {
    this.config = config;
    this.cognitoUser = null;
    this.idToken = null;
    this.logger = this._createLogger();
    this.logger.info("AuthManager initialized", { hasConfig: !!config });
    this.setupCognito();
    this.restoreSession();

    // Set up periodic cleanup of expired sessions (every 5 minutes)
    setInterval(() => {
      this.cleanupExpiredSessions();
    }, 5 * 60 * 1000);
  }

  // Create a structured logger with different levels
  _createLogger() {
    const isDevelopment = window.location.hostname === "localhost" ||
      window.location.hostname === "127.0.0.1" ||
      window.location.search.includes("debug=true");

    const logLevel = isDevelopment ? "debug" : "warn";

    const levels = {
      debug: 0,
      info: 1,
      warn: 2,
      error: 3
    };

    const logger = {};

    Object.keys(levels).forEach(level => {
      logger[level] = (message, data = {}) => {
        if (levels[level] >= levels[logLevel]) {
          const timestamp = new Date().toISOString();
          const prefix = `[${timestamp}] AuthManager:${level.toUpperCase()}`;

          if (data && Object.keys(data).length > 0) {
            console[level === "debug" ? "log" : level](`${prefix} ${message}`, data);
          } else {
            console[level === "debug" ? "log" : level](`${prefix} ${message}`);
          }
        }
      };
    });

    return logger;
  }

  setupCognito() {
    this.logger.debug("Setting up Cognito user pool", {
      userPoolId: `${this.config.userPoolId?.substring(0, 10)}...`,
      clientId: `${this.config.userPoolWebClientId?.substring(0, 10)}...`
    });

    const poolData = {
      UserPoolId: this.config.userPoolId,
      ClientId: this.config.userPoolWebClientId
    };

    this.userPool = new AmazonCognitoIdentity.CognitoUserPool(poolData);
    this.logger.info("Cognito User Pool created successfully");
  }

  // Restore session from localStorage on page refresh
  restoreSession() {
    this.logger.debug("Attempting to restore session from storage");

    try {
      // Try to restore Google OAuth session
      const storedIdToken = localStorage.getItem("oauth_id_token");
      if (storedIdToken) {
        this.logger.debug("Found stored OAuth token, validating");

        // Validate the token before using it
        const tokenInfo = this.decodeJWTToken(storedIdToken);
        const currentTime = Math.floor(Date.now() / 1000);

        if (tokenInfo.exp && tokenInfo.exp > currentTime) {
          this.idToken = storedIdToken;
          this.logger.info("OAuth session restored successfully");
        } else {
          this.logger.debug("Stored OAuth token has expired, removing");
          localStorage.removeItem("oauth_id_token");
        }
      }

      // Cognito sessions are handled automatically by the SDK through localStorage
      this.logger.debug("Session restoration completed");
    } catch (error) {
      this.logger.error("Error during session restoration", { error: error.message });
      // Clean up invalid stored data
      localStorage.removeItem("oauth_id_token");
    }
  }

  // Clean up expired sessions from localStorage
  cleanupExpiredSessions() {
    try {
      const storedIdToken = localStorage.getItem("oauth_id_token");
      if (storedIdToken) {
        const tokenInfo = this.decodeJWTToken(storedIdToken);
        const currentTime = Math.floor(Date.now() / 1000);

        if (tokenInfo.exp && tokenInfo.exp <= currentTime) {
          localStorage.removeItem("oauth_id_token");
          this.idToken = null;
          this.cognitoUser = null;
          this.logger.info("Cleaned up expired OAuth session");
        }
      }
    } catch (error) {
      this.logger.error("Error during session cleanup", { error: error.message });
      localStorage.removeItem("oauth_id_token");
    }
  }

  // Helper method to create errors
  _generateCustomError(userMessage, originalError) {
    const userAuthenticationError = new Error(userMessage);
    userAuthenticationError.originalError = originalError;
    return userAuthenticationError;
  }

  async signIn(username, password) {
    this.logger.info("Starting sign-in process", {
      username: `${username?.substring(0, 3)}***`,
      hasPassword: !!password
    });

    return new Promise((resolve, reject) => {
      if (!username || !password) {
        const error = new Error("Username and password are required");
        this.logger.error("Sign-in failed: missing credentials");
        reject(error);
        return;
      }

      const authData = {
        Username: username.trim(),
        Password: password
      };
      this.logger.debug("Auth data prepared for user", {
        username: `${username.trim().substring(0, 3)}***`
      });

      const authDetails = new AmazonCognitoIdentity.AuthenticationDetails(authData);
      const userData = {
        Username: username.trim(),
        Pool: this.userPool
      };

      this.cognitoUser = new AmazonCognitoIdentity.CognitoUser(userData);
      this.logger.debug("CognitoUser created, starting authentication");

      this.cognitoUser.authenticateUser(authDetails, {
        onSuccess: async (result) => {
          this.logger.info("Authentication successful");
          this.logger.debug("ID token received", {
            tokenPreview: `${result.getIdToken().getJwtToken().substring(0, 20)}...`
          });

          try {
            await this.setupAWSCredentials(result.getIdToken().getJwtToken());
            resolve(result);
          } catch (credentialError) {
            this.logger.error("Failed to setup AWS credentials", { error: credentialError.message });
            reject(credentialError);
          }
        },
        onFailure: (err) => {
          this.logger.error("Authentication failed", {
            code: err.code,
            message: err.message
          });

          let userMessage = "Login failed. Please check your credentials.";
          if (err.code === "NotAuthorizedException") {
            userMessage = "Invalid email or password.";
          } else if (err.code === "UserNotFoundException") {
            userMessage = "User not found. Please check your email address.";
          } else if (err.code === "UserNotConfirmedException") {
            userMessage = "Please confirm your email address before signing in.";
          } else if (err.code === "PasswordResetRequiredException") {
            userMessage = "Password reset required. Please reset your password.";
          }

          const customErrorMessage = this._generateCustomError(userMessage, err);
          reject(customErrorMessage);
        },
        newPasswordRequired: (userAttributes, requiredAttributes) => {
          this.logger.info("New password required for user");
          this.logger.debug("Password change requirements", {
            hasAttributes: !!userAttributes,
            requiredCount: requiredAttributes?.length || 0
          });

          const newPassword = prompt("Please enter a new password:");
          if (newPassword) {
            this.cognitoUser.completeNewPasswordChallenge(
              newPassword,
              {},
              {
                onSuccess: async (result) => {
                  this.logger.info("Password changed successfully");
                  try {
                    await this.setupAWSCredentials(result.getIdToken().getJwtToken());
                    resolve(result);
                  } catch (credentialError) {
                    reject(credentialError);
                  }
                },
                onFailure: (err) => {
                  this.logger.error("Password change failed", { error: err.message });
                  reject(err);
                }
              }
            );
          } else {
            reject(new Error("New password required"));
          }
        }
      });
    });
  }

  async setupAWSCredentials(idToken) {
    this.logger.debug("Setting up AWS credentials");

    try {
      this.idToken = idToken;

      // Set up AWS credentials using Cognito Identity Pool
      const loginKey = `cognito-idp.${this.config.region}.amazonaws.com/${this.config.userPoolId}`;
      this.logger.debug("Configuring AWS credentials with login key");

      // Configure AWS credentials
      AWS.config.credentials = new AWS.CognitoIdentityCredentials({
        IdentityPoolId: this.config.identityPoolId,
        Logins: {
          [loginKey]: idToken
        }
      });

      // Refresh credentials to get temporary AWS keys
      await AWS.config.credentials.refreshPromise();
      this.logger.info("AWS credentials configured successfully");

      return Promise.resolve();
    } catch (error) {
      this.logger.warn("AWS credential setup failed, attempting Google OAuth retry", {
        error: error.message
      });

      // For Google OAuth users, we might need to handle this differently
      try {
        const tokenInfo = this.decodeJWTToken(idToken);
        const isGoogleUser = tokenInfo.identities && tokenInfo.identities.some(identity => identity.providerName === "Google");

        if (isGoogleUser) {
          this.logger.debug("Detected Google OAuth user, attempting alternative credential setup");

          // Clear any existing credentials
          AWS.config.credentials = null;

          // Recreate the login key for the retry
          const retryLoginKey = `cognito-idp.${this.config.region}.amazonaws.com/${this.config.userPoolId}`;

          // Try a fresh credentials setup
          AWS.config.credentials = new AWS.CognitoIdentityCredentials({
            IdentityPoolId: this.config.identityPoolId,
            Logins: {
              [retryLoginKey]: idToken
            }
          });

          // Force clear any cached identity
          AWS.config.credentials.clearCachedId();

          // Try refresh again
          await AWS.config.credentials.refreshPromise();
          this.logger.info("Google OAuth AWS credentials configured successfully");

          return Promise.resolve();
        }
      } catch (retryError) {
        this.logger.error("Failed to set up credentials for Google OAuth user", {
          error: retryError.message
        });
      }

      this.logger.warn("Continuing without AWS credentials - S3 features will be unavailable");
      return Promise.resolve();
    }
  }

  async signOut() {
    this.logger.info("Starting sign-out process");

    if (this.cognitoUser) {
      this.logger.debug("Signing out current user");
      this.cognitoUser.signOut();
      this.cognitoUser = null;

      // Clear AWS credentials
      if (AWS.config.credentials) {
        AWS.config.credentials.clearCachedId();
        AWS.config.credentials = null;
      }
      this.logger.debug("AWS credentials cleared");
    }

    // Clear Google OAuth session data
    this.idToken = null;
    localStorage.removeItem("oauth_id_token");

    // Clear any stored OAuth state
    sessionStorage.removeItem("oauth_state");
    sessionStorage.removeItem("oauth_action");

    this.logger.info("Sign-out completed");
  }

  isAuthenticated() {
    this.logger.debug("Checking authentication status");
    return new Promise((resolve) => {
      const user = this.userPool.getCurrentUser();

      if (user !== null) {
        this.logger.debug("Found current user", { username: `${user.getUsername().substring(0, 3)}***` });

        user.getSession(async (err, session) => {
          if (err) {
            this.logger.warn("Session error during auth check", { error: err.message });
            resolve(false);
            return;
          }

          const isValid = session.isValid();
          this.logger.debug("Session validation result", { isValid });

          if (isValid) {
            this.cognitoUser = user;
            // Set up AWS credentials with the current session
            try {
              await this.setupAWSCredentials(session.getIdToken().getJwtToken());
              this.logger.info("User authenticated successfully");
              resolve(true);
            } catch (error) {
              this.logger.error("Failed to setup credentials for existing session", {
                error: error.message
              });
              resolve(false);
            }
          } else {
            this.logger.debug("Session is invalid");
            resolve(false);
          }
        });
      } else if (this.idToken) {
        // Check if we have a Google OAuth session (restored from localStorage)
        this.logger.debug("Checking Google OAuth session");
        try {
          // Verify the token is still valid (basic check)
          const tokenInfo = this.decodeJWTToken(this.idToken);
          const currentTime = Math.floor(Date.now() / 1000);

          if (tokenInfo.exp && tokenInfo.exp > currentTime) {
            this.logger.info("Google OAuth session is valid");
            // Recreate the cognitoUser object if it doesn't exist
            if (!this.cognitoUser && tokenInfo.email) {
              const userData = {
                Username: tokenInfo.email,
                Pool: this.userPool
              };
              this.cognitoUser = new AmazonCognitoIdentity.CognitoUser(userData);
              this.logger.debug("Recreated CognitoUser object for OAuth session");
            }
            resolve(true);
          } else {
            this.logger.debug("Google OAuth token has expired");
            // Clear expired session
            this.cognitoUser = null;
            this.idToken = null;
            localStorage.removeItem("oauth_id_token");
            resolve(false);
          }
        } catch (error) {
          this.logger.error("Error checking Google OAuth session", { error: error.message });
          // Clear invalid token
          this.idToken = null;
          localStorage.removeItem("oauth_id_token");
          resolve(false);
        }
      } else {
        this.logger.debug("No current user found");
        resolve(false);
      }
    });
  }

  // Helper method to process user attributes
  _processUserAttributes(attributes) {
    return attributes.reduce((acc, attr) => {
      acc[attr.getName()] = attr.getValue();
      return acc;
    }, {});
  }

  // Helper method to get user attributes
  _getUserAttributes(user, resolve, reject) {
    user.getUserAttributes((err, attributes) => {
      if (err) {
        reject(err);
        return;
      }

      const processedAttributes = this._processUserAttributes(attributes);

      // Parse identities if they exist
      let identities = [];
      if (processedAttributes.identities) {
        try {
          identities = JSON.parse(processedAttributes.identities);
        } catch (error) {
          console.warn("AuthManager: Failed to parse identities:", error);
          identities = [];
        }
      }

      const userInfo = {
        username: user.getUsername(),
        identities: identities,
        attributes: processedAttributes
      };

      console.log("AuthManager: Current user info loaded successfully");
      console.log("AuthManager: User has", identities.length, "linked identities");
      resolve(userInfo);
    });
  }

  // Helper method to handle user session
  _handleUserSession(user, resolve, reject) {
    user.getSession((err, _session) => {
      if (err) {
        reject(err);
        return;
      }

      this._getUserAttributes(user, resolve, reject);
    });
  }

  // Get current user info
  getCurrentUser() {
    console.log("AuthManager: Getting current user info...");
    console.log("AuthManager: Current state - cognitoUser:", !!this.cognitoUser, "idToken:", !!this.idToken);

    return new Promise((resolve, reject) => {
      const user = this.userPool.getCurrentUser();
      console.log("AuthManager: Pool current user:", !!user);

      if (user) {
        console.log("AuthManager: Using user pool current user");
        this._handleUserSession(user, resolve, reject);
      } else if (this.idToken) {
        // Handle Google OAuth users who might not be in the current user pool session
        console.log("AuthManager: Using stored OAuth token");
        try {
          // For Google OAuth users, create user info from stored token
          const tokenInfo = this.decodeJWTToken(this.idToken);
          console.log("AuthManager: Decoded token info - user authenticated via OAuth");

          // Recreate cognitoUser if it doesn't exist
          if (!this.cognitoUser && tokenInfo.email) {
            const userData = {
              Username: tokenInfo.email,
              Pool: this.userPool
            };
            this.cognitoUser = new AmazonCognitoIdentity.CognitoUser(userData);
            console.log("AuthManager: Recreated CognitoUser object for OAuth session");
          }

          const userInfo = {
            username: tokenInfo.email,
            identities: tokenInfo.identities || [],
            attributes: {
              email: tokenInfo.email,
              email_verified: "true",
              sub: tokenInfo.sub,
              name: tokenInfo.name,
              given_name: tokenInfo.given_name,
              family_name: tokenInfo.family_name,
              picture: tokenInfo.picture
            }
          };
          this.logger.info("Successfully created Google OAuth user info");

          // Set up AWS credentials for OAuth users when restoring session
          this.setupAWSCredentials(this.idToken).then(() => {
            this.logger.info("AWS credentials restored for OAuth session");
            console.log("✅ AuthManager: AWS credentials successfully restored for OAuth user");
            resolve(userInfo);
          }).catch((credentialsError) => {
            this.logger.warn("AWS credentials setup failed during session restore:", credentialsError.message);
            console.warn("⚠️ AuthManager: AWS credentials setup failed during session restore. S3 uploads may not work:", credentialsError.message);
            // Continue without credentials - user can still log in but uploads won't work
            resolve(userInfo);
          });
        } catch (error) {
          this.logger.error("Failed to decode OAuth token", { error: error.message });
          // Clean up invalid token
          this.idToken = null;
          localStorage.removeItem("oauth_id_token");
          reject(new Error(`Failed to get user info from OAuth token: ${error.message}`));
        }
      } else {
        this.logger.debug("No authenticated user found");
        reject(new Error("No authenticated user"));
      }
    });
  }

  async signUp(email, password) {
    this.logger.info("Starting sign-up process", {
      email: `${email?.substring(0, 3)}***@${email?.split("@")[1]}`
    });

    return new Promise((resolve, reject) => {
      // Validate inputs
      if (!email || !password) {
        this.logger.error("Sign-up validation failed: missing email or password");
        reject(new Error("Email and password are required"));
        return;
      }

      // Validate email format
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(email)) {
        this.logger.warn("Sign-up failed: invalid email format");
        reject(new Error("Please enter a valid email address"));
        return;
      }

      // Validate password strength
      const passwordError = this.validatePassword(password);
      if (passwordError) {
        this.logger.warn("Sign-up failed: password validation", { reason: passwordError });
        reject(new Error(passwordError));
        return;
      }

      this.logger.debug("Registering user with Cognito");

      // Prepare user attributes
      const attributeList = [
        new AmazonCognitoIdentity.CognitoUserAttribute({
          Name: "email",
          Value: email
        })
      ];

      this.userPool.signUp(
        email.trim(),
        password,
        attributeList,
        null,
        (err, result) => {
          if (err) {
            console.error("AuthManager: Registration failed:", err);

            // Provide user-friendly error messages
            let userMessage = "Registration failed. Please try again.";
            if (err.code === "UsernameExistsException") {
              userMessage = "An account with this email already exists.";
            } else if (err.code === "InvalidParameterException") {
              userMessage = "Invalid email or password format.";
            } else if (err.code === "InvalidPasswordException") {
              userMessage =
                err.message || "Password does not meet requirements.";
            }

            const customError = this._generateCustomError(userMessage, err);
            reject(customError);
            return;
          }

          console.log("AuthManager: Registration successful!");
          console.log(
            "AuthManager: User registered:",
            result.user.getUsername()
          );
          console.log(
            "AuthManager: Confirmation needed:",
            !result.userConfirmed
          );

          resolve({
            user: result.user,
            userConfirmed: result.userConfirmed,
            userSub: result.userSub
          });
        }
      );
    });
  }

  validatePassword(password) {
    console.log("AuthManager: Validating password strength...");

    if (password.length < 8) {
      return "Password must be at least 8 characters long";
    }

    if (!/[a-z]/.test(password)) {
      return "Password must contain at least one lowercase letter";
    }

    if (!/[A-Z]/.test(password)) {
      return "Password must contain at least one uppercase letter";
    }

    if (!/\d/.test(password)) {
      return "Password must contain at least one number";
    }

    console.log("AuthManager: Password validation passed");
    return null;
  }

  // Helper method to create CognitoUser
  _createCognitoUser(username) {
    const userData = {
      Username: username.trim(),
      Pool: this.userPool
    };
    return new AmazonCognitoIdentity.CognitoUser(userData);
  }

  async confirmSignUp(username, confirmationCode) {
    console.log("AuthManager: Confirming sign-up...");
    console.log("AuthManager: Username:", username);

    return new Promise((resolve, reject) => {
      const cognitoUser = this._createCognitoUser(username);

      cognitoUser.confirmRegistration(confirmationCode, true, (err, result) => {
        if (err) {
          console.error("AuthManager: Confirmation failed:", err);

          let userMessage = "Confirmation failed. Please try again.";
          if (err.code === "CodeMismatchException") {
            userMessage =
              "Invalid confirmation code. Please check and try again.";
          } else if (err.code === "ExpiredCodeException") {
            userMessage =
              "Confirmation code has expired. Please request a new one.";
          }

          const customError = this._generateCustomError(userMessage, err);
          reject(customError);
          return;
        }

        console.log("AuthManager: User confirmed successfully!");
        resolve(result);
      });
    });
  }

  async resendConfirmationCode(username) {
    console.log("AuthManager: Resending confirmation code...");

    return new Promise((resolve, reject) => {
      const cognitoUser = this._createCognitoUser(username);

      cognitoUser.resendConfirmationCode((err, result) => {
        if (err) {
          console.error(
            "AuthManager: Failed to resend confirmation code:",
            err
          );

          // Provide user-friendly error messages and preserve original error
          let userMessage =
            "Failed to resend confirmation code. Please try again.";
          if (err.code === "InvalidParameterException") {
            userMessage = "This account is already confirmed.";
          } else if (err.code === "NotAuthorizedException") {
            userMessage = "This account is already confirmed.";
          } else if (err.code === "UserNotFoundException") {
            userMessage = "No account found with this email address.";
          }

          const customError = this._generateCustomError(userMessage, err);
          reject(customError);
          return;
        }

        console.log("AuthManager: Confirmation code resent successfully");
        resolve(result);
      });
    });
  }

  async checkUserStatus(username) {
    console.log("AuthManager: Checking user status...");

    return new Promise((resolve, _reject) => {
      const cognitoUser = this._createCognitoUser(username);

      // Try to initiate auth with a dummy password to check user status
      const authDetails = new AmazonCognitoIdentity.AuthenticationDetails({
        Username: username.trim(),
        Password: "dummy_password_to_check_status"
      });

      cognitoUser.authenticateUser(authDetails, {
        onSuccess: () => {
          // This shouldn't happen with dummy password
          resolve({ status: "CONFIRMED", verified: true });
        },
        onFailure: (err) => {
          console.log("AuthManager: Auth check error:", err.code);

          if (err.code === "UserNotConfirmedException") {
            resolve({ status: "UNCONFIRMED", verified: false });
          } else if (err.code === "NotAuthorizedException") {
            // Wrong password but user exists and is confirmed
            resolve({ status: "CONFIRMED", verified: true });
          } else if (err.code === "UserNotFoundException") {
            resolve({ status: "NOT_FOUND", verified: false });
          } else {
            // For any other error, assume user is confirmed to be safe
            resolve({ status: "CONFIRMED", verified: true });
          }
        }
      });
    });
  }

  // Google SSO Methods

  signInWithGoogle() {
    console.log("AuthManager: Starting Google SSO sign-in...");

    try {
      // Validate configuration
      if (!this.config.cognitoDomainUrl) {
        throw new Error("Cognito domain URL not configured");
      }

      // Generate state parameter for CSRF protection
      const state = this.generateRandomState();
      sessionStorage.setItem("oauth_state", state);

      // Construct Google OAuth URL
      const googleSignInUrl = `${this.config.cognitoDomainUrl}/oauth2/authorize?` +
        "identity_provider=Google&" +
        `redirect_uri=${encodeURIComponent(`${window.location.origin}/`)}&` +
        "response_type=code&" +
        `client_id=${this.config.userPoolWebClientId}&` +
        "scope=openid%20profile%20email&" +
        `state=${state}`;

      console.log("AuthManager: Redirecting to Google OAuth URL");
      window.location.href = googleSignInUrl;
    } catch (error) {
      console.error("AuthManager: Failed to initiate Google sign-in:", error);
      throw new Error(`Failed to initiate Google sign-in: ${error.message}`);
    }
  }

  async handleOAuthCallback() {
    console.log("AuthManager: Handling OAuth callback...");

    try {
      const urlParams = new URLSearchParams(window.location.search);
      const code = urlParams.get("code");
      const error = urlParams.get("error");
      const state = urlParams.get("state");
      const storedState = sessionStorage.getItem("oauth_state");

      // Clear stored state
      sessionStorage.removeItem("oauth_state");

      // Handle OAuth errors
      if (error) {
        console.error("AuthManager: OAuth error:", error);
        throw new Error(this.getOAuthErrorMessage(error));
      }

      // Validate state parameter for CSRF protection
      if (!state || state !== storedState) {
        console.error("AuthManager: Invalid OAuth state parameter");
        throw new Error("Invalid authentication request. Please try again.");
      }

      if (!code) {
        console.error("AuthManager: No authorization code received");
        throw new Error("No authorization code received from Google");
      }

      console.log("AuthManager: Valid authorization code received");

      // Exchange code for tokens
      const tokens = await this.exchangeCodeForTokens(code);

      // Set up the Cognito user session from the Google OAuth tokens first
      await this.setupCognitoUserFromOAuth(tokens);

      // Try to set up AWS credentials with the received tokens
      // But don't fail the entire OAuth process if this fails
      try {
        await this.setupAWSCredentials(tokens.id_token);
      } catch (credentialsError) {
        console.warn("AuthManager: AWS credentials setup failed, but continuing with authentication:", credentialsError.message);
        // We'll continue without AWS credentials - user can still log in
      }

      console.log("AuthManager: Google SSO authentication successful!");
      return tokens;

    } catch (error) {
      console.error("AuthManager: OAuth callback handling failed:", error);
      throw error;
    }
  }

  async exchangeCodeForTokens(authorizationCode) {
    console.log("AuthManager: Exchanging authorization code for tokens...");

    try {
      const tokenEndpoint = `${this.config.cognitoDomainUrl}/oauth2/token`;
      const redirectUri = `${window.location.origin}/`;

      const requestBody = new URLSearchParams({
        grant_type: "authorization_code",
        client_id: this.config.userPoolWebClientId,
        code: authorizationCode,
        redirect_uri: redirectUri
      });

      const response = await fetch(tokenEndpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded"
        },
        body: requestBody
      });

      if (!response.ok) {
        const errorData = await response.text();
        console.error("AuthManager: Token exchange failed:", errorData);
        throw new Error("Failed to exchange authorization code for tokens");
      }

      const tokens = await response.json();
      console.log("AuthManager: Successfully exchanged code for tokens");

      return tokens;
    } catch (error) {
      console.error("AuthManager: Token exchange error:", error);
      throw new Error("Failed to complete Google authentication");
    }
  }

  async setupCognitoUserFromOAuth(tokens) {
    console.log("AuthManager: Setting up Cognito user session from OAuth tokens...");

    try {
      // Decode the ID token to get user information
      const userInfo = this.decodeJWTToken(tokens.id_token);
      console.log("AuthManager: Decoded user info from Google token - user authenticated successfully");

      // Create a Cognito user object for session management
      // Use the email as the username since that's how Google OAuth users are identified
      const userData = {
        Username: userInfo.email,
        Pool: this.userPool
      };

      this.cognitoUser = new AmazonCognitoIdentity.CognitoUser(userData);

      // Store the ID token for session management
      this.idToken = tokens.id_token;

      // Persist the token to localStorage for page refresh recovery
      localStorage.setItem("oauth_id_token", tokens.id_token);
      this.logger.info("OAuth token persisted to localStorage");

      console.log("AuthManager: Cognito user session set up for Google OAuth user");
      return true;

    } catch (error) {
      console.error("AuthManager: Failed to set up Cognito user from OAuth:", error);
      throw new Error("Failed to establish user session after Google authentication");
    }
  }

  generateRandomState() {
    // Generate a random state parameter for CSRF protection
    const array = new Uint8Array(32);
    crypto.getRandomValues(array);
    return Array.from(array, byte => byte.toString(16).padStart(2, "0")).join("");
  }

  getOAuthErrorMessage(error) {
    const errorMap = {
      "access_denied": "Sign-in was cancelled. You can try again or use email/password.",
      "invalid_request": "Invalid authentication request. Please try again.",
      "unauthorized_client": "Authentication service temporarily unavailable.",
      "unsupported_response_type": "Authentication method not supported.",
      "invalid_scope": "Requested permissions not available.",
      "server_error": "Authentication service error. Please try again.",
      "temporarily_unavailable": "Google sign-in temporarily unavailable."
    };

    return errorMap[error] || "An unexpected error occurred during sign-in.";
  }

  // Check if Google SSO is available
  isGoogleSSOAvailable() {
    return !!(this.config.cognitoDomainUrl && this.config.googleClientId);
  }

  // Account Linking Methods

  async validateAccountLinking(googleUserInfo, currentUser) {
    console.log("AuthManager: Validating account linking...");

    try {
      // Extract email from Google user info
      const googleEmail = googleUserInfo.email;
      const currentEmail = currentUser.attributes?.email;

      // Validate that emails match
      if (googleEmail !== currentEmail) {
        throw new Error(
          `Google account email (${googleEmail}) must match your current account email (${currentEmail})`
        );
      }

      console.log("AuthManager: Client-side validation passed, backend will handle duplicate checks");
      console.log("AuthManager: Account linking validation passed");
      return true;

    } catch (error) {
      console.error("AuthManager: Account linking validation failed:", error);
      throw error;
    }
  }

  decodeJWTToken(token) {
    try {
      // Simple JWT decode (just the payload, no signature verification)
      // In production, you should verify the signature
      const base64Url = token.split(".")[1];
      const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
      const jsonPayload = decodeURIComponent(atob(base64).split("").map((c) => {
        return `%${(`00${c.charCodeAt(0).toString(16)}`).slice(-2)}`;
      }).join(""));

      return JSON.parse(jsonPayload);
    } catch (error) {
      console.error("AuthManager: Failed to decode JWT token:", error);
      throw new Error("Invalid token format");
    }
  }

  async linkGoogleAccount(googleTokens) {
    console.log("AuthManager: Linking Google account...");

    try {
      const currentUser = await this.getCurrentUser();

      // Decode the Google ID token to get user info
      const googleUserInfo = this.decodeJWTToken(googleTokens.id_token);

      // Validate the linking request (client-side pre-validation)
      await this.validateAccountLinking(googleUserInfo, currentUser);

      // Call the backend API to actually link the accounts
      console.log("AuthManager: Calling backend API to link Google account...");

      const apiUrl = `${this.config.apiGatewayUrl}/user/link-google`;
      const result = await this.makeAuthenticatedRequest(apiUrl, {
        method: "POST",
        body: JSON.stringify({
          googleUserInfo: googleUserInfo
        })
      });

      console.log("AuthManager: Google account linked successfully via backend API");
      return result;

    } catch (error) {
      console.error("AuthManager: Failed to link Google account:", error);
      throw error;
    }
  }

  // API Helper Methods

  async makeAuthenticatedRequest(url, options = {}) {
    console.log(`AuthManager: Making authenticated request to ${url}`);

    try {
      // Get the current user's ID token
      let idToken = this.idToken;

      // If we don't have a stored token, try to get it from the current session
      if (!idToken) {
        const user = this.userPool.getCurrentUser();
        if (user) {
          const session = await new Promise((resolve, reject) => {
            user.getSession((err, session) => {
              if (err) { reject(err); }
              else { resolve(session); }
            });
          });

          if (session && session.isValid()) {
            idToken = session.getIdToken().getJwtToken();
          }
        }
      }

      if (!idToken) {
        throw new Error("No valid authentication token available");
      }

      // Prepare headers with authentication
      const headers = {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${idToken}`,
        ...options.headers
      };

      // Make the request
      const response = await fetch(url, {
        ...options,
        headers
      });

      console.log(`AuthManager: Request to ${url} returned status ${response.status}`);

      if (!response.ok) {
        const errorData = await response.text();
        console.error(`AuthManager: Request failed with status ${response.status}: ${errorData}`);
        throw new Error(`Request failed: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      console.log(`AuthManager: Request to ${url} successful`);
      return data;

    } catch (error) {
      console.error(`AuthManager: Authenticated request to ${url} failed:`, error);
      throw error;
    }
  }

  // Helper method for common API operations
  async _performApiOperation(endpoint, options, operationName) {
    console.log(`AuthManager: Starting ${operationName} via API...`);

    try {
      const apiUrl = `${this.config.apiGatewayUrl}${endpoint}`;
      const result = await this.makeAuthenticatedRequest(apiUrl, options);
      console.log(`AuthManager: ${operationName} successful via API`);
      return result;
    } catch (error) {
      console.error(`AuthManager: Failed to ${operationName.toLowerCase()} via API:`, error);
      throw error;
    }
  }

  async setUserPassword(password) {
    return this._performApiOperation("/user/set-password", {
      method: "POST",
      body: JSON.stringify({ password })
    }, "Password set");
  }

  async unlinkGoogleAccount() {
    return this._performApiOperation("/user/unlink-google", {
      method: "DELETE"
    }, "Google account unlinking");
  }
}

export { AuthManager };
