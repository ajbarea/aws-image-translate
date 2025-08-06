import { BaseComponent } from "./BaseComponent.js";

/**
 * Performance Dashboard Component for monitoring Lambda function performance metrics
 * Provides real-time and historical views of system performance through interactive charts
 */
export class PerformanceDashboardComponent extends BaseComponent {
  constructor(containerId, authManager, options = {}) {
    super(containerId, options);
    this.auth = authManager;

    // Chart.js instance references for cleanup
    this.charts = new Map();

    // Component state
    this.currentTimeRange = "1h";
    this.selectedFunction = null;
    this.selectedService = null;
    this.isAutoRefreshEnabled = true;
    this.autoRefreshInterval = null;
    this.lastUpdateTime = null;
    this.autoRefreshCountdown = 30;
    this.countdownInterval = null;
    this.isPaused = false;

    // Live performance indicators
    this.healthThresholds = {
      responseTime: { good: 1000, warning: 3000 }, // ms
      successRate: { good: 95, warning: 85 }, // %
      errorRate: { good: 5, warning: 15 } // %
    };
    this.currentHealthStatus = {
      overall: "unknown",
      responseTime: "unknown",
      successRate: "unknown",
      errorRate: "unknown"
    };
    this.activeNotifications = new Map();
    this.notificationQueue = [];

    // Performance data cache
    this.metricsCache = new Map();
    this.cacheExpiry = 30000; // 30 seconds
    this.previousMetricsData = null; // For data diffing

    // Loading states
    this.isLoading = false;
    this.loadingStates = new Set();

    // Error handling
    this.retryCount = 0;
    this.maxRetries = 3;
    this.retryDelay = 1000;

    console.log("📊 PerformanceDashboardComponent: Constructor initialized");
  }

  async onInit() {
    console.log("📊 PerformanceDashboardComponent: Initializing performance dashboard...");

    try {
      // Initialize Chart.js if not already loaded
      await this.initializeChartJS();

      // Setup the dashboard UI structure
      await this.setupDashboardStructure();

      // Setup event listeners for controls
      this.setupControlEventListeners();

      // Setup resize handler for proper chart sizing
      this.setupResizeHandler();

      // Load initial metrics data
      await this.loadInitialMetrics();

      // Setup auto-refresh if enabled
      if (this.isAutoRefreshEnabled) {
        this.setupAutoRefresh();
      }

      console.log("✅ PerformanceDashboardComponent: Dashboard initialized successfully");
    } catch (error) {
      console.error("❌ PerformanceDashboardComponent: Initialization failed:", error);
      this.showError("Failed to initialize performance dashboard. Please refresh the page.");
    }
  }

  /**
     * Initialize Chart.js library
     */
  async initializeChartJS() {
    try {
      // Check if Chart.js is already loaded globally (from CDN)
      if (typeof window.Chart !== "undefined") {
        console.log("📊 PerformanceDashboardComponent: Chart.js already loaded globally (CDN)");
        this.zoomEnabled = false; // CDN version doesn't include zoom plugin
        return;
      }

      // Try to dynamically import Chart.js
      console.log("📊 PerformanceDashboardComponent: Loading Chart.js dynamically...");

      try {
        const chartModule = await import("chart.js/auto");

        // Extract Chart constructor and registerables
        const { Chart, registerables } = chartModule;

        // Verify Chart constructor is available
        if (typeof Chart !== "function") {
          throw new Error("Chart constructor is not a function");
        }

        // Set global Chart reference
        window.Chart = Chart;

        // Register Chart.js components
        Chart.register(...registerables);
        console.log("📊 PerformanceDashboardComponent: Chart.js components registered");

        // Try to load zoom plugin
        try {
          const zoomModule = await import("chartjs-plugin-zoom");
          if (zoomModule.default) {
            Chart.register(zoomModule.default);
            console.log("📊 PerformanceDashboardComponent: Chart.js zoom plugin loaded");
            this.zoomEnabled = true;
          } else {
            console.warn("⚠️ PerformanceDashboardComponent: Zoom plugin module loaded but no default export");
            this.zoomEnabled = false;
          }
        } catch (_zoomError) {
          console.warn("⚠️ PerformanceDashboardComponent: Zoom plugin not available, continuing without zoom functionality");
          this.zoomEnabled = false;
        }

        console.log("📊 PerformanceDashboardComponent: Chart.js initialized successfully via dynamic import");

      } catch (importError) {
        console.warn("⚠️ PerformanceDashboardComponent: Dynamic import failed, waiting for CDN fallback...", importError.message);

        // Wait for CDN Chart.js to load (with timeout)
        const maxWaitTime = 5000; // 5 seconds
        const checkInterval = 100; // 100ms
        let waitTime = 0;

        while (typeof window.Chart === "undefined" && waitTime < maxWaitTime) {
          await new Promise(resolve => setTimeout(resolve, checkInterval));
          waitTime += checkInterval;
        }

        if (typeof window.Chart !== "undefined") {
          console.log("📊 PerformanceDashboardComponent: Chart.js loaded via CDN fallback");
          this.zoomEnabled = false; // CDN version doesn't include zoom plugin
        } else {
          throw new Error("Chart.js could not be loaded via dynamic import or CDN fallback");
        }
      }

      // Final verification
      if (typeof window.Chart !== "function") {
        throw new Error("Chart.js failed to initialize properly");
      }

      console.log("📊 PerformanceDashboardComponent: Chart.js initialization complete");

    } catch (error) {
      console.error("❌ PerformanceDashboardComponent: Failed to load Chart.js:", error);
      throw new Error(`Chart.js library could not be loaded: ${error.message}`);
    }
  }

  /**
     * Setup the basic dashboard UI structure
     */
  async setupDashboardStructure() {
    if (!this.container) {
      throw new Error("Container not found for PerformanceDashboardComponent");
    }

    try {
      const response = await fetch("/components/performance-dashboard.html");
      if (!response.ok) {
        throw new Error(`Failed to load template: ${response.status}`);
      }
      const htmlContent = await response.text();
      this.container.innerHTML = htmlContent;

      console.log("📊 PerformanceDashboardComponent: Dashboard structure loaded from external template");
    } catch (error) {
      console.error("❌ PerformanceDashboardComponent: Failed to load external template, falling back to inline HTML:", error);

      // Fallback to inline HTML if external template fails to load
      this.container.innerHTML = `
        <div class="performance-dashboard">
          <div class="performance-header">
            <div class="performance-controls">
              <div class="time-range-selector">
                <label for="timeRange">Time Range:</label>
                <select id="timeRange" class="control-select">
                  <option value="1h">Last Hour</option>
                  <option value="6h">Last 6 Hours</option>
                  <option value="24h">Last 24 Hours</option>
                  <option value="7d">Last 7 Days</option>
                </select>
              </div>
              <div class="function-filter">
                <label for="functionFilter">Function:</label>
                <select id="functionFilter" class="control-select">
                  <option value="">All Functions</option>
                </select>
              </div>
              <div class="service-filter">
                <label for="serviceFilter">Service:</label>
                <select id="serviceFilter" class="control-select">
                  <option value="">All Services</option>
                </select>
              </div>
              <div class="refresh-controls">
                <button id="refresh-btn" class="btn-secondary">Refresh</button>
                <button id="autoRefreshToggle" class="btn-secondary active">Auto-Refresh</button>
                <button id="pause-refresh-btn" class="btn-secondary" style="display: none;">Pause</button>
                <div class="refresh-countdown">
                  <span id="countdownText">Next refresh in: <span id="countdownTimer">30s</span></span>
                </div>
              </div>
            </div>
          </div>
          <div class="performance-dashboard-placeholder">Template loading failed. Please refresh the page.</div>
        </div>
      `;
    }
  }

  /**
     * Setup event listeners for dashboard controls
     */
  setupControlEventListeners() {
    // Time range selector
    const timeRangeSelect = this.querySelector("#timeRange");
    if (timeRangeSelect) {
      this.addEventListener(timeRangeSelect, "change", this.handleTimeRangeChange.bind(this));
    }

    // Function filter
    const functionFilter = this.querySelector("#functionFilter");
    if (functionFilter) {
      this.addEventListener(functionFilter, "change", this.handleFunctionFilterChange.bind(this));
    }

    // Service filter
    const serviceFilter = this.querySelector("#serviceFilter");
    if (serviceFilter) {
      this.addEventListener(serviceFilter, "change", this.handleServiceFilterChange.bind(this));
    }

    // Refresh button
    const refreshBtn = this.querySelector("#refresh-btn");
    if (refreshBtn) {
      this.addEventListener(refreshBtn, "click", this.handleManualRefresh.bind(this));
    }

    // Auto-refresh toggle
    const autoRefreshToggle = this.querySelector("#autoRefreshToggle");
    if (autoRefreshToggle) {
      this.addEventListener(autoRefreshToggle, "click", this.handleAutoRefreshToggle.bind(this));
    }

    // Pause/Resume button
    const pauseRefreshBtn = this.querySelector("#pause-refresh-btn");
    if (pauseRefreshBtn) {
      this.addEventListener(pauseRefreshBtn, "click", this.handlePauseResumeToggle.bind(this));
    }

    // Close notifications button
    const closeNotifications = this.querySelector("#closeNotifications");
    if (closeNotifications) {
      this.addEventListener(closeNotifications, "click", this.handleCloseNotifications.bind(this));
    }

    console.log("📊 PerformanceDashboardComponent: Event listeners setup complete");
  }

  /**
     * Setup resize handler to maintain proper chart sizing
     */
  setupResizeHandler() {
    let resizeTimeout;

    const handleResize = () => {
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(() => {
        // Resize all active charts
        for (const [chartId, chart] of this.charts) {
          try {
            const canvas = this.querySelector(`#${chartId}`);
            if (canvas) {
              this.setCanvasSize(canvas);
              chart.resize();
            }
          } catch (error) {
            console.warn(`⚠️ PerformanceDashboardComponent: Error resizing chart ${chartId}:`, error);
          }
        }
      }, 250); // Debounce resize events
    };

    this.addEventListener(window, "resize", handleResize);
    console.log("📊 PerformanceDashboardComponent: Resize handler setup complete");
  }

  /**
     * Load initial metrics data
     */
  async loadInitialMetrics() {
    try {
      this.setLoadingState(true);

      // Load metrics with retry logic
      await this.loadMetricsWithRetry();

      this.updateLastUpdateTime();
      this.retryCount = 0; // Reset retry count on success

    } catch (error) {
      console.error("❌ PerformanceDashboardComponent: Failed to load initial metrics:", error);

      // Show appropriate error message based on error type
      if (error.message.includes("401") || error.message.includes("403")) {
        this.showError("Authentication required. Please log in to view performance metrics.");
      } else if (error.message.includes("404")) {
        this.showError("Performance monitoring is not available. Please contact your administrator.");
      } else {
        this.showError("Failed to load performance metrics. Please check your connection and try refreshing.");
      }

      // Show empty state in charts
      this.showEmptyChartState();

    } finally {
      this.setLoadingState(false);
    }
  }

  /**
     * Show empty state when no data is available
     */
  showEmptyChartState() {
    const chartIds = [
      "responseTimeChart",
      "successRateChart",
      "serviceBreakdownChart",
      "functionComparisonChart"
    ];

    chartIds.forEach(chartId => {
      const loadingElement = this.querySelector(`#${chartId}Loading`);
      const canvasElement = this.querySelector(`#${chartId}`);

      if (loadingElement) {
        loadingElement.innerHTML = `
                    <div class="empty-state">
                        <span>No performance data available</span>
                    </div>
                `;
      }

      if (canvasElement) {
        canvasElement.style.display = "none";
      }
    });
  }

  /**
     * Setup auto-refresh functionality with countdown
     */
  setupAutoRefresh() {
    if (this.autoRefreshInterval) {
      clearInterval(this.autoRefreshInterval);
    }
    if (this.countdownInterval) {
      clearInterval(this.countdownInterval);
    }

    // Reset countdown
    this.autoRefreshCountdown = 30;
    this.updateCountdownDisplay();

    // Setup countdown timer (updates every second)
    this.countdownInterval = setInterval(() => {
      if (this.isAutoRefreshEnabled && !this.isPaused && !this.isLoading) {
        this.autoRefreshCountdown--;
        this.updateCountdownDisplay();

        if (this.autoRefreshCountdown <= 0) {
          this.autoRefreshCountdown = 30; // Reset countdown
          this.performAutoRefresh();
        }
      }
    }, 1000);

    // Setup main refresh interval as backup
    this.autoRefreshInterval = setInterval(async () => {
      if (this.isAutoRefreshEnabled && !this.isPaused && !this.isLoading) {
        // This serves as a backup in case countdown gets out of sync
        if (this.autoRefreshCountdown <= 0) {
          this.autoRefreshCountdown = 30;
          await this.performAutoRefresh();
        }
      }
    }, 30000); // 30 seconds

    this.updateRefreshStatus();
    console.log("📊 PerformanceDashboardComponent: Auto-refresh enabled (30s interval with countdown)");
  }

  /**
     * Perform auto-refresh with error handling
     */
  async performAutoRefresh() {
    try {
      this.updateRefreshStatus("Refreshing...");
      await this.loadMetrics();
      this.updateLastUpdateTime();
      this.retryCount = 0; // Reset retry count on success
      this.updateRefreshStatus();
    } catch (error) {
      console.error("❌ PerformanceDashboardComponent: Auto-refresh failed:", error);
      this.handleAutoRefreshError(error);
    }
  }

  /**
     * Update countdown display
     */
  updateCountdownDisplay() {
    const countdownTimer = this.querySelector("#countdownTimer");
    const countdownText = this.querySelector("#countdownText");

    if (countdownTimer) {
      if (this.isPaused) {
        countdownTimer.textContent = "Paused";
        countdownTimer.className = "countdown-paused";
      } else if (this.isLoading) {
        countdownTimer.textContent = "Loading...";
        countdownTimer.className = "countdown-loading";
      } else if (!this.isAutoRefreshEnabled) {
        countdownTimer.textContent = "Disabled";
        countdownTimer.className = "countdown-disabled";
      } else {
        countdownTimer.textContent = `${this.autoRefreshCountdown}s`;
        countdownTimer.className = this.autoRefreshCountdown <= 5 ? "countdown-warning" : "countdown-normal";
      }
    }

    if (countdownText) {
      if (this.isPaused) {
        countdownText.textContent = "Auto-refresh: ";
      } else if (!this.isAutoRefreshEnabled) {
        countdownText.textContent = "Auto-refresh: ";
      } else {
        countdownText.textContent = "Next refresh in: ";
      }
    }
  }

  /**
     * Update refresh status display
     */
  updateRefreshStatus(customMessage = null) {
    const refreshStatus = this.querySelector("#refreshStatus");
    if (!refreshStatus) { return; }

    if (customMessage) {
      refreshStatus.textContent = customMessage;
      refreshStatus.className = "refresh-status-active";
      return;
    }

    if (!this.isAutoRefreshEnabled) {
      refreshStatus.textContent = "Auto-refresh disabled";
      refreshStatus.className = "refresh-status-disabled";
    } else if (this.isPaused) {
      refreshStatus.textContent = "Auto-refresh paused";
      refreshStatus.className = "refresh-status-paused";
    } else {
      refreshStatus.textContent = "Auto-refresh enabled";
      refreshStatus.className = "refresh-status-enabled";
    }
  }

  /**
     * Handle auto-refresh errors with retry logic
     */
  handleAutoRefreshError(_error) {
    this.retryCount++;

    if (this.retryCount >= this.maxRetries) {
      console.error("❌ PerformanceDashboardComponent: Max retries reached, disabling auto-refresh");
      this.isAutoRefreshEnabled = false;
      this.updateAutoRefreshButton();
      this.showError("Auto-refresh disabled due to repeated failures. Please refresh manually.");
    } else {
      console.warn(`⚠️ PerformanceDashboardComponent: Auto-refresh failed (${this.retryCount}/${this.maxRetries}), will retry`);
    }
  }

  /**
     * Set loading state for the entire dashboard or specific components
     */
  setLoadingState(isLoading, component = null) {
    this.isLoading = isLoading;

    const statusIndicator = this.querySelector(".status-indicator .status-dot");
    const statusText = this.querySelector(".status-indicator .status-text");

    if (isLoading) {
      if (component) {
        this.loadingStates.add(component);
      }

      if (statusIndicator) {
        statusIndicator.className = "status-dot loading";
      }
      if (statusText) {
        statusText.textContent = "Loading...";
      }
    } else {
      if (component) {
        this.loadingStates.delete(component);
      }

      // Only update status if no components are still loading
      if (this.loadingStates.size === 0) {
        if (statusIndicator) {
          statusIndicator.className = "status-dot success";
        }
        if (statusText) {
          statusText.textContent = "Active";
        }
      }
    }
  }

  /**
     * Update the last update time display with detailed status
     */
  updateLastUpdateTime() {
    const lastUpdateElement = this.querySelector("#lastUpdateTime");
    const updateStatus = this.querySelector("#updateStatus");

    if (lastUpdateElement) {
      this.lastUpdateTime = new Date();
      lastUpdateElement.textContent = this.lastUpdateTime.toLocaleTimeString();
    }

    if (updateStatus) {
      const timeSinceUpdate = this.getTimeSinceLastUpdate();
      if (timeSinceUpdate) {
        updateStatus.textContent = ` (${timeSinceUpdate} ago)`;
        updateStatus.className = "update-status-recent";
      } else {
        updateStatus.textContent = " (just now)";
        updateStatus.className = "update-status-current";
      }
    }
  }

  /**
     * Get human-readable time since last update
     */
  getTimeSinceLastUpdate() {
    if (!this.lastUpdateTime) { return null; }

    const now = new Date();
    const diffMs = now - this.lastUpdateTime;
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);

    if (diffSeconds < 60) {
      return `${diffSeconds}s`;
    } else if (diffMinutes < 60) {
      return `${diffMinutes}m`;
    } else {
      const diffHours = Math.floor(diffMinutes / 60);
      return `${diffHours}h`;
    }
  }

  /**
     * Event handler for time range changes
     */
  async handleTimeRangeChange(event) {
    const newTimeRange = event.target.value;
    if (newTimeRange !== this.currentTimeRange) {
      this.currentTimeRange = newTimeRange;
      console.log(`📊 PerformanceDashboardComponent: Time range changed to ${newTimeRange}`);
      await this.refreshMetrics();
    }
  }

  /**
     * Event handler for function filter changes
     */
  async handleFunctionFilterChange(event) {
    const newFunction = event.target.value || null;
    if (newFunction !== this.selectedFunction) {
      this.selectedFunction = newFunction;
      console.log(`📊 PerformanceDashboardComponent: Function filter changed to ${newFunction || "All"}`);
      await this.refreshMetrics();
    }
  }

  /**
     * Event handler for service filter changes
     */
  async handleServiceFilterChange(event) {
    const newService = event.target.value || null;
    if (newService !== this.selectedService) {
      this.selectedService = newService;
      console.log(`📊 PerformanceDashboardComponent: Service filter changed to ${newService || "All"}`);
      await this.refreshMetrics();
    }
  }

  /**
     * Event handler for manual refresh
     */
  async handleManualRefresh(_event) {
    console.log("📊 PerformanceDashboardComponent: Manual refresh triggered");
    await this.refreshMetrics();
  }

  /**
     * Event handler for auto-refresh toggle
     */
  handleAutoRefreshToggle(_event) {
    this.isAutoRefreshEnabled = !this.isAutoRefreshEnabled;
    console.log(`📊 PerformanceDashboardComponent: Auto-refresh ${this.isAutoRefreshEnabled ? "enabled" : "disabled"}`);

    if (this.isAutoRefreshEnabled) {
      this.isPaused = false; // Unpause when enabling
      this.setupAutoRefresh();
    } else {
      if (this.autoRefreshInterval) {
        clearInterval(this.autoRefreshInterval);
        this.autoRefreshInterval = null;
      }
      if (this.countdownInterval) {
        clearInterval(this.countdownInterval);
        this.countdownInterval = null;
      }
    }

    this.updateAutoRefreshButton();
    this.updatePauseResumeButton();
    this.updateCountdownDisplay();
    this.updateRefreshStatus();
  }

  /**
     * Event handler for pause/resume toggle
     */
  handlePauseResumeToggle(_event) {
    if (!this.isAutoRefreshEnabled) {
      return; // Can"t pause if auto-refresh is disabled
    }

    this.isPaused = !this.isPaused;
    console.log(`📊 PerformanceDashboardComponent: Auto-refresh ${this.isPaused ? "paused" : "resumed"}`);

    if (!this.isPaused) {
      // Reset countdown when resuming
      this.autoRefreshCountdown = 30;
    }

    this.updatePauseResumeButton();
    this.updateCountdownDisplay();
    this.updateRefreshStatus();
  }

  /**
     * Update auto-refresh button appearance
     */
  updateAutoRefreshButton() {
    const autoRefreshToggle = this.querySelector("#autoRefreshToggle");
    if (autoRefreshToggle) {
      if (this.isAutoRefreshEnabled) {
        autoRefreshToggle.classList.add("active");
        autoRefreshToggle.textContent = "Auto-Refresh";
        autoRefreshToggle.title = "Disable auto-refresh";
      } else {
        autoRefreshToggle.classList.remove("active");
        autoRefreshToggle.textContent = "Enable Auto-Refresh";
        autoRefreshToggle.title = "Enable auto-refresh";
      }
    }
  }

  /**
     * Update pause/resume button appearance
     */
  updatePauseResumeButton() {
    const pauseRefreshBtn = this.querySelector("#pause-refresh-btn");
    if (pauseRefreshBtn) {
      if (this.isAutoRefreshEnabled) {
        pauseRefreshBtn.style.display = "inline-block";

        if (this.isPaused) {
          pauseRefreshBtn.textContent = "Resume";
          pauseRefreshBtn.classList.add("paused");
          pauseRefreshBtn.title = "Resume auto-refresh";
        } else {
          pauseRefreshBtn.textContent = "Pause";
          pauseRefreshBtn.classList.remove("paused");
          pauseRefreshBtn.title = "Pause auto-refresh";
        }
      } else {
        pauseRefreshBtn.style.display = "none";
      }
    }
  }

  /**
     * Refresh metrics data and update charts
     */
  async refreshMetrics() {
    try {
      this.setLoadingState(true);
      this.clearMessages();

      // Clear cache to force fresh data
      this.metricsCache.clear();

      await this.loadMetrics();
      this.updateLastUpdateTime();

      console.log("📊 PerformanceDashboardComponent: Metrics refreshed successfully");
    } catch (error) {
      console.error("❌ PerformanceDashboardComponent: Failed to refresh metrics:", error);
      this.showError("Failed to refresh performance metrics. Please try again.");
    } finally {
      this.setLoadingState(false);
    }
  }

  /**
     * Pause component when tab is hidden to save resources
     */
  pauseComponent() {
    super.pauseComponent();

    if (this.autoRefreshInterval) {
      clearInterval(this.autoRefreshInterval);
      this.autoRefreshInterval = null;
    }

    if (this.countdownInterval) {
      clearInterval(this.countdownInterval);
      this.countdownInterval = null;
    }

    console.log("⏸️ PerformanceDashboardComponent: Auto-refresh paused");
  }

  /**
     * Resume component when tab becomes visible
     */
  resumeComponent() {
    super.resumeComponent();

    if (this.isAutoRefreshEnabled && !this.isPaused) {
      this.setupAutoRefresh();
    }

    console.log("▶️ PerformanceDashboardComponent: Auto-refresh resumed");
  }

  /**
     * Cleanup component resources
     */
  destroy() {
    // Clear auto-refresh interval
    if (this.autoRefreshInterval) {
      clearInterval(this.autoRefreshInterval);
      this.autoRefreshInterval = null;
    }

    // Clear countdown interval
    if (this.countdownInterval) {
      clearInterval(this.countdownInterval);
      this.countdownInterval = null;
    }

    // Destroy all Chart.js instances
    for (const [chartId, chart] of this.charts) {
      try {
        chart.destroy();
        console.log(`📊 PerformanceDashboardComponent: Chart ${chartId} destroyed`);
      } catch (error) {
        console.warn(`⚠️ PerformanceDashboardComponent: Error destroying chart ${chartId}:`, error);
      }
    }
    this.charts.clear();

    // Clear caches
    this.metricsCache.clear();
    this.loadingStates.clear();
    this.previousMetricsData = null;

    // Clear live indicators
    this.activeNotifications.clear();
    this.notificationQueue = [];

    // Call parent cleanup
    super.destroy();

    console.log("🧹 PerformanceDashboardComponent: Component destroyed and cleaned up");
  }

  /**
     * Load performance metrics from the API
     */
  async loadMetrics(timeRange = null, functionName = null, service = null) {
    const effectiveTimeRange = timeRange || this.currentTimeRange;
    const effectiveFunction = functionName || this.selectedFunction;
    const effectiveService = service || this.selectedService;

    console.log("📊 PerformanceDashboardComponent: Loading metrics", {
      timeRange: effectiveTimeRange,
      function: effectiveFunction,
      service: effectiveService
    });

    try {
      // Check cache first
      const cacheKey = this.getCacheKey(effectiveTimeRange, effectiveFunction, effectiveService);
      const cachedData = this.getCachedData(cacheKey);

      if (cachedData) {
        console.log("📊 PerformanceDashboardComponent: Using cached metrics data");
        await this.processMetricsData(cachedData);
        return cachedData;
      }

      // Build API URL with query parameters
      const apiUrl = this.buildApiUrl(effectiveTimeRange, effectiveFunction, effectiveService);

      // Make authenticated request to performance API
      const metricsData = await this.auth.makeAuthenticatedRequest(apiUrl);

      console.log("📊 PerformanceDashboardComponent: Metrics data received", {
        functions: metricsData.functions?.length || 0,
        services: Object.keys(metricsData.services || {}).length,
        alerts: metricsData.alerts?.length || 0
      });

      // Cache the data
      this.setCachedData(cacheKey, metricsData);

      // Process and display the data
      await this.processMetricsData(metricsData);

      return metricsData;

    } catch (error) {
      console.error("❌ PerformanceDashboardComponent: Failed to load metrics:", error);

      // Handle specific error types
      if (error.message.includes("401") || error.message.includes("403")) {
        this.showError("Authentication failed. Please log in again.");
        this.emit("auth:required");
      } else if (error.message.includes("404")) {
        this.showError("Performance API endpoint not found. Please check your configuration.");
      } else if (error.message.includes("500")) {
        this.showError("Server error occurred while loading performance data. Please try again later.");
      } else {
        this.showError("Failed to load performance metrics. Please check your connection and try again.");
      }

      throw error;
    }
  }

  /**
     * Load metrics with retry logic (without artificial error)
     */
  async loadMetricsWithRetry(timeRange = null, functionName = null, service = null) {
    let lastError = null;

    for (let attempt = 1; attempt <= this.maxRetries; attempt++) {
      try {
        return await this.loadMetrics(timeRange, functionName, service);
      } catch (error) {
        lastError = error;
        console.error(`❌ PerformanceDashboardComponent: Load attempt ${attempt}/${this.maxRetries} failed:`, error);

        if (attempt < this.maxRetries) {
          console.log(`📊 PerformanceDashboardComponent: Retrying request (${attempt}/${this.maxRetries})`);

          // Exponential backoff
          const delay = this.retryDelay * Math.pow(2, attempt - 1);
          await new Promise(resolve => setTimeout(resolve, delay));
        }
      }
    }

    // If all retries failed, throw the last error
    throw lastError;
  }

  /**
     * Build API URL with query parameters
     */
  buildApiUrl(timeRange, functionName, service) {
    const { AWS_CONFIG } = window;
    let url = `${AWS_CONFIG.apiGatewayUrl}/performance`;

    const params = new URLSearchParams();

    if (timeRange) {
      params.append("time_range", timeRange);
    }

    if (functionName) {
      params.append("function_name", functionName);
    }

    if (service) {
      params.append("service", service);
    }

    const queryString = params.toString();
    if (queryString) {
      url += `?${queryString}`;
    }

    console.log("📊 PerformanceDashboardComponent: Built API URL:", url);
    return url;
  }

  /**
     * Generate cache key for metrics data
     */
  getCacheKey(timeRange, functionName, service) {
    return `metrics_${timeRange}_${functionName || "all"}_${service || "all"}`;
  }

  /**
     * Get cached metrics data if still valid
     */
  getCachedData(cacheKey) {
    const cached = this.metricsCache.get(cacheKey);

    if (!cached) {
      return null;
    }

    const now = Date.now();
    if (now - cached.timestamp > this.cacheExpiry) {
      this.metricsCache.delete(cacheKey);
      return null;
    }

    return cached.data;
  }

  /**
     * Cache metrics data with timestamp
     */
  setCachedData(cacheKey, data) {
    this.metricsCache.set(cacheKey, {
      data: data,
      timestamp: Date.now()
    });

    // Clean up old cache entries
    this.cleanupCache();
  }

  /**
     * Clean up expired cache entries
     */
  cleanupCache() {
    const now = Date.now();

    for (const [key, cached] of this.metricsCache.entries()) {
      if (now - cached.timestamp > this.cacheExpiry) {
        this.metricsCache.delete(key);
      }
    }
  }

  /**
     * Normalize metrics data to ensure proper structure
     */
  normalizeMetricsData(metricsData) {
    if (!metricsData || typeof metricsData !== "object") {
      return {
        functions: [],
        services: {},
        alerts: []
      };
    }

    return {
      functions: Array.isArray(metricsData.functions) ? metricsData.functions : [],
      services: (metricsData.services && typeof metricsData.services === "object" && metricsData.services !== null) ? metricsData.services : {},
      alerts: Array.isArray(metricsData.alerts) ? metricsData.alerts : []
    };
  }

  /**
     * Process and display metrics data with efficient diffing
     */
  async processMetricsData(metricsData) {
    try {
      console.log("📊 PerformanceDashboardComponent: Processing metrics data");

      // Normalize the data to ensure proper structure
      const normalizedData = this.normalizeMetricsData(metricsData);

      // Perform data diffing to minimize re-rendering
      const changes = this.diffMetricsData(this.previousMetricsData, normalizedData);

      if (changes.hasChanges) {
        console.log("📊 PerformanceDashboardComponent: Data changes detected:", changes);

        // Update filter options only if functions or services changed
        if (changes.functionsChanged || changes.servicesChanged) {
          this.updateFilterOptions(normalizedData);
        }

        // Update charts only if relevant data changed
        await this.updateChartsSelectively(normalizedData, changes);

        // Update alerts if they changed
        if (changes.alertsChanged) {
          this.updateAlerts(normalizedData.alerts || []);
        }

        // Update live performance indicators
        this.updateLivePerformanceIndicators(normalizedData);
      } else {
        console.log("📊 PerformanceDashboardComponent: No significant data changes detected, skipping re-render");

        // Still update live indicators even if no major changes (for real-time status)
        this.updateLivePerformanceIndicators(normalizedData);
      }

      // Store current data for next comparison
      this.previousMetricsData = this.deepClone(normalizedData);

      console.log("📊 PerformanceDashboardComponent: Metrics data processed successfully");

    } catch (error) {
      console.error("❌ PerformanceDashboardComponent: Error processing metrics data:", error);
      this.showError("Error processing performance data. Please refresh and try again.");
    }
  }

  /**
     * Compare metrics data to detect changes
     */
  diffMetricsData(previousData, currentData) {
    if (!previousData) {
      return {
        hasChanges: true,
        functionsChanged: true,
        servicesChanged: true,
        alertsChanged: true,
        metricsChanged: true
      };
    }

    const changes = {
      hasChanges: false,
      functionsChanged: false,
      servicesChanged: false,
      alertsChanged: false,
      metricsChanged: false
    };

    // Check if functions changed
    if (this.arraysDiffer(
      previousData.functions?.map(f => f.name) || [],
      currentData.functions?.map(f => f.name) || []
    )) {
      changes.functionsChanged = true;
      changes.hasChanges = true;
    }

    // Check if function metrics changed significantly
    if (!changes.functionsChanged && previousData.functions && currentData.functions) {
      for (let i = 0; i < currentData.functions.length; i++) {
        const prev = previousData.functions[i];
        const curr = currentData.functions[i];

        if (prev && curr && this.metricsSignificantlyChanged(prev.metrics, curr.metrics)) {
          changes.metricsChanged = true;
          changes.hasChanges = true;
          break;
        }
      }
    }

    // Check if services changed
    if (this.objectsDiffer(previousData.services || {}, currentData.services || {})) {
      changes.servicesChanged = true;
      changes.hasChanges = true;
    }

    // Check if alerts changed
    if (this.arraysDiffer(
      previousData.alerts?.map(a => a.type + a.function + a.timestamp) || [],
      currentData.alerts?.map(a => a.type + a.function + a.timestamp) || []
    )) {
      changes.alertsChanged = true;
      changes.hasChanges = true;
    }

    return changes;
  }

  /**
     * Check if arrays differ
     */
  arraysDiffer(arr1, arr2) {
    if (arr1.length !== arr2.length) { return true; }
    return arr1.some((item, index) => item !== arr2[index]);
  }

  /**
     * Check if objects differ significantly
     */
  objectsDiffer(obj1, obj2) {
    const keys1 = Object.keys(obj1);
    const keys2 = Object.keys(obj2);

    if (keys1.length !== keys2.length) { return true; }

    return keys1.some(key => {
      if (!obj2.hasOwnProperty(key)) { return true; }

      // For service objects, check if metrics changed significantly
      if (typeof obj1[key] === "object" && typeof obj2[key] === "object") {
        return this.metricsSignificantlyChanged(obj1[key], obj2[key]);
      }

      return obj1[key] !== obj2[key];
    });
  }

  /**
     * Check if metrics changed significantly (more than 5% or 100ms)
     */
  metricsSignificantlyChanged(prev, curr) {
    if (!prev || !curr) { return true; }

    const thresholds = {
      avgResponseTime: 100, // 100ms threshold
      avgDuration: 100,     // 100ms threshold
      successRate: 5,       // 5% threshold
      totalCalls: 10        // 10 calls threshold
    };

    for (const [key, threshold] of Object.entries(thresholds)) {
      if (prev[key] !== undefined && curr[key] !== undefined) {
        const diff = Math.abs(prev[key] - curr[key]);

        if (key === "successRate") {
          // Percentage-based threshold
          if (diff > threshold) { return true; }
        } else if (key === "totalCalls") {
          // Absolute threshold for counts
          if (diff > threshold) { return true; }
        } else {
          // Time-based threshold
          if (diff > threshold) { return true; }
        }
      }
    }

    return false;
  }

  /**
     * Deep clone object for comparison
     */
  deepClone(obj) {
    if (obj === null || typeof obj !== "object") { return obj; }
    if (obj instanceof Date) { return new Date(obj.getTime()); }
    if (obj instanceof Array) { return obj.map(item => this.deepClone(item)); }

    const cloned = {};
    for (const key in obj) {
      if (obj.hasOwnProperty(key)) {
        cloned[key] = this.deepClone(obj[key]);
      }
    }
    return cloned;
  }

  /**
     * Update filter dropdown options based on available data
     */
  updateFilterOptions(metricsData) {
    // Update function filter options
    const functionFilter = this.querySelector("#functionFilter");
    if (functionFilter && metricsData.functions && Array.isArray(metricsData.functions)) {
      const currentValue = functionFilter.value;

      // Clear existing options except "All Functions"
      functionFilter.innerHTML = '<option value="">All Functions</option>';

      // Add function options
      const uniqueFunctions = [...new Set(metricsData.functions.map(f => f.name))];
      uniqueFunctions.forEach(functionName => {
        const option = document.createElement("option");
        option.value = functionName;
        option.textContent = functionName;
        if (functionName === currentValue) {
          option.selected = true;
        }
        functionFilter.appendChild(option);
      });
    }

    // Update service filter options
    const serviceFilter = this.querySelector("#serviceFilter");
    if (serviceFilter && metricsData.services && typeof metricsData.services === "object" && metricsData.services !== null) {
      const currentValue = serviceFilter.value;

      // Clear existing options except "All Services"
      serviceFilter.innerHTML = '<option value="">All Services</option>';

      // Add service options
      const serviceNames = Object.keys(metricsData.services);
      serviceNames.forEach(serviceName => {
        const option = document.createElement("option");
        option.value = serviceName;
        option.textContent = serviceName.charAt(0).toUpperCase() + serviceName.slice(1);
        if (serviceName === currentValue) {
          option.selected = true;
        }
        serviceFilter.appendChild(option);
      });
    }

    console.log("📊 PerformanceDashboardComponent: Filter options updated");
  }

  /**
     * Update charts with new metrics data
     */
  async updateCharts(metricsData) {
    console.log("📊 PerformanceDashboardComponent: Updating charts with new data");

    try {
      // Hide loading indicators and show chart canvases
      const chartContainers = [
        "responseTimeChart",
        "successRateChart",
        "serviceBreakdownChart",
        "functionComparisonChart"
      ];

      chartContainers.forEach(chartId => {
        const loadingElement = this.querySelector(`#${chartId}Loading`);
        const canvasElement = this.querySelector(`#${chartId}`);

        if (loadingElement) {
          loadingElement.style.display = "none";
        }

        if (canvasElement) {
          canvasElement.style.display = "block";
        }
      });

      // Update individual charts
      await this.updateResponseTimeChart(metricsData);
      await this.updateSuccessRateChart(metricsData);
      await this.updateServiceBreakdownChart(metricsData);
      await this.updateFunctionComparisonChart(metricsData);

      console.log("📊 PerformanceDashboardComponent: All charts updated successfully");

    } catch (error) {
      console.error("❌ PerformanceDashboardComponent: Error updating charts:", error);
      this.showError("Failed to update performance charts. Please refresh and try again.");
    }
  }

  /**
     * Update charts selectively based on what changed
     */
  async updateChartsSelectively(metricsData, changes) {
    console.log("📊 PerformanceDashboardComponent: Updating charts selectively based on changes");

    try {
      // Hide loading indicators and show chart canvases
      const chartContainers = [
        "responseTimeChart",
        "successRateChart",
        "serviceBreakdownChart",
        "functionComparisonChart"
      ];

      chartContainers.forEach(chartId => {
        const loadingElement = this.querySelector(`#${chartId}Loading`);
        const canvasElement = this.querySelector(`#${chartId}`);

        if (loadingElement) {
          loadingElement.style.display = "none";
        }

        if (canvasElement) {
          canvasElement.style.display = "block";
        }
      });

      // Update charts based on what changed
      if (changes.functionsChanged || changes.metricsChanged) {
        await this.updateResponseTimeChart(metricsData);
        await this.updateSuccessRateChart(metricsData);
        await this.updateFunctionComparisonChart(metricsData);
      }

      if (changes.servicesChanged) {
        await this.updateServiceBreakdownChart(metricsData);
      }

      console.log("📊 PerformanceDashboardComponent: Selective chart update completed");

    } catch (error) {
      console.error("❌ PerformanceDashboardComponent: Error updating charts selectively:", error);
      this.showError("Failed to update performance charts. Please refresh and try again.");
    }
  }

  /**
     * Check if Chart.js is available
     */
  isChartJSAvailable() {
    return typeof window.Chart === "function";
  }

  /**
     * Update response time chart with line visualization
     */
  async updateResponseTimeChart(metricsData) {
    const chartId = "responseTimeChart";
    const canvas = this.querySelector(`#${chartId}`);

    if (!canvas) {
      console.warn(`⚠️ PerformanceDashboardComponent: Canvas ${chartId} not found`);
      return;
    }

    // Check if Chart.js is available
    if (!this.isChartJSAvailable()) {
      console.error("❌ PerformanceDashboardComponent: Chart.js is not available");
      this.showEmptyChart(canvas, "Chart.js library not loaded");
      return;
    }

    try {
      // Destroy existing chart if it exists
      if (this.charts.has(chartId)) {
        this.charts.get(chartId).destroy();
      }

      // Prepare data for response time visualization
      const chartData = this.prepareResponseTimeData(metricsData);

      if (!chartData || chartData.datasets.length === 0) {
        this.showEmptyChart(canvas, "No response time data available");
        return;
      }

      // Create Chart.js configuration
      const config = {
        type: "line",
        data: chartData,
        options: {
          responsive: true,
          maintainAspectRatio: false,
          aspectRatio: 2,
          interaction: {
            mode: "index",
            intersect: false
          },
          plugins: {
            title: {
              display: true,
              text: "Average Response Times Over Time"
            },
            legend: {
              display: true,
              position: "top"
            },
            tooltip: {
              mode: "index",
              intersect: false,
              callbacks: {
                title: function (context) {
                  return `Time: ${context[0].label}`;
                },
                label: function (context) {
                  const functionName = context.dataset.label;
                  const responseTime = context.parsed.y;
                  return `${functionName}: ${responseTime.toFixed(2)}ms`;
                },
                afterBody: function (context) {
                  // Add additional metrics info in tooltip
                  const dataIndex = context[0].dataIndex;
                  const dataset = context[0].dataset;
                  const additionalInfo = dataset.additionalInfo?.[dataIndex];

                  if (additionalInfo) {
                    return [
                      `Success Rate: ${additionalInfo.successRate}%`,
                      `Total Calls: ${additionalInfo.totalCalls}`
                    ];
                  }
                  return [];
                }
              }
            }
          },
          scales: {
            x: {
              display: true,
              title: {
                display: true,
                text: "Time"
              },
              grid: {
                display: true,
                color: "rgba(0, 0, 0, 0.1)"
              }
            },
            y: {
              display: true,
              title: {
                display: true,
                text: "Response Time (ms)"
              },
              beginAtZero: true,
              grid: {
                display: true,
                color: "rgba(0, 0, 0, 0.1)"
              }
            }
          },
          elements: {
            line: {
              tension: 0.1,
              borderWidth: 2
            },
            point: {
              radius: 4,
              hoverRadius: 6
            }
          }
        }
      };

      // Add zoom functionality if plugin is available
      if (this.zoomEnabled !== false) {
        config.options.plugins.zoom = {
          zoom: {
            wheel: {
              enabled: true
            },
            pinch: {
              enabled: true
            },
            mode: "x"
          },
          pan: {
            enabled: true,
            mode: "x"
          }
        };
      }

      // Set canvas dimensions before creating chart
      this.setCanvasSize(canvas);

      // Create the chart
      const ctx = canvas.getContext("2d");
      const chart = new window.Chart(ctx, config);

      // Store chart reference for cleanup
      this.charts.set(chartId, chart);

      console.log("📊 PerformanceDashboardComponent: Response time chart updated");

    } catch (error) {
      console.error(`❌ PerformanceDashboardComponent: Error updating ${chartId}:`, error);
      this.showEmptyChart(canvas, "Error loading response time chart");
    }
  }

  /**
     * Prepare data for response time chart
     */
  prepareResponseTimeData(metricsData) {
    if (!metricsData.functions || !Array.isArray(metricsData.functions) || metricsData.functions.length === 0) {
      return null;
    }

    // Use the timestamps provided by the backend
    const timeLabels = metricsData.functions[0]?.metrics?.timeSeries?.timestamps || [];

    // Color palette for different functions
    const colors = [
      "rgb(255, 99, 132)",   // Red
      "rgb(54, 162, 235)",   // Blue
      "rgb(255, 205, 86)",   // Yellow
      "rgb(75, 192, 192)",   // Green
      "rgb(153, 102, 255)",  // Purple
      "rgb(255, 159, 64)",   // Orange
      "rgb(199, 199, 199)",  // Grey
      "rgb(83, 102, 147)"    // Dark Blue
    ];

    const datasets = [];

    // Create dataset for each function
    metricsData.functions.forEach((functionData, index) => {
      const timeSeries = functionData.metrics?.timeSeries;
      if (!timeSeries || !timeSeries.responseTimes) {
        return;
      }

      const dataPoints = timeSeries.responseTimes;

      // Additional info for tooltips
      const additionalInfo = dataPoints.map((_, i) => ({
        successRate: timeSeries.successRates?.[i] || 0,
        totalCalls: timeSeries.callCounts?.[i] || 0
      }));

      const color = colors[index % colors.length];

      datasets.push({
        label: functionData.name,
        data: dataPoints,
        borderColor: color,
        backgroundColor: color.replace("rgb", "rgba").replace(")", ", 0.1)"),
        fill: false,
        tension: 0.1,
        additionalInfo: additionalInfo
      });
    });

    return {
      labels: timeLabels,
      datasets: datasets
    };
  }

  /**
     * Update success rate chart with area visualization
     */
  async updateSuccessRateChart(metricsData) {
    const chartId = "successRateChart";
    const canvas = this.querySelector(`#${chartId}`);

    if (!canvas) {
      console.warn(`⚠️ PerformanceDashboardComponent: Canvas ${chartId} not found`);
      return;
    }

    // Check if Chart.js is available
    if (!this.isChartJSAvailable()) {
      console.error("❌ PerformanceDashboardComponent: Chart.js is not available");
      this.showEmptyChart(canvas, "Chart.js library not loaded");
      return;
    }

    try {
      // Destroy existing chart if it exists
      if (this.charts.has(chartId)) {
        this.charts.get(chartId).destroy();
      }

      // Prepare data for success rate visualization
      const chartData = this.prepareSuccessRateData(metricsData);

      if (!chartData || chartData.datasets.length === 0) {
        this.showEmptyChart(canvas, "No success rate data available");
        return;
      }

      // Create Chart.js configuration for area chart
      const config = {
        type: "line",
        data: chartData,
        options: {
          responsive: true,
          maintainAspectRatio: false,
          aspectRatio: 2,
          interaction: {
            mode: "index",
            intersect: false
          },
          plugins: {
            title: {
              display: true,
              text: "Success Rate and Failure Tracking Over Time"
            },
            legend: {
              display: true,
              position: "top"
            },
            tooltip: {
              mode: "index",
              intersect: false,
              callbacks: {
                title: function (context) {
                  return `Time: ${context[0].label}`;
                },
                label: function (context) {
                  const functionName = context.dataset.label;
                  const value = context.parsed.y;
                  const isFailureRate = functionName.includes("Failures");

                  if (isFailureRate) {
                    return `${functionName}: ${value.toFixed(1)}% failure rate`;
                  } else {
                    return `${functionName}: ${value.toFixed(1)}% success rate`;
                  }
                },
                afterBody: function (context) {
                  // Add threshold information
                  const dataIndex = context[0].dataIndex;
                  const dataset = context[0].dataset;
                  const thresholdInfo = dataset.thresholdInfo?.[dataIndex];

                  if (thresholdInfo) {
                    const alerts = [];
                    if (thresholdInfo.exceedsThreshold) {
                      alerts.push(`⚠️ Exceeds threshold: ${thresholdInfo.threshold}%`);
                    }
                    if (thresholdInfo.totalCalls) {
                      alerts.push(`Total calls: ${thresholdInfo.totalCalls}`);
                    }
                    return alerts;
                  }
                  return [];
                }
              }
            }
          },
          scales: {
            x: {
              display: true,
              title: {
                display: true,
                text: "Time"
              },
              grid: {
                display: true,
                color: "rgba(0, 0, 0, 0.1)"
              }
            },
            y: {
              display: true,
              title: {
                display: true,
                text: "Rate (%)"
              },
              beginAtZero: true,
              max: 100,
              grid: {
                display: true,
                color: "rgba(0, 0, 0, 0.1)"
              }
            }
          },
          elements: {
            line: {
              tension: 0.1,
              borderWidth: 2
            },
            point: {
              radius: 3,
              hoverRadius: 5
            }
          }
        }
      };

      // Add zoom functionality if plugin is available
      if (this.zoomEnabled !== false) {
        config.options.plugins.zoom = {
          zoom: {
            wheel: {
              enabled: true
            },
            pinch: {
              enabled: true
            },
            mode: "x"
          },
          pan: {
            enabled: true,
            mode: "x"
          }
        };
      }

      // Set canvas dimensions before creating chart
      this.setCanvasSize(canvas);

      // Create the chart
      const ctx = canvas.getContext("2d");
      const chart = new window.Chart(ctx, config);

      // Store chart reference for cleanup
      this.charts.set(chartId, chart);

      console.log("📊 PerformanceDashboardComponent: Success rate chart updated");

    } catch (error) {
      console.error(`❌ PerformanceDashboardComponent: Error updating ${chartId}:`, error);
      this.showEmptyChart(canvas, "Error loading success rate chart");
    }
  }

  /**
     * Prepare data for success rate chart
     */
  prepareSuccessRateData(metricsData) {
    if (!metricsData.functions || !Array.isArray(metricsData.functions) || metricsData.functions.length === 0) {
      return null;
    }

    // Use the timestamps provided by the backend
    const timeLabels = metricsData.functions[0]?.metrics?.timeSeries?.timestamps || [];

    // Color palette for success/failure visualization
    const successColors = [
      "rgba(75, 192, 192, 0.6)",   // Green
      "rgba(54, 162, 235, 0.6)",   // Blue
      "rgba(153, 102, 255, 0.6)",  // Purple
      "rgba(255, 205, 86, 0.6)"    // Yellow
    ];

    const failureColors = [
      "rgba(255, 99, 132, 0.6)",   // Red
      "rgba(255, 159, 64, 0.6)",   // Orange
      "rgba(199, 199, 199, 0.6)",  // Grey
      "rgba(83, 102, 147, 0.6)"    // Dark Blue
    ];

    const datasets = [];

    // Performance thresholds for alerting
    const successThreshold = 95; // 95% success rate threshold
    const failureThreshold = 5;  // 5% failure rate threshold

    // Create datasets for each function
    metricsData.functions.forEach((functionData, index) => {
      const timeSeries = functionData.metrics?.timeSeries;
      if (!timeSeries || !timeSeries.successRates) {
        return;
      }

      const successDataPoints = timeSeries.successRates;
      const failureDataPoints = successDataPoints.map(success => 100 - success);

      // Create threshold information for tooltips
      const successThresholdInfo = successDataPoints.map((rate, i) => ({
        exceedsThreshold: rate < successThreshold,
        threshold: successThreshold,
        totalCalls: timeSeries.callCounts?.[i] || 0
      }));

      const failureThresholdInfo = failureDataPoints.map((rate, i) => ({
        exceedsThreshold: rate > failureThreshold,
        threshold: failureThreshold,
        totalCalls: timeSeries.callCounts?.[i] || 0
      }));

      // Success rate dataset (area chart)
      datasets.push({
        label: `${functionData.name} Success`,
        data: successDataPoints,
        borderColor: successColors[index % successColors.length].replace("0.6", "1"),
        backgroundColor: successColors[index % successColors.length],
        fill: true,
        tension: 0.1,
        thresholdInfo: successThresholdInfo
      });

      // Failure rate dataset (line chart for spikes)
      datasets.push({
        label: `${functionData.name} Failures`,
        data: failureDataPoints,
        borderColor: failureColors[index % failureColors.length].replace("0.6", "1"),
        backgroundColor: failureColors[index % failureColors.length],
        fill: false,
        tension: 0.1,
        borderWidth: 2,
        pointRadius: function (context) {
          // Highlight failure spikes with larger points
          const value = context.parsed.y;
          return value > failureThreshold ? 6 : 3;
        },
        pointBackgroundColor: function (context) {
          // Red points for threshold violations
          const value = context.parsed.y;
          return value > failureThreshold ? "#ff4444" : failureColors[index % failureColors.length].replace("0.6", "1");
        },
        thresholdInfo: failureThresholdInfo
      });
    });

    // Add threshold lines as datasets
    const thresholdLineData = new Array(timeLabels.length).fill(successThreshold);
    datasets.push({
      label: "Success Threshold (95%)",
      data: thresholdLineData,
      borderColor: "rgba(0, 200, 0, 0.8)",
      backgroundColor: "transparent",
      borderDash: [5, 5],
      borderWidth: 2,
      fill: false,
      pointRadius: 0,
      tension: 0
    });

    const failureThresholdLineData = new Array(timeLabels.length).fill(failureThreshold);
    datasets.push({
      label: "Failure Threshold (5%)",
      data: failureThresholdLineData,
      borderColor: "rgba(200, 0, 0, 0.8)",
      backgroundColor: "transparent",
      borderDash: [5, 5],
      borderWidth: 2,
      fill: false,
      pointRadius: 0,
      tension: 0
    });

    return {
      labels: timeLabels,
      datasets: datasets
    };
  }

  /**
     * Update service breakdown chart with pie/doughnut visualization
     */
  async updateServiceBreakdownChart(metricsData) {
    const chartId = "serviceBreakdownChart";
    const canvas = this.querySelector(`#${chartId}`);

    if (!canvas) {
      console.warn(`⚠️ PerformanceDashboardComponent: Canvas ${chartId} not found`);
      return;
    }

    // Check if Chart.js is available
    if (!this.isChartJSAvailable()) {
      console.error("❌ PerformanceDashboardComponent: Chart.js is not available");
      this.showEmptyChart(canvas, "Chart.js library not loaded");
      return;
    }

    try {
      // Destroy existing chart if it exists
      if (this.charts.has(chartId)) {
        this.charts.get(chartId).destroy();
      }

      // Prepare data for service breakdown visualization
      const chartData = this.prepareServiceBreakdownData(metricsData);

      if (!chartData || chartData.datasets.length === 0) {
        this.showEmptyChart(canvas, "No service breakdown data available");
        return;
      }

      // Create Chart.js configuration for pie chart
      const config = {
        type: "doughnut",
        data: chartData,
        options: {
          responsive: true,
          maintainAspectRatio: false,
          aspectRatio: 2,
          plugins: {
            title: {
              display: true,
              text: "AWS Service Performance Distribution"
            },
            legend: {
              display: true,
              position: "right",
              onClick: (event, legendItem, legend) => {
                // Custom legend click handler for filtering
                this.handleServiceLegendClick(legendItem, legend);
              },
              labels: {
                generateLabels: (chart) => {
                  // Custom legend labels with additional info
                  const data = chart.data;
                  if (data.labels.length && data.datasets.length) {
                    return data.labels.map((label, i) => {
                      const dataset = data.datasets[0];
                      const value = dataset.data[i];
                      const total = dataset.data.reduce((a, b) => a + b, 0);
                      const percentage = ((value / total) * 100).toFixed(1);

                      return {
                        text: `${label} (${percentage}%)`,
                        fillStyle: dataset.backgroundColor[i],
                        strokeStyle: dataset.borderColor[i],
                        lineWidth: dataset.borderWidth,
                        hidden: false,
                        index: i
                      };
                    });
                  }
                  return [];
                }
              }
            },
            tooltip: {
              callbacks: {
                title: function (context) {
                  return `AWS Service: ${context[0].label}`;
                },
                label: function (context) {
                  const serviceName = context.label;
                  const value = context.parsed;
                  const total = context.dataset.data.reduce((a, b) => a + b, 0);
                  const percentage = ((value / total) * 100).toFixed(1);

                  return `${serviceName}: ${value.toFixed(2)}ms (${percentage}%)`;
                },
                afterBody: function (context) {
                  // Add detailed service metrics
                  const serviceIndex = context[0].dataIndex;
                  const serviceData = context[0].dataset.serviceDetails?.[serviceIndex];

                  if (serviceData) {
                    return [
                      `Success Rate: ${serviceData.successRate}%`,
                      `Total Calls: ${serviceData.totalCalls}`,
                      `Avg Duration: ${serviceData.avgDuration}ms`,
                      "Click to view details"
                    ];
                  }
                  return [];
                }
              }
            }
          },
          onClick: (event, elements) => {
            // Handle click for drill-down functionality
            if (elements.length > 0) {
              const elementIndex = elements[0].index;
              const serviceName = chartData.labels[elementIndex];
              this.handleServiceDrillDown(serviceName, metricsData);
            }
          },
          cutout: "50%", // Makes it a doughnut chart
          radius: "80%"
        }
      };

      // Set canvas dimensions before creating chart
      this.setCanvasSize(canvas);

      // Create the chart
      const ctx = canvas.getContext("2d");
      const chart = new window.Chart(ctx, config);

      // Store chart reference for cleanup
      this.charts.set(chartId, chart);

      console.log("📊 PerformanceDashboardComponent: Service breakdown chart updated");

    } catch (error) {
      console.error(`❌ PerformanceDashboardComponent: Error updating ${chartId}:`, error);
      this.showEmptyChart(canvas, "Error loading service breakdown chart");
    }
  }

  /**
     * Prepare data for service breakdown chart
     */
  prepareServiceBreakdownData(metricsData) {
    if (!metricsData.services || typeof metricsData.services !== "object" || metricsData.services === null || Object.keys(metricsData.services).length === 0) {
      return null;
    }

    const services = metricsData.services;
    const serviceNames = Object.keys(services);

    // Color palette for AWS services
    const serviceColors = [
      "#FF6384", // Red - Rekognition
      "#36A2EB", // Blue - S3
      "#FFCE56", // Yellow - Comprehend
      "#4BC0C0", // Teal - Translate
      "#9966FF", // Purple - Cognito
      "#FF9F40", // Orange - Lambda
      "#FF6384", // Pink - DynamoDB
      "#C9CBCF"  // Grey - Other
    ];

    // Prepare chart data
    const labels = [];
    const data = [];
    const backgroundColor = [];
    const borderColor = [];
    const serviceDetails = [];

    serviceNames.forEach((serviceName, index) => {
      const serviceData = services[serviceName];

      // Use average duration as the primary metric for pie chart
      const avgDuration = serviceData.avgDuration || 0;

      if (avgDuration > 0) {
        labels.push(this.formatServiceName(serviceName));
        data.push(avgDuration);

        const color = serviceColors[index % serviceColors.length];
        backgroundColor.push(color);
        borderColor.push(color);

        // Store detailed service information for tooltips
        serviceDetails.push({
          name: serviceName,
          avgDuration: avgDuration,
          successRate: serviceData.successRate || 0,
          totalCalls: serviceData.totalCalls || 0
        });
      }
    });

    if (data.length === 0) {
      return null;
    }

    return {
      labels: labels,
      datasets: [{
        data: data,
        backgroundColor: backgroundColor,
        borderColor: borderColor,
        borderWidth: 2,
        serviceDetails: serviceDetails
      }]
    };
  }

  /**
     * Format service name for display
     */
  formatServiceName(serviceName) {
    const serviceDisplayNames = {
      "rekognition": "Amazon Rekognition",
      "s3": "Amazon S3",
      "comprehend": "Amazon Comprehend",
      "translate": "Amazon Translate",
      "cognito": "Amazon Cognito",
      "lambda": "AWS Lambda",
      "dynamodb": "Amazon DynamoDB"
    };

    return serviceDisplayNames[serviceName.toLowerCase()] ||
      serviceName.charAt(0).toUpperCase() + serviceName.slice(1);
  }

  /**
     * Handle legend click for service filtering
     */
  handleServiceLegendClick(legendItem, _legend) {
    const serviceName = legendItem.text.split(" (")[0]; // Remove percentage
    console.log(`📊 PerformanceDashboardComponent: Service filter clicked: ${serviceName}`);

    // Update service filter dropdown
    const serviceFilter = this.querySelector("#serviceFilter");
    if (serviceFilter) {
      // Find the corresponding option value
      for (const option of serviceFilter.options) {
        if (option.textContent === serviceName) {
          serviceFilter.value = option.value;
          this.handleServiceFilterChange({ target: serviceFilter });
          break;
        }
      }
    }
  }

  /**
     * Handle service drill-down functionality
     */
  handleServiceDrillDown(serviceName, metricsData) {
    console.log(`📊 PerformanceDashboardComponent: Drilling down into service: ${serviceName}`);

    // Show detailed service metrics in a modal or expanded view
    this.showServiceDetails(serviceName, metricsData);
  }

  /**
     * Show detailed service metrics
     */
  showServiceDetails(serviceName, metricsData) {
    const serviceData = metricsData.services[serviceName.toLowerCase()];

    if (!serviceData) {
      console.warn(`⚠️ PerformanceDashboardComponent: No data found for service: ${serviceName}`);
      return;
    }

    // Create a simple modal or alert with service details
    const details = [
      `Service: ${this.formatServiceName(serviceName)}`,
      `Average Duration: ${serviceData.avgDuration?.toFixed(2) || 0}ms`,
      `Success Rate: ${serviceData.successRate?.toFixed(1) || 0}%`,
      `Total Calls: ${serviceData.totalCalls || 0}`,
      "",
      "Click OK to filter dashboard by this service"
    ].join("\n");

    if (confirm(details)) {
      // Apply service filter
      const serviceFilter = this.querySelector("#serviceFilter");
      if (serviceFilter) {
        // Find the option that matches this service
        for (const option of serviceFilter.options) {
          if (option.textContent.toLowerCase().includes(serviceName.toLowerCase())) {
            serviceFilter.value = option.value;
            this.handleServiceFilterChange({ target: serviceFilter });
            break;
          }
        }
      }
    }
  }

  /**
     * Update function comparison chart (placeholder for now)
     */
  async updateFunctionComparisonChart(_metricsData) {
    const chartId = "functionComparisonChart";
    const canvas = this.querySelector(`#${chartId}`);

    if (!canvas) {
      console.warn(`⚠️ PerformanceDashboardComponent: Canvas ${chartId} not found`);
      return;
    }

    try {
      // Destroy existing chart if it exists
      if (this.charts.has(chartId)) {
        this.charts.get(chartId).destroy();
      }

      // For now, show a placeholder message
      this.showEmptyChart(canvas, "Function comparison chart - Coming soon");

      console.log("📊 PerformanceDashboardComponent: Function comparison chart placeholder updated");

    } catch (error) {
      console.error(`❌ PerformanceDashboardComponent: Error updating ${chartId}:`, error);
      this.showEmptyChart(canvas, "Error loading function comparison chart");
    }
  }

  /**
     * Set proper canvas dimensions to prevent expansion
     */
  setCanvasSize(canvas) {
    const container = canvas.parentElement;
    if (container) {
      const containerWidth = container.clientWidth - 48; // Account for padding
      const containerHeight = 320; // Fixed height

      canvas.width = containerWidth;
      canvas.height = containerHeight;
      canvas.style.width = `${containerWidth}px`;
      canvas.style.height = `${containerHeight}px`;
    }
  }

  /**
     * Show empty chart state with message
     */
  showEmptyChart(canvas, message) {
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    ctx.fillStyle = "#666";
    ctx.font = "16px Arial";
    ctx.textAlign = "center";
    ctx.fillText(message, canvas.width / 2, canvas.height / 2);
  }

  /**
     * Show placeholder content on chart canvases
     */
  showChartPlaceholders(metricsData) {
    const chartConfigs = [
      {
        id: "responseTimeChart",
        title: "Response Time Trends",
        dataPoints: metricsData.functions?.length || 0
      },
      {
        id: "successRateChart",
        title: "Success Rate Overview",
        dataPoints: metricsData.functions?.length || 0
      },
      {
        id: "serviceBreakdownChart",
        title: "AWS Service Performance",
        dataPoints: Object.keys(metricsData.services || {}).length
      },
      {
        id: "functionComparisonChart",
        title: "Function Performance Comparison",
        dataPoints: metricsData.functions?.length || 0
      }
    ];

    chartConfigs.forEach(config => {
      const canvas = this.querySelector(`#${config.id}`);
      if (canvas) {
        const ctx = canvas.getContext("2d");

        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Set canvas size with proper constraints
        this.setCanvasSize(canvas);

        // Draw placeholder
        ctx.fillStyle = "#f8fafc";
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        ctx.fillStyle = "#64748b";
        ctx.font = "16px system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";

        const text = `${config.title}\n${config.dataPoints} data points available\n(Chart rendering in task 5)`;
        const lines = text.split("\n");

        lines.forEach((line, index) => {
          ctx.fillText(line, canvas.width / 2, (canvas.height / 2) + (index - 1) * 25);
        });
      }
    });
  }

  /**
     * Update performance alerts display
     */
  updateAlerts(alerts) {
    const alertsContainer = this.querySelector("#performanceAlerts");
    const alertsContent = this.querySelector(".alerts-container");

    if (!alertsContainer || !alertsContent) {
      return;
    }

    if (!alerts || !Array.isArray(alerts) || alerts.length === 0) {
      alertsContainer.style.display = "none";
      return;
    }

    // Show alerts container
    alertsContainer.style.display = "block";

    // Clear existing alerts
    alertsContent.innerHTML = "";

    // Add alert items
    alerts.forEach(alert => {
      const alertElement = document.createElement("div");
      alertElement.className = "alert-item";

      alertElement.innerHTML = `
                <div class="alert-content">
                    <div class="alert-title">${this.formatAlertTitle(alert)}</div>
                    <div class="alert-description">${this.formatAlertDescription(alert)}</div>
                    <div class="alert-timestamp">${new Date(alert.timestamp).toLocaleString()}</div>
                </div>
            `;

      alertsContent.appendChild(alertElement);
    });

    console.log(`📊 PerformanceDashboardComponent: Updated ${alerts.length} alerts`);
  }

  /**
     * Format alert title for display
     */
  formatAlertTitle(alert) {
    const titles = {
      "high_response_time": "High Response Time",
      "low_success_rate": "Low Success Rate",
      "high_error_rate": "High Error Rate",
      "service_degradation": "Service Degradation"
    };

    return titles[alert.type] || "Performance Alert";
  }

  /**
     * Format alert description for display
     */
  formatAlertDescription(alert) {
    switch (alert.type) {
      case "high_response_time":
        return `Function ${alert.function} response time (${alert.current}s) exceeded threshold (${alert.threshold}s)`;
      case "low_success_rate":
        return `Function ${alert.function} success rate (${alert.current}%) below threshold (${alert.threshold}%)`;
      case "high_error_rate":
        return `Function ${alert.function} error rate (${alert.current}%) exceeded threshold (${alert.threshold}%)`;
      case "service_degradation":
        return `AWS service ${alert.service} showing degraded performance`;
      default:
        return alert.message || "Performance threshold exceeded";
    }
  }

  /**
     * Handle network errors with retry logic
     */
  async handleNetworkError(error, retryFunction, maxRetries = 3) {
    console.error("❌ PerformanceDashboardComponent: Network error occurred:", error);

    if (this.retryCount < maxRetries) {
      this.retryCount++;
      console.log(`📊 PerformanceDashboardComponent: Retrying request (${this.retryCount}/${maxRetries})`);

      // Exponential backoff
      const delay = this.retryDelay * Math.pow(2, this.retryCount - 1);
      await new Promise(resolve => setTimeout(resolve, delay));

      try {
        return await retryFunction();
      } catch (retryError) {
        return await this.handleNetworkError(retryError, retryFunction, maxRetries);
      }
    } else {
      this.retryCount = 0;
      throw error;
    }
  }

  /**
   * Update live performance indicators based on metrics data
   */
  updateLivePerformanceIndicators(metricsData) {
    if (!metricsData || !Array.isArray(metricsData.functions)) {
      this.updateHealthBadgeWithAnimation("overallHealthBadge", "unknown", "No Data", "❓");
      return;
    }

    // Calculate overall system metrics
    const systemMetrics = this.calculateSystemMetrics(metricsData);

    // Update health badges with animated transitions
    this.updateHealthBadgeWithAnimation("responseTimeHealthBadge",
      this.getHealthStatus("responseTime", systemMetrics.avgResponseTime),
      `${systemMetrics.avgResponseTime.toFixed(0)}ms`,
      "⚡"
    );

    this.updateHealthBadgeWithAnimation("successRateHealthBadge",
      this.getHealthStatus("successRate", systemMetrics.successRate),
      `${systemMetrics.successRate.toFixed(1)}%`,
      "✅"
    );

    this.updateHealthBadgeWithAnimation("errorRateHealthBadge",
      this.getHealthStatus("errorRate", systemMetrics.errorRate),
      `${systemMetrics.errorRate.toFixed(1)}%`,
      "⚠️"
    );

    // Calculate overall health status
    const overallHealth = this.calculateOverallHealth(systemMetrics);
    this.updateHealthBadgeWithAnimation("overallHealthBadge",
      overallHealth.status,
      overallHealth.label,
      overallHealth.icon
    );

    // Check for performance alerts and create notifications
    this.checkPerformanceAlerts(systemMetrics, metricsData);

    console.log("📊 PerformanceDashboardComponent: Live indicators updated", systemMetrics);
  }

  /**
   * Calculate system-wide metrics from function data
   */
  calculateSystemMetrics(metricsData) {
    const functions = Array.isArray(metricsData.functions) ? metricsData.functions : [];

    if (functions.length === 0) {
      return {
        avgResponseTime: 0,
        successRate: 0,
        errorRate: 100,
        totalCalls: 0
      };
    }

    let totalResponseTime = 0;
    let totalCalls = 0;
    let totalSuccessfulCalls = 0;
    let _validFunctions = 0;

    functions.forEach(func => {
      if (func.metrics) {
        const metrics = func.metrics;
        const calls = metrics.totalCalls || 0;

        if (calls > 0) {
          totalResponseTime += (metrics.avgResponseTime || 0) * calls;
          totalCalls += calls;
          totalSuccessfulCalls += calls * (metrics.successRate || 0) / 100;
          _validFunctions++;
        }
      }
    });

    if (totalCalls === 0) {
      return {
        avgResponseTime: 0,
        successRate: 0,
        errorRate: 100,
        totalCalls: 0
      };
    }

    const avgResponseTime = totalResponseTime / totalCalls;
    const successRate = (totalSuccessfulCalls / totalCalls) * 100;
    const errorRate = 100 - successRate;

    return {
      avgResponseTime,
      successRate,
      errorRate,
      totalCalls
    };
  }

  /**
   * Get health status based on thresholds
   */
  getHealthStatus(metric, value) {
    const thresholds = this.healthThresholds[metric];
    if (!thresholds) { return "unknown"; }

    if (metric === "responseTime") {
      if (value <= thresholds.good) { return "good"; }
      if (value <= thresholds.warning) { return "warning"; }
      return "critical";
    } else if (metric === "successRate") {
      if (value >= thresholds.good) { return "good"; }
      if (value >= thresholds.warning) { return "warning"; }
      return "critical";
    } else if (metric === "errorRate") {
      if (value <= thresholds.good) { return "good"; }
      if (value <= thresholds.warning) { return "warning"; }
      return "critical";
    }

    return "unknown";
  }

  /**
   * Calculate overall system health
   */
  calculateOverallHealth(systemMetrics) {
    const responseTimeHealth = this.getHealthStatus("responseTime", systemMetrics.avgResponseTime);
    const successRateHealth = this.getHealthStatus("successRate", systemMetrics.successRate);
    const errorRateHealth = this.getHealthStatus("errorRate", systemMetrics.errorRate);

    // Determine overall health based on worst metric
    const healthLevels = { "critical": 0, "warning": 1, "good": 2, "unknown": -1 };
    const worstHealth = [responseTimeHealth, successRateHealth, errorRateHealth]
      .reduce((worst, current) => {
        if (healthLevels[current] < healthLevels[worst]) { return current; }
        return worst;
      });

    const healthConfig = {
      "good": { label: "Healthy", icon: "✅" },
      "warning": { label: "Warning", icon: "⚠️" },
      "critical": { label: "Critical", icon: "🔴" },
      "unknown": { label: "Unknown", icon: "❓" }
    };

    return {
      status: worstHealth,
      ...healthConfig[worstHealth]
    };
  }

  /**
   * Update health badge with animated transitions
   */
  updateHealthBadgeWithAnimation(badgeId, status, value, icon) {
    const badge = this.querySelector(`#${badgeId}`);
    if (!badge) { return; }

    const statusElement = badge.querySelector(".badge-status");
    const iconElement = badge.querySelector(".badge-icon");

    if (!statusElement || !iconElement) { return; }

    // Check if status changed for animation
    const previousStatus = this.currentHealthStatus[badgeId.replace("HealthBadge", "").replace("overall", "overall")];
    const statusChanged = previousStatus !== status;

    // Update status tracking
    this.currentHealthStatus[badgeId.replace("HealthBadge", "").replace("overall", "overall")] = status;

    // Apply status-based styling
    badge.className = `health-badge health-${status}`;

    // Update content
    statusElement.textContent = value;
    iconElement.textContent = icon;

    // Add animation if status changed
    if (statusChanged && previousStatus !== "unknown") {
      badge.classList.add("status-changed");
      setTimeout(() => {
        badge.classList.remove("status-changed");
      }, 1000);

      // Log significant status changes
      console.log(`📊 PerformanceDashboardComponent: Health status changed for ${badgeId}: ${previousStatus} → ${status}`);
    }
  }

  /**
   * Check for performance alerts and create notifications
   */
  checkPerformanceAlerts(systemMetrics, _metricsData) {
    const alerts = [];

    // Check response time alerts
    if (systemMetrics.avgResponseTime > this.healthThresholds.responseTime.warning) {
      alerts.push({
        id: "high-response-time",
        type: "warning",
        title: "High Response Time",
        message: `System response time (${systemMetrics.avgResponseTime.toFixed(0)}ms) exceeds threshold`,
        timestamp: new Date(),
        severity: systemMetrics.avgResponseTime > this.healthThresholds.responseTime.warning ? "critical" : "warning"
      });
    }

    // Check success rate alerts
    if (systemMetrics.successRate < this.healthThresholds.successRate.warning) {
      alerts.push({
        id: "low-success-rate",
        type: "error",
        title: "Low Success Rate",
        message: `System success rate (${systemMetrics.successRate.toFixed(1)}%) below threshold`,
        timestamp: new Date(),
        severity: systemMetrics.successRate < this.healthThresholds.successRate.warning ? "critical" : "warning"
      });
    }

    // Check error rate alerts
    if (systemMetrics.errorRate > this.healthThresholds.errorRate.warning) {
      alerts.push({
        id: "high-error-rate",
        type: "error",
        title: "High Error Rate",
        message: `System error rate (${systemMetrics.errorRate.toFixed(1)}%) exceeds threshold`,
        timestamp: new Date(),
        severity: systemMetrics.errorRate > this.healthThresholds.errorRate.warning ? "critical" : "warning"
      });
    }

    // Process alerts
    alerts.forEach(alert => this.processPerformanceAlert(alert));

    // Clean up old notifications
    this.cleanupOldNotifications();
  }

  /**
   * Process a performance alert
   */
  processPerformanceAlert(alert) {
    const existingAlert = this.activeNotifications.get(alert.id);

    if (existingAlert) {
      // Update existing alert if severity changed
      if (existingAlert.severity !== alert.severity) {
        this.activeNotifications.set(alert.id, alert);
        this.updateNotificationDisplay();
      }
    } else {
      // New alert
      this.activeNotifications.set(alert.id, alert);
      this.showNotification(alert);
      this.updateNotificationDisplay();
    }
  }

  /**
   * Show a notification with animation
   */
  showNotification(alert) {
    // Add to notification queue for display
    this.notificationQueue.push(alert);

    // Show notifications panel if hidden
    const notificationsPanel = this.querySelector("#performanceNotifications");
    if (notificationsPanel) {
      notificationsPanel.style.display = "block";
      notificationsPanel.classList.add("notification-show");
    }

    console.log(`📊 PerformanceDashboardComponent: New performance alert: ${alert.title}`);
  }

  /**
   * Update notification display
   */
  updateNotificationDisplay() {
    const notificationList = this.querySelector("#notificationList");
    if (!notificationList) { return; }

    // Clear existing notifications
    notificationList.innerHTML = "";

    // Sort notifications by severity and timestamp
    const sortedNotifications = Array.from(this.activeNotifications.values())
      .sort((a, b) => {
        const severityOrder = { "critical": 0, "warning": 1, "info": 2 };
        if (severityOrder[a.severity] !== severityOrder[b.severity]) {
          return severityOrder[a.severity] - severityOrder[b.severity];
        }
        return b.timestamp - a.timestamp;
      });

    // Create notification elements
    sortedNotifications.forEach(notification => {
      const notificationElement = document.createElement("div");
      notificationElement.className = `notification-item notification-${notification.severity}`;
      notificationElement.innerHTML = `
        <div class="notification-content">
          <div class="notification-header">
            <span class="notification-icon">${this.getNotificationIcon(notification.type)}</span>
            <span class="notification-title">${notification.title}</span>
            <span class="notification-time">${this.formatNotificationTime(notification.timestamp)}</span>
          </div>
          <div class="notification-message">${notification.message}</div>
        </div>
        <button class="notification-dismiss" data-alert-id="${notification.id}">×</button>
      `;

      // Add dismiss event listener
      const dismissBtn = notificationElement.querySelector(".notification-dismiss");
      if (dismissBtn) {
        dismissBtn.addEventListener("click", (e) => {
          this.dismissNotification(e.target.dataset.alertId);
        });
      }

      notificationList.appendChild(notificationElement);
    });

    // Hide panel if no notifications
    if (sortedNotifications.length === 0) {
      const notificationsPanel = this.querySelector("#performanceNotifications");
      if (notificationsPanel) {
        notificationsPanel.style.display = "none";
      }
    }
  }

  /**
   * Get notification icon based on type
   */
  getNotificationIcon(type) {
    const icons = {
      "warning": "⚠️",
      "error": "🔴",
      "info": "ℹ️",
      "success": "✅"
    };
    return icons[type] || "📊";
  }

  /**
   * Format notification timestamp
   */
  formatNotificationTime(timestamp) {
    const now = new Date();
    const diff = now - timestamp;
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);

    if (seconds < 60) {
      return `${seconds}s ago`;
    } else if (minutes < 60) {
      return `${minutes}m ago`;
    } else {
      return timestamp.toLocaleTimeString();
    }
  }

  /**
   * Dismiss a notification
   */
  dismissNotification(alertId) {
    this.activeNotifications.delete(alertId);
    this.updateNotificationDisplay();
    console.log(`📊 PerformanceDashboardComponent: Dismissed alert: ${alertId}`);
  }

  /**
   * Handle close notifications button
   */
  handleCloseNotifications() {
    const notificationsPanel = this.querySelector("#performanceNotifications");
    if (notificationsPanel) {
      notificationsPanel.style.display = "none";
      notificationsPanel.classList.remove("notification-show");
    }

    // Clear all notifications
    this.activeNotifications.clear();
    console.log("📊 PerformanceDashboardComponent: All notifications cleared");
  }

  /**
   * Clean up old notifications (older than 5 minutes)
   */
  cleanupOldNotifications() {
    const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);

    for (const [id, notification] of this.activeNotifications.entries()) {
      if (notification.timestamp < fiveMinutesAgo) {
        this.activeNotifications.delete(id);
      }
    }

    this.updateNotificationDisplay();
  }
}
