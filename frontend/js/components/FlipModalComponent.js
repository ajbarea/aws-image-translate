import { BaseComponent } from "./BaseComponent.js";
import { LanguageSelectionComponent } from "./LanguageSelectionComponent.js";
import { getLanguageName } from "../constants/languages.js";

// Cache for translation results
const translationCache = {};

/**
 * Modal component for image translation with flip card interface
 */
export class FlipModalComponent extends BaseComponent {
  constructor(containerId, options = {}) {
    super(containerId, options);

    this.modalElement = null;
    this.flipCard = null;
    this.closeButton = null;
    this.flipButton = null;
    this.resultsContent = null;

    this.languageSelectionComponent = null;
    this.currentImageData = null;
    this.currentResults = null;
    this.isFlipped = false;

    // Bind methods
    this.open = this.open.bind(this);
    this.close = this.close.bind(this);
    this.toggle = this.toggle.bind(this);
    this.handleCloseClick = this.handleCloseClick.bind(this);
    this.handleModalClick = this.handleModalClick.bind(this);
    this.handleFlipClick = this.handleFlipClick.bind(this);
    this.handleEscapeKey = this.handleEscapeKey.bind(this);
    this.handleLanguageChange = this.handleLanguageChange.bind(this);
  }

  async onInit() {
    // Get DOM elements
    this.modalElement = this.container;
    this.flipCard = this.modalElement.querySelector("#flip-card");
    this.closeButton = this.modalElement.querySelector("#close-modal");
    this.flipButton = this.modalElement.querySelector("#flip-button");
    this.resultsContent = this.modalElement.querySelector("#results-content");

    if (
      !this.flipCard ||
      !this.closeButton ||
      !this.flipButton ||
      !this.resultsContent
    ) {
      throw new Error("Required modal elements not found");
    }

    // Initialize modal structure and language selection
    await this.initializeModalStructure();
    await this.initializeLanguageSelection();
  }

  setupEventListeners() {
    // Modal controls
    this.addEventListener(this.closeButton, "click", this.handleCloseClick);
    this.addEventListener(this.modalElement, "click", this.handleModalClick);
    this.addEventListener(this.flipButton, "click", this.handleFlipClick);

    // Global events
    this.addEventListener(document, "keydown", this.handleEscapeKey);
    this.addEventListener(document, "language:changed", this.handleLanguageChange);

    // Image preview clicks
    this.addEventListener(this.resultsContent, "click", this.handleResultsClick);
    this.addEventListener(document, "click", this.handleHeaderImageClick);
  }

  async initializeModalStructure() {
    const flipCardInner = this.flipCard.querySelector(".flip-card-inner");
    if (!flipCardInner || !flipCardInner.querySelector(".flip-card-front")) {
      flipCardInner.innerHTML = `
        <div class="flip-card-front">
          <img id="modal-image" src="" alt="">
        </div>
        <div class="flip-card-back">
          <div class="results-modal-container">
            <div class="results-modal-header">
              <div id="modal-language-selection-placeholder">
                <!-- Language selection component will be populated here -->
              </div>
            </div>
            <div class="results-modal-content" id="results-content">
              <!-- Results will be populated here -->
            </div>
          </div>
        </div>
      `;
    }
  }

  async initializeLanguageSelection() {
    try {
      // Load language selection component HTML
      const response = await fetch("components/language-selection.html");
      const html = await response.text();

      const placeholder = document.getElementById(
        "modal-language-selection-placeholder"
      );
      if (placeholder) {
        // Add header above language selection
        placeholder.innerHTML = `
          <div class="result-header" id="modal-result-header" style="display: none;">
            <div class="upload-image-preview" data-image-url="" data-image-name="" title="View original image">
              <img src="" alt="" />
            </div>
            <h3 class="result-title"></h3>
          </div>
          ${html}
        `;

        // Update IDs for modal context
        const label = placeholder.querySelector('label[for="targetLanguage"]');
        const select = placeholder.querySelector("#targetLanguage");

        if (label) {
          label.setAttribute("for", "modalTargetLanguage");
        }
        if (select) {
          select.setAttribute("id", "modalTargetLanguage");
        }

        // Initialize language selection component
        this.languageSelectionComponent = new LanguageSelectionComponent(
          "modal-language-selection-placeholder",
          {
            defaultLanguage: "en"
          }
        );

        await this.languageSelectionComponent.initialize();
        console.log("Language selection component initialized");
      }
    } catch (error) {
      console.error("Failed to initialize language selection:", error);
    }
  }

  /**
   * Open modal with image data
   */
  open(imageData) {
    if (!imageData) {
      console.error("No image data provided");
      return;
    }

    this.currentImageData = imageData;
    this.currentResults = null;

    // Set modal image
    const modalImg = this.modalElement.querySelector("#modal-image");
    if (modalImg) {
      modalImg.src = imageData.src;
      modalImg.alt = imageData.alt;
    }

    this.modalElement.classList.add("active");
    this.resetFlipState();

    console.log("Modal opened with image:", imageData.alt);
  }

  /**
   * Close modal
   */
  close() {
    this.modalElement.classList.remove("active");
    this.resetFlipState();

    if (this.resultsContent) {
      this.resultsContent.innerHTML = "";
    }

    this.currentImageData = null;
    console.log("Modal closed");
  }

  /**
   * Toggle flip state
   */
  toggle() {
    if (this.isFlipped) {
      this.flipToImage();
    } else {
      this.flipToResults();
    }
  }

  /**
   * Reset flip to show image
   */
  resetFlipState() {
    this.flipCard.classList.remove("flipped");
    this.flipButton.textContent = "Translate Image";
    this.isFlipped = false;
    this.hideResultHeader();
  }

  /**
   * Flip to show image
   */
  flipToImage() {
    this.flipCard.classList.remove("flipped");
    this.flipButton.textContent = "Translate Image";
    this.isFlipped = false;
    this.hideResultHeader();
  }

  /**
   * Flip to show results
   */
  async flipToResults() {
    this.flipCard.classList.add("flipped");
    this.flipButton.textContent = "Back to Image";
    this.isFlipped = true;
    this.updateResultHeader();

    if (this.currentImageData) {
      const targetLang = this.getSelectedLanguage();
      await this.fetchAndRenderResults(targetLang);
    }
  }

  /**
   * Fetch and render translation results
   */
  async fetchAndRenderResults(targetLanguage) {
    const cacheKey = `${this.currentImageData.key}_${targetLanguage}`;

    if (translationCache[cacheKey]) {
      console.log("Using cached translation for", cacheKey);
      this.currentResults = translationCache[cacheKey];
      this.resultsContent.innerHTML = this.generateResultsHTML(this.currentResults);
      return;
    }

    this.resultsContent.innerHTML = "<p>⏳ Processing image, please wait...</p>";

    try {
      this.emit("flipmodal:translateRequest", {
        imageData: this.currentImageData,
        targetLanguage,
        currentResults: this.currentResults,
        callback: (error, results) => {
          if (error) {
            throw error;
          }
          this.currentResults = results;
          translationCache[cacheKey] = results;
          this.resultsContent.innerHTML = this.generateResultsHTML(results);
        }
      });
    } catch (error) {
      console.error("Translation processing failed:", error);
      this.resultsContent.innerHTML = `<div class="result-error-section">❌ Failed to process image: ${error.message}</div>`;
    }
  }

  /**
   * Update result header with current image
   */
  updateResultHeader() {
    const resultHeader = document.getElementById("modal-result-header");
    if (resultHeader && this.currentImageData) {
      const imagePreview = resultHeader.querySelector(".upload-image-preview");
      const img = resultHeader.querySelector("img");
      const title = resultHeader.querySelector(".result-title");

      if (imagePreview && img && title) {
        imagePreview.setAttribute("data-image-url", this.currentImageData.src);
        imagePreview.setAttribute("data-image-name", this.escapeHtml(this.currentImageData.alt));
        img.src = this.currentImageData.src;
        img.alt = this.escapeHtml(this.currentImageData.alt);
        title.textContent = this.currentImageData.alt;
      }
    }
  }

  /**
   * Hide result header
   */
  hideResultHeader() {
    const resultHeader = document.getElementById("modal-result-header");
    if (resultHeader) {
      resultHeader.style.display = "none";
    }
  }

  /**
   * Generate HTML for translation results
   */
  generateResultsHTML(results) {
    const detectedLangName = getLanguageName(results.detectedLanguage || "");
    const targetLangName = getLanguageName(results.targetLanguage || "");

    return `
      <div class="result-item">
        ${results.detectedText
    ? `<div class="result-section">
              <div class="result-section-header">
                <span class="result-label-detected">🔍 Detected Text:</span>
              </div>
              <div class="result-text-box result-detected-text">
                ${this.escapeHtml(results.detectedText)}
              </div>
            </div>`
    : ""}

        ${results.detectedLanguage
    ? `<div data-section="detected-language" class="result-section">
              <div class="result-section-header">
                <span class="result-label-language">🌍 Detected Language:</span>
                <span class="result-language-badge">${detectedLangName}</span>
              </div>
            </div>`
    : ""}

        ${results.translatedText && results.translatedText !== results.detectedText
    ? `<div data-section="translation" class="result-section">
              <div class="result-section-header">
                <span class="result-label-translation">🔄 Translation Language:</span>
                <span class="result-language-badge">${targetLangName}</span>
              </div>
              <div class="result-text-box result-translation-text">
                ${this.escapeHtml(results.translatedText)}
              </div>
            </div>`
    : ""}

        ${(results.detectedText || "").trim() === "" ? "<div class=\"result-no-data\">No text detected in this image.</div>" : ""}
      </div>
    `;
  }

  /**
   * Update results when language changes
   */
  async updateResultsWithLanguage() {
    if (this.isFlipped && this.currentImageData) {
      const targetLang = this.getSelectedLanguage();
      await this.fetchAndRenderResults(targetLang);
    }
  }

  // Event Handlers
  handleCloseClick(e) {
    e.preventDefault();
    this.close();
  }

  handleModalClick(e) {
    if (e.target === this.modalElement) {
      this.close();
    }
  }

  handleFlipClick(e) {
    e.preventDefault();
    this.toggle();
  }

  handleEscapeKey(e) {
    if (e.key === "Escape" && this.modalElement.classList.contains("active")) {
      this.close();
    }
  }

  handleLanguageChange(e) {
    const { language } = e.detail;
    console.log(`Language changed to: ${language}`);
    this.updateResultsWithLanguage();
  }

  handleResultsClick(e) {
    // Handle image preview clicks in results
    const imagePreview = e.target.closest(".upload-image-preview");
    if (imagePreview) {
      e.preventDefault();
      e.stopPropagation();

      if (this.isFlipped) {
        this.flipToImage();
        console.log("Flipped to image via results click");
      }
    }
  }

  handleHeaderImageClick(e) {
    // Handle image preview clicks in header
    const imagePreview = e.target.closest("#modal-result-header .upload-image-preview");
    if (imagePreview && this.modalElement.classList.contains("active")) {
      e.preventDefault();
      e.stopPropagation();

      if (this.isFlipped) {
        this.flipToImage();
        console.log("Flipped to image via header click");
      }
    }
  }

  /**
   * Check if modal is open
   */
  isOpen() {
    return this.modalElement.classList.contains("active");
  }

  /**
   * Get current image data
   */
  getCurrentImageData() {
    return this.currentImageData;
  }

  /**
   * Get selected language
   */
  getSelectedLanguage() {
    return this.languageSelectionComponent
      ? this.languageSelectionComponent.getSelectedLanguage()
      : "en";
  }

  /**
   * Escape HTML to prevent XSS
   */
  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }
}
