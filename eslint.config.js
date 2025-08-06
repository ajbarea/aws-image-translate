import js from "@eslint/js";

export default [
  js.configs.recommended,
  {
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: {
        // Browser globals
        window: "readonly",
        document: "readonly",
        console: "readonly",
        fetch: "readonly",
        localStorage: "readonly",
        sessionStorage: "readonly",
        btoa: "readonly",
        atob: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
        setInterval: "readonly",
        clearInterval: "readonly",
        URLSearchParams: "readonly",
        CustomEvent: "readonly",
        crypto: "readonly",
        prompt: "readonly",
        Image: "readonly",
        URL: "readonly",
        FileReader: "readonly",
        confirm: "readonly",
        performance: "readonly",

        // AWS SDK globals
        AWS: "readonly",
        AmazonCognitoIdentity: "readonly",

        // Chart.js global
        Chart: "readonly",

        // Node.js globals for tests
        global: "readonly",
        process: "readonly",
        Buffer: "readonly",
        __dirname: "readonly",
        __filename: "readonly"
      }
    },
    rules: {
      // Code quality rules
      "no-unused-vars": ["error", {
        varsIgnorePattern: "^_",
        argsIgnorePattern: "^_",
        caughtErrorsIgnorePattern: "^_"
      }],
      "no-undef": "error",
      "no-console": "off", // Allow console statements for logging
      "no-debugger": "warn",

      // Style rules
      "semi": ["error", "always"],
      "quotes": ["error", "double", { avoidEscape: true }],
      "indent": ["error", 2, { SwitchCase: 1 }],
      "comma-dangle": ["error", "never"],
      "no-trailing-spaces": "error",
      "eol-last": "error",

      // Best practices
      "eqeqeq": ["error", "always"],
      "curly": ["error", "all"],
      "no-eval": "error",
      "no-implied-eval": "error",
      "no-new-func": "error",
      "no-script-url": "error",
      "prefer-const": "error",
      "no-var": "error",

      // ES6+ rules
      "arrow-spacing": "error",
      "prefer-arrow-callback": "error",
      "prefer-template": "error",

      // Allow accessing Object.prototype methods
      "no-prototype-builtins": "off"
    }
  },
  {
    // Test-specific configuration
    files: ["tests/**/*.js", "**/*.test.js"],
    languageOptions: {
      globals: {
        // Jest globals
        describe: "readonly",
        test: "readonly",
        it: "readonly",
        expect: "readonly",
        beforeEach: "readonly",
        afterEach: "readonly",
        beforeAll: "readonly",
        afterAll: "readonly",
        jest: "readonly"
      }
    },
    rules: {
      // Relax some rules for tests
      "no-unused-vars": ["error", {
        varsIgnorePattern: "^(mock|Mock|_)",
        argsIgnorePattern: "^_"
      }]
    }
  },
  {
    // Ignore patterns
    ignores: [
      "node_modules/**",
      "**/node_modules/**",
      "dist/**",
      "build/**",
      "coverage/**",
      "**/__pycache__/**",
      "**/venv/**",
      "**/env/**",
      ".terraform/**",
      "terraform/**/*.zip",
      "lambda_functions/build/**",
      "**/*.min.js"
    ]
  }
];
