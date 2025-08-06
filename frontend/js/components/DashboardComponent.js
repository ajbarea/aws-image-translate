import { BaseComponent } from "./BaseComponent.js";
import { ProfileComponent } from "./ProfileComponent.js";
import { PerformanceDashboardComponent } from "./PerformanceDashboardComponent.js";
const { AWS_CONFIG } = window;

/**
 * Dashboard component displaying user stats, history, and settings access
 */
export class DashboardComponent extends BaseComponent {
  constructor(containerId, authManager, options = {}) {
    super(containerId, options);
    this.auth = authManager;
    this.currentUser = null;
    this.profileModal = null;
    this.performanceDashboard = null;
    this.translationHistory = [];
    this.userStats = {
      imagesProcessed: 0,
      translationsMade: 0,
      mostUsedLanguage: "-"
    };
  }

  async onInit() {
    console.log("📊 DashboardComponent: Initializing dashboard...");

    // Load current user information
    await this.loadUserInfo();

    // Load translation history and stats
    await this.loadTranslationHistory();
    await this.loadUserStats();

    // Initialize performance dashboard
    await this.initializePerformanceDashboard();

    // Setup event listeners for the dashboard
    this.setupDashboardEventListeners();

    console.log("✅ DashboardComponent: Dashboard initialized");
  }

  async loadUserInfo() {
    try {
      this.currentUser = await this.auth.getCurrentUser();
      console.log("👤 DashboardComponent: User info loaded:", {
        username: this.currentUser.username,
        email: this.currentUser.attributes?.email
      });
    } catch (_error) {
      console.log("ℹ️ DashboardComponent: No user info to load; user is not authenticated.");
    }
  }

  async initializePerformanceDashboard() {
    try {
      console.log("📊 DashboardComponent: Initializing performance dashboard...");

      const performancePlaceholder = this.querySelector("#performance-dashboard-placeholder");
      if (!performancePlaceholder) {
        console.warn("⚠️ DashboardComponent: Performance dashboard placeholder not found");
        return;
      }

      // Create performance dashboard component
      this.performanceDashboard = new PerformanceDashboardComponent(
        "performance-dashboard-placeholder",
        this.auth,
        {
          responsive: true,
          autoRefresh: true
        }
      );

      // Initialize the performance dashboard
      await this.performanceDashboard.initialize();

      console.log("✅ DashboardComponent: Performance dashboard initialized");
    } catch (error) {
      console.error("❌ DashboardComponent: Failed to initialize performance dashboard:", error);

      // Show error message in placeholder
      const performancePlaceholder = this.querySelector("#performance-dashboard-placeholder");
      if (performancePlaceholder) {
        performancePlaceholder.innerHTML = `
          <div class="error-message">
            <p>Performance monitoring is currently unavailable.</p>
            <button class="btn-secondary" onclick="location.reload()">Retry</button>
          </div>
        `;
      }
    }
  }

  setupDashboardEventListeners() {
    // Listen for the edit settings button click
    const editSettingsBtn = this.querySelector("#edit-settings-btn");
    if (editSettingsBtn) {
      editSettingsBtn.addEventListener("click", () => this.openSettingsModal());
    }

    // Listen for modal close events
    this.on("settings:closed", () => this.closeSettingsModal());

    // Listen for history item clicks for event delegation
    this.addEventListener(this.container, "click", (e) => {
      const historyItem = e.target.closest(".history-item");
      if (historyItem) {
        const historyId = historyItem.dataset.historyId;
        if (historyId) {
          this.openHistoryDetail(historyId);
        }
      }
    });
  }

  async openSettingsModal() {
    console.log("⚙️ DashboardComponent: Opening settings modal...");

    const modal = this.querySelector("#settingsModal");
    const modalContent = this.querySelector("#settingsModalContent");

    if (!modal || !modalContent) {
      console.error("❌ DashboardComponent: Settings modal elements not found");
      return;
    }

    // Create and initialize ProfileComponent as modal content
    if (!this.profileModal) {
      this.profileModal = new ProfileComponent("settingsModalContent", this.auth, {
        isModal: true // Pass flag to indicate this is modal mode
      });

      // Override the profile component's close behavior
      this.profileModal.closeProfile = () => {
        this.emit("settings:closed");
      };
    }

    // Initialize the profile component
    await this.profileModal.initialize();

    // Show the modal
    modal.style.display = "flex";

    // Add click-outside-to-close functionality
    modal.addEventListener("click", (e) => {
      if (e.target === modal) {
        this.closeSettingsModal();
      }
    });

    // Add escape key to close
    document.addEventListener("keydown", this.handleEscapeKey.bind(this));
  }

  closeSettingsModal() {
    console.log("⚙️ DashboardComponent: Closing settings modal...");

    const modal = this.querySelector("#settingsModal");
    if (modal) {
      modal.style.display = "none";
    }

    // Remove escape key listener
    document.removeEventListener("keydown", this.handleEscapeKey.bind(this));
  }

  handleEscapeKey(e) {
    if (e.key === "Escape") {
      this.closeSettingsModal();
    }
  }

  async refresh() {
    console.log("🔄 DashboardComponent: Refreshing dashboard data...");
    await this.loadUserInfo();
    await this.loadTranslationHistory();
    await this.loadUserStats();

    // Refresh performance dashboard if it exists
    if (this.performanceDashboard && typeof this.performanceDashboard.refresh === "function") {
      try {
        await this.performanceDashboard.refresh();
      } catch (error) {
        console.error("❌ DashboardComponent: Failed to refresh performance dashboard:", error);
      }
    }
  }

  destroy() {
    // Cleanup performance dashboard
    if (this.performanceDashboard && typeof this.performanceDashboard.destroy === "function") {
      try {
        this.performanceDashboard.destroy();
        this.performanceDashboard = null;
        console.log("🧹 DashboardComponent: Performance dashboard cleaned up");
      } catch (error) {
        console.error("❌ DashboardComponent: Error cleaning up performance dashboard:", error);
      }
    }

    // Cleanup profile modal
    if (this.profileModal && typeof this.profileModal.destroy === "function") {
      try {
        this.profileModal.destroy();
        this.profileModal = null;
      } catch (error) {
        console.error("❌ DashboardComponent: Error cleaning up profile modal:", error);
      }
    }

    // Call parent cleanup
    super.destroy();

    console.log("🧹 DashboardComponent: Component destroyed and cleaned up");
  }

  async loadTranslationHistory() {
    try {
      if (!this.currentUser) {
        console.log("ℹ️ DashboardComponent: No user authenticated, skipping history load");
        return;
      }

      const data = await this.auth.makeAuthenticatedRequest(`${AWS_CONFIG.apiGatewayUrl}/history`);

      console.log("📜 DashboardComponent: History response received successfully");

      this.translationHistory = data.history || [];
      this.updateHistoryDisplay();
      console.log("📜 DashboardComponent: Translation history loaded:", this.translationHistory.length, "items");

    } catch (error) {
      console.error("❌ DashboardComponent: Error loading translation history:", error);
      this.showEmptyHistoryMessage();
    }
  }

  async loadUserStats() {
    try {
      if (!this.translationHistory.length) {
        this.updateStatsDisplay(this.userStats);
        return;
      }

      // Calculate stats from translation history
      const stats = {
        imagesProcessed: this.translationHistory.length,
        translationsMade: this.translationHistory.length,
        mostUsedLanguage: this.getMostUsedLanguage()
      };

      this.userStats = stats;
      this.updateStatsDisplay(stats);
      console.log("📊 DashboardComponent: User stats calculated:", stats);
    } catch (error) {
      console.error("❌ DashboardComponent: Error calculating user stats:", error);
      this.updateStatsDisplay(this.userStats);
    }
  }

  updateStatsDisplay(stats) {
    const statCards = this.querySelectorAll(".stat-card");
    if (statCards.length >= 3) {
      statCards[0].querySelector(".stat-number").textContent = stats.imagesProcessed;
      statCards[1].querySelector(".stat-number").textContent = stats.translationsMade;
      statCards[2].querySelector(".stat-number").textContent = stats.mostUsedLanguage;
    }
  }

  updateHistoryDisplay() {
    const historyContainer = this.querySelector(".history-placeholder");
    if (!historyContainer) { return; }

    if (this.translationHistory.length === 0) {
      this.showEmptyHistoryMessage();
      return;
    }

    const historyHTML = this.translationHistory
      .sort((a, b) => new Date(b.created_on) - new Date(a.created_on))
      .slice(0, 10) // Show last 10 translations
      .map(item => `
                <div class="history-item" data-history-id="${item.history_id}">
                    <div class="history-item-content">
                        <div class="history-image-name">${item.image_name}</div>
                        <div class="history-languages">${item.src_lang} → ${item.t_lang}</div>
                        <div class="history-date">${new Date(item.created_on).toLocaleDateString()}</div>
                    </div>
                </div>
            `).join("");

    historyContainer.innerHTML = `
            <div class="history-list">
                ${historyHTML}
            </div>
        `;
  }

  showEmptyHistoryMessage() {
    const historyContainer = this.querySelector(".history-placeholder");
    if (historyContainer) {
      historyContainer.innerHTML = `
                <p class="no-data-message">Your translation history will appear here once you start using the service.</p>
            `;
    }
  }

  getMostUsedLanguage() {
    if (!this.translationHistory.length) { return "-"; }

    const languageCounts = {};
    this.translationHistory.forEach(item => {
      const pair = `${item.src_lang} → ${item.t_lang}`;
      languageCounts[pair] = (languageCounts[pair] || 0) + 1;
    });

    const mostUsed = Object.entries(languageCounts)
      .sort(([, a], [, b]) => b - a)[0];

    return mostUsed ? mostUsed[0] : "-";
  }

  async openHistoryDetail(historyId) {
    try {
      const url = `${AWS_CONFIG.apiGatewayUrl}/history/${historyId}`;
      const historyDetail = await this.auth.makeAuthenticatedRequest(url);
      this.showHistoryDetailModal(historyDetail);
    } catch (error) {
      console.error("❌ DashboardComponent: Error loading history detail:", error);
    }
  }

  showHistoryDetailModal(detail) {
    // Simple modal to show translation details
    const modal = document.createElement("div");
    modal.className = "history-detail-modal-overlay";
    modal.innerHTML = `
            <div class="history-detail-modal">
                <div class="history-detail-header">
                    <h3>Translation Details</h3>
                    <button class="close-btn">&times;</button>
                </div>
                <div class="history-detail-content">
                    <div class="detail-section">
                        <label>Image:</label>
                        <span>${detail.image_name}</span>
                    </div>
                    <div class="detail-section">
                        <label>Source (${detail.src_lang}):</label>
                        <div class="text-content">${detail.src_text || "No text extracted"}</div>
                    </div>
                    <div class="detail-section">
                        <label>Translation (${detail.t_lang}):</label>
                        <div class="text-content">${detail.t_text || "No translation available"}</div>
                    </div>
                </div>
            </div>
        `;

    document.body.appendChild(modal);

    // Close modal handlers
    const closeBtn = modal.querySelector(".close-btn");
    const closeModal = () => {
      document.body.removeChild(modal);
    };

    closeBtn.addEventListener("click", closeModal);
    modal.addEventListener("click", (e) => {
      if (e.target === modal) { closeModal(); }
    });

    document.addEventListener("keydown", function escHandler(e) {
      if (e.key === "Escape") {
        closeModal();
        document.removeEventListener("keydown", escHandler);
      }
    });
  }
}
