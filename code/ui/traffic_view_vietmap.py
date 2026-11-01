# ui/traffic_view_vietmap.py
# TripSmart Pro — Traffic View VietMap realtime marker-only.
# Mục tiêu bản này:
# - Không cố tô màu toàn bộ đường nữa.
# - Chỉ đọc vector tile traffic VietMap trong viewport hiện tại.
# - Nếu phát hiện feature chậm/kẹt thì đặt marker cảnh báo trên điểm giữa đoạn đó.
# - Không dùng demo giả lập.
# - Không cần sửa app.py; app.py chỉ gọi render_traffic_view_vietmap(...).

from __future__ import annotations

import os
import streamlit as st
import streamlit.components.v1 as components

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def _get_vietmap_api_key() -> str:
    """Lấy VietMap API key từ .env / biến môi trường / st.secrets."""
    for key_name in ("VIETMAP_API_KEY", "VIETMAP_TILE_KEY", "VIETMAP_MAP_KEY"):
        val = os.environ.get(key_name, "")
        if val:
            return str(val).strip()
        try:
            if key_name in st.secrets:  # type: ignore[attr-defined]
                val = str(st.secrets[key_name] or "").strip()  # type: ignore[attr-defined]
                if val:
                    return val
        except Exception:
            pass
    return ""


def render_traffic_view_vietmap(height: int = 760) -> None:
    """Render Traffic View realtime dạng marker kẹt xe.

    Màn hình này không cần điểm đi/điểm đến.
    Nó tải traffic tile VietMap theo viewport, sau đó chỉ đặt marker ở đoạn chậm/kẹt.
    """
    api_key = _get_vietmap_api_key()

    st.title("🚦 Kiểm tra kẹt xe")
    st.caption(
        "Bản đồ traffic riêng. App chỉ đặt marker ở các đoạn VietMap báo chậm/kẹt trong vùng đang xem. "
        "Nếu không có marker nghĩa là vùng đó chưa có feature kẹt rõ hoặc VietMap không trả dữ liệu kẹt ở thời điểm hiện tại."
    )

    if not api_key:
        st.warning(
            "⚠️ Chưa tìm thấy VietMap API key. Thêm `VIETMAP_API_KEY` vào `.streamlit/secrets.toml` "
            "hoặc file `.env`."
        )
        with st.expander("Cách thêm VietMap API key", expanded=False):
            st.code('''# .streamlit/secrets.toml\nVIETMAP_API_KEY = "YOUR_VIETMAP_API_KEY"''', language="toml")

    html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no" />
  <script src="https://unpkg.com/@vietmap/vietmap-gl-js@6.0.1/dist/vietmap-gl.js"></script>
  <link rel="stylesheet" href="https://unpkg.com/@vietmap/vietmap-gl-js@6.0.1/dist/vietmap-gl.css" />
  <style>
    html, body {{ margin:0; padding:0; width:100%; height:100%; background:#ffffff; font-family: Inter, Arial, sans-serif; }}
    #traffic-map {{ width:100%; height:{height}px; border-radius:18px; overflow:hidden; background:#eef2f7; }}
    .gps-dot {{
      width:18px; height:18px; border-radius:50%; background:#0b84ff;
      border:3px solid #fff; box-shadow:0 0 0 8px rgba(11,132,255,.18), 0 2px 8px rgba(0,0,0,.35);
    }}
    .traffic-badge {{
      position:absolute; z-index:10; right:18px; top:14px;
      background:rgba(255,255,255,.96); color:#065f46;
      border:1px solid rgba(6,95,70,.18); border-radius:999px;
      padding:7px 12px; font-size:13px; font-weight:800;
      box-shadow:0 8px 20px rgba(15,23,42,.12);
      max-width:520px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
    }}
    .traffic-badge.warn {{ color:#92400e; border-color:rgba(146,64,14,.22); }}
    .traffic-badge.err {{ color:#991b1b; border-color:rgba(153,27,27,.22); }}
    .legend {{
      position:absolute; z-index:10; right:18px; top:52px;
      background:rgba(255,255,255,.93); border-radius:12px; padding:7px 10px;
      font-size:12px; font-weight:700; color:#111827; box-shadow:0 8px 20px rgba(15,23,42,.10);
      display:flex; gap:8px; align-items:center;
    }}
    .dot {{ width:10px; height:10px; border-radius:50%; display:inline-block; margin-right:4px; }}
    .jam-marker {{
      width:30px; height:30px; border-radius:50%; color:white;
      display:flex; align-items:center; justify-content:center;
      font-size:17px; font-weight:900; border:2px solid white;
      box-shadow:0 4px 14px rgba(0,0,0,.35);
    }}
    .jam-marker.red {{ background:#ef4444; }}
    .jam-marker.orange {{ background:#f59e0b; }}
    .jam-pulse {{
      animation: tripSmartPulse 1.35s infinite;
    }}
    @keyframes tripSmartPulse {{
      0% {{ transform:scale(1); box-shadow:0 0 0 0 rgba(239,68,68,.42), 0 4px 14px rgba(0,0,0,.35); }}
      70% {{ transform:scale(1.04); box-shadow:0 0 0 12px rgba(239,68,68,0), 0 4px 14px rgba(0,0,0,.35); }}
      100% {{ transform:scale(1); box-shadow:0 0 0 0 rgba(239,68,68,0), 0 4px 14px rgba(0,0,0,.35); }}
    }}
  </style>
</head>
<body>
  <div id="traffic-map"></div>
  <div id="traffic-badge" class="traffic-badge">Traffic: đang tải tile tf/...</div>
  <div class="legend">
    <span><i class="dot" style="background:#f59e0b"></i>chậm</span>
    <span><i class="dot" style="background:#ef4444"></i>kẹt</span>
  </div>

<script>
const API_KEY = {api_key!r};
const hasKey = !!API_KEY;
const badge = document.getElementById('traffic-badge');
function setBadge(text, type='ok') {{
  badge.textContent = text;
  badge.classList.toggle('err', type === 'err');
  badge.classList.toggle('warn', type === 'warn');
}}

// Nền bản đồ luôn dùng OSM raster để tránh trắng map.
const baseStyle = {{
  version: 8,
  sources: {{
    osm: {{
      type: 'raster',
      tiles: ['https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png'],
      tileSize: 256,
      attribution: '© OpenStreetMap'
    }}
  }},
  layers: [{{ id: 'osm-base', type: 'raster', source: 'osm' }}]
}};

const map = new vietmapgl.Map({{
  container: 'traffic-map',
  style: baseStyle,
  center: [106.7009, 10.7769],
  zoom: 13,
  maxZoom: 20
}});
map.addControl(new vietmapgl.NavigationControl(), 'bottom-right');

let gpsMarker = null;
let jamMarkers = [];
let refreshTimer = null;
let sourceReady = false;
let printedSample = false;

function addTrafficSourceForMarkers() {{
  if (!hasKey) {{
    setBadge('Chưa có VietMap API key', 'err');
    return;
  }}

  const tfTileUrl = `https://maps.vietmap.vn/maps/tiles/tf/{{z}}/{{x}}/{{y}}.pbf?apikey=${{API_KEY}}`;

  if (!map.getSource('ts-traffic')) {{
    map.addSource('ts-traffic', {{
      type: 'vector',
      tiles: [tfTileUrl],
      minzoom: 10,
      maxzoom: 24
    }});
  }}

  // Layer ẩn gần như hoàn toàn để ép vector tile tf được tải theo viewport.
  // Không tô màu đường, vì yêu cầu hiện tại chỉ muốn marker đoạn kẹt/chậm.
  if (!map.getLayer('ts-traffic-hit-layer')) {{
    map.addLayer({{
      id: 'ts-traffic-hit-layer',
      type: 'line',
      source: 'ts-traffic',
      'source-layer': 'jam',
      minzoom: 10,
      layout: {{ 'line-cap':'round', 'line-join':'round' }},
      paint: {{
        'line-color': 'rgba(239,68,68,0.01)',
        'line-width': ['interpolate', ['linear'], ['zoom'], 10, 8, 13, 12, 16, 18, 20, 24],
        'line-opacity': 0.01
      }}
    }});
  }}

  sourceReady = true;
  setBadge('Traffic marker mode ON · đang đọc tf/...', 'ok');
  console.log('[TripSmart Traffic Markers] source:', tfTileUrl.replace(API_KEY, '***'));
  scheduleMarkerRefresh(700);
}}

function parseRgbString(s) {{
  const m = String(s).match(/rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i);
  if (!m) return null;
  return {{ r: Number(m[1]), g: Number(m[2]), b: Number(m[3]) }};
}}

function parseHexColor(s) {{
  let v = String(s || '').trim().toLowerCase();
  const m = v.match(/#([0-9a-f]{{3}}|[0-9a-f]{{6}})/i);
  if (!m) return null;
  let hex = m[1];
  if (hex.length === 3) hex = hex.split('').map(c => c+c).join('');
  const n = parseInt(hex, 16);
  return {{ r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 }};
}}

function rgbToSeverity(rgb) {{
  if (!rgb) return null;
  const {{r,g,b}} = rgb;
  // Đỏ/kẹt: đỏ trội, xanh lá thấp.
  if (r >= 170 && g <= 120 && b <= 140) return 'red';
  // Cam/vàng/chậm: đỏ cao, xanh lá vừa-cao, xanh dương thấp.
  if (r >= 170 && g >= 90 && g <= 220 && b <= 150) return 'orange';
  return null;
}}

function getSeverityFromProps(props) {{
  props = props || {{}};
  const candidates = [
    props.color, props.rcolor, props.lcolor, props.jam_color, props.jamColor,
    props.severity, props.level, props.congestion, props.status, props.speed_level,
    props.traffic, props.traffic_level
  ].filter(v => v !== undefined && v !== null && String(v).trim() !== '');

  for (const raw of candidates) {{
    const s = String(raw).trim().toLowerCase();
    if (!s) continue;

    if (s.includes('red') || s.includes('heavy') || s.includes('jam') || s.includes('congest') || s.includes('kẹt')) return 'red';
    if (s.includes('orange') || s.includes('yellow') || s.includes('amber') || s.includes('slow') || s.includes('medium') || s.includes('chậm')) return 'orange';

    const rgb = parseRgbString(s) || parseHexColor(s);
    const sev = rgbToSeverity(rgb);
    if (sev) return sev;

    const num = Number(s);
    if (!Number.isNaN(num)) {{
      // Không biết thang đo chính xác của VietMap nên chỉ coi mức cao là kẹt/chậm.
      if (num >= 4) return 'red';
      if (num >= 2) return 'orange';
    }}
  }}
  return null;
}}

function midpointFromGeometry(geom) {{
  if (!geom || !geom.coordinates) return null;
  let line = null;
  if (geom.type === 'LineString') {{
    line = geom.coordinates;
  }} else if (geom.type === 'MultiLineString') {{
    line = (geom.coordinates || []).reduce((best, cur) => (cur && cur.length > (best ? best.length : 0)) ? cur : best, null);
  }}
  if (!line || line.length < 2) return null;
  const c = line[Math.floor(line.length / 2)];
  if (!Array.isArray(c) || c.length < 2) return null;
  const lon = Number(c[0]);
  const lat = Number(c[1]);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return null;
  return [lon, lat];
}}

function clearJamMarkers() {{
  jamMarkers.forEach(m => m.remove());
  jamMarkers = [];
}}

function addJamMarker(lngLat, severity, props) {{
  const el = document.createElement('div');
  el.className = `jam-marker ${{severity}}${{severity === 'red' ? ' jam-pulse' : ''}}`;
  el.textContent = severity === 'red' ? '!' : '⚠';
  const label = severity === 'red' ? 'Kẹt xe' : 'Đường chậm';
  el.title = label;
  const marker = new vietmapgl.Marker(el)
    .setLngLat(lngLat)
    .setPopup(new vietmapgl.Popup({{ offset: 18 }}).setHTML(
      `<b>${{label}}</b><br><small>VietMap traffic tile</small>`
    ))
    .addTo(map);
  jamMarkers.push(marker);
}}

function refreshJamMarkers() {{
  if (!sourceReady || !map.getLayer('ts-traffic-hit-layer')) return;
  try {{
    const features = map.queryRenderedFeatures({{ layers: ['ts-traffic-hit-layer'] }}) || [];

    if (!printedSample && features.length) {{
      printedSample = true;
      console.log('[TripSmart Traffic] sample properties:', features.slice(0, 5).map(f => f.properties));
    }}

    const candidates = [];
    const seen = new Set();
    for (const f of features) {{
      const sev = getSeverityFromProps(f.properties);
      if (!sev) continue;
      const mid = midpointFromGeometry(f.geometry);
      if (!mid) continue;

      // Dedupe theo ô ~100m để không spam marker.
      const key = `${{sev}}:${{mid[0].toFixed(3)}}:${{mid[1].toFixed(3)}}`;
      if (seen.has(key)) continue;
      seen.add(key);
      candidates.push({{ mid, sev, props: f.properties || {{}} }});
    }}

    candidates.sort((a, b) => (a.sev === b.sev ? 0 : (a.sev === 'red' ? -1 : 1)));
    const limited = candidates.slice(0, 35);
    clearJamMarkers();
    limited.forEach(item => addJamMarker(item.mid, item.sev, item.props));

    const redCount = limited.filter(x => x.sev === 'red').length;
    const orangeCount = limited.filter(x => x.sev === 'orange').length;
    if (features.length === 0) {{
      setBadge('Traffic tf đã gọi · chưa có feature trong viewport', 'warn');
    }} else if (limited.length === 0) {{
      setBadge(`Traffic tf có ${{features.length}} feature · chưa thấy đoạn chậm/kẹt`, 'warn');
    }} else {{
      setBadge(`Traffic marker: ${{redCount}} kẹt · ${{orangeCount}} chậm · ${{features.length}} feature`, 'ok');
    }}
  }} catch (err) {{
    console.warn('[TripSmart Traffic] marker refresh failed:', err);
    setBadge('Không đọc được feature traffic · xem Console', 'err');
  }}
}}

function scheduleMarkerRefresh(delay=450) {{
  if (refreshTimer) clearTimeout(refreshTimer);
  refreshTimer = setTimeout(refreshJamMarkers, delay);
}}

function updateGps(lat, lon, acc) {{
  if (!gpsMarker) {{
    const el = document.createElement('div');
    el.className = 'gps-dot';
    gpsMarker = new vietmapgl.Marker(el).setLngLat([lon, lat]).addTo(map);
    map.flyTo({{ center: [lon, lat], zoom: 15 }});
  }} else {{
    gpsMarker.setLngLat([lon, lat]);
  }}
}}

map.on('load', () => {{
  addTrafficSourceForMarkers();
}});

map.on('idle', () => scheduleMarkerRefresh(250));
map.on('moveend', () => scheduleMarkerRefresh(500));
map.on('zoomend', () => scheduleMarkerRefresh(500));
map.on('sourcedata', (e) => {{
  if (e.sourceId === 'ts-traffic') scheduleMarkerRefresh(600);
}});

map.on('error', (e) => {{
  const msg = (e && e.error && e.error.message) ? e.error.message : String(e && e.error || 'unknown');
  console.warn('[TripSmart Traffic/map error]', msg, e);
  if (msg.includes('ts-traffic') || msg.includes('/tf/') || msg.includes('traffic')) {{
    setBadge('Traffic tile lỗi · kiểm tra Network tf', 'err');
  }}
}});

if ('geolocation' in navigator) {{
  navigator.geolocation.watchPosition(
    pos => updateGps(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy),
    err => console.warn('[TripSmart GPS]', err),
    {{ enableHighAccuracy:true, maximumAge:1000, timeout:10000 }}
  );
}}
</script>
</body>
</html>
"""
    components.html(html, height=height + 8, scrolling=False)
