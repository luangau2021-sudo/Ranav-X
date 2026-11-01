import json
import streamlit as st
import streamlit.components.v1 as components

try:
    from streamlit_js_eval import get_geolocation, streamlit_js_eval
    _JSEVAL_OK = True
except ImportError:
    get_geolocation = None
    streamlit_js_eval = None
    _JSEVAL_OK = False

try:
    from streamlit_autorefresh import st_autorefresh
    _AUTOREFRESH_OK = True
except ImportError:
    st_autorefresh = None
    _AUTOREFRESH_OK = False

def _build_gps_component_html(interval_ms: int = 5000) -> str:
    """
    Trả về HTML nhúng component JS:
    - Hỏi quyền GPS 1 lần
    - Cập nhật tự động theo interval_ms
    - Ghi tọa độ vào localStorage key 'tripsmart_gps'
    - Hiển thị badge trạng thái GPS nhỏ gọn
    - Dùng postMessage để gửi toạ độ lên Streamlit parent frame
    """
    return f"""
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body{{margin:0;padding:6px;font-family:'Segoe UI',sans-serif;background:transparent;}}
  #gps-box{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;}}
  .badge{{display:inline-flex;align-items:center;gap:6px;border-radius:20px;
          padding:5px 14px;font-size:.82rem;font-weight:600;border:1.5px solid;}}
  .badge-ok   {{background:#e3f2fd;border-color:#1976d2;color:#1565c0;}}
  .badge-warn {{background:#fff3e0;border-color:#f57c00;color:#e65100;}}
  .badge-err  {{background:#ffebee;border-color:#e53935;color:#b71c1c;}}
  .dot{{width:9px;height:9px;border-radius:50%;animation:pulse 1.4s infinite;}}
  .dot-blue  {{background:#1976d2;}}
  .dot-orange{{background:#f57c00;}}
  .dot-red   {{background:#e53935;}}
  @keyframes pulse{{0%,100%{{opacity:1;transform:scale(1)}}50%{{opacity:.4;transform:scale(1.5)}}}}
  #coords{{font-size:.78rem;color:#555;margin-top:2px;}}
  #btn-gps{{padding:6px 16px;background:#1976d2;color:white;border:none;
            border-radius:20px;cursor:pointer;font-size:.82rem;font-weight:600;}}
  #btn-gps:hover{{background:#1565c0;}}
</style>
</head>
<body>
<div id="gps-box">
  <button id="btn-gps" onclick="requestGPS()">📡 Bật GPS tự động</button>
  <span id="badge-area"></span>
</div>
<div id="coords"></div>

<script>
const INTERVAL_MS = {interval_ms};
let watchId = null;
let gpsPollId = null;
let permitted = false;

function setBadge(cls, dot, text) {{
  document.getElementById('badge-area').innerHTML =
    `<span class="badge ${{cls}}"><span class="dot ${{dot}}"></span>${{text}}</span>`;
}}

function sendPos(lat, lon, acc) {{
  const payload = {{lat, lon, acc, ts: Date.now(), source: 'shared_gps_component'}};
  // Gửi lên Streamlit qua postMessage + lưu cùng 1 key GPS chung
  try {{ window.parent.postMessage({{type: 'tripsmart_gps', payload}}, '*'); }} catch(e) {{}}
  try {{ localStorage.setItem('tripsmart_gps', JSON.stringify(payload)); }} catch(e) {{}}
  try {{ window.parent.localStorage.setItem('tripsmart_gps', JSON.stringify(payload)); }} catch(e) {{}}
  document.getElementById('coords').textContent =
    `📍 Lat: ${{lat.toFixed(6)}}  Lon: ${{lon.toFixed(6)}}  ±${{acc ? acc.toFixed(0) : '?'}}m`;
}}

function onPos(pos) {{
  setBadge('badge-ok','dot-blue','GPS đang hoạt động');
  sendPos(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy);
}}

function onErr(err) {{
  setBadge('badge-err','dot-red', err.code === 1 ? 'Bị từ chối quyền GPS' : 'Không lấy được GPS');
}}

function requestGPS() {{
  if (!navigator.geolocation) {{
    setBadge('badge-err','dot-red','Trình duyệt không hỗ trợ GPS');
    return;
  }}
  setBadge('badge-warn','dot-orange','Đang chờ quyền GPS…');
  // Lần đầu: lấy ngay, KHÔNG dùng cache cũ
  navigator.geolocation.getCurrentPosition(onPos, onErr, {{
    enableHighAccuracy: true, timeout: 8000, maximumAge: 0
  }});
  // Theo dõi liên tục bằng watchPosition. Lưu ý: trình duyệt không cam kết callback đúng mỗi 1 giây.
  if (watchId !== null) navigator.geolocation.clearWatch(watchId);
  watchId = navigator.geolocation.watchPosition(onPos, onErr, {{
    enableHighAccuracy: true, timeout: 8000, maximumAge: 0
  }});
  // ÉP kiểm tra lại mỗi 1 giây để localStorage/SOS luôn có vị trí mới nhất có thể.
  // Nếu hệ điều hành chưa trả vị trí mới thì vẫn dùng vị trí mới nhất hiện có, không chờ khi bấm SOS.
  if (gpsPollId !== null) clearInterval(gpsPollId);
  gpsPollId = setInterval(() => {{
    navigator.geolocation.getCurrentPosition(onPos, onErr, {{
      enableHighAccuracy: true, timeout: 8000, maximumAge: 0
    }});
  }}, 1000);
  document.getElementById('btn-gps').textContent = '🔄 GPS đang theo dõi…';
  document.getElementById('btn-gps').disabled = true;
  permitted = true;
}}

// Tự khởi động nếu đã được cấp quyền trước đó (check localStorage)
window.addEventListener('load', () => {{
  try {{
    const saved = localStorage.getItem('tripsmart_gps');
    if (saved) {{
      const p = JSON.parse(saved);
      // Nếu GPS cũ < 30 giây thì tự bật
      if (Date.now() - p.ts < 30000) {{
        requestGPS();
      }}
    }}
  }} catch(e) {{}}
}});
</script>
</body>
</html>
"""



# ─────────────────────────────────────────────────────────────────────────────
# GPS SYNC + AUTO ETA HELPERS
# ─────────────────────────────────────────────────────────────────────────────
AUTO_ETA_INTERVAL_SEC = 5 * 60
GPS_MAX_AGE_SEC       = 5 * 60

# ── Tốc độ trung bình dùng để tính ETA / AI Risk Forecast ───────────────────
# Không dùng thời gian OSRM để tính ETA vì OSRM thường giả định tốc độ cao hơn
# thực tế khi đi đường Việt Nam. Các giá trị này áp dụng nhất quán cho:
# tuyến ban đầu, auto ETA, reroute, ETA thủ công và AI forecast theo thời gian.
AVG_SPEED_KMH_BY_MODE = {
    "car": 40.0,
    "motorbike": 40.0,
    "bike": 20.0,
    "walk": 5.0,
}



# Không dùng thời gian OSRM để tính ETA vì OSRM thường giả định tốc độ cao hơn
# thực tế khi đi đường Việt Nam. Các giá trị này áp dụng nhất quán cho:
# tuyến ban đầu, auto ETA, reroute, ETA thủ công và AI forecast theo thời gian.
AVG_SPEED_KMH_BY_MODE = {
    "car": 40.0,
    "motorbike": 40.0,
    "bike": 20.0,
    "walk": 5.0,
}


def _sync_nav_gps_from_browser(now_ts=None):
    """Đồng bộ GPS live từ trình duyệt về session_state để Python dùng."""
    import time as _time
    if now_ts is None:
        now_ts = _time.time()
    if not st.session_state.get("nav_active") or st.session_state.get("nav_arrived"):
        return False
    updated = False

    if _JSEVAL_OK and streamlit_js_eval is not None:
        try:
            raw = streamlit_js_eval(
                js_expressions="localStorage.getItem('tripsmart_gps')",
                key="sync_tripsmart_gps_localstorage",
            )
            if raw:
                payload = json.loads(raw) if isinstance(raw, str) else raw
                lat = payload.get("lat")
                lon = payload.get("lon")
                ts  = payload.get("ts", 0)
                if isinstance(ts, (int, float)) and ts > 10_000_000_000:
                    ts = ts / 1000.0
                if lat is not None and lon is not None:
                    st.session_state["nav_gps_lat"] = float(lat)
                    st.session_state["nav_gps_lon"] = float(lon)
                    st.session_state["nav_gps_ts"]  = float(ts or now_ts)
                    st.session_state["nav_gps_source"] = "live_js"
                    updated = True
        except Exception as e:
            st.session_state["nav_gps_sync_error"] = str(e)

    gps_ts = st.session_state.get("nav_gps_ts", 0.0)
    gps_age = now_ts - gps_ts if gps_ts else 999999
    if (not updated or gps_age > GPS_MAX_AGE_SEC) and _JSEVAL_OK and get_geolocation is not None:
        try:
            geo = get_geolocation()
            if geo and isinstance(geo, dict) and geo.get("coords"):
                coords = geo.get("coords", {})
                lat = coords.get("latitude")
                lon = coords.get("longitude")
                if lat is not None and lon is not None:
                    st.session_state["nav_gps_lat"] = float(lat)
                    st.session_state["nav_gps_lon"] = float(lon)
                    st.session_state["nav_gps_ts"]  = now_ts
                    st.session_state["nav_gps_source"] = "geolocation_eval"
                    updated = True
        except Exception as e:
            st.session_state["nav_gps_sync_error"] = str(e)
    return updated




def _maybe_schedule_nav_rerun():
    if st.session_state.get("nav_active") and not st.session_state.get("nav_arrived"):
        if _AUTOREFRESH_OK and st_autorefresh is not None:
            st_autorefresh(interval=AUTO_ETA_INTERVAL_SEC * 1000, key="auto_eta_5min_refresh")



# ─────────────────────────────────────────────────────────────────────────────
# GPS ONE-CLICK ORIGIN HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _build_gps_preload_html(interval_ms: int = 1000, hidden: bool = True) -> str:
    """
    Component JS chạy sớm khi mở trang Tìm đường:
    - Tự xin quyền GPS nếu trình duyệt cho phép
    - getCurrentPosition() lấy ngay 1 lần
    - watchPosition() theo dõi liên tục
    - Lưu chung vào localStorage key 'tripsmart_gps'

    Mục tiêu: khi bấm 'Dùng vị trí GPS của tôi', Python chỉ đọc GPS đã có,
    tránh phải bấm nhiều lần.
    """
    box_style = "display:none;" if hidden else "display:flex;align-items:center;gap:8px;font-size:12px;color:#64748b;"
    return f"""
<!DOCTYPE html>
<html>
<head><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:transparent;">
<div id="ts-gps-preload" style="{box_style}">📡 GPS preload đang sẵn sàng…</div>
<script>
const TS_GPS_INTERVAL_MS = {int(interval_ms)};
let tsWatchId = null;
let tsPollId = null;
let tsStarted = false;

function tsSaveGPS(pos) {{
  if (!pos || !pos.coords) return;
  const payload = {{
    lat: pos.coords.latitude,
    lon: pos.coords.longitude,
    acc: pos.coords.accuracy,
    ts: Date.now(),
    source: 'gps_preload_oneclick'
  }};
  try {{ localStorage.setItem('tripsmart_gps', JSON.stringify(payload)); }} catch(e) {{}}
  try {{ window.parent.localStorage.setItem('tripsmart_gps', JSON.stringify(payload)); }} catch(e) {{}}
  try {{ window.parent.postMessage({{type:'tripsmart_gps', payload}}, '*'); }} catch(e) {{}}
  const box = document.getElementById('ts-gps-preload');
  if (box) box.textContent = `📡 GPS ready: ${{payload.lat.toFixed(5)}},${{payload.lon.toFixed(5)}}`;
}}

function tsGpsErr(err) {{
  const box = document.getElementById('ts-gps-preload');
  if (box) box.textContent = err && err.code === 1 ? 'GPS bị chặn quyền' : 'Đang chờ GPS…';
}}

function tsStartGPS() {{
  if (tsStarted) return;
  tsStarted = true;
  if (!navigator.geolocation) return;
  const opts = {{enableHighAccuracy:true, timeout:10000, maximumAge:0}};
  try {{ navigator.geolocation.getCurrentPosition(tsSaveGPS, tsGpsErr, opts); }} catch(e) {{}}
  try {{
    if (tsWatchId !== null) navigator.geolocation.clearWatch(tsWatchId);
    tsWatchId = navigator.geolocation.watchPosition(tsSaveGPS, tsGpsErr, opts);
  }} catch(e) {{}}
  try {{
    if (tsPollId !== null) clearInterval(tsPollId);
    tsPollId = setInterval(() => {{
      navigator.geolocation.getCurrentPosition(tsSaveGPS, tsGpsErr, opts);
    }}, TS_GPS_INTERVAL_MS);
  }} catch(e) {{}}
}}

window.addEventListener('load', () => {{ setTimeout(tsStartGPS, 80); }});
// Nếu browser chặn auto prompt, lần click đầu tiên bất kỳ trên trang cũng kích hoạt lại.
window.addEventListener('click', tsStartGPS, {{once:true}});
</script>
</body>
</html>
"""


def _read_latest_gps_from_browser(max_age_sec: int = 600, key: str = "read_latest_tripsmart_gps"):
    """Đọc GPS mới nhất từ localStorage tripsmart_gps, không yêu cầu nav_active."""
    import time as _time
    if not (_JSEVAL_OK and streamlit_js_eval is not None):
        return None
    try:
        raw = streamlit_js_eval(
            js_expressions="localStorage.getItem('tripsmart_gps')",
            key=key,
        )
        if not raw:
            return None
        payload = json.loads(raw) if isinstance(raw, str) else raw
        lat = payload.get("lat")
        lon = payload.get("lon")
        if lat is None or lon is None:
            return None
        ts = payload.get("ts", 0)
        if isinstance(ts, (int, float)) and ts > 10_000_000_000:
            ts = ts / 1000.0
        age = _time.time() - float(ts or 0)
        if max_age_sec is not None and age > max_age_sec:
            return None
        return {
            "lat": float(lat),
            "lon": float(lon),
            "acc": payload.get("acc"),
            "ts": float(ts or _time.time()),
            "age_sec": age,
            "source": payload.get("source", "localStorage"),
        }
    except Exception as e:
        st.session_state["gps_origin_read_error"] = str(e)
        return None
