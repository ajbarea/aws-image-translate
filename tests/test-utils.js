/**
 * Test utilities for AuthManager testing
 */

import { jest } from "@jest/globals";

export class MockCognitoUser {
  constructor(userData) {
    this.userData = userData;
    this.callbacks = {};
  }

  authenticateUser(authDetails, callbacks) {
    this.callbacks = callbacks;
    // Default to success for testing
    if (this.shouldSucceed !== false) {
      const mockResult = {
        getIdToken: () => ({
          getJwtToken: () => "mock-jwt-token"
        })
      };
      setTimeout(() => callbacks.onSuccess(mockResult), 0);
    }
  }

  confirmRegistration(code, forceAliasCreation, callback) {
    setTimeout(() => callback(null, "SUCCESS"), 0);
  }

  resendConfirmationCode(callback) {
    setTimeout(() => callback(null, { destination: "email" }), 0);
  }

  getSession(callback) {
    const session = {
      isValid: () => true,
      getIdToken: () => ({
        getJwtToken: () => "mock-session-token"
      })
    };
    setTimeout(() => callback(null, session), 0);
  }

  getUserAttributes(callback) {
    const attributes = [
      { getName: () => "email", getValue: () => "test@example.com" },
      { getName: () => "email_verified", getValue: () => "true" }
    ];
    setTimeout(() => callback(null, attributes), 0);
  }

  signOut() {
    // Mock sign out
  }

  getUsername() {
    return this.userData.Username;
  }

  simulateFailure(error) {
    this.shouldSucceed = false;
    setTimeout(() => this.callbacks.onFailure(error), 0);
  }

  simulateNewPasswordRequired(userAttributes, requiredAttributes) {
    setTimeout(() => this.callbacks.newPasswordRequired(userAttributes, requiredAttributes), 0);
  }
}

export class MockUserPool {
  constructor(poolData) {
    this.poolData = poolData;
    this.currentUser = null;
  }

  getCurrentUser() {
    return this.currentUser;
  }

  signUp(username, password, attributeList, validationData, callback) {
    const result = {
      user: new MockCognitoUser({ Username: username }),
      userConfirmed: false,
      userSub: "mock-user-sub"
    };
    setTimeout(() => callback(null, result), 0);
  }

  setCurrentUser(user) {
    this.currentUser = user;
  }
}

export function createMockConfig(overrides = {}) {
  return {
    userPoolId: "us-east-1_TEST123",
    userPoolWebClientId: "test-client-id",
    region: "us-east-1",
    identityPoolId: "us-east-1:test-identity-pool",
    cognitoDomainUrl: "https://test.auth.us-east-1.amazoncognito.com",
    apiGatewayUrl: "https://api.test.com",
    googleClientId: "google-client-id",
    ...overrides
  };
}

export function mockJWTToken(payload = {}) {
  const defaultPayload = {
    sub: "123456789",
    email: "test@example.com",
    email_verified: true,
    name: "Test User",
    exp: Math.floor(Date.now() / 1000) + 3600, // 1 hour from now
    ...payload
  };

  // Create a simple base64 encoded payload
  const encodedPayload = btoa(JSON.stringify(defaultPayload))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=/g, "");

  return `header.${encodedPayload}.signature`;
}

export function setupFetchMock(responses = []) {
  let callCount = 0;

  global.fetch = jest.fn().mockImplementation(() => {
    const response = responses[callCount] || responses[responses.length - 1];
    callCount++;

    if (response.error) {
      return Promise.reject(response.error);
    }

    return Promise.resolve({
      ok: response.ok !== false,
      status: response.status || 200,
      statusText: response.statusText || "OK",
      json: () => Promise.resolve(response.data || {}),
      text: () => Promise.resolve(response.text || JSON.stringify(response.data || {}))
    });
  });
}

export function expectLogMessage(level, message) {
  const consoleMethods = {
    debug: console.log,
    info: console.log,
    warn: console.warn,
    error: console.error
  };

  expect(consoleMethods[level]).toHaveBeenCalledWith(
    expect.stringMatching(new RegExp(`AuthManager:${level.toUpperCase()}.*${message}`)),
    expect.any(Object)
  );
}

export function mockEnvironment(environment = "development") {
  window.location.hostname = environment === "development" ? "localhost" : "production.com";
}
