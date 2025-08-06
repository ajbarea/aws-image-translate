/**
 * Base class for all UI components
 * Provides common functionality for component lifecycle and DOM management
 * Optimized for memory efficiency with WeakMap tracking and automatic cleanup
 */
export class BaseComponent {
  constructor(containerId, options = {}) {
    this.containerId = containerId;
    this.container = null;
    this.options = options;
    this.isInitialized = false;

    // Using Map to track event listeners for cleanup
    this.eventListeners = new Map();
    this.boundHandlers = new Map(); // Track bound handlers for cleanup
    this.cleanupTasks = new Set(); // Track cleanup tasks

    // Bind cleanup to component lifecycle
    this.setupLifecycleCleanup();
  }

  /**
   * Setup automatic cleanup when component is destroyed or page unloads
   */
  setupLifecycleCleanup() {
    // Cleanup on page unload
    const unloadHandler = () => this.destroy();
    window.addEventListener("beforeunload", unloadHandler);
    this.cleanupTasks.add(() => window.removeEventListener("beforeunload", unloadHandler));

    // Cleanup on visibility change (helps with memory when tab is hidden)
    const visibilityHandler = () => {
      if (document.hidden && this.isInitialized) {
        this.pauseComponent();
      } else if (!document.hidden && this.isInitialized) {
        this.resumeComponent();
      }
    };
    document.addEventListener("visibilitychange", visibilityHandler);
    this.cleanupTasks.add(() => document.removeEventListener("visibilitychange", visibilityHandler));
  }

  /**
   * Initialize the component after DOM is ready
   */
  async initialize() {
    this.container = document.getElementById(this.containerId);
    if (!this.container) {
      throw new Error(`Container with ID '${this.containerId}' not found`);
    }

    await this.onInit();
    this.setupEventListeners();
    this.isInitialized = true;
    console.log(`✅ ${this.constructor.name}: Initialized`);
  }

  /**
   * Override this method in child classes for custom initialization
   */
  async onInit() {
    // Override in child classes
  }

  /**
   * Override this method in child classes to setup event listeners
   */
  setupEventListeners() {
    // Override in child classes
  }

  /**
   * Add event listener with automatic cleanup tracking
   */
  addEventListener(element, event, handler, options = {}) {
    const wrappedHandler = (e) => {
      try {
        handler.call(this, e);
      } catch (error) {
        console.error(
          `Error in ${this.constructor.name} event handler:`,
          error
        );
      }
    };

    element.addEventListener(event, wrappedHandler, options);

    // Track for cleanup
    if (!this.eventListeners.has(element)) {
      this.eventListeners.set(element, []);
    }
    this.eventListeners
      .get(element)
      .push({ event, handler: wrappedHandler, options });
  }

  /**
   * Pause component when tab is hidden to save resources
   */
  pauseComponent() {
    // Override in child classes for specific pause behavior
    console.log(`⏸️ ${this.constructor.name}: Paused`);
  }

  /**
   * Resume component when tab becomes visible
   */
  resumeComponent() {
    // Override in child classes for specific resume behavior
    console.log(`▶️ ${this.constructor.name}: Resumed`);
  }

  /**
   * Find element within component container
   */
  querySelector(selector) {
    return this.container?.querySelector(selector);
  }

  /**
   * Find elements within component container
   */
  querySelectorAll(selector) {
    return this.container?.querySelectorAll(selector);
  }

  /**
   * Show the component
   */
  show() {
    if (this.container) {
      this.container.style.display = "block";
    }
  }

  /**
   * Hide the component
   */
  hide() {
    if (this.container) {
      this.container.style.display = "none";
    }
  }

  /**
   * Enable the component
   */
  enable() {
    if (this.container) {
      this.container.classList.remove("disabled");
      const inputs = this.container.querySelectorAll(
        "input, button, select, textarea"
      );
      inputs.forEach((input) => (input.disabled = false));
    }
  }

  /**
   * Disable the component
   */
  disable() {
    if (this.container) {
      this.container.classList.add("disabled");
      const inputs = this.container.querySelectorAll(
        "input, button, select, textarea"
      );
      inputs.forEach((input) => (input.disabled = true));
    }
  }

  /**
   * Emit custom event
   */
  emit(eventName, detail = {}) {
    const event = new CustomEvent(eventName, {
      detail: {
        component: this.constructor.name,
        containerId: this.containerId,
        ...detail
      }
    });
    document.dispatchEvent(event);
  }

  /**
   * Listen for custom events
   */
  on(eventName, handler) {
    this.addEventListener(document, eventName, handler);
  }

  /**
   * Cleanup component resources
   */
  destroy() {
    // Run all cleanup tasks first
    for (const cleanupTask of this.cleanupTasks) {
      try {
        cleanupTask();
      } catch (error) {
        console.error(`Error in cleanup task for ${this.constructor.name}:`, error);
      }
    }
    this.cleanupTasks.clear();

    // Remove all tracked event listeners
    if (this.eventListeners && this.eventListeners.size > 0) {
      for (const [element, listeners] of this.eventListeners) {
        if (listeners && Array.isArray(listeners)) {
          for (const { event, handler, options } of listeners) {
            try {
              element.removeEventListener(event, handler, options);
            } catch (error) {
              console.warn(`Failed to remove event listener for ${this.constructor.name}:`, error);
            }
          }
        }
      }
      this.eventListeners.clear();
    }

    // Clear bound handlers
    this.boundHandlers.clear();
    this.isInitialized = false;
    console.log(`🧹 ${this.constructor.name}: Destroyed and cleaned up`);
  }

  /**
   * Show error message within component
   */
  showError(message, duration = 5000) {
    this.clearMessages();
    const errorDiv = document.createElement("div");
    errorDiv.className = "component-error";
    errorDiv.textContent = message;

    if (this.container) {
      this.container.insertBefore(errorDiv, this.container.firstChild);

      if (duration > 0) {
        setTimeout(() => this.clearMessages(), duration);
      }
    }
  }

  /**
   * Show success message within component
   */
  showSuccess(message, duration = 5000) {
    this.clearMessages();
    const successDiv = document.createElement("div");
    successDiv.className = "component-success";
    successDiv.textContent = message;

    if (this.container) {
      this.container.insertBefore(successDiv, this.container.firstChild);

      if (duration > 0) {
        setTimeout(() => this.clearMessages(), duration);
      }
    }
  }

  /**
   * Show loading message within component
   */
  showLoading(message = "Loading...", duration = 0) {
    this.clearMessages();
    const loadingDiv = document.createElement("div");
    loadingDiv.className = "component-loading";
    loadingDiv.textContent = message;

    if (this.container) {
      this.container.insertBefore(loadingDiv, this.container.firstChild);

      if (duration > 0) {
        setTimeout(() => this.clearMessages(), duration);
      }
    }
  }

  /**
   * Clear error/success messages
   */
  clearMessages() {
    if (this.container) {
      const messages = this.container.querySelectorAll(
        ".component-error, .component-success, .component-loading"
      );
      messages.forEach((msg) => msg.remove());
    }
  }
}
