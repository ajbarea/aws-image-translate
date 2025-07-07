/**
 * Base class for all UI components
 * Provides common functionality for component lifecycle and DOM management
 */
export class BaseComponent {
  constructor(containerId, options = {}) {
    this.containerId = containerId;
    this.container = null;
    this.options = options;
    this.isInitialized = false;
    this.eventListeners = new Map();
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
        ...detail,
      },
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
    // Remove all tracked event listeners
    for (const [element, listeners] of this.eventListeners) {
      for (const { event, handler, options } of listeners) {
        element.removeEventListener(event, handler, options);
      }
    }
    this.eventListeners.clear();
    this.isInitialized = false;
    console.log(`🧹 ${this.constructor.name}: Destroyed`);
  }

  /**
   * Show error message within component
   */
  showError(message, duration = 5000) {
    this.clearMessages();
    const errorDiv = document.createElement("div");
    errorDiv.className = "error-message component-error";
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
    successDiv.className = "success-message component-success";
    successDiv.textContent = message;

    if (this.container) {
      this.container.insertBefore(successDiv, this.container.firstChild);

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
        ".component-error, .component-success"
      );
      messages.forEach((msg) => msg.remove());
    }
  }
}
