// Prüft die Skripte der Webseite mit ESLint (npm run lint; siehe README „Code prüfen“).
//
// Die Skripte in app/ sind normale Browser-Skripte, die sich ihre Funktionen über den
// globalen Namensraum teilen, und vorschlag.js entsteht erst aus den Teilen in
// app/vorschlag/ (Teile 10–95 sind einzeln kein gültiges JavaScript). Deshalb prüft ESLint
// hier alle Skripte zusammen, so wie der Browser sie lädt (Reihenfolge SKRIPTE aus
// app/__init__.py), und die Meldungen zeigen wieder auf Datei und Zeile des Teils.
//
// Regeln: die empfohlenen von ESLint (Fehler wie undefinierte oder unbenutzte Namen,
// doppelte Schlüssel, unerreichbarer Code) – keine Stilregeln.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { ESLint } from "eslint";
import { builtinRules } from "eslint/use-at-your-own-risk";
import globals from "globals";

const HIER = path.dirname(fileURLToPath(import.meta.url));
const APP = path.join(HIER, "app");
const WURZEL = path.resolve(HIER, "..", "..", "..");

// Reihenfolge und zusammengesetzte Skripte wie in app/__init__.py
function inPython(name) {
  const text = fs.readFileSync(path.join(APP, "__init__.py"), "utf-8");
  const m = text.match(new RegExp(`^${name} = ([\\s\\S]*?)\\n(?=\\S)`, "m"));
  if (!m) throw new Error(`${name} fehlt in app/__init__.py`);
  return m[1];
}
const SKRIPTE = [...inPython("SKRIPTE").matchAll(/"([^"]+\.js)"/g)].map(m => m[1]);
const ZUSAMMENGESETZT = Object.fromEntries(
  [...inPython("ZUSAMMENGESETZT").matchAll(/"([^"]+\.js)":\s*"([^"]+)"/g)].map(m => [m[1], m[2]]),
);

function dateienVon(skript) {
  const ordner = ZUSAMMENGESETZT[skript];
  if (!ordner) return [path.join(APP, skript)];
  return fs.readdirSync(path.join(APP, ordner)).filter(n => n.endsWith(".js")).sort()
    .map(n => path.join(APP, ordner, n));
}

// Alle Dateien hintereinander; je Datei die erste Zeile im Ganzen
const teile = [];
let ganz = "";
let zeile = 1;
for (const datei of SKRIPTE.flatMap(dateienVon)) {
  let text = fs.readFileSync(datei, "utf-8");
  if (!text.endsWith("\n")) text += "\n";
  teile.push({ datei, ab: zeile });
  ganz += text;
  zeile += text.split("\n").length - 1;
}
function wo(z) {
  let t = teile[0];
  for (const x of teile) if (x.ab <= z) t = x;
  return { datei: path.relative(WURZEL, t.datei), zeile: z - t.ab + 1 };
}

const empfohlen = Object.fromEntries(
  [...builtinRules].filter(([, r]) => r.meta?.docs?.recommended).map(([n]) => [n, "error"]),
);
const eslint = new ESLint({
  cwd: WURZEL,
  overrideConfigFile: true,  // keine eslint.config.js: alles steht hier
  overrideConfig: {
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "script",
      globals: {
        ...globals.browser,
        L: "readonly",  // Leaflet
        QUELLE: "readonly",  // in index.html eingesetzt (KONFIG holt grundlagen.js aus window)
      },
    },
    linterOptions: { reportUnusedDisableDirectives: "error" },
    rules: {
      ...empfohlen,
      // Parameter, die eine Rückruffunktion nicht braucht, und catch (e) ohne e sind in Ordnung
      "no-unused-vars": ["error", { args: "none", caughtErrors: "none" }],
    },
  },
});

const [ergebnis] = await eslint.lintText(ganz, { filePath: path.join(APP, "alle-skripte.js") });
for (const m of ergebnis.messages) {
  const o = wo(m.line);
  console.log(`${o.datei}:${o.zeile}:${m.column}  ${m.ruleId || "Syntax"}  ${m.message}`);
}
const n = ergebnis.errorCount + ergebnis.warningCount;
console.log(n ? `${n} Meldung${n === 1 ? "" : "en"}` : `ESLint: keine Meldungen (${teile.length} Dateien)`);
process.exitCode = n ? 1 : 0;
