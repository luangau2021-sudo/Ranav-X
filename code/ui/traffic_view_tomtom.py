# ui/traffic_view_tomtom.py
# Traffic View riêng cho TripSmart Pro dùng TomTom Traffic Incidents realtime.
# - Không cần điểm đi / điểm đến.
# - Có chấm xanh GPS hiện tại.
# - Chỉ gọi dữ liệu trong vùng bản đồ đang nhìn thấy.
# - Pan/zoom sẽ gọi lại TomTom theo viewport mới.

from __future__ import annotations

import os
import streamlit as st
import streamlit.components.v1 as components

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def _get_tomtom_api_key() -> str:
    """Lấy TomTom API key từ .env / biến môi trường / st.secrets."""
    for key_name in ("TOMTOM_API_KEY", "TOMTOM_KEY"):
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


def render_traffic_view_tomtom(height: int = 760) -> None:
    """Render bản đồ traffic riêng bằng TomTom Incident Details theo viewport."""
    api_key = _get_tomtom_api_key()

    st.title("🚦 Kiểm tra kẹt xe")
    st.caption(
        "Bản đồ traffic riêng, không cần tìm đường trước. "
        "App lấy sự cố/kẹt xe TomTom trong đúng vùng bản đồ đang xem."
    )

    if not api_key:
        st.warning(
            "⚠️ Chưa tìm thấy `TOMTOM_API_KEY`. Thêm key vào `.streamlit/secrets.toml` "
            "hoặc file `.env`, rồi chạy lại app."
        )
        with st.expander("Cách thêm TomTom API key", expanded=False):
            st.code('''# .streamlit/secrets.toml\nTOMTOM_API_KEY = "YOUR_TOMTOM_API_KEY"''', language="toml")

    # Dùng repr để đưa key vào JS an toàn.
    key_js = repr(api_key)

    html = r"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    html, body {{ margin:0; padding:0; width:100%; height:100%; font-family: Inter, Arial, sans-serif; background:#fff; }}
    #traffic-map {{ width:100%; height:__HEIGHT__px; border-radius:18px; overflow:hidden; background:#eef2f7; }}
    .ts-badge {{
      position:absolute; z-index:600; right:16px; top:14px;
      background:rgba(255,255,255,.94); color:#0f172a;
      border:1px solid rgba(15,23,42,.12); border-radius:999px;
      box-shadow:0 8px 22px rgba(15,23,42,.14);
      padding:8px 12px; font-size:13px; font-weight:800;
      max-width:520px; white-space:normal;
    }}
    .ts-legend {{
      position:absolute; z-index:600; right:16px; top:56px;
      background:rgba(255,255,255,.94); border:1px solid rgba(15,23,42,.12);
      border-radius:14px; padding:8px 10px; font-size:12px; font-weight:700;
      box-shadow:0 8px 22px rgba(15,23,42,.10);
    }}
    .lg {{ display:inline-flex; align-items:center; gap:5px; margin-right:8px; }}
    .dot {{ width:10px; height:10px; border-radius:99px; display:inline-block; }}
    .gps-dot {{
      width:18px; height:18px; border-radius:50%; background:#0b84ff;
      border:3px solid #fff; box-shadow:0 0 0 8px rgba(11,132,255,.18), 0 2px 8px rgba(0,0,0,.35);
    }}
    .jam-marker {{
      width:34px; height:34px; border-radius:50%; display:flex; align-items:center; justify-content:center;
      color:white; font-size:17px; font-weight:900; border:3px solid white;
      box-shadow:0 4px 14px rgba(0,0,0,.35);
    }}
    .jam-red {{ background:#ef4444; }}
    .jam-orange {{ background:#f59e0b; }}
    .jam-dark {{ background:#111827; }}
    .leaflet-popup-content {{ font-family:Inter,Arial,sans-serif; font-size:13px; line-height:1.35; }}
    .ts-panel {{
      position:absolute; z-index:600; left:14px; top:14px; width:250px;
      background:rgba(255,255,255,.94); border:1px solid rgba(15,23,42,.12);
      border-radius:16px; padding:10px 12px; box-shadow:0 10px 26px rgba(15,23,42,.16);
      font-size:12px; color:#0f172a;
    }}
    .ts-title {{ font-size:14px; font-weight:900; margin-bottom:5px; }}
    .ts-small {{ color:#64748b; font-size:11px; line-height:1.3; }}
    .ts-btn {{
      border:1px solid #cbd5e1; background:white; border-radius:10px; padding:6px 9px;
      cursor:pointer; font-weight:800; margin-top:8px; font-size:12px;
    }}
  </style>
</head>
<body>
  <div id="traffic-map"></div>
  <div id="status" class="ts-badge">Đang khởi tạo TomTom Traffic…</div>
  <div class="ts-legend">
    <span class="lg"><span class="dot" style="background:#f59e0b"></span>chậm</span>
    <span class="lg"><span class="dot" style="background:#ef4444"></span>kẹt/sự cố</span>
    <span class="lg"><span class="dot" style="background:#111827"></span>đường đóng</span>
  </div>
  <div class="ts-panel">
    <div class="ts-title">🚦 Traffic View</div>
    <div id="gpsStatus" class="ts-small">GPS: đang xin quyền vị trí…</div>
    <div id="viewStatus" class="ts-small">Viewport: đang khởi tạo…</div>
    <button id="locateBtn" class="ts-btn">📍 Về vị trí tôi</button>
    <button id="refreshBtn" class="ts-btn">↻ Tải lại traffic</button>
  </div>

<script>
const API_KEY = __KEY__;
const map = L.map('traffic-map', {{ zoomControl:true }}).setView([10.7769, 106.7009], 12);
L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  maxZoom: 19,
  attribution: '© OpenStreetMap · Traffic © TomTom'
}}).addTo(map);

let gpsMarker = null;
let lastGps = null;
let incidentLayer = L.layerGroup().addTo(map);
let incidentLines = L.layerGroup().addTo(map);
let timer = null;

function setText(id, txt) {{
  const el = document.getElementById(id);
  if (el) el.textContent = txt;
}}
function setStatus(txt) {{ setText('status', txt); }}
function esc(s) {{
  return String(s ?? '').replace(/[&<>\"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}}[c]));
}}
function centerOfGeometry(geom) {{
  if (!geom || !geom.coordinates) return null;
  if (geom.type === 'Point') return [geom.coordinates[1], geom.coordinates[0]];
  if (geom.type === 'LineString' && geom.coordinates.length) {{
    const mid = geom.coordinates[Math.floor(geom.coordinates.length / 2)];
    return [mid[1], mid[0]];
  }}
  if (Array.isArray(geom.coordinates) && geom.coordinates.length >= 2 && typeof geom.coordinates[0] === 'number') {{
    return [geom.coordinates[1], geom.coordinates[0]];
  }}
  return null;
}}
function lineLatLngs(geom) {{
  if (!geom || geom.type !== 'LineString' || !Array.isArray(geom.coordinates)) return null;
  return geom.coordinates.map(c => [c[1], c[0]]);
}}
function severity(props) {{
  const icon = Number(props.iconCategory ?? 0);
  const mag = Number(props.magnitudeOfDelay ?? 0);
  // TomTom icon categories: 6 = Jam, 8 = Road Closed, 1 = Accident, 7 = Lane Closed, 9 = Road Works.
  if (icon === 8 || mag === 4) return {{ level:'closed', cls:'jam-dark', color:'#111827', label:'Đường đóng', emoji:'⛔' }};
  if (icon === 6 || mag >= 3 || icon === 1) return {{ level:'red', cls:'jam-red', color:'#ef4444', label:'Kẹt / sự cố nặng', emoji:'!' }};
  if (mag >= 1 || icon === 7 || icon === 9 || icon === 14 || icon === 3) return {{ level:'orange', cls:'jam-orange', color:'#f59e0b', label:'Chậm / sự cố nhẹ', emoji:'!' }};
  return {{ level:'orange', cls:'jam-orange', color:'#f59e0b', label:'Sự cố giao thông', emoji:'!' }};
}}
function eventText(props) {{
  try {{
    const events = props.events || [];
    if (events.length && events[0].description) return events[0].description;
  }} catch (e) {{}}
  const icon = Number(props.iconCategory ?? 0);
  const names = {{1:'Tai nạn',2:'Sương mù',3:'Điều kiện nguy hiểm',4:'Mưa',5:'Băng trơn',6:'Ùn tắc',7:'Đóng làn',8:'Đường đóng',9:'Công trình',10:'Gió',11:'Ngập',14:'Xe hỏng'}};
  return names[icon] || 'Sự cố giao thông';
}}
function updateViewportText() {{
  const b = map.getBounds();
  setText('viewStatus', `Viewport: W ${{b.getWest().toFixed(4)}} · S ${{b.getSouth().toFixed(4)}} · E ${{b.getEast().toFixed(4)}} · N ${{b.getNorth().toFixed(4)}}`);
}}
function clearIncidents() {{
  incidentLayer.clearLayers();
  incidentLines.clearLayers();
}}
function bboxAreaKm2(b) {{
  const latMid = (b.getNorth() + b.getSouth()) / 2;
  const kmLat = 111.0;
  const kmLon = 111.0 * Math.cos(latMid * Math.PI / 180);
  return Math.abs(b.getEast() - b.getWest()) * kmLon * Math.abs(b.getNorth() - b.getSouth()) * kmLat;
}}
async function loadIncidents() {{
  updateViewportText();
  clearIncidents();
  if (!API_KEY) {{ setStatus('Thiếu TOMTOM_API_KEY'); return; }}
  const z = map.getZoom();
  if (z < 9) {{ setStatus('Zoom gần hơn để tải kẹt xe realtime'); return; }}
  const b = map.getBounds();
  const area = bboxAreaKm2(b);
  if (area > 10000) {{ setStatus('Vùng xem quá rộng, zoom gần hơn để tải traffic'); return; }}
  const bbox = `${{b.getWest().toFixed(6)}},${{b.getSouth().toFixed(6)}},${{b.getEast().toFixed(6)}},${{b.getNorth().toFixed(6)}}`;
  const fields = `{incidents{{type,geometry{{type,coordinates}},properties{{id,iconCategory,magnitudeOfDelay,events{{description,code,iconCategory}},startTime,endTime,from,to,length,delay,roadNumbers,timeValidity,probabilityOfOccurrence,numberOfReports,lastReportTime}}}}}}`;
  const url = 'https://api.tomtom.com/maps/orbis/traffic/incidentDetails'
    + '?apiVersion=1'
    + '&key=' + encodeURIComponent(API_KEY)
    + '&bbox=' + encodeURIComponent(bbox)
    + '&fields=' + encodeURIComponent(fields)
    // TomTom Incident Details không hỗ trợ vi-VN; dùng en-US để tránh HTTP 400 INVALID_REQUEST.
    + '&language=en-US'
    + '&timeValidityFilter=present';
  setStatus('Đang tải TomTom traffic incidents…');
  try {{
    const res = await fetch(url);
    if (!res.ok) {{
      const txt = await res.text().catch(()=>'');
      throw new Error('HTTP ' + res.status + (txt ? ' · ' + txt.slice(0,120) : ''));
    }}
    const data = await res.json();
    const incidents = (data && data.incidents) || [];
    if (!incidents.length) {{
      setStatus('TomTom: không có kẹt xe/sự cố trong vùng đang xem');
      return;
    }}
    let red = 0, orange = 0, closed = 0;
    incidents.forEach((inc) => {{
      const props = inc.properties || {{}};
      const sev = severity(props);
      if (sev.level === 'closed') closed++; else if (sev.level === 'red') red++; else orange++;
      const line = lineLatLngs(inc.geometry);
      if (line && line.length >= 2) {{
        L.polyline(line, {{color: sev.color, weight: 6, opacity: .82}}).addTo(incidentLines);
      }}
      const c = centerOfGeometry(inc.geometry);
      if (!c) return;
      const desc = eventText(props);
      const road = (props.roadNumbers || []).join(', ');
      const fromTo = [props.from, props.to].filter(Boolean).join(' → ');
      const delayMin = props.delay ? Math.round(Number(props.delay) / 60) : 0;
      const lenM = props.length ? Math.round(Number(props.length)) : 0;
      const html = `<div class="jam-marker ${{sev.cls}}">${{sev.emoji}}</div>`;
      const icon = L.divIcon({{className:'', html, iconSize:[34,34], iconAnchor:[17,17]}});
      const popup = `
        <b>${{esc(sev.label)}}</b><br>
        ${{esc(desc)}}<br>
        ${{road ? 'Đường: <b>' + esc(road) + '</b><br>' : ''}}
        ${{fromTo ? esc(fromTo) + '<br>' : ''}}
        ${{delayMin ? 'Trễ khoảng: <b>' + delayMin + ' phút</b><br>' : ''}}
        ${{lenM ? 'Chiều dài ảnh hưởng: <b>' + lenM + ' m</b><br>' : ''}}
        <span style="color:#64748b">Nguồn: TomTom realtime</span>`;
      L.marker(c, {{icon}}).bindPopup(popup).addTo(incidentLayer);
    }});
    setStatus(`TomTom realtime: ${{incidents.length}} sự cố · 🔴 ${{red}} · 🟠 ${{orange}} · ⛔ ${{closed}}`);
  }} catch (e) {{
    console.error(e);
    setStatus('Lỗi TomTom traffic: ' + (e.message || e));
  }}
}}
function scheduleLoad() {{
  clearTimeout(timer);
  timer = setTimeout(loadIncidents, 650);
}}

map.on('load', loadIncidents);
map.on('moveend', scheduleLoad);
map.on('zoomend', scheduleLoad);
document.getElementById('refreshBtn').onclick = loadIncidents;
document.getElementById('locateBtn').onclick = () => {{ if (lastGps) map.flyTo({{center:[lastGps.lat,lastGps.lon], zoom:15}}); }};

if ('geolocation' in navigator) {{
  navigator.geolocation.watchPosition(
    pos => {{
      const lat = pos.coords.latitude, lon = pos.coords.longitude, acc = pos.coords.accuracy;
      lastGps = {{lat, lon, acc}};
      if (!gpsMarker) {{
        const el = document.createElement('div');
        el.className = 'gps-dot';
        gpsMarker = L.marker([lat, lon], {{icon: L.divIcon({{className:'', html:el.outerHTML, iconSize:[18,18], iconAnchor:[9,9]}})}}).addTo(map);
        map.flyTo([lat, lon], 14);
      }} else {{ gpsMarker.setLatLng([lat, lon]); }}
      setText('gpsStatus', `GPS: ${{lat.toFixed(5)}}, ${{lon.toFixed(5)}} ±${{Math.round(acc)}}m`);
    }},
    err => setText('gpsStatus', 'GPS: chưa cấp quyền hoặc thiết bị không trả vị trí'),
    {{enableHighAccuracy:true, maximumAge:1000, timeout:10000}}
  );
}} else {{ setText('gpsStatus', 'GPS: trình duyệt không hỗ trợ geolocation'); }}

// Load lần đầu sau khi tile base map render.
setTimeout(loadIncidents, 800);
</script>
</body>
</html>
"""
    # Vì html ở trên dùng raw string, các dấu {{ }} từng được escape cho f-string
    # sẽ đi nguyên vào trình duyệt và làm CSS/JS lỗi cú pháp.
    # Chuyển lại về { } trước khi render để Leaflet chạy được.
    html = html.replace("__HEIGHT__", str(height)).replace("__KEY__", key_js)
    html = html.replace("{{", "{").replace("}}", "}")
    components.html(html, height=height + 8, scrolling=False)
