/**
 * Centralized language definitions for AWS Translate supported languages
 *
 * Data source: AWS Translate documentation
 * @see https://docs.aws.amazon.com/translate/latest/dg/what-is.html
 */

export const AWS_SUPPORTED_LANGUAGES = {
  af: "Afrikaans",
  sq: "Albanian",
  am: "Amharic",
  ar: "Arabic",
  hy: "Armenian",
  az: "Azerbaijani",
  bn: "Bengali",
  bs: "Bosnian",
  bg: "Bulgarian",
  ca: "Catalan",
  zh: "Chinese (Simplified)",
  "zh-TW": "Chinese (Traditional)",
  hr: "Croatian",
  cs: "Czech",
  da: "Danish",
  "fa-AF": "Dari",
  nl: "Dutch",
  en: "English",
  et: "Estonian",
  fa: "Farsi (Persian)",
  tl: "Filipino, Tagalog",
  fi: "Finnish",
  fr: "French",
  "fr-CA": "French (Canada)",
  ka: "Georgian",
  de: "German",
  el: "Greek",
  gu: "Gujarati",
  ht: "Haitian Creole",
  ha: "Hausa",
  he: "Hebrew",
  hi: "Hindi",
  hu: "Hungarian",
  is: "Icelandic",
  id: "Indonesian",
  ga: "Irish",
  it: "Italian",
  ja: "Japanese",
  kn: "Kannada",
  kk: "Kazakh",
  ko: "Korean",
  lv: "Latvian",
  lt: "Lithuanian",
  mk: "Macedonian",
  ms: "Malay",
  ml: "Malayalam",
  mt: "Maltese",
  mr: "Marathi",
  mn: "Mongolian",
  no: "Norwegian (Bokmål)",
  ps: "Pashto",
  pl: "Polish",
  pt: "Portuguese (Brazil)",
  "pt-PT": "Portuguese (Portugal)",
  pa: "Punjabi",
  ro: "Romanian",
  ru: "Russian",
  sr: "Serbian",
  si: "Sinhala",
  sk: "Slovak",
  sl: "Slovenian",
  so: "Somali",
  es: "Spanish",
  "es-MX": "Spanish (Mexico)",
  sw: "Swahili",
  sv: "Swedish",
  ta: "Tamil",
  te: "Telugu",
  th: "Thai",
  tr: "Turkish",
  uk: "Ukrainian",
  ur: "Urdu",
  uz: "Uzbek",
  vi: "Vietnamese",
  cy: "Welsh"
};

export function getLanguageName(languageCode) {
  return AWS_SUPPORTED_LANGUAGES[languageCode] || languageCode;
}

export function isLanguageSupported(languageCode) {
  return languageCode in AWS_SUPPORTED_LANGUAGES;
}

export function getSupportedLanguageCodes() {
  return Object.keys(AWS_SUPPORTED_LANGUAGES);
}

export function getSupportedLanguages() {
  return Object.entries(AWS_SUPPORTED_LANGUAGES).map(([code, name]) => ({
    code,
    name
  }));
}

export const COMMON_LANGUAGES = {
  en: "English",
  es: "Spanish",
  fr: "French",
  de: "German",
  it: "Italian",
  pt: "Portuguese (Brazil)",
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
  no: "Norwegian (Bokmål)",
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
  cy: "Welsh"
};

export const DEFAULT_LANGUAGE = "en";
