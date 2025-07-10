// Authentication helper functions
class AuthManager {
  constructor(config) {
    console.log("🔧 AuthManager: Initializing with config:", config);
    this.config = config;
    this.cognitoUser = null;
    this.setupCognito();
  }

  setupCognito() {
    console.log("🔧 AuthManager: Setting up Cognito...");
    const poolData = {
      UserPoolId: this.config.userPoolId,
      ClientId: this.config.userPoolWebClientId,
    };
    console.log("📋 AuthManager: Pool data:", poolData);
    this.userPool = new AmazonCognitoIdentity.CognitoUserPool(poolData);
    console.log("✅ AuthManager: Cognito User Pool created successfully");
  }

  async signIn(username, password) {
    console.log("🔐 AuthManager: Starting sign-in process...");
    console.log("👤 AuthManager: Username:", username);
    console.log(
      "🔒 AuthManager: Password length:",
      password ? password.length : 0
    );

    return new Promise((resolve, reject) => {
      // Validate inputs
      if (!username || !password) {
        console.error("❌ AuthManager: Missing username or password");
        reject(new Error("Username and password are required"));
        return;
      }

      // Prepare authentication data
      const authData = {
        Username: username.trim(),
        Password: password,
      };
      console.log("📝 AuthManager: Auth data prepared:", {
        Username: username.trim(),
        Password: "[HIDDEN]",
      });

      const authDetails = new AmazonCognitoIdentity.AuthenticationDetails(
        authData
      );
      console.log("✅ AuthManager: AuthenticationDetails created");

      const userData = {
        Username: username.trim(),
        Pool: this.userPool,
      };
      console.log("👥 AuthManager: User data prepared:", userData);

      this.cognitoUser = new AmazonCognitoIdentity.CognitoUser(userData);
      console.log("👤 AuthManager: CognitoUser created");

      console.log("🚀 AuthManager: Starting authentication...");
      this.cognitoUser.authenticateUser(authDetails, {
        onSuccess: async (result) => {
          console.log("🎉 AuthManager: Authentication successful!");
          console.log("🎫 AuthManager: Result:", result);
          console.log(
            "🆔 AuthManager: ID Token:",
            result.getIdToken().getJwtToken().substring(0, 50) + "..."
          );

          try {
            await this.setupAWSCredentials(result.getIdToken().getJwtToken());
            resolve(result);
          } catch (credentialError) {
            console.error("❌ AuthManager: Failed to setup AWS credentials");
            reject(credentialError);
          }
        },
        onFailure: (err) => {
          console.error("❌ AuthManager: Authentication failed!");
          console.error("💥 AuthManager: Error details:", err);
          console.error("📋 AuthManager: Error message:", err.message);
          console.error("🔍 AuthManager: Error code:", err.code);

          // Provide user-friendly error messages
          let userMessage = "Login failed. Please check your credentials.";
          if (err.code === "NotAuthorizedException") {
            userMessage = "Invalid email or password.";
          } else if (err.code === "UserNotFoundException") {
            userMessage = "User not found. Please check your email address.";
          } else if (err.code === "UserNotConfirmedException") {
            userMessage =
              "Please confirm your email address before signing in.";
          } else if (err.code === "PasswordResetRequiredException") {
            userMessage =
              "Password reset required. Please reset your password.";
          }

          const enhancedError = new Error(userMessage);
          enhancedError.originalError = err;
          reject(enhancedError);
        },
        newPasswordRequired: (userAttributes, requiredAttributes) => {
          console.log("🔄 AuthManager: New password required");
          console.log("👤 AuthManager: User attributes:", userAttributes);
          console.log(
            "📋 AuthManager: Required attributes:",
            requiredAttributes
          );

          // Handle new password requirement (for temporary passwords)
          const newPassword = prompt("Please enter a new password:");
          if (newPassword) {
            this.cognitoUser.completeNewPasswordChallenge(
              newPassword,
              {},
              {
                onSuccess: async (result) => {
                  console.log("🎉 AuthManager: Password changed successfully!");
                  try {
                    await this.setupAWSCredentials(
                      result.getIdToken().getJwtToken()
                    );
                    resolve(result);
                  } catch (credentialError) {
                    reject(credentialError);
                  }
                },
                onFailure: (err) => {
                  console.error("❌ AuthManager: Password change failed:", err);
                  reject(err);
                },
              }
            );
          } else {
            reject(new Error("New password required"));
          }
        },
      });
    });
  }

  async setupAWSCredentials(idToken) {
    console.log("🔧 AuthManager: Setting up AWS credentials...");
    console.log(
      "🆔 AuthManager: Using ID token (first 50 chars):",
      idToken.substring(0, 50) + "..."
    );

    try {
      // Store the ID token for later use
      this.idToken = idToken;

      // Set up AWS credentials using Cognito Identity Pool
      const loginKey = `cognito-idp.${this.config.region}.amazonaws.com/${this.config.userPoolId}`;
      console.log("🔑 AuthManager: Login key:", loginKey);

      // Configure AWS credentials
      AWS.config.credentials = new AWS.CognitoIdentityCredentials({
        IdentityPoolId: this.config.identityPoolId,
        Logins: {
          [loginKey]: idToken,
        },
      });

      console.log("✅ AuthManager: AWS credentials configured");

      // Refresh credentials to get temporary AWS keys
      console.log("🔄 AuthManager: Refreshing AWS credentials...");
      await AWS.config.credentials.refreshPromise();
      console.log("✅ AuthManager: AWS credentials refreshed successfully");

      return Promise.resolve();
    } catch (error) {
      console.error("❌ AuthManager: Failed to refresh AWS credentials");
      console.error("💥 AuthManager: Credentials error:", error);
      throw error;
    }
  }

  async signOut() {
    console.log("🚪 AuthManager: Starting sign-out process...");
    if (this.cognitoUser) {
      console.log("👤 AuthManager: Signing out current user");
      this.cognitoUser.signOut();
      this.cognitoUser = null;

      // Clear AWS credentials
      if (AWS.config.credentials) {
        AWS.config.credentials.clearCachedId();
        AWS.config.credentials = null;
      }

      console.log("✅ AuthManager: Sign-out completed");
    } else {
      console.log("ℹ️ AuthManager: No user to sign out");
    }
  }

  isAuthenticated() {
    console.log("🔍 AuthManager: Checking authentication status...");
    return new Promise((resolve) => {
      const user = this.userPool.getCurrentUser();

      if (user !== null) {
        console.log("👤 AuthManager: Found current user:", user.getUsername());

        user.getSession(async (err, session) => {
          if (err) {
            console.error("❌ AuthManager: Session error:", err);
            resolve(false);
            return;
          }

          console.log("📊 AuthManager: Session valid:", session.isValid());
          if (session.isValid()) {
            console.log("✅ AuthManager: User is authenticated");
            this.cognitoUser = user;
            // Set up AWS credentials with the current session
            try {
              await this.setupAWSCredentials(
                session.getIdToken().getJwtToken()
              );
              resolve(true);
            } catch (error) {
              console.error(
                "❌ AuthManager: Failed to setup credentials for existing session:",
                error
              );
              resolve(false);
            }
          } else {
            console.log("❌ AuthManager: Session is invalid");
            resolve(false);
          }
        });
      } else {
        console.log("❌ AuthManager: No current user found");
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

      const userInfo = {
        username: user.getUsername(),
        attributes: this._processUserAttributes(attributes),
      };

      console.log("👤 AuthManager: Current user info:", userInfo);
      resolve(userInfo);
    });
  }

  // Helper method to handle user session
  _handleUserSession(user, resolve, reject) {
    user.getSession((err, session) => {
      if (err) {
        reject(err);
        return;
      }

      this._getUserAttributes(user, resolve, reject);
    });
  }

  // Add method to get current user info
  getCurrentUser() {
    console.log("👤 AuthManager: Getting current user info...");
    return new Promise((resolve, reject) => {
      const user = this.userPool.getCurrentUser();

      if (user) {
        this._handleUserSession(user, resolve, reject);
      } else {
        reject(new Error("No authenticated user"));
      }
    });
  }

  async signUp(email, password) {
    console.log("📝 AuthManager: Starting sign-up process...");
    console.log("👤 AuthManager: Email:", email);

    return new Promise((resolve, reject) => {
      // Validate inputs
      if (!email || !password) {
        console.error("❌ AuthManager: Missing email or password");
        reject(new Error("Email and password are required"));
        return;
      }

      // Validate email format
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(email)) {
        reject(new Error("Please enter a valid email address"));
        return;
      }

      // Validate password strength
      const passwordError = this.validatePassword(password);
      if (passwordError) {
        reject(new Error(passwordError));
        return;
      }

      console.log("📝 AuthManager: Registering user with Cognito...");

      // Prepare user attributes
      const attributeList = [
        new AmazonCognitoIdentity.CognitoUserAttribute({
          Name: "email",
          Value: email,
        }),
      ];

      this.userPool.signUp(
        email.trim(),
        password,
        attributeList,
        null,
        (err, result) => {
          if (err) {
            console.error("❌ AuthManager: Registration failed:", err);

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

            const enhancedError = new Error(userMessage);
            enhancedError.originalError = err;
            reject(enhancedError);
            return;
          }

          console.log("🎉 AuthManager: Registration successful!");
          console.log(
            "👤 AuthManager: User registered:",
            result.user.getUsername()
          );
          console.log(
            "📧 AuthManager: Confirmation needed:",
            !result.userConfirmed
          );

          resolve({
            user: result.user,
            userConfirmed: result.userConfirmed,
            userSub: result.userSub,
          });
        }
      );
    });
  }

  validatePassword(password) {
    console.log("🔍 AuthManager: Validating password strength...");

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

    console.log("✅ AuthManager: Password validation passed");
    return null;
  }

  async confirmSignUp(username, confirmationCode) {
    console.log("📧 AuthManager: Confirming sign-up...");
    console.log("👤 AuthManager: Username:", username);

    return new Promise((resolve, reject) => {
      const userData = {
        Username: username.trim(),
        Pool: this.userPool,
      };

      const cognitoUser = new AmazonCognitoIdentity.CognitoUser(userData);

      cognitoUser.confirmRegistration(confirmationCode, true, (err, result) => {
        if (err) {
          console.error("❌ AuthManager: Confirmation failed:", err);

          let userMessage = "Confirmation failed. Please try again.";
          if (err.code === "CodeMismatchException") {
            userMessage =
              "Invalid confirmation code. Please check and try again.";
          } else if (err.code === "ExpiredCodeException") {
            userMessage =
              "Confirmation code has expired. Please request a new one.";
          }

          const enhancedError = new Error(userMessage);
          enhancedError.originalError = err;
          reject(enhancedError);
          return;
        }

        console.log("🎉 AuthManager: User confirmed successfully!");
        resolve(result);
      });
    });
  }

  async resendConfirmationCode(username) {
    console.log("📧 AuthManager: Resending confirmation code...");

    return new Promise((resolve, reject) => {
      const userData = {
        Username: username.trim(),
        Pool: this.userPool,
      };

      const cognitoUser = new AmazonCognitoIdentity.CognitoUser(userData);

      cognitoUser.resendConfirmationCode((err, result) => {
        if (err) {
          console.error(
            "❌ AuthManager: Failed to resend confirmation code:",
            err
          );
          reject(err);
          return;
        }

        console.log("✅ AuthManager: Confirmation code resent successfully");
        resolve(result);
      });
    });
  }
}

export { AuthManager };
