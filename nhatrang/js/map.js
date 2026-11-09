/* Карта на Leaflet. Подложка берётся из настройки tiles_url (провайдер выбирает Некит); без неё карта рисует только слои. */
(function () {
  const COL = { none: '#8d8a99', good: '#30a46c', mid: '#e3a93c', bad: '#e5484d' };
  const ratingColor = r => r == null ? COL.none : r >= 4 ? COL.good : r >= 3 ? COL.mid : COL.bad;

  function createMap(el, { center, zoom, tilesUrl }) {
    if (!window.L) return null;
    const m = L.map(el, { zoomControl: false, attributionControl: false, tap: true }).setView(center, zoom || 12);
    if (tilesUrl && /\.pmtiles$/.test(tilesUrl)) {
      if (window.protomapsL) protomapsL.leafletLayer({ url: tilesUrl, flavor: 'light', lang: 'en', maxZoom: 15 }).addTo(m);
    } else if (tilesUrl) L.tileLayer(tilesUrl, { maxZoom: 19 }).addTo(m);
    const dl = L.layerGroup().addTo(m), pl = L.layerGroup().addTo(m), fl = L.layerGroup().addTo(m);
    let pick = null, pickMarker = null;
    m.on('click', e => { if (pick) pick(e.latlng.lat, e.latlng.lng); });
    return {
      map: m,
      addDistricts(fc) {
        dl.clearLayers();
        L.geoJSON(fc, {
          style: { color: '#6b5dd3', weight: 1.5, fillOpacity: 0.06 },
          pointToLayer: (f, ll) => L.circleMarker(ll, { radius: 4, color: '#6b5dd3', weight: 2, fillColor: '#fff', fillOpacity: 1, interactive: false }),
          onEachFeature: (f, layer) => layer.bindTooltip(dom.h('span', { text: f.properties.name_ru }),
            { permanent: true, direction: 'center', className: 'dist-label' }),
        }).addTo(dl);
      },
      setPlaces(items, onTap) {
        pl.clearLayers();
        items.forEach(p => {
          const mk = L.circleMarker([p.lat, p.lon], { radius: 9, color: '#fff', weight: 2, fillColor: ratingColor(p.rating), fillOpacity: 0.95 });
          mk.bindTooltip(dom.h('span', { text: p.name }), { direction: 'top' });
          mk.on('click', () => onTap(p));
          mk.addTo(pl);
        });
      },
      setFlags(items, onTap) {
        fl.clearLayers();
        items.forEach(f => {
          const mk = L.circleMarker([f.lat, f.lon], { radius: 8, color: '#2a2831', weight: 2, fillColor: f.color, fillOpacity: 1 });
          mk.bindTooltip(dom.h('span', { text: f.label }), { direction: 'top' });
          mk.on('click', ev => { L.DomEvent.stopPropagation(ev); onTap(f); });
          mk.addTo(fl);
        });
      },
      onPick(cb) { pick = cb; },
      setPickMarker(lat, lon) {
        if (pickMarker) m.removeLayer(pickMarker);
        pickMarker = L.circleMarker([lat, lon], { radius: 10, color: '#fff', weight: 3, fillColor: '#6b5dd3', fillOpacity: 1 }).addTo(m);
      },
      invalidate() { m.invalidateSize(); },
      fitTo(items) { if (items.length) m.fitBounds(items.map(p => [p.lat, p.lon]), { padding: [24, 24], maxZoom: 16 }); },
      setView(lat, lon, z) { m.setView([lat, lon], z || m.getZoom()); },
    };
  }
  window.mapkit = { createMap, ratingColor };
})();
