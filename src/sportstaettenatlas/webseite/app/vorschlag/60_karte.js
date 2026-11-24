// vorschlag/60_karte.js: Karte im Formular: Lage setzen, Gemeinde bestimmen, Lage aus der Adresse.
// Teil des Rumpfs von ansichtVorschlag – nur zusammen mit den anderen Teilen gültig
// (app/__init__.py setzt vorschlag/*.js der Reihe nach zu app/vorschlag.js zusammen).
  // --- Karte im Formular ---
  function starteKarte() {
    if (vkarte) { vkarte.invalidateSize(); return; }
    vkarte = L.map("v-karte", { preferCanvas: true, maxZoom: 19 });
    L.tileLayer(BASEMAP, { layer: "de_basemapde_web_raster_farbe", maxNativeZoom: 18, maxZoom: 19,
      attribution: BKG }).addTo(vkarte);
    vkarte.fitBounds(karte.getBounds());
    nachbarn = L.layerGroup().addTo(vkarte);
    for (const e of bestand.eintraege) {
      L.circleMarker([e.lat, e.lon], { radius: 4, weight: 1, color: "#fff", fillColor: "#7a7975",
        fillOpacity: 0.9 }).bindTooltip(esc(e.p.name || e.kat)).bindPopup(() =>
        `<b>${esc(e.p.name || e.kat)}</b><br>${esc(e.p.kategorie || "")}<br>${esc(e.p.adresse || "")}`
        + `<br><a href="#" data-bearbeiten="${esc(e.p.id)}">Diese Sportstätte ändern</a>`).addTo(nachbarn);
    }
    vkarte.on("click", ev => setzeLage(ev.latlng.lat, ev.latlng.lng));
  }
  // Auswahl der Sportkomplexe: die in der Nähe der Lage (PRUEFUNG().komplex_nah_m), nach
  // Abstand; der gewählte bleibt
  function komplexAuswahl() {
    const e = FELD_KOMPLEX && F(FELD_KOMPLEX.pfad);
    if (!e) return;
    const alt = e.value;
    const nah = [...SPORTKOMPLEXE.values()]
      .map(k => [k, lage && k.lat != null ? abstand(lage[0], lage[1], k.lat, k.lon) : Infinity])
      .filter(([k, d]) => d <= PRUEFUNG().komplex_nah_m || k.id === alt)
      .sort((a, b) => a[1] - b[1]);
    if (alt && !nah.some(([k]) => k.id === alt)) nah.unshift([{ id: alt, name: komplexName(alt) }, Infinity]);
    const weg = d => !isFinite(d) ? "" : ` (${d < 1000 ? Math.round(d) + " m" : (d / 1000).toFixed(1) + " km"})`;
    e.innerHTML = `<option value="">kein Sportkomplex</option>`
      + nah.map(([k, d]) => `<option value="${esc(k.id)}">${esc(k.name)}${weg(d)}</option>`).join("")
      + (unter ? "" : `<option value="${NEUER_KOMPLEX}">+ neuer Sportkomplex …</option>`);
    e.value = alt;
    zeigeNk();
  }
  function setzeLage(lat, lon, zoomen = false) {
    lage = lat == null ? null : [+lat, +lon];
    komplexAuswahl();
    if (marke) { marke.remove(); marke = null; }
    const t = el.querySelector("#v-lage");
    if (!lage) { t.textContent = "Bitte in der Karte rechts auf die Sportstätte klicken."; ars = "";
      el.querySelector("#v-gemeinde").textContent = ""; planePruefung(); return; }
    t.innerHTML = `<span class="koord">${lage[0].toFixed(6)}, ${lage[1].toFixed(6)}</span>`;
    if (vkarte) {
      marke = L.marker(lage, { draggable: true, keyboard: false, icon: L.divIcon({ className: "",
        iconSize: [26, 34], iconAnchor: [13, 32], html: `<div class="nadel"></div>` }) }).addTo(vkarte);
      marke.on("dragend", () => { const p = marke.getLatLng(); setzeLage(p.lat, p.lng); });
      if (zoomen) vkarte.setView(lage, Math.max(vkarte.getZoom(), 17));
    }
    bestimmeGemeinde();
    planePruefung();
  }
  async function bestimmeGemeinde() {
    const ziel = el.querySelector("#v-gemeinde");
    ars = "";
    if (!lage || !GEBIETE.length) { ziel.textContent = ""; return; }
    const fc = await ladeUmrisse("gemeinde"), [lat, lon] = lage;
    if (!fc || !lage || lage[0] !== lat) return;
    const f = fc.features.find(x => x.geometry && punktIn(lon, lat, x.geometry));
    const g = f && NACH_S[f.properties.s];
    ars = g ? g.s : "";
    ziel.textContent = g ? `Gemeinde: ${gebietTitel(g)}` : "Liegt außerhalb von Rheinland-Pfalz?";
    const ort = F("adresse.ort");
    if (g && ort && !ort.value.trim()) ort.value = g.n;
  }
  async function lageAusAdresse() {
    const w = n => (F(`adresse.${n}`) ? F(`adresse.${n}`).value : "");
    const q = [w("strasse") + " " + w("hausnummer"), w("plz") + " " + w("ort")]
      .map(s => s.trim()).filter(Boolean).join(", ");
    const b = el.querySelector("#v-geocode");
    if (!q) { zeigeFehlerliste(["Für die Suche bitte Straße und Ort eintragen."]); return; }
    b.disabled = true; b.textContent = "suche …";
    try {
      const t = await geocode(q);
      if (t.length) { const c = t[0].grenzen().getCenter(); setzeLage(c.lat, c.lng, true); }
      else zeigeFehlerliste(["Adresse nicht gefunden – bitte die Lage in der Karte setzen."]);
    } catch (_) { zeigeFehlerliste(["Adresssuche gerade nicht erreichbar – bitte die Lage in der Karte setzen."]); }
    b.disabled = false; b.textContent = "Lage aus der Adresse suchen";
  }

