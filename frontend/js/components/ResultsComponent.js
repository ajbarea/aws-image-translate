import { BaseComponent } from "./BaseComponent.js";

/**
 * Results display component for showing processing results
 */
export class ResultsComponent extends BaseComponent {
  constructor(containerId, options = {}) {
    super(containerId, options);
    this.results = [];
  }

  async onInit() {
    this.resultsContainer = this.querySelector("#results");
    if (!this.resultsContainer) {
      throw new Error("Results container not found");
    }
  }

  setupEventListeners() {
    // Listen for queue item updates to show results
    this.on("queue:itemUpdated", this.handleQueueItemUpdated.bind(this));

    // Listen for language changes to retranslate results
    this.on("language:changed", this.handleLanguageChanged.bind(this));

    // Listen for remove button clicks
    this.addEventListener(
      this.container,
      "click",
      this.handleRemoveButtonClick.bind(this)
    );
  }

  handleRemoveButtonClick(e) {
    if (e.target.matches(".result-remove-btn")) {
      const itemId = e.target.dataset.itemId;
      this.removeResult(itemId);
      this.emit("result:removed", { itemId });
    }
  }

  handleQueueItemUpdated(e) {
    const { item } = e.detail;
    if (item.status === "complete" && item.processingResults) {
      this.addResult(item);
    }
  }

  async handleLanguageChanged(e) {
    const { language } = e.detail;
    console.log(`📝 Results: Re-translating all results to ${language}`);
    await this.retranslateAllResults(language);
  }

  addResult(item) {
    console.log(`📊 Results: Adding result for ${item.file.name}`);

    // Remove existing result for this item if it exists
    this.removeResult(item.id);

    const resultElement = this.createResultElement(item);
    this.resultsContainer.appendChild(resultElement);

    // Store result reference
    this.results.push({
      id: item.id,
      item,
      element: resultElement,
    });

    // Show the results container
    this.resultsContainer.classList.remove("hidden");
  }

  removeResult(itemId) {
    const resultIndex = this.results.findIndex(
      (result) => result.id === itemId
    );
    if (resultIndex !== -1) {
      const result = this.results[resultIndex];
      if (result.element && result.element.parentNode) {
        result.element.remove();
      }
      this.results.splice(resultIndex, 1);
    }

    // Hide container if no results
    if (this.results.length === 0) {
      this.resultsContainer.classList.add("hidden");
    }
  }

  createResultElement(item) {
    const resultDiv = document.createElement("div");
    resultDiv.className = "result-item result-item-dark";
    resultDiv.setAttribute("data-item-id", item.id);

    let resultHTML = `
      <div class="result-header">
        <h3 class="result-title">${item.file.name}</h3>
        <button class="result-remove-btn" data-item-id="${item.id}" title="Remove result">×</button>
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
            <span class="result-label-language">🌍 Detected Language:</span>
            <span class="result-language-badge">
              ${detectedLangName}
            </span>
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
    this.results = [];
    this.resultsContainer.innerHTML = "";
    this.resultsContainer.classList.add("hidden");
  }

  getResults() {
    return [...this.results];
  }

  hasResults() {
    return this.results.length > 0;
  }
}
