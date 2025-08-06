/**
 * Integration tests for AuthManager in browser-like environment
 * These tests focus on real-world usage scenarios
 */

// Import Jest functions and your module
import { jest, describe, test, expect, beforeEach } from "@jest/globals";
import { AuthManager } from "../frontend/js/auth.js";

describe("AuthManager Integration Tests", () => {
  let authManager;
  let mockConfig;

  beforeEach(() => {
    jest.clearAllMocks();

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

  describe("Full Authentication Flow", () => {
    test("complete sign-up and confirmation flow", async () => {
      // Step 1: Sign up
      const mockSignUpResult = {
        user: {
          getUsername: () => "test@example.com"
        },
        userConfirmed: false,
        userSub: "user-123"
      };

      authManager.userPool.signUp = jest.fn((email, password, attrs, validation, callback) => {
        callback(null, mockSignUpResult);
      });

      const signUpResult = await authManager.signUp("test@example.com", "ValidPass123");
      expect(signUpResult.userConfirmed).toBe(false);

      // Step 2: Confirm sign up
      const mockCognitoUser = {
        confirmRegistration: jest.fn((code, forceAliasCreation, callback) => {
          callback(null, "SUCCESS");
        })
      };

      AmazonCognitoIdentity.CognitoUser.mockImplementationOnce(() => mockCognitoUser);

      const confirmResult = await authManager.confirmSignUp("test@example.com", "123456");
      expect(confirmResult).toBe("SUCCESS");

      // Step 3: Sign in
      const mockSignInResult = {
        getIdToken: () => ({
          getJwtToken: () => "mock-jwt-token"
        })
      };

      const mockAuthUser = {
        authenticateUser: jest.fn((authDetails, callbacks) => {
          callbacks.onSuccess(mockSignInResult);
        })
      };

      AmazonCognitoIdentity.CognitoUser.mockImplementationOnce(() => mockAuthUser);
      authManager.setupAWSCredentials = jest.fn().mockResolvedValue();

      const signInResult = await authManager.signIn("test@example.com", "ValidPass123");
      expect(signInResult).toBe(mockSignInResult);
    });

    test("handle user not confirmed during sign-in", async () => {
      const mockError = {
        code: "UserNotConfirmedException",
        message: "User is not confirmed."
      };

      const mockCognitoUser = {
        authenticateUser: jest.fn((authDetails, callbacks) => {
          callbacks.onFailure(mockError);
        })
      };

      AmazonCognitoIdentity.CognitoUser.mockImplementationOnce(() => mockCognitoUser);

      await expect(authManager.signIn("test@example.com", "ValidPass123"))
        .rejects.toThrow("Please confirm your email address before signing in.");
    });
  });

  describe("Google OAuth Flow", () => {
    test("initiate Google sign-in", () => {
      // Mock sessionStorage
      window.sessionStorage.setItem = jest.fn();

      authManager.signInWithGoogle();

      expect(window.sessionStorage.setItem).toHaveBeenCalledWith("oauth_state", expect.any(String));
      expect(window.location.href).toEqual(
        expect.stringContaining("oauth2/authorize")
      );
    });

    test("handle OAuth callback with valid code", async () => {
      // Mock URL params
      global.URLSearchParams = jest.fn().mockImplementation(() => ({
        get: jest.fn((key) => {
          const params = {
            "code": "valid-auth-code",
            "state": "valid-state"
          };
          return params[key];
        })
      }));

      // Mock stored state
      window.sessionStorage.getItem = jest.fn().mockReturnValue("valid-state");
      window.sessionStorage.removeItem = jest.fn();

      // Mock token exchange
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          id_token: "mock-id-token",
          access_token: "mock-access-token"
        })
      });

      // Mock JWT decode
      authManager.decodeJWTToken = jest.fn().mockReturnValue({
        email: "test@example.com",
        name: "Test User"
      });

      // Mock AWS credentials setup
      authManager.setupAWSCredentials = jest.fn().mockResolvedValue();

      const result = await authManager.handleOAuthCallback();

      expect(result).toEqual({
        id_token: "mock-id-token",
        access_token: "mock-access-token"
      });
      expect(window.sessionStorage.removeItem).toHaveBeenCalledWith("oauth_state");
    });

    test("handle OAuth callback with error", async () => {
      global.URLSearchParams = jest.fn().mockImplementation(() => ({
        get: jest.fn((key) => {
          const params = {
            "error": "access_denied"
          };
          return params[key];
        })
      }));

      window.sessionStorage.removeItem = jest.fn();

      await expect(authManager.handleOAuthCallback())
        .rejects.toThrow("Sign-in was cancelled. You can try again or use email/password.");
    });
  });

  describe("Session Persistence", () => {
    test("check authentication with existing session", async () => {
      const mockUser = {
        getUsername: () => "test@example.com",
        getSession: jest.fn((callback) => {
          const session = {
            isValid: () => true,
            getIdToken: () => ({
              getJwtToken: () => "valid-session-token"
            })
          };
          callback(null, session);
        })
      };

      authManager.userPool.getCurrentUser = jest.fn().mockReturnValue(mockUser);
      authManager.setupAWSCredentials = jest.fn().mockResolvedValue();

      const isAuthenticated = await authManager.isAuthenticated();

      expect(isAuthenticated).toBe(true);
      expect(authManager.cognitoUser).toBe(mockUser);
    });

    test("check authentication with expired session", async () => {
      const mockUser = {
        getUsername: () => "test@example.com",
        getSession: jest.fn((callback) => {
          const session = {
            isValid: () => false
          };
          callback(null, session);
        })
      };

      authManager.userPool.getCurrentUser = jest.fn().mockReturnValue(mockUser);

      const isAuthenticated = await authManager.isAuthenticated();

      expect(isAuthenticated).toBe(false);
    });
  });

  describe("API Operations", () => {
    test("make authenticated request with valid token", async () => {
      authManager.idToken = "valid-token";

      global.fetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ success: true })
      });

      const result = await authManager.makeAuthenticatedRequest("https://api.test.com/user");

      expect(result).toEqual({ success: true });
      expect(global.fetch).toHaveBeenCalledWith(
        "https://api.test.com/user",
        expect.objectContaining({
          headers: expect.objectContaining({
            "Authorization": "Bearer valid-token"
          })
        })
      );
    });

    test("handle API request failure", async () => {
      authManager.idToken = "valid-token";

      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        statusText: "Unauthorized",
        text: () => Promise.resolve("Invalid token")
      });

      await expect(authManager.makeAuthenticatedRequest("https://api.test.com/user"))
        .rejects.toThrow("Request failed: 401 Unauthorized");
    });

    test("set user password via API", async () => {
      authManager.makeAuthenticatedRequest = jest.fn().mockResolvedValue({ success: true });

      const result = await authManager.setUserPassword("NewPassword123");

      expect(result).toEqual({ success: true });
      expect(authManager.makeAuthenticatedRequest).toHaveBeenCalledWith(
        `${mockConfig.apiGatewayUrl}/user/set-password`,
        {
          method: "POST",
          body: JSON.stringify({ password: "NewPassword123" })
        }
      );
    });
  });

  describe("Error Recovery", () => {
    test("continue without AWS credentials on failure", async () => {
      const mockToken = "test-token";

      // Mock credential failure
      AWS.CognitoIdentityCredentials.mockImplementationOnce(() => ({
        refreshPromise: jest.fn().mockRejectedValue(new Error("Credential error"))
      }));

      // Mock token decode to return non-Google user
      authManager.decodeJWTToken = jest.fn().mockReturnValue({
        identities: []
      });

      // Should not throw error, but resolve anyway
      await expect(authManager.setupAWSCredentials(mockToken)).resolves.toBeUndefined();

      // Should warn about continuing without credentials
      expect(console.warn).toHaveBeenCalledWith(
        expect.stringContaining("Continuing without AWS credentials")
      );
    });
  });
});
