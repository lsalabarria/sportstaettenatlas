// ESLint für die Skripte der Webseite (npm run lint; README „Code prüfen“): die von ESLint
// empfohlenen Regeln (undefinierte und unbenutzte Namen, doppelte Schlüssel, unerreichbarer
// Code …), keine Stilregeln. Die Skripte sind ES-Module (app/), konfig.js ein normales Skript.
import { builtinRules } from "eslint/use-at-your-own-risk";
import globals from "globals";

const APP = "src/sportstaettenatlas/webseite/app";
const empfohlen = Object.fromEntries(
  [...builtinRules].filter(([, r]) => r.meta?.docs?.recommended).map(([n]) => [n, "error"]),
);
const regeln = {
  ...empfohlen,
  // Parameter, die eine Rückruffunktion nicht braucht, und catch (e) ohne e sind in Ordnung
  "no-unused-vars": ["error", { args: "none", caughtErrors: "none" }],
};

export default [
  {
    files: [`${APP}/**/*.js`],
    ignores: [`${APP}/vorlagen/**`],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: {
        ...globals.browser,
        L: "readonly",  // Leaflet (eigenes Skript vor den Modulen)
        QUELLE: "readonly",  // Quellenvermerk, in index.html eingesetzt
      },
    },
    linterOptions: { reportUnusedDisableDirectives: "error" },
    rules: regeln,
  },
  {
    files: [`${APP}/vorlagen/**/*.js`],
    languageOptions: { ecmaVersion: "latest", sourceType: "script", globals: globals.browser },
    rules: regeln,
  },
];
