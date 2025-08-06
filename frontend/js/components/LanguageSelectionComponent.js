import { BaseComponent } from "./BaseComponent.js";
import {
  AWS_SUPPORTED_LANGUAGES,
  getLanguageName,
  isLanguageSupported,
  DEFAULT_LANGUAGE
} from "../constants/languages.js";

/**
 * Language selection component for translation target language
 */
export class LanguageSelectionComponent extends BaseComponent {
  constructor(containerId, options = {}) {
    super(containerId, options);
    this.defaultLanguage = options.defaultLanguage || DEFAULT_LANGUAGE;
    this.excludeLanguages = options.excludeLanguages || [];
  }

  async onInit() {
    // Look for any select element within this container
    this.languageSelect = this.querySelector("select");
    if (!this.languageSelect) {
      throw new Error("Language select element not found");
    }

    this.populateLanguageOptions();
  }

  setupEventListeners() {
    this.addEventListener(
      this.languageSelect,
      "change",
      this.handleLanguageChange.bind(this)
    );
  }

  handleLanguageChange(e) {
    const selectedLanguage = e.target.value;
    console.log(
      `🌍 LanguageSelection: Language changed to: ${selectedLanguage}`
    );
    this.emit("language:changed", { language: selectedLanguage });
  }

  populateLanguageOptions() {
    const languages = AWS_SUPPORTED_LANGUAGES;

    // Clear existing options
    this.languageSelect.innerHTML = "";

    // Add options
    for (const [code, name] of Object.entries(languages)) {
      if (!this.excludeLanguages.includes(code)) {
        const option = document.createElement("option");
        option.value = code;
        option.textContent = name;
        option.selected = code === this.defaultLanguage;
        this.languageSelect.appendChild(option);
      }
    }
  }

  getSupportedLanguages() {
    return AWS_SUPPORTED_LANGUAGES;
  }

  getSelectedLanguage() {
    return this.languageSelect?.value || this.defaultLanguage;
  }

  setSelectedLanguage(languageCode) {
    if (this.languageSelect) {
      const option = this.languageSelect.querySelector(
        `option[value="${languageCode}"]`
      );
      if (option) {
        this.languageSelect.value = languageCode;
        this.emit("language:changed", { language: languageCode });
      } else {
        console.warn(
          `⚠️ LanguageSelection: Language code '${languageCode}' not found`
        );
      }
    }
  }

  getLanguageName(languageCode) {
    return getLanguageName(languageCode);
  }

  isLanguageSupported(languageCode) {
    return (
      isLanguageSupported(languageCode) &&
      !this.excludeLanguages.includes(languageCode)
    );
  }

  addLanguage(code, name) {
    if (!this.isLanguageSupported(code)) {
      const option = document.createElement("option");
      option.value = code;
      option.textContent = name;
      this.languageSelect.appendChild(option);
    }
  }

  removeLanguage(code) {
    if (this.languageSelect) {
      const option = this.languageSelect.querySelector(
        `option[value="${code}"]`
      );
      if (option) {
        option.remove();
        // If this was the selected language, switch to default
        if (this.languageSelect.value === code) {
          this.setSelectedLanguage(this.defaultLanguage);
        }
      }
    }
  }

  enable() {
    super.enable();
    if (this.languageSelect) {
      this.languageSelect.disabled = false;
    }
  }

  disable() {
    super.disable();
    if (this.languageSelect) {
      this.languageSelect.disabled = true;
    }
  }
}
