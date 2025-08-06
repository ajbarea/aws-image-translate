import { jest } from "@jest/globals";

// Mock global objects that would be available in a browser
Object.assign(global, {
  AWS: {
    config: {
      credentials: null,
      update: jest.fn()
    },
    CognitoIdentityCredentials: jest.fn().mockImplementation(() => ({
      refreshPromise: jest.fn().mockResolvedValue(true),
      clearCachedId: jest.fn()
    })),
    Credentials: jest.fn()
  },
  AmazonCognitoIdentity: {
    CognitoUserPool: jest.fn().mockImplementation(() => ({
      getCurrentUser: jest.fn(),
      signUp: jest.fn()
    })),
    CognitoUser: jest.fn().mockImplementation(() => {
      const instance = {
        authenticateUser: jest.fn(),
        confirmRegistration: jest.fn(),
        resendConfirmationCode: jest.fn(),
        getSession: jest.fn(),
        getUserAttributes: jest.fn(),
        signOut: jest.fn()
      };
      // Make the instance pass instanceof checks
      Object.setPrototypeOf(instance, global.AmazonCognitoIdentity.CognitoUser.prototype);
      return instance;
    }),
    AuthenticationDetails: jest.fn(),
    CognitoUserAttribute: jest.fn()
  },
  fetch: jest.fn(),
  atob: jest.fn((str) => Buffer.from(str, "base64").toString("binary")),
  btoa: jest.fn((str) => Buffer.from(str, "binary").toString("base64"))
});

// Mock window.crypto
if (!window.crypto) {
  Object.defineProperty(window, "crypto", {
    value: {
      getRandomValues: jest.fn((array) => {
        for (let i = 0; i < array.length; i++) {
          array[i] = Math.floor(Math.random() * 256);
        }
        return array;
      })
    }
  });
}

// JSDOM's window.location is read-only. For tests that need to manipulate it,
// we can make it writable.
Object.defineProperty(window, "location", {
  writable: true,
  value: {
    hostname: "localhost",
    origin: "http://localhost:3000",
    href: "http://localhost:3000",
    search: "",
    hash: ""
  }
});

// JSDOM provides sessionStorage and localStorage. We'll mock them to have
// clear functions available via jest.
Object.defineProperty(window, "sessionStorage", {
  writable: true,
  value: {
    setItem: jest.fn(),
    getItem: jest.fn(),
    removeItem: jest.fn(),
    clear: jest.fn()
  }
});

Object.defineProperty(window, "localStorage", {
  writable: true,
  value: {
    setItem: jest.fn(),
    getItem: jest.fn(),
    removeItem: jest.fn(),
    clear: jest.fn()
  }
});

// Mock console methods for cleaner test output
Object.assign(console, {
  log: jest.fn(),
  error: jest.fn(),
  warn: jest.fn(),
  info: jest.fn(),
  debug: jest.fn()
});
