import json
from datetime import datetime
from urllib.parse import quote

import streamlit as st
import streamlit.components.v1 as components

try:
    from streamlit_js_eval import streamlit_js_eval
    _JSEVAL_OK = True
except ImportError:
    streamlit_js_eval = None
    _JSEVAL_OK = False

def _sos_init_state():
    """Khởi tạo bộ nhớ SOS trong session. Chuyển menu không mất; restart web/server thì mất."""
    if "sos_family_contacts" not in st.session_state:
        st.session_state["sos_family_contacts"] = []
    if "sos_pending_messages" not in st.session_state:
        st.session_state["sos_pending_messages"] = []


def _sos_normalize_phone_for_sms(phone: str) -> str:
    """Giữ số điện thoại ở định dạng đủ an toàn cho sms:."""
    raw = str(phone or "").strip()
    keep = ""
    for i, ch in enumerate(raw):
        if ch.isdigit() or (ch == "+" and i == 0):
            keep += ch
    return keep


def _sos_get_family_contacts():
    _sos_init_state()
    return list(st.session_state.get("sos_family_contacts", []))


def _sos_add_family_contact(name: str, phone: str):
    _sos_init_state()
    p = _sos_normalize_phone_for_sms(phone)
    if not p or len(p) < 8:
        return False, "Nhập số điện thoại hợp lệ trước khi thêm."
    contacts = st.session_state.get("sos_family_contacts", [])
    if any(_sos_normalize_phone_for_sms(c.get("phone")) == p for c in contacts):
        return False, "Số này đã có trong danh sách."
    contacts.append({"name": (name or "Người thân").strip(), "phone": p})
    st.session_state["sos_family_contacts"] = contacts
    return True, "Đã thêm số người thân."


def _sos_build_sms_link(phone: str, body: str) -> str:
    import urllib.parse as _urlparse
    phone = _sos_normalize_phone_for_sms(phone)
    return f"sms:{phone}?&body={_urlparse.quote(body or '')}"


def _sos_latest_gps_from_browser(key_suffix: str = "sos_gps"):
    """
    Đọc GPS mới nhất do bản đồ live ghi vào localStorage.
    Khi người dùng bấm nút trong Streamlit, rerun xảy ra → hàm này lấy tọa độ gần nhất.
    """
    # Ưu tiên localStorage của bản đồ live GPS
    if _JSEVAL_OK and streamlit_js_eval is not None:
        try:
            raw = streamlit_js_eval(
                js_expressions="localStorage.getItem('tripsmart_gps')",
                key=f"read_tripsmart_gps_for_{key_suffix}",
            )
            if raw:
                payload = json.loads(raw) if isinstance(raw, str) else raw
                lat = payload.get("lat")
                lon = payload.get("lon")
                if lat is not None and lon is not None:
                    return {
                        "lat": float(lat),
                        "lon": float(lon),
                        "ts": payload.get("ts"),
                        "acc": payload.get("acc"),
                        "source": "live_map_localstorage",
                    }
        except Exception:
            pass
    # Fallback: GPS đã sync vào session khi Auto ETA/IOT chạy
    try:
        lat = st.session_state.get("nav_gps_lat")
        lon = st.session_state.get("nav_gps_lon")
        if lat is not None and lon is not None:
            return {"lat": float(lat), "lon": float(lon), "ts": st.session_state.get("nav_gps_ts"), "source": "session_nav_gps"}
    except Exception:
        pass
    return None


def _sos_message_template(etype_label, lat, lon, msg_text=""):
    now_txt = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    if lat is not None and lon is not None:
        loc_line = f"Vị trí: {float(lat):.6f}, {float(lon):.6f}\nBản đồ: https://maps.google.com/?q={float(lat):.6f},{float(lon):.6f}"
    else:
        loc_line = "Vị trí: chưa lấy được GPS. Hãy gọi lại ngay để xác minh vị trí."
    desc = str(msg_text or "").strip()
    desc_line = f"\nMô tả: {desc}" if desc else ""
    return (
        "SOS KHẨN CẤP - TripSmart Pro\n"
        f"Tôi đang gặp sự cố: {etype_label}\n"
        f"Thời gian: {now_txt}\n"
        f"{loc_line}"
        f"{desc_line}\n"
        "Vui lòng gọi lại hoặc hỗ trợ ngay khi có thể."
    )


def _render_sos_contacts_manager(prefix: str = "sos", require_hint: bool = False):
    """UI nhập số người thân dùng chung ở Tìm đường và SOS."""
    _sos_init_state()
    if require_hint:
        st.caption("Nhập số người thân trước khi bắt đầu hành trình để khi có sự cố chỉ cần bấm gửi SOS.")
    add_c1, add_c2, add_c3 = st.columns([1.2, 1.2, 0.75])
    with add_c1:
        new_name = st.text_input("Tên người thân", placeholder="VD: Mẹ, Ba, Anh...", key=f"{prefix}_new_contact_name")
    with add_c2:
        new_phone = st.text_input("Số điện thoại", placeholder="VD: 0987654321", key=f"{prefix}_new_contact_phone")
    with add_c3:
        st.write("")
        st.write("")
        if st.button("➕ Thêm số", use_container_width=True, key=f"{prefix}_add_contact"):
            ok, msg = _sos_add_family_contact(new_name, new_phone)
            if ok:
                st.success(msg)
            else:
                st.warning(msg)

    contacts = _sos_get_family_contacts()
    if contacts:
        for idx, c in enumerate(list(contacts)):
            row_l, row_r = st.columns([4, 1])
            row_l.markdown(f"**{idx+1}. {c.get('name','Người thân')}** · `{c.get('phone','')}`")
            if row_r.button("🗑️ Xóa", key=f"{prefix}_delete_contact_{idx}", use_container_width=True):
                contacts.pop(idx)
                st.session_state["sos_family_contacts"] = contacts
                st.rerun()
    else:
        st.info("Chưa có số người thân. Hãy thêm ít nhất 1 số để bật SOS nhanh khi đi đường.")
    return contacts


def _render_one_tap_journey_sos_button(prefix: str = "journey_sos"):
    """
    Nút SOS nhanh trong sidebar.

    Nguyên lý đúng theo yêu cầu:
    - GPS KHÔNG đợi tới lúc bấm SOS mới lấy.
    - Khi đang dẫn đường, GPS dùng một nguồn chung: chấm xanh live trên bản đồ.
    - Component SOS chỉ đọc tripsmart_gps đã được bản đồ ghi sẵn.
    - Khi bấm SOS, nút chỉ dùng latestGps đã có sẵn để mở SMS ngay.
    - Không đợi lấy GPS tại thời điểm bấm SOS.
    """
    contacts = _sos_get_family_contacts()
    if not contacts:
        st.warning("Chưa có số người thân. Thêm số trước khi bắt đầu hành trình để dùng SOS nhanh.")
        return

    numbers = ",".join(_sos_normalize_phone_for_sms(c.get("phone")) for c in contacts)
    names = ", ".join(c.get("name", "Người thân") for c in contacts)

    # Fallback Python: dùng GPS gần nhất trong session nếu JS chưa đọc được localStorage.
    fallback_gps = _sos_latest_gps_from_browser(f"{prefix}_fallback") or {}

    import html as _html
    import json as _json
    # Trạng thái hiển thị ban đầu lấy trực tiếp từ Python/session_state.
    # Như vậy nếu phần bản đồ/ETA đã có "GPS mới", sidebar SOS không còn hiện "đang chờ GPS" vô lý.
    import time as _time
    def _norm_ts_ms(_ts):
        try:
            t = float(_ts or 0)
            if t and t < 10_000_000_000:
                t *= 1000.0
            return t
        except Exception:
            return 0.0

    _fb_lat = fallback_gps.get("lat")
    _fb_lon = fallback_gps.get("lon")
    _fb_ts_ms = _norm_ts_ms(fallback_gps.get("ts"))
    _fb_age = int(max(0, (_time.time()*1000 - _fb_ts_ms) / 1000)) if _fb_ts_ms else None
    if _fb_lat is not None and _fb_lon is not None and _fb_age is not None and _fb_age <= 60:
        initial_gps_class = "gps-ok" if _fb_age <= 15 else "gps-warn"
        initial_gps_text = f"✅ GPS sẵn sàng · {float(_fb_lat):.5f}, {float(_fb_lon):.5f} · mới {_fb_age}s"
    elif _fb_lat is not None and _fb_lon is not None:
        initial_gps_class = "gps-warn"
        initial_gps_text = f"🟡 GPS sẵn sàng · {float(_fb_lat):.5f}, {float(_fb_lon):.5f}"
    else:
        initial_gps_class = "gps-warn"
        initial_gps_text = "⏳ Đang đồng bộ GPS mới nhất..."

    payload = {
        "numbers": numbers,
        "names": names,
        "fallback_lat": _fb_lat,
        "fallback_lon": _fb_lon,
        "fallback_ts": fallback_gps.get("ts"),
        "initial_status_text": initial_gps_text,
        "initial_status_class": initial_gps_class,
    }
    payload_js = _json.dumps(payload, ensure_ascii=False)

    html = f"""
<!DOCTYPE html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{{margin:0;font-family:Arial,sans-serif;background:transparent;}}
.sos-wrap{{border:2px solid #ff4b4b;background:#fff5f5;border-radius:14px;padding:12px;}}
.sos-title{{font-weight:700;color:#b71c1c;margin-bottom:8px;font-size:15px;}}
.sos-btn{{width:100%;border:0;border-radius:12px;padding:13px 16px;background:#ff4b4b;color:white;
font-size:16px;font-weight:800;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.18);}}
.sos-btn:active{{transform:scale(.99);}}
.sos-note{{font-size:12px;color:#666;margin-top:7px;line-height:1.35;}}
.gps-cache{{font-size:12px;margin:8px 0 2px 0;border-radius:10px;padding:7px 9px;background:#fff;border:1px solid #ffcdd2;color:#555;}}
.gps-ok{{border-color:#43a047;color:#1b5e20;background:#f1f8e9;}}
.gps-warn{{border-color:#f9a825;color:#e65100;background:#fffde7;}}
.gps-bad{{border-color:#e53935;color:#b71c1c;background:#ffebee;}}
</style></head>
<body>
<div class="sos-wrap">
  <div class="sos-title">🆘 SOS nhanh hành trình</div>
  <div id="gps-cache-status" class="gps-cache {initial_gps_class}">{_html.escape(initial_gps_text)}</div>
  <button class="sos-btn" onclick="sendJourneySOS()">🆘 Gửi SOS ngay</button>
  <div class="sos-note">
    Gửi đến: {_html.escape(names)}.<br>
    GPS lấy từ chấm xanh bản đồ; bấm SOS là gửi đúng vị trí đó.
  </div>
</div>
<script>
const SOS_DATA = {payload_js};
let latestGps = null;
let latestGpsTs = 0;
let cacheTimer = null;
let sosGpsWatchId = null; // giữ tên biến cũ để không ảnh hưởng code, không dùng watcher riêng

function normalizeTs(ts) {{
  let n = Number(ts || 0);
  if (!n) return 0;
  if (n < 10000000000) n = n * 1000; // giây → mili giây
  return n;
}}

function setStatus(text, cls) {{
  const el = document.getElementById('gps-cache-status');
  if (!el) return;
  el.className = 'gps-cache ' + cls;
  el.textContent = text;
}}

function saveLatestGps(p, source) {{
  if (!p || p.lat == null || p.lon == null) return false;
  const lat = Number(p.lat), lon = Number(p.lon);
  if (!isFinite(lat) || !isFinite(lon)) return false;
  const ts = normalizeTs(p.ts) || Date.now();
  latestGps = {{lat: lat, lon: lon, acc: p.acc, ts: ts, source: source || 'cache'}};
  latestGpsTs = ts;
  return true;
}}

function readGpsFromLocalStorage() {{
  try {{
    const raw = (window.parent && window.parent.localStorage ? window.parent.localStorage.getItem('tripsmart_gps') : null) || localStorage.getItem('tripsmart_gps');
    if (!raw) return false;
    const p = JSON.parse(raw);
    return saveLatestGps(p, 'localStorage');
  }} catch(e) {{
    return false;
  }}
}}

function refreshGpsCacheStatus() {{
  readGpsFromLocalStorage();

  // Fallback từ Python session nếu chưa có GPS trong localStorage.
  if (!latestGps && SOS_DATA.fallback_lat != null && SOS_DATA.fallback_lon != null) {{
    saveLatestGps({{lat: SOS_DATA.fallback_lat, lon: SOS_DATA.fallback_lon, ts: SOS_DATA.fallback_ts}}, 'python_fallback');
  }}

  if (!latestGps) {{
    setStatus('⚠️ Chưa có GPS mới. Hãy bật GPS/dẫn đường hoặc cho phép vị trí.', 'gps-bad');
    return;
  }}

  const ageSec = Math.max(0, Math.round((Date.now() - latestGpsTs) / 1000));
  const accText = latestGps.acc ? (' ±' + Math.round(Number(latestGps.acc)) + 'm') : '';
  if (ageSec <= 15) {{
    setStatus('✅ GPS đã sẵn sàng · ' + latestGps.lat.toFixed(5) + ', ' + latestGps.lon.toFixed(5) + accText + ' · mới ' + ageSec + 's', 'gps-ok');
  }} else if (ageSec <= 60) {{
    setStatus('🟡 GPS có sẵn nhưng đã ' + ageSec + 's · vẫn có thể gửi SOS', 'gps-warn');
  }} else {{
    setStatus('🔴 GPS đã cũ ' + ageSec + 's · nên bật/làm mới GPS trên bản đồ', 'gps-bad');
  }}
}}


function startSOSGpsWatcher() {{
  // SOS không tự gọi navigator.geolocation.
  // Nguồn đúng duy nhất là GPS live của bản đồ (chấm xanh) ghi vào tripsmart_gps.
  // Như vậy chấm xanh đi tới đâu, SOS gửi đúng tọa độ đó.
  refreshGpsCacheStatus();
  if (window.__tripsmartSOSPollId) clearInterval(window.__tripsmartSOSPollId);
  window.__tripsmartSOSPollId = setInterval(function() {{
    refreshGpsCacheStatus();
  }}, 1000);
}}

// Nhận GPS từ iframe bản đồ nếu bản đồ postMessage lên parent.
window.addEventListener('message', function(e) {{
  try {{
    if (e.data && e.data.type === 'tripsmart_gps' && e.data.payload) {{
      saveLatestGps(e.data.payload, 'postMessage');
      try {{ localStorage.setItem('tripsmart_gps', JSON.stringify(e.data.payload)); }} catch(err) {{}}
      refreshGpsCacheStatus();
    }}
  }} catch(err) {{}}
}});

function buildSmsBody() {{
  const gps = latestGps;
  const now = new Date().toLocaleString('vi-VN');
  let body = 'SOS KHẨN CẤP - TripSmart Pro\n' +
             'Tôi đang gặp sự cố trên hành trình.\n' +
             'Thời gian: ' + now + '\n';
  if (gps) {{
    const lat = gps.lat.toFixed(6), lon = gps.lon.toFixed(6);
    const ageSec = Math.max(0, Math.round((Date.now() - gps.ts) / 1000));
    body += 'Vị trí mới nhất: ' + lat + ', ' + lon + '\n' +
            'Bản đồ: https://maps.google.com/?q=' + lat + ',' + lon + '\n' +
            'GPS cập nhật cách đây: ' + ageSec + ' giây\n';
  }} else {{
    body += 'Vị trí: chưa lấy được GPS. Hãy gọi lại ngay để xác minh vị trí.\n';
  }}
  body += 'Vui lòng gọi lại hoặc hỗ trợ ngay khi có thể.';
  return body;
}}

function sendJourneySOS() {{
  // Không gọi geolocation ở đây. Chỉ dùng latestGps đã được cập nhật sẵn.
  refreshGpsCacheStatus();
  const uri = 'sms:' + SOS_DATA.numbers + '?&body=' + encodeURIComponent(buildSmsBody());
  try {{ window.top.location.href = uri; }} catch(e) {{ window.location.href = uri; }}
}}

startSOSGpsWatcher();
refreshGpsCacheStatus();
if (cacheTimer) clearInterval(cacheTimer);
cacheTimer = setInterval(refreshGpsCacheStatus, 1000);
</script>
</body></html>
"""

    components.html(html, height=172, scrolling=False)


def _render_floating_sos_button(prefix: str = "floating_sos"):
    """
    SOS nổi cố định ở góc màn hình, dùng được ở mọi trang/chức năng.
    Bản này không đặt SOS trong sidebar nữa, mà render trực tiếp vào main DOM.
    GPS dùng một nguồn chung: chấm xanh live trên bản đồ ghi vào localStorage tripsmart_gps; SOS chỉ đọc lại nguồn đó.
    """
    contacts = _sos_get_family_contacts()
    if not contacts:
        return

    numbers = ",".join(_sos_normalize_phone_for_sms(c.get("phone")) for c in contacts)
    names = ", ".join(c.get("name", "Người thân") for c in contacts)
    fallback_gps = _sos_latest_gps_from_browser(f"{prefix}_fallback") or {}

    import time as _time
    import json as _json
    import html as _html
    from urllib.parse import quote as _quote

    def _norm_ts_sec(ts):
        try:
            t = float(ts or 0)
            if t > 10_000_000_000:
                t = t / 1000.0
            return t
        except Exception:
            return 0.0

    lat = fallback_gps.get("lat")
    lon = fallback_gps.get("lon")
    ts_sec = _norm_ts_sec(fallback_gps.get("ts"))
    age = int(max(0, _time.time() - ts_sec)) if ts_sec else None

    if lat is not None and lon is not None:
        if age is None:
            gps_status = f"✅ GPS sẵn sàng · {float(lat):.5f}, {float(lon):.5f}"
            gps_class = "ok"
        elif age <= 60:
            gps_status = f"✅ GPS sẵn sàng · {float(lat):.5f}, {float(lon):.5f} · mới {age}s"
            gps_class = "ok"
        else:
            gps_status = f"🟡 GPS có sẵn · {float(lat):.5f}, {float(lon):.5f} · {age}s"
            gps_class = "warn"
        initial_body = _sos_message_template("Hành trình", lat, lon)
    else:
        gps_status = "⚠️ Chưa có GPS từ bản đồ · vẫn có thể gửi SOS"
        gps_class = "warn"
        initial_body = _sos_message_template("Hành trình", None, None)

    initial_href = f"sms:{numbers}?&body={_quote(initial_body)}"
    safe_names = _html.escape(names)
    safe_status = _html.escape(gps_status)
    safe_href = _html.escape(initial_href, quote=True)

    # Thẻ SOS cố định trong main DOM, nên luôn thấy ở góc màn hình và không bị cuộn theo sidebar.
    st.markdown(f"""
<style>
#ts-fixed-sos-card {{
  position: fixed;
  right: 22px;
  bottom: 22px;
  width: 198px;
  z-index: 2147483000;
  background: linear-gradient(180deg,#ff4b4b,#e53935);
  color: white;
  border-radius: 20px;
  padding: 13px 13px 14px 13px;
  box-shadow: 0 14px 34px rgba(0,0,0,.28);
  border: 2px solid rgba(255,255,255,.75);
  font-family: 'Be Vietnam Pro', Arial, sans-serif;
}}
#ts-fixed-sos-card .ts-title {{font-size: 15px; font-weight: 900; margin-bottom: 7px;}}
#ts-fixed-sos-status {{font-size: 11px; line-height: 1.25; padding: 7px 8px; border-radius: 11px; margin-bottom: 9px; background: rgba(255,255,255,.92); color: #1b5e20;}}
#ts-fixed-sos-status.warn {{color:#e65100;}}
#ts-fixed-sos-status.bad {{color:#b71c1c;}}
#ts-fixed-sos-card .ts-send {{
  display: block; text-align: center; text-decoration: none;
  background: white; color: #c62828; font-size: 15px; font-weight: 900;
  border-radius: 14px; padding: 12px 10px;
  box-shadow: inset 0 -2px 0 rgba(0,0,0,.06);
}}
#ts-fixed-sos-card .ts-small {{font-size: 10.5px; opacity: .92; margin-top: 7px; line-height: 1.25;}}
@media (max-width: 700px) {{
  #ts-fixed-sos-card {{right: 12px; bottom: 12px; width: 160px; padding: 11px;}}
  #ts-fixed-sos-card .ts-send {{font-size: 14px; padding: 11px 8px;}}
  #ts-fixed-sos-status {{font-size: 10.5px;}}
}}
</style>
<div id="ts-fixed-sos-card">
  <div class="ts-title">🆘 SOS nhanh</div>
  <div id="ts-fixed-sos-status" class="{gps_class}">{safe_status}</div>
  <a id="ts-fixed-sos-link" class="ts-send" href="{safe_href}">Gửi SOS</a>
  <div class="ts-small">Gửi đến: {safe_names}</div>
</div>
""", unsafe_allow_html=True)

    payload = {
        "numbers": numbers,
        "fallback_lat": lat,
        "fallback_lon": lon,
        "fallback_ts": fallback_gps.get("ts"),
    }
    payload_js = _json.dumps(payload, ensure_ascii=False)

    # JS cập nhật trạng thái/href mỗi giây từ nguồn GPS chung do chấm xanh trên bản đồ ghi vào localStorage.
    # SOS KHÔNG tự gọi geolocation riêng để tránh lệch nguồn với chấm xanh.
    html = f"""
<!DOCTYPE html>
<html><body>
<script>
(function() {{
  const DATA = {payload_js};
  let latestGps = null;
  let latestGpsTs = 0;

  function normalizeTs(ts) {{
    let n = Number(ts || 0);
    if (!n) return 0;
    if (n < 10000000000) n = n * 1000;
    return n;
  }}

  function saveGps(p, source) {{
    if (!p || p.lat == null || p.lon == null) return false;
    const lat = Number(p.lat), lon = Number(p.lon);
    if (!isFinite(lat) || !isFinite(lon)) return false;
    const ts = normalizeTs(p.ts) || Date.now();
    if (latestGps && latestGpsTs && ts < latestGpsTs) return false;
    latestGps = {{lat: lat, lon: lon, acc: p.acc, ts: ts, source: source || 'gps'}};
    latestGpsTs = ts;
    return true;
  }}

  function readLocalStorageGps() {{
    try {{
      const raw = window.parent.localStorage.getItem('tripsmart_gps') || localStorage.getItem('tripsmart_gps');
      if (!raw) return false;
      return saveGps(JSON.parse(raw), 'localStorage');
    }} catch(e) {{ return false; }}
  }}

  function useFallbackGps() {{
    if (DATA.fallback_lat != null && DATA.fallback_lon != null) {{
      return saveGps({{lat: DATA.fallback_lat, lon: DATA.fallback_lon, ts: DATA.fallback_ts}}, 'python_session');
    }}
    return false;
  }}

  function ageSec() {{
    if (!latestGpsTs) return null;
    return Math.max(0, Math.round((Date.now() - latestGpsTs) / 1000));
  }}

  function buildBody() {{
    readLocalStorageGps();
    if (!latestGps) useFallbackGps();
    const now = new Date().toLocaleString('vi-VN');
    let body = 'SOS KHẨN CẤP - TripSmart Pro\\n' +
               'Tôi đang gặp sự cố trên hành trình.\\n' +
               'Thời gian: ' + now + '\\n';
    if (latestGps) {{
      const lat = latestGps.lat.toFixed(6), lon = latestGps.lon.toFixed(6);
      const age = ageSec();
      body += 'Vị trí mới nhất: ' + lat + ', ' + lon + '\\n' +
              'Bản đồ: https://maps.google.com/?q=' + lat + ',' + lon + '\\n' +
              'GPS cập nhật cách đây: ' + (age == null ? '?' : age) + ' giây\\n';
    }} else {{
      body += 'Vị trí: chưa lấy được GPS. Hãy gọi lại ngay để xác minh vị trí.\\n';
    }}
    body += 'Vui lòng gọi lại hoặc hỗ trợ ngay khi có thể.';
    return body;
  }}

  function updateCard() {{
    readLocalStorageGps();
    if (!latestGps) useFallbackGps();
    const doc = window.parent.document;
    const status = doc.getElementById('ts-fixed-sos-status');
    const link = doc.getElementById('ts-fixed-sos-link');
    if (!status || !link) return;
    let text = '⚠️ Chưa có GPS từ bản đồ · vẫn có thể gửi SOS';
    let cls = 'warn';
    if (latestGps) {{
      const a = ageSec();
      const acc = latestGps.acc ? (' ±' + Math.round(Number(latestGps.acc)) + 'm') : '';
      if (a <= 60) {{
        text = '✅ GPS sẵn sàng · ' + latestGps.lat.toFixed(5) + ', ' + latestGps.lon.toFixed(5) + acc + ' · ' + a + 's';
        cls = 'ok';
      }} else {{
        text = '🟡 GPS có sẵn · ' + latestGps.lat.toFixed(5) + ', ' + latestGps.lon.toFixed(5) + ' · ' + a + 's';
        cls = 'warn';
      }}
    }}
    status.className = cls;
    status.textContent = text;
    link.href = 'sms:' + DATA.numbers + '?&body=' + encodeURIComponent(buildBody());
  }}

  function startWatcher() {{
    // SOS không tự gọi navigator.geolocation.
    // Nguồn đúng duy nhất là GPS live của bản đồ (chấm xanh) đã ghi vào tripsmart_gps.
    // Hàm này chỉ đọc localStorage/postMessage để SOS gửi đúng nơi chấm xanh đang đứng.
    readLocalStorageGps();
    updateCard();
  }}

  try {{
    window.parent.addEventListener('message', function(e) {{
      try {{
        if (e.data && e.data.type === 'tripsmart_gps' && e.data.payload) {{
          saveGps(e.data.payload, 'postMessage');
          updateCard();
        }}
      }} catch(err) {{}}
    }});
  }} catch(e) {{}}

  readLocalStorageGps();
  useFallbackGps();
  updateCard();
  startWatcher();
  setInterval(function(){{ readLocalStorageGps(); updateCard(); }}, 1000);
}})();
</script>
</body></html>
"""
    components.html(html, height=1, scrolling=False)


# ─────────────────────────────────────────────────────────────────────────────
# NET ZERO + SOCIAL IMPACT + SAFETY EDUCATION HELPERS
# ─────────────────────────────────────────────────────────────────────────────
CO2_G_PER_KM_BY_MODE = {
    "car": 180.0,       # ước tính trung bình cho ô tô xăng phổ thông
    "motorbike": 75.0, # ước tính trung bình cho xe máy
    "bike": 0.0,
    "walk": 0.0,
}

