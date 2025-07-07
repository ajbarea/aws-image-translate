import { BaseComponent } from "./BaseComponent.js";

/**
 * Results display component for showing processing results
 */
export class ResultsComponent extends BaseComponent {
  constructor(containerId, options = {}) {
    super(containerId, options);
    this.results = [];
    this.noTextResults = [];
  }

  async onInit() {
    this.resultsContainer = this.container;
    if (!this.resultsContainer) {
      throw new Error("Results container not found");
    }

    this.resultsContainer.id = "results";
    this.resultsContainer.classList.add("hidden");

    this.resultsContainer.innerHTML = `
      <div id="successful-results" class="results-section"></div>
      <div id="no-text-results" class="results-section hidden">
        <h3 class="no-text-title">📷 Images with No Text Detected</h3>
        <p class="no-text-description">The following images were processed but no text was found:</p>
        <div class="no-text-list"></div>
      </div>
    `;

    this.successfulResultsContainer = this.resultsContainer.querySelector(
      "#successful-results"
    );
    this.noTextResultsContainer =
      this.resultsContainer.querySelector("#no-text-results");
    this.noTextList = this.resultsContainer.querySelector(".no-text-list");
  }

  setupEventListeners() {
    this.on("queue:itemUpdated", this.handleQueueItemUpdated.bind(this));
    this.on("language:changed", this.handleLanguageChanged.bind(this));
    this.addEventListener(
      this.container,
      "click",
      this.handleButtonClick.bind(this)
    );
  }

  handleButtonClick(e) {
    if (e.target.matches(".result-remove-btn")) {
      const itemId = e.target.dataset.itemId;
      this.removeResult(itemId);
      this.emit("result:removed", { itemId });
    } else if (e.target.matches(".no-text-remove-btn")) {
      const itemId = e.target.dataset.itemId;
      this.removeNoTextResult(itemId);
      this.updateContainerVisibility();
      this.emit("result:removed", { itemId });
    } else if (
      e.target.matches(".upload-image-preview") ||
      e.target.closest(".upload-image-preview")
    ) {
      const button = e.target.closest(".upload-image-preview") || e.target;
      const imageUrl = button.dataset.imageUrl;
      const imageName = button.dataset.imageName;
      this.openImageModal(imageUrl, imageName);
    }
  }

  handleQueueItemUpdated(e) {
    const { item } = e.detail;
    if (item.status === "complete" && item.processingResults) {
      const results =
        typeof item.processingResults === "string"
          ? JSON.parse(item.processingResults)
          : item.processingResults;

      if (results.detectedText && results.detectedText.trim()) {
        this.addResult(item);
      } else {
        this.addNoTextResult(item);
      }
    }
  }

  async handleLanguageChanged(e) {
    const { language } = e.detail;
    console.log(`📝 Results: Re-translating all results to ${language}`);
    await this.retranslateAllResults(language);
  }

  addResult(item) {
    console.log(`📊 Results: Adding result for ${item.file.name}`);

    this.removeResult(item.id);

    const resultElement = this.createResultElement(item);
    this.successfulResultsContainer.appendChild(resultElement);

    this.results.push({
      id: item.id,
      item,
      element: resultElement,
    });

    this.resultsContainer.classList.remove("hidden");
  }

  addNoTextResult(item) {
    console.log(`📊 Results: Adding no-text result for ${item.file.name}`);

    this.removeNoTextResult(item.id);

    const noTextElement = this.createNoTextElement(item);
    this.noTextList.appendChild(noTextElement);

    this.noTextResults.push({
      id: item.id,
      item,
      element: noTextElement,
    });

    this.resultsContainer.classList.remove("hidden");
    this.noTextResultsContainer.classList.remove("hidden");
  }

  removeResult(itemId) {
    const resultIndex = this.results.findIndex(
      (result) => result.id === itemId
    );
    if (resultIndex !== -1) {
      const result = this.results[resultIndex];

      const imagePreview = result.element?.querySelector(
        ".upload-image-preview"
      );
      if (imagePreview?.dataset.imageUrl) {
        URL.revokeObjectURL(imagePreview.dataset.imageUrl);
      }

      if (result.element && result.element.parentNode) {
        result.element.remove();
      }
      this.results.splice(resultIndex, 1);
    }

    this.removeNoTextResult(itemId);

    this.updateContainerVisibility();
  }

  removeNoTextResult(itemId) {
    const noTextIndex = this.noTextResults.findIndex(
      (result) => result.id === itemId
    );
    if (noTextIndex !== -1) {
      const result = this.noTextResults[noTextIndex];

      const imagePreview = result.element?.querySelector(
        ".no-text-image-preview"
      );
      if (imagePreview?.dataset.imageUrl) {
        URL.revokeObjectURL(imagePreview.dataset.imageUrl);
      }

      if (result.element && result.element.parentNode) {
        result.element.remove();
      }
      this.noTextResults.splice(noTextIndex, 1);
    }

    if (this.noTextResults.length === 0) {
      this.noTextResultsContainer.classList.add("hidden");
    }
  }

  updateContainerVisibility() {
    const hasResults = this.results.length > 0 || this.noTextResults.length > 0;

    if (hasResults) {
      this.resultsContainer.classList.remove("hidden");
    } else {
      this.resultsContainer.classList.add("hidden");
    }
  }

  createResultElement(item) {
    const resultDiv = document.createElement("div");
    resultDiv.className = "result-item";
    resultDiv.setAttribute("data-item-id", item.id);

    // Create image preview URL
    const imageUrl = item.file ? URL.createObjectURL(item.file) : "";

    let resultHTML = `
      <div class="result-header">
        <button class="upload-image-preview" data-image-url="${imageUrl}" data-image-name="${this.escapeHtml(
      item.file.name
    )}" title="View original image">
          <img src="${imageUrl}" alt="${this.escapeHtml(item.file.name)}" />
        </button>
        <h3 class="result-title">${item.file.name}</h3>
        <button class="result-remove-btn" data-item-id="${
          item.id
        }" title="Remove result">×</button>
      </div>
    `;

    if (item.processingResults) {
      const results =
        typeof item.processingResults === "string"
          ? JSON.parse(item.processingResults)
          : item.processingResults;

      // Detected text section
      if (results.detectedText) {
        resultHTML += `
          <div class="result-section">
            <div class="result-section-header">
              <span class="result-label-detected">🔍 Detected Text:</span>
            </div>
            <div class="result-text-box result-detected-text">
              ${this.escapeHtml(results.detectedText)}
            </div>
          </div>
        `;
      }

      // Detected language section
      if (results.detectedLanguage) {
        const detectedLangName = this.getLanguageName(results.detectedLanguage);
        resultHTML += `
          <div data-section="detected-language" class="result-section">
            <div class="result-section-header">
              <span class="result-label-language">🌍 Detected Language:</span>
              <span class="result-language-badge">
                ${detectedLangName}
              </span>
            </div>
          </div>
        `;
      }

      // Translation section
      if (
        results.translatedText &&
        results.translatedText !== results.detectedText
      ) {
        const targetLang = results.targetLanguage || "en";
        const targetLangName = this.getLanguageName(targetLang);
        resultHTML += `
          <div data-section="translation" class="result-section">
            <div class="result-section-header">
              <span class="result-label-translation">🔄 Translation Language:</span>
              <span class="result-language-badge">
                ${targetLangName}
              </span>
            </div>
            <div class="result-text-box result-translation-text">
              ${this.escapeHtml(results.translatedText)}
            </div>
          </div>
        `;
      }

      // S3 location section
      if (results.bucket && results.key) {
        resultHTML += `
          <div class="result-footer">
            <span class="result-s3-location">
              📁 S3 Location: s3://${results.bucket}/${results.key}
            </span>
          </div>
        `;
      }
    } else {
      resultHTML += `
        <div class="result-no-data">
          Processing completed but no detailed results available.
        </div>
      `;
    }

    if (item.error) {
      resultHTML += `
        <div class="result-error-section">
          ❌ Error: ${this.escapeHtml(item.error)}
        </div>
      `;
    }

    resultDiv.innerHTML = resultHTML;

    // Add click handler for remove button
    const removeBtn = resultDiv.querySelector(".result-remove-btn");
    if (removeBtn) {
      this.addEventListener(removeBtn, "click", () => {
        this.removeResult(item.id);
        this.emit("result:removed", { itemId: item.id });
      });
    }

    return resultDiv;
  }

  createNoTextElement(item) {
    const noTextDiv = document.createElement("div");
    noTextDiv.className = "no-text-item";
    noTextDiv.setAttribute("data-item-id", item.id);

    // Create image preview URL
    const imageUrl = item.file ? URL.createObjectURL(item.file) : "";

    const fileSize = item.file.size
      ? this.formatFileSize(item.file.size)
      : "Unknown size";

    noTextDiv.innerHTML = `
      <div class="no-text-item-content">
        <button class="upload-image-preview no-text-image-preview" data-image-url="${imageUrl}" data-image-name="${this.escapeHtml(
      item.file.name
    )}" title="View image">
          <img src="${imageUrl}" alt="${this.escapeHtml(item.file.name)}" />
        </button>
        <div class="no-text-item-info">
          <span class="no-text-item-name">${this.escapeHtml(
            item.file.name
          )}</span>
          <span class="no-text-item-size">${fileSize}</span>
        </div>
        <button class="no-text-remove-btn" data-item-id="${
          item.id
        }" title="Remove from list">×</button>
      </div>
    `;

    return noTextDiv;
  }

  formatFileSize(bytes) {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  }

  async retranslateAllResults(targetLanguage) {
    console.log(`📝 Results: Re-translating ${this.results.length} results`);

    for (const result of this.results) {
      if (result.item.processingResults?.detectedText) {
        await this.retranslateResult(result, targetLanguage);
      }
    }
  }

  async retranslateResult(result, targetLanguage) {
    const { item } = result;

    if (!item.processingResults?.detectedText) {
      console.log(
        `📝 Results: No detected text to translate for ${item.file.name}`
      );
      return;
    }

    try {
      console.log(
        `🔄 Results: Re-translating ${item.file.name} to ${targetLanguage}`
      );

      // Emit event to request translation (the main app will handle the API call)
      this.emit("result:retranslateRequest", {
        item,
        targetLanguage,
        callback: (translationResult) => {
          this.updateTranslation(result, translationResult, targetLanguage);
        },
      });
    } catch (error) {
      console.error(
        `❌ Results: Translation error for ${item.file.name}:`,
        error
      );
      this.showError(
        `Translation failed for ${item.file.name}: ${error.message}`
      );
    }
  }

  updateTranslation(result, translationResult, targetLanguage) {
    const { item, element } = result;

    // Update the item's processing results
    if (item.processingResults) {
      if (typeof item.processingResults === "string") {
        item.processingResults = JSON.parse(item.processingResults);
      }
      item.processingResults.translatedText = translationResult.translatedText;
      item.processingResults.targetLanguage = targetLanguage;
    }

    // Update the DOM
    this.updateTranslationSection(element, item, targetLanguage);
  }

  updateTranslationSection(resultElement, item, targetLanguage) {
    if (!item.processingResults) return;

    const results =
      typeof item.processingResults === "string"
        ? JSON.parse(item.processingResults)
        : item.processingResults;

    // Find existing translation section
    const existingTranslationDiv = resultElement.querySelector(
      '[data-section="translation"]'
    );

    if (
      results.translatedText &&
      results.translatedText !== results.detectedText
    ) {
      const targetLangName = this.getLanguageName(targetLanguage);

      const translationHTML = `
        <div data-section="translation" class="result-section">
          <div class="result-section-header">
            <span class="result-label-translation">🔄 Translation Language:</span>
            <span class="result-language-badge">
              ${targetLangName}
            </span>
          </div>
          <div class="result-text-box result-translation-text">
            ${this.escapeHtml(results.translatedText)}
          </div>
        </div>
      `;

      if (existingTranslationDiv) {
        // Replace existing translation section
        existingTranslationDiv.outerHTML = translationHTML;
      } else {
        // Add new translation section after detected language
        const detectedLanguageDiv = resultElement.querySelector(
          '[data-section="detected-language"]'
        );
        if (detectedLanguageDiv) {
          detectedLanguageDiv.insertAdjacentHTML("afterend", translationHTML);
        }
      }
    } else if (existingTranslationDiv) {
      // Remove translation section if no translation needed
      existingTranslationDiv.remove();
    }
  }

  getLanguageName(languageCode) {
    const languageMap = {
      en: "English",
      es: "Spanish",
      fr: "French",
      de: "German",
      it: "Italian",
      pt: "Portuguese",
      ru: "Russian",
      ja: "Japanese",
      ko: "Korean",
      zh: "Chinese (Simplified)",
      "zh-TW": "Chinese (Traditional)",
      ar: "Arabic",
      hi: "Hindi",
      th: "Thai",
      vi: "Vietnamese",
      nl: "Dutch",
      pl: "Polish",
      tr: "Turkish",
      sv: "Swedish",
      da: "Danish",
      no: "Norwegian",
      fi: "Finnish",
      cs: "Czech",
      hu: "Hungarian",
      ro: "Romanian",
      bg: "Bulgarian",
      hr: "Croatian",
      sk: "Slovak",
      sl: "Slovenian",
      et: "Estonian",
      lv: "Latvian",
      lt: "Lithuanian",
      mt: "Maltese",
      ga: "Irish",
      cy: "Welsh",
    };
    return languageMap[languageCode] || languageCode;
  }

  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  clearResults() {
    // Clean up object URLs to prevent memory leaks
    this.results.forEach((result) => {
      const imagePreview = result.element?.querySelector(
        ".upload-image-preview"
      );
      if (imagePreview?.dataset.imageUrl) {
        URL.revokeObjectURL(imagePreview.dataset.imageUrl);
      }
    });

    // Clean up object URLs from no-text results
    this.noTextResults.forEach((result) => {
      const imagePreview = result.element?.querySelector(
        ".no-text-image-preview"
      );
      if (imagePreview?.dataset.imageUrl) {
        URL.revokeObjectURL(imagePreview.dataset.imageUrl);
      }
    });

    this.results = [];
    this.noTextResults = [];
    this.successfulResultsContainer.innerHTML = "";
    this.noTextList.innerHTML = "";
    this.resultsContainer.classList.add("hidden");
    this.noTextResultsContainer.classList.add("hidden");

    // Close any open modal
    this.closeImageModal();
  }

  getResults() {
    return [...this.results];
  }

  hasResults() {
    return this.results.length > 0 || this.noTextResults.length > 0;
  }

  openImageModal(imageUrl, imageName) {
    // Remove existing modal if present
    this.closeImageModal();

    // Create modal backdrop
    const modalBackdrop = document.createElement("div");
    modalBackdrop.className = "image-modal-backdrop";
    modalBackdrop.id = "imageModal";

    // Create modal content
    modalBackdrop.innerHTML = `
      <div class="image-modal-content">
        <div class="image-modal-header">
          <h3 class="image-modal-title">${this.escapeHtml(imageName)}</h3>
          <button class="image-modal-close" title="Close">&times;</button>
        </div>
        <div class="image-modal-body">
          <img src="${imageUrl}" alt="${this.escapeHtml(
      imageName
    )}" class="image-modal-img" />
        </div>
      </div>
    `;

    // Add to document
    document.body.appendChild(modalBackdrop);

    // Add event listeners
    const closeBtn = modalBackdrop.querySelector(".image-modal-close");
    closeBtn.addEventListener("click", () => this.closeImageModal());

    // Close on backdrop click
    modalBackdrop.addEventListener("click", (e) => {
      if (e.target === modalBackdrop) {
        this.closeImageModal();
      }
    });

    // Close on Escape key
    const handleEscape = (e) => {
      if (e.key === "Escape") {
        this.closeImageModal();
        document.removeEventListener("keydown", handleEscape);
      }
    };
    document.addEventListener("keydown", handleEscape);

    // Store escape handler for cleanup
    modalBackdrop._escapeHandler = handleEscape;
  }

  closeImageModal() {
    const modal = document.getElementById("imageModal");
    if (modal) {
      // Clean up escape key listener
      if (modal._escapeHandler) {
        document.removeEventListener("keydown", modal._escapeHandler);
      }
      modal.remove();
    }
  }
}
