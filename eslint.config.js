// ESLint flat config for TaskMate's Lovelace cards + admin panel (CI-3).
// The cards run in the browser and obtain LitElement from the Lovelace custom
// element registry, so they are linted as browser scripts. This gate is
// eslint:recommended only — a static-analysis floor over ~32k lines of JS that
// previously had no automated checks.
import js from "@eslint/js";
import globals from "globals";

export default [
  {
    files: ["custom_components/taskmate/www/**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: {
        ...globals.browser,
        // Lovelace / HA frontend globals these cards rely on.
        customElements: "readonly",
        loadCardHelpers: "readonly",
      },
    },
    rules: {
      ...js.configs.recommended.rules,
      // Swallowing errors in a bare catch is an intentional pattern here.
      "no-empty": ["error", { allowEmptyCatch: true }],
      // Unused locals are non-blocking style noise, not correctness bugs; report
      // as warnings so the gate still fails on real issues (no-undef, etc.).
      // `_`-prefixed names are deliberately unused.
      "no-unused-vars": ["warn", {
        argsIgnorePattern: "^_",
        varsIgnorePattern: "^_",
        caughtErrors: "none",
      }],
    },
  },
];
