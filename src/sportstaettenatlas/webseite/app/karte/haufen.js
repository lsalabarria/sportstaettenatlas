// Punkte zu Haufen zusammenfassen, je nach Zoomstufe: unter KREISE_BIS einer je Kreis, unter
// GEMEINDEN_BIS einer je Gemeinde, darüber jeder Punkt einzeln. Ein Haufen zählt alle Punkte
// seines Gebiets (auch außerhalb des Bildes) und steht an dem Punkt, der dem Mittel am nächsten
// liegt (also im Gebiet); liegen zwei zu dicht, schieben sie sich auseinander. Darüberfahren
// zeigt den Umriss des Gebiets, ein Klick zoomt hinein (mindestens bis zur nächsten Stufe).
// Punkte ohne Gebiet und Gebiete mit weniger als HAUFEN_AB Punkten bleiben einzeln.
// Dieselben Methoden wie eine L.layerGroup (addLayer, removeLayer), dazu einzeln(layer): diesen Punkt immer zeigen (z. B. für sein Popup), bis das
// Popup zu ist.
// optionen: ars(layer) → Regionalschlüssel der Gemeinde oder null; name(ebene, schlüssel);
// grenzen(ebene, schlüssel) → Bounds oder null; umriss(ebene, schlüssel) zeigt den Umriss,
// umriss(null) nimmt ihn weg
import { zahl } from "../lib/text.js";

const KREISE_BIS = 10, GEMEINDEN_BIS = 13, HAUFEN_AB = 3;
const HAUFEN_STUFEN = [{ ebene: "kreis", bis: KREISE_BIS, stellen: 5 },
  { ebene: "gemeinde", bis: GEMEINDEN_BIS, stellen: 12 }];
export function haufen(optionen = {}) {
  const punkte = new Set(), sicht = L.layerGroup();
  let karteH = null, geheftet = null, geplant = false, merke = null;
  const umriss = (e, k) => optionen.umriss && optionen.umriss(e, k);
  const plane = () => {
    if (!karteH || geplant) return;
    geplant = true;
    requestAnimationFrame(() => { geplant = false; zeichne(); });
  };
  function zeichne() {
    if (!karteH) return;
    // Neu zeichnen, ohne Punkte, die bleiben, abzunehmen: sonst schlösse sich ihr Popup
    // (z. B. wenn die Karte für ein Popup verschoben wird und dabei neu zeichnet)
    const vorher = new Set(sicht.getLayers()), jetzt = new Set();
    merke = l => jetzt.add(l);
    umriss(null);
    const z = karteH.getZoom(), rand = karteH.getBounds().pad(0.5);
    const stufe = optionen.ars ? HAUFEN_STUFEN.find(s => z < s.bis) : null;
    const gruppen = new Map();
    for (const p of punkte) {
      const ars = stufe && p !== geheftet ? optionen.ars(p) : null;
      if (ars && ars.length >= stufe.stellen) {
        const k = ars.slice(0, stufe.stellen);
        (gruppen.get(k) || gruppen.set(k, []).get(k)).push(p);
      } else if (p === geheftet || rand.contains(p.getLatLng())) merke(p);
    }
    if (stufe) zeigeGruppen(stufe, gruppen, z, rand);
    for (const l of vorher) if (!jetzt.has(l)) sicht.removeLayer(l);
    for (const l of jetzt) if (!vorher.has(l)) sicht.addLayer(l);
  }
  // Größe wächst stufenlos mit der Zahl (logarithmisch): 3 → 26 px, 100 → 38 px, 1.000 → 46 px
  const groesse = n => Math.round(22 + 8 * Math.log10(Math.max(n, 1)));
  function zeigeGruppen(stufe, gruppen, z, rand) {
    const blasen = [];
    for (const [k, g] of gruppen) {
      let lat = 0, lon = 0;
      for (const p of g) { const ll = p.getLatLng(); lat += ll.lat; lon += ll.lng; }
      lat /= g.length; lon /= g.length;
      let ort = null, best = Infinity;
      for (const p of g) {
        const ll = p.getLatLng(), d = (ll.lat - lat) ** 2 + ((ll.lng - lon) * 0.64) ** 2;
        if (d < best) { best = d; ort = ll; }
      }
      if (!rand.contains(ort)) continue;
      if (g.length < HAUFEN_AB) { g.forEach(merke); continue; }  // kleine Haufen: Punkte
      blasen.push({ k, g, pt: karteH.project(ort, z), r: groesse(g.length) / 2 });
    }
    auseinander(blasen);
    for (const { k, g, pt } of blasen) {
      const name = optionen.name ? optionen.name(stufe.ebene, k) : "";
      const m = L.marker(karteH.unproject(pt, z), { keyboard: false,
        title: `${name ? name + ": " : ""}${zahl(g.length)} Sportstätten – hineinzoomen`,
        icon: L.divIcon({ className: "haufen " + stufe.ebene, html: `<span>${zahl(g.length)}</span>`,
          iconSize: [groesse(g.length), groesse(g.length)] }) });
      m.on("mouseover", () => umriss(stufe.ebene, k));
      m.on("mouseout", () => umriss(null));
      m.on("click", () => hinein(stufe, k, g));
      merke(m);
    }
  }
  // Blasen, die sich überdecken, paarweise auseinanderschieben (Raster zum schnellen Finden)
  function auseinander(blasen) {
    blasen.forEach((b, i) => { b.i = i; });
    const zelle = 2 * Math.max(0, ...blasen.map(b => b.r)) + 3;
    for (let runde = 0; runde < 40; runde++) {
      const raster = new Map();
      for (const b of blasen) {
        const k = Math.floor(b.pt.x / zelle) + ":" + Math.floor(b.pt.y / zelle);
        (raster.get(k) || raster.set(k, []).get(k)).push(b);
      }
      let bewegt = false;
      for (const a of blasen) {
        const cx = Math.floor(a.pt.x / zelle), cy = Math.floor(a.pt.y / zelle);
        for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) {
          for (const b of raster.get((cx + dx) + ":" + (cy + dy)) || []) {
            if (b.i <= a.i) continue;  // jedes Paar einmal
            const ex = b.pt.x - a.pt.x, ey = b.pt.y - a.pt.y;
            const d = Math.hypot(ex, ey) || 0.01, soll = a.r + b.r + 3;
            if (d >= soll) continue;
            const f = (soll - d) / 2 / d;
            a.pt = L.point(a.pt.x - ex * f, a.pt.y - ey * f);
            b.pt = L.point(b.pt.x + ex * f, b.pt.y + ey * f);
            bewegt = true;
          }
        }
      }
      if (!bewegt) break;
    }
  }
  // Hineinzoomen: auf das ganze Gebiet, aber mindestens bis zur nächsten Stufe
  function hinein(stufe, k, g) {
    umriss(null);
    const grenzen = (optionen.grenzen && optionen.grenzen(stufe.ebene, k))
      || L.latLngBounds(g.map(p => p.getLatLng())).pad(0.1);
    const z = Math.max(karteH.getBoundsZoom(grenzen, false, L.point(40, 40)), stufe.bis);
    karteH.setView(grenzen.getCenter(), Math.min(z, karteH.getMaxZoom()));
  }
  const ebene = {
    addLayer(p) { punkte.add(p); plane(); return ebene; },
    removeLayer(p) { punkte.delete(p); if (p === geheftet) geheftet = null; plane(); return ebene; },
    hasLayer: p => punkte.has(p),
    einzeln(p) {
      geheftet = p;
      p.once("popupclose", () => { if (geheftet === p) { geheftet = null; plane(); } });
      zeichne();
    },
    addTo(m) {
      karteH = m; sicht.addTo(m); m.on("zoomend moveend", plane); zeichne(); return ebene;
    },
    remove() {
      if (karteH) { karteH.off("zoomend moveend", plane); karteH.removeLayer(sicht); }
      umriss(null);
      karteH = null; return ebene;
    },
  };
  return ebene;
}
