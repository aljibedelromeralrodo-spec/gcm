import js from "@eslint/js";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";

export default [
  { ignores: ["build/**", "node_modules/**", "src/components/ui/**", "public/**"] },
  js.configs.recommended,
  {
    files: ["src/**/*.{js,jsx}"],
    plugins: { react, "react-hooks": reactHooks },
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: {
        window: "readonly", document: "readonly", localStorage: "readonly",
        navigator: "readonly", fetch: "readonly", console: "readonly",
        setTimeout: "readonly", clearTimeout: "readonly", setInterval: "readonly",
        clearInterval: "readonly", URL: "readonly", URLSearchParams: "readonly",
        FormData: "readonly", File: "readonly", Blob: "readonly", FileReader: "readonly",
        btoa: "readonly", atob: "readonly", unescape: "readonly", escape: "readonly",
        alert: "readonly", confirm: "readonly", prompt: "readonly", process: "readonly",
        AbortController: "readonly", requestAnimationFrame: "readonly",
        IntersectionObserver: "readonly", ResizeObserver: "readonly", crypto: "readonly",
        sessionStorage: "readonly", indexedDB: "readonly", Image: "readonly", Audio: "readonly",
        location: "readonly", history: "readonly", CustomEvent: "readonly", Event: "readonly",
        SpeechSynthesisUtterance: "readonly", speechSynthesis: "readonly",
      },
    },
    settings: { react: { version: "detect" } },
    rules: {
      ...react.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      "react/react-in-jsx-scope": "off",
      "react/prop-types": "off",
      "react/no-unescaped-entities": "off",
      "react/display-name": "off",
      "no-unused-vars": ["warn", { argsIgnorePattern: "^_", varsIgnorePattern: "^_", caughtErrors: "none" }],
      "no-empty": ["warn", { allowEmptyCatch: true }],
    },
  },
];
