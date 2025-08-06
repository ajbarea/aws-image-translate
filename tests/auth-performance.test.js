/**
 * Performance tests for AuthManager
 * Tests for memory usage, logging performance, and concurrent operations
 */

// Import Jest functions and your module
import { jest, describe, test, expect, beforeEach } from "@jest/globals";
import { AuthManager } from "../frontend/js/auth.js";
import { createMockConfig, mockEnvironment } from "./test-utils.js";

describe("AuthManager Performance Tests", () => {
  let authManager;

  beforeEach(() => {
    jest.clearAllMocks();
    authManager = new AuthManager(createMockConfig());
  });

  describe("Memory Usage", () => {
    test("should not leak memory with multiple instances", () => {
      const instances = [];

      // Create multiple instances
      for (let i = 0; i < 100; i++) {
        instances.push(new AuthManager(createMockConfig()));
      }

      // All instances should be independently configured
      expect(instances.length).toBe(100);

      // Each should have its own logger
      instances.forEach(instance => {
        expect(instance.logger).toBeDefined();
        expect(instance.cognitoUser).toBeNull();
      });
    });

    test("should clean up resources on signOut", async () => {
      // Set up some session data
      authManager.cognitoUser = { signOut: jest.fn() };
      authManager.idToken = "some-token";
      AWS.config.credentials = { clearCachedId: jest.fn() };

      await authManager.signOut();

      // Verify cleanup
      expect(authManager.cognitoUser).toBeNull();
      expect(authManager.idToken).toBeNull();
      expect(AWS.config.credentials).toBeNull();
    });
  });

  describe("Logging Performance", () => {
    test("development logging should not block operations", () => {
      mockEnvironment("development");
      const devManager = new AuthManager(createMockConfig());

      const startTime = performance.now();

      // Log many messages
      for (let i = 0; i < 1000; i++) {
        devManager.logger.debug(`Test message ${i}`, { iteration: i });
      }

      const endTime = performance.now();
      const duration = endTime - startTime;

      // Should complete quickly (less than 100ms for 1000 logs)
      expect(duration).toBeLessThan(100);
    });

    test("production logging should be even faster", () => {
      mockEnvironment("production");
      const prodManager = new AuthManager(createMockConfig());

      // Clear mocks after constructor, which may log messages
      jest.clearAllMocks();

      const startTime = performance.now();

      // Log many debug messages (should be filtered out)
      for (let i = 0; i < 1000; i++) {
        prodManager.logger.debug(`Debug message ${i}`, { iteration: i });
      }

      const endTime = performance.now();
      const duration = endTime - startTime;

      // Should be very fast since debug logs are filtered
      expect(duration).toBeLessThan(50);

      // Debug logs should not have been called
      expect(console.log).not.toHaveBeenCalled();
    });

    test("logging with large data objects should be efficient", () => {
      const largeObject = {
        data: new Array(1000).fill(0).map((_, i) => ({ id: i, value: `item-${i}` }))
      };

      const startTime = performance.now();

      authManager.logger.info("Large data test", largeObject);

      const endTime = performance.now();
      const duration = endTime - startTime;

      // Should handle large objects efficiently
      expect(duration).toBeLessThan(10);
    });
  });

  describe("Concurrent Operations", () => {
    test("multiple simultaneous sign-in attempts should be handled", async () => {
      const mockCognitoUser = {
        authenticateUser: jest.fn((authDetails, callbacks) => {
          // Simulate async auth
          setTimeout(() => {
            callbacks.onSuccess({
              getIdToken: () => ({
                getJwtToken: () => "mock-token"
              })
            });
          }, Math.random() * 10);
        })
      };

      AmazonCognitoIdentity.CognitoUser.mockImplementation(() => mockCognitoUser);
      authManager.setupAWSCredentials = jest.fn().mockResolvedValue();

      // Start multiple sign-in operations
      const signInPromises = Array.from({ length: 5 }, (_, i) =>
        authManager.signIn(`user${i}@test.com`, "ValidPass123")
      );

      const results = await Promise.all(signInPromises);

      // All should succeed
      expect(results).toHaveLength(5);
      results.forEach(result => {
        expect(result.getIdToken().getJwtToken()).toBe("mock-token");
      });
    });

    test("concurrent API requests should not interfere", async () => {
      authManager.idToken = "valid-token";

      let requestCount = 0;
      global.fetch = jest.fn().mockImplementation((url) => {
        const delay = Math.random() * 50; // Random delay up to 50ms
        requestCount++;

        return new Promise(resolve => {
          setTimeout(() => {
            resolve({
              ok: true,
              status: 200,
              json: () => Promise.resolve({
                url,
                requestNumber: requestCount
              })
            });
          }, delay);
        });
      });

      // Make multiple concurrent API requests
      const requests = Array.from({ length: 10 }, (_, i) =>
        authManager.makeAuthenticatedRequest(`https://api.test.com/endpoint${i}`)
      );

      const responses = await Promise.all(requests);

      // All requests should succeed
      expect(responses).toHaveLength(10);
      responses.forEach((response, index) => {
        expect(response.url).toBe(`https://api.test.com/endpoint${index}`);
        expect(response.requestNumber).toBeGreaterThan(0);
      });
    });
  });

  describe("Token Validation Performance", () => {
    test("JWT token decoding should be fast", () => {
      const mockPayload = {
        sub: "123",
        email: "test@test.com",
        exp: 9999999999
      };
      const encodedPayload = btoa(JSON.stringify(mockPayload));
      const mockToken = `header.${encodedPayload}.signature`;

      global.atob = jest.fn().mockReturnValue(JSON.stringify(mockPayload));

      const startTime = performance.now();

      // Decode token many times
      for (let i = 0; i < 1000; i++) {
        authManager.decodeJWTToken(mockToken);
      }

      const endTime = performance.now();
      const duration = endTime - startTime;

      // Should be very fast (less than 50ms for 1000 operations)
      expect(duration).toBeLessThan(50);
    });

    test("password validation should be efficient", () => {
      const passwords = [
        "ValidPass123",
        "short",
        "NoUppercase123",
        "NOLOWERCASE123",
        "NoNumbers",
        "AnotherValidPass456"
      ];

      const startTime = performance.now();

      // Validate many passwords
      for (let i = 0; i < 1000; i++) {
        const password = passwords[i % passwords.length];
        authManager.validatePassword(password);
      }

      const endTime = performance.now();
      const duration = endTime - startTime;

      // Should be very fast
      expect(duration).toBeLessThan(20);
    });
  });

  describe("Error Handling Performance", () => {
    test("error creation should not be expensive", () => {
      const originalError = new Error("Original error");
      originalError.code = "TEST_ERROR";

      const startTime = performance.now();

      // Create many errors
      for (let i = 0; i < 1000; i++) {
        authManager._generateCustomError(`Error ${i}`, originalError);
      }

      const endTime = performance.now();
      const duration = endTime - startTime;

      // Should be fast
      expect(duration).toBeLessThan(10);
    });
  });
});
