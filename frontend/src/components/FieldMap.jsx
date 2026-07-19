import React, { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet-draw/dist/leaflet.draw.css";
import "leaflet-draw";
import { MAP } from "@/constants/testIds";

// spectral color per status
const COLOR = {
  healthy: "#22c55e",
  monitoring: "#facc15",
  diseased: "#f97316",
  critical: "#ef4444",
};

/**
 * FieldMap — Leaflet map with optional polygon rendering + drawing.
 * Props:
 *   fields: array of field docs with location + optional polygon
 *   center: [lat, lng] initial center
 *   zoom: initial zoom
 *   draw: boolean — enable polygon drawing tool
 *   onPolygonDrawn: (ring: [[lng,lat], ...], centroid: {lat, lng}) => void
 *   onFieldClick: (field) => void
 *   height: css height, default 480
 */
export default function FieldMap({
  fields = [], center = [30.9, 75.85], zoom = 7,
  draw = false, onPolygonDrawn, onFieldClick, height = 480,
}) {
  const el = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);
  const drawRef = useRef(null);

  // one-time init
  useEffect(() => {
    if (mapRef.current || !el.current) return;
    const map = L.map(el.current, {
      center, zoom, zoomControl: true, attributionControl: true, worldCopyJump: true,
    });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '© OpenStreetMap',
      className: "cv-map-tiles",
    }).addTo(map);
    const layer = L.featureGroup().addTo(map);
    mapRef.current = map;
    layerRef.current = layer;

    if (draw) {
      const drawn = new L.FeatureGroup().addTo(map);
      const drawControl = new L.Control.Draw({
        edit: { featureGroup: drawn, edit: false, remove: true },
        draw: {
          polygon: {
            shapeOptions: { color: "#22c55e", weight: 2, fillOpacity: 0.25 },
            allowIntersection: false, showArea: true,
          },
          polyline: false, rectangle: false, circle: false, marker: false, circlemarker: false,
        },
      });
      map.addControl(drawControl);
      drawRef.current = drawn;
      map.on(L.Draw.Event.CREATED, (e) => {
        drawn.clearLayers();
        drawn.addLayer(e.layer);
        const latlngs = e.layer.getLatLngs()[0];
        const ring = latlngs.map(p => [p.lng, p.lat]);
        // centroid
        const c = latlngs.reduce((acc, p) => ({ lat: acc.lat + p.lat, lng: acc.lng + p.lng }), { lat: 0, lng: 0 });
        c.lat /= latlngs.length; c.lng /= latlngs.length;
        onPolygonDrawn?.(ring, c);
      });
    }

    return () => { map.remove(); mapRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // draw / redraw fields
  useEffect(() => {
    const map = mapRef.current; const layer = layerRef.current;
    if (!map || !layer) return;
    layer.clearLayers();
    if (!fields.length) return;

    const bounds = L.latLngBounds([]);
    fields.forEach(f => {
      const color = COLOR[f.status] || COLOR.healthy;
      let feature = null;
      if (f.polygon?.coordinates?.[0]) {
        const ring = f.polygon.coordinates[0].map(([lng, lat]) => [lat, lng]);
        feature = L.polygon(ring, {
          color, weight: 2, fillOpacity: 0.35, fillColor: color,
        });
      }
      if (!feature && f.location?.coordinates) {
        const [lng, lat] = f.location.coordinates;
        feature = L.circleMarker([lat, lng], {
          radius: 8, color, weight: 2, fillOpacity: 0.7, fillColor: color,
        });
      }
      if (feature) {
        feature.addTo(layer);
        const popup = `
          <div style="font-family:'Manrope',sans-serif;min-width:180px">
            <div style="font-size:10px;letter-spacing:.15em;text-transform:uppercase;color:#94a3b8">${f.region || ""}</div>
            <div style="font-weight:600;font-size:15px;margin-top:2px">${f.name}</div>
            <div style="font-size:12px;color:#64748b;text-transform:capitalize">${f.crop} · ${f.area_hectares} ha</div>
            <div style="margin-top:6px;font-weight:700;color:${color}">Health ${Math.round(f.health_score || 0)}</div>
          </div>`;
        feature.bindPopup(popup);
        if (onFieldClick) feature.on("click", () => onFieldClick(f));
        try { bounds.extend(feature.getBounds ? feature.getBounds() : feature.getLatLng()); } catch (e) {}
      }
    });
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [30, 30], maxZoom: 12 });
    setTimeout(() => map.invalidateSize(), 100);
  }, [fields, onFieldClick]);

  return (
    <div className="relative border border-border bg-card" style={{ height }}>
      <div
        data-testid={MAP.container}
        ref={el}
        className="w-full h-full cv-leaflet-container"
        style={{ background: "hsl(144 24% 5%)" }}
      />
    </div>
  );
}
