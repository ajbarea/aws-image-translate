import { AuthManager } from "../frontend/js/auth.js";

// Import Jest functions and your module
import { jest, describe, test, expect, beforeEach } from "@jest/globals";
import { mockEnvironment } from "./test-utils.js";

describe("AuthManager", () => {
  let authManager;
  let mockConfig;

  beforeEach(() => {
    // Reset all mocks
    jest.clearAllMocks();

    // Mock configuration
    mockConfig = {
      userPoolId: "us-east-1_TEST123",
      userPoolWebClientId: "test-client-id",
      region: "us-east-1",
      identityPoolId: "us-east-1:test-identity-pool",
      cognitoDomainUrl: "https://test.auth.us-east-1.amazoncognito.com",
      apiGatewayUrl: "https://api.test.com",
      googleClientId: "google-client-id"
    };

    authManager = new AuthManager(mockConfig);
  });

  describe("Constructor and Setup", () => {
    test("should initialize with config", () => {
      expect(authManager.config).toEqual(mockConfig);
      expect(authManager.cognitoUser).toBeNull();
      expect(authManager.logger).toBeDefined();
    });

    test("should create logger with correct environment detection", () => {
      // Test development environment
      mockEnvironment("development");
      const devAuthManager = new AuthManager(mockConfig);
      expect(devAuthManager.logger).toBeDefined();

      // Test production environment
      mockEnvironment("production");
      const prodAuthManager = new AuthManager(mockConfig);
      expect(prodAuthManager.logger).toBeDefined();
    });

    test("should setup Cognito user pool", () => {
      expect(AmazonCognitoIdentity.CognitoUserPool).toHaveBeenCalledWith({
        UserPoolId: mockConfig.userPoolId,
        ClientId: mockConfig.userPoolWebClientId
      });
    });
  });

  describe("Helper Methods", () => {
    test("_generateCustomError should create error with original", () => {
      const originalError = new Error("Original error");
      originalError.code = "TEST_ERROR";

      const customError = authManager._generateCustomError("User friendly message", originalError);

      expect(customError.message).toBe("User friendly message");
      expect(customError.originalError).toBe(originalError);
    });

    test("_createCognitoUser should create user with correct data", () => {
      const username = "test@example.com";
      const cognitoUser = authManager._createCognitoUser(username);

      expect(AmazonCognitoIdentity.CognitoUser).toHaveBeenCalledWith({
        Username: username.trim(),
        Pool: authManager.userPool
      });
      expect(cognitoUser).toBeInstanceOf(AmazonCognitoIdentity.CognitoUser);
    });

    test("validatePassword should validate correctly", () => {
      // Valid password
      expect(authManager.validatePassword("ValidPass123")).toBeNull();

      // Too short
      expect(authManager.validatePassword("short")).toContain("at least 8 characters");

      // No lowercase
      expect(authManager.validatePassword("UPPERCASE123")).toContain("lowercase letter");

      // No uppercase
      expect(authManager.validatePassword("lowercase123")).toContain("uppercase letter");

      // No number
      expect(authManager.validatePassword("NoNumbers")).toContain("number");
    });
  });

  describe("Authentication Methods", () => {
    test("signIn should handle successful authentication", async () => {
      const mockResult = {
        getIdToken: () => ({
          getJwtToken: () => "mock-token"
        })
      };

      // Mock successful authentication
      const mockCognitoUser = {
        authenticateUser: jest.fn((authDetails, callbacks) => {
          callbacks.onSuccess(mockResult);
        })
      };

      AmazonCognitoIdentity.CognitoUser.mockImplementationOnce(() => mockCognitoUser);

      // Mock setupAWSCredentials to resolve
      authManager.setupAWSCredentials = jest.fn().mockResolvedValue();

      const result = await authManager.signIn("test@example.com", "ValidPass123");

      expect(result).toBe(mockResult);
      expect(authManager.setupAWSCredentials).toHaveBeenCalledWith("mock-token");
    });

    test("signIn should handle authentication failure", async () => {
      const mockError = {
        code: "NotAuthorizedException",
        message: "Incorrect username or password."
      };

      const mockCognitoUser = {
        authenticateUser: jest.fn((authDetails, callbacks) => {
          callbacks.onFailure(mockError);
        })
      };

      AmazonCognitoIdentity.CognitoUser.mockImplementationOnce(() => mockCognitoUser);

      await expect(authManager.signIn("test@example.com", "wrongpass"))
        .rejects.toThrow("Invalid email or password.");
    });

    test("signIn should handle missing credentials", async () => {
      await expect(authManager.signIn("", "")).rejects.toThrow("Username and password are required");
      await expect(authManager.signIn("test@example.com", "")).rejects.toThrow("Username and password are required");
      await expect(authManager.signIn("", "password")).rejects.toThrow("Username and password are required");
    });

    test("signUp should validate inputs", async () => {
      // Missing email
      await expect(authManager.signUp("", "ValidPass123"))
        .rejects.toThrow("Email and password are required");

      // Invalid email format
      await expect(authManager.signUp("invalid-email", "ValidPass123"))
        .rejects.toThrow("Please enter a valid email address");

      // Weak password
      await expect(authManager.signUp("test@example.com", "weak"))
        .rejects.toThrow("Password must be at least 8 characters long");
    });

    test("signUp should handle successful registration", async () => {
      const mockResult = {
        user: { getUsername: () => "test@example.com" },
        userConfirmed: false,
        userSub: "user-sub-123"
      };

      const mockUserPool = {
        signUp: jest.fn((email, password, attributes, validationData, callback) => {
          callback(null, mockResult);
        })
      };

      authManager.userPool = mockUserPool;

      const result = await authManager.signUp("test@example.com", "ValidPass123");

      expect(result).toEqual(mockResult);
      expect(mockUserPool.signUp).toHaveBeenCalled();
    });
  });

  describe("OAuth Methods", () => {
    test("isGoogleSSOAvailable should check config", () => {
      expect(authManager.isGoogleSSOAvailable()).toBe(true);

      const noOAuthConfig = { ...mockConfig };
      delete noOAuthConfig.cognitoDomainUrl;
      const noOAuthManager = new AuthManager(noOAuthConfig);
      expect(noOAuthManager.isGoogleSSOAvailable()).toBe(false);
    });

    test("generateRandomState should return hex string", () => {
      const state = authManager.generateRandomState();
      expect(typeof state).toBe("string");
      expect(state.length).toBe(64); // 32 bytes = 64 hex chars
      expect(/^[0-9a-f]+$/.test(state)).toBe(true);
    });

    test("getOAuthErrorMessage should map errors correctly", () => {
      expect(authManager.getOAuthErrorMessage("access_denied"))
        .toBe("Sign-in was cancelled. You can try again or use email/password.");

      expect(authManager.getOAuthErrorMessage("unknown_error"))
        .toBe("An unexpected error occurred during sign-in.");
    });

    test("decodeJWTToken should decode valid token", () => {
      // Create a mock JWT token (header.payload.signature)
      const mockPayload = { sub: "123", email: "test@example.com", exp: 9999999999 };
      const encodedPayload = btoa(JSON.stringify(mockPayload)).replace(/=/g, "");
      const mockToken = `header.${encodedPayload}.signature`;

      global.atob = jest.fn().mockReturnValue(JSON.stringify(mockPayload));

      const decoded = authManager.decodeJWTToken(mockToken);
      expect(decoded).toEqual(mockPayload);
    });
  });

  describe("Session Management", () => {
    test("signOut should clear session data", async () => {
      const mockCognitoUser = {
        signOut: jest.fn()
      };

      authManager.cognitoUser = mockCognitoUser;
      authManager.idToken = "some-token";

      AWS.config.credentials = {
        clearCachedId: jest.fn()
      };

      await authManager.signOut();

      expect(mockCognitoUser.signOut).toHaveBeenCalled();
      expect(authManager.cognitoUser).toBeNull();
      expect(authManager.idToken).toBeNull();
      expect(window.sessionStorage.removeItem).toHaveBeenCalledWith("oauth_state");
      expect(window.sessionStorage.removeItem).toHaveBeenCalledWith("oauth_action");
    });

    test("isAuthenticated should check user session", async () => {
      const mockUser = {
        getUsername: () => "test@example.com",
        getSession: jest.fn((callback) => {
          const mockSession = {
            isValid: () => true,
            getIdToken: () => ({
              getJwtToken: () => "valid-token"
            })
          };
          callback(null, mockSession);
        })
      };

      const mockUserPool = {
        getCurrentUser: jest.fn().mockReturnValue(mockUser)
      };

      authManager.userPool = mockUserPool;
      authManager.setupAWSCredentials = jest.fn().mockResolvedValue();

      const isAuth = await authManager.isAuthenticated();

      expect(isAuth).toBe(true);
      expect(mockUser.getSession).toHaveBeenCalled();
      expect(authManager.setupAWSCredentials).toHaveBeenCalledWith("valid-token");
    });
  });

  describe("Logging System", () => {
    test("logger should respect environment", () => {
      // Test development mode
      mockEnvironment("development");
      const devManager = new AuthManager(mockConfig);

      // Test that debug logs work in development
      devManager.logger.debug("test message");
      expect(console.log).toHaveBeenCalled();

      // Test production mode
      jest.clearAllMocks();
      mockEnvironment("production");
      const prodManager = new AuthManager(mockConfig);

      // Debug logs should be filtered out in production
      prodManager.logger.debug("test message");
      expect(console.log).not.toHaveBeenCalled();

      // But error logs should still work
      prodManager.logger.error("error message");
      expect(console.error).toHaveBeenCalled();
    });

    test("logger should format messages correctly", () => {
      mockEnvironment("development");
      const localAuthManager = new AuthManager(mockConfig);

      // Mock the logger's info method directly
      const infoSpy = jest.spyOn(localAuthManager.logger, "info");

      localAuthManager.logger.info("Test message", { data: "value" });

      // Assert that the mocked info method was called correctly
      expect(infoSpy).toHaveBeenCalledTimes(1);
      expect(infoSpy).toHaveBeenCalledWith("Test message", { data: "value" });

      // Restore the original method
      infoSpy.mockRestore();
    });
  });

  describe("Error Handling", () => {
    test("should create errors properly", () => {
      const originalError = new Error("Original");
      originalError.code = "TEST_CODE";

      const customError = authManager._generateCustomError("User message", originalError);

      expect(customError.message).toBe("User message");
      expect(customError.originalError).toBe(originalError);
      expect(customError.originalError.code).toBe("TEST_CODE");
    });

    test("should handle network errors gracefully", async () => {
      global.fetch.mockRejectedValueOnce(new Error("Network error"));

      await expect(authManager.exchangeCodeForTokens("test-code"))
        .rejects.toThrow("Failed to complete Google authentication");
    });
  });
});
