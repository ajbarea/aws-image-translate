export default {
  testEnvironment: "jsdom",
  setupFilesAfterEnv: ["<rootDir>/tests/setup.js"],
  injectGlobals: true,
  transform: {},
  moduleFileExtensions: ["js", "json", "node"],
  testMatch: ["**/tests/**/*.test.js"],
  clearMocks: true,
  collectCoverageFrom: ["frontend/js/**/*.js", "!**/node_modules/**"]
};
