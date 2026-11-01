import streamlit as st
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
FAVICON_PATH = BASE_DIR / "assets" / "Favicon.png"
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
import streamlit.components.v1 as components
import sys, os, folium, json
from urllib.parse import quote, unquote

                                                                              
                                                                                 
try:
    from live_navigation import _snap_to_route, _hav, _do_reroute
    _LIVE_NAV_OK = True
except ImportError:
    _LIVE_NAV_OK = False
from datetime import datetime, date, time, timedelta
EMOTION_LABELS = {1:"😞",2:"😐",3:"😊",4:"😄",5:"🤩"}

                                             
from ui.styles import load_global_styles
from features.gps_live import (
    _build_gps_component_html,
    _build_gps_preload_html,
    _read_latest_gps_from_browser,
    _sync_nav_gps_from_browser,
    _maybe_schedule_nav_rerun,
    GPS_MAX_AGE_SEC,
    AUTO_ETA_INTERVAL_SEC,
)
from features.floating_sos import (
    _sos_init_state,
    _sos_normalize_phone_for_sms,
    _sos_get_family_contacts,
    _sos_add_family_contact,
    _sos_build_sms_link,
    _sos_latest_gps_from_browser,
    _sos_message_template,
    _render_sos_contacts_manager,
    _render_one_tap_journey_sos_button,
    _render_floating_sos_button,
)
from core.route_state import (
    _persist_current_route_snapshot,
    _restore_route_snapshot_if_needed,
    _clear_pending_route_search_state,
    _clear_route_snapshot_from_browser_session,
)
                                            

                                             
from core.route_calc import (
    RED_RISK_THRESHOLD, ORANGE_RISK_THRESHOLD, YELLOW_RISK_THRESHOLD,
    AVG_SPEED_KMH_BY_MODE,
    _risk_score_float, _risk_level_icon, _risk_alert_css, risk_color,
    _haversine_km, _find_nearest_segment, _calc_iot_state_from_gps,
    _default_avg_speed_kmh_by_mode, _avg_speed_kmh_by_mode,
    _format_speed_label, _format_default_speed_label,
    _duration_seconds_by_distance_mode, _distance_km_from_polyline,
    _get_route_distance_km, _apply_avg_speed_timing,
    _apply_avg_speed_timing_to_routes, _format_duration_from_seconds,
    _get_route_duration_seconds, _compute_route_forecast,
    _route_cache_key, _clear_route_view_cache,
    _parse_session_datetime, _save_route_runtime_options,
    _restore_route_runtime_options,
)
from core.copilot import (
    _safe_parse_dt, _minutes_until_eta, _copilot_segment_score,
    _copilot_is_high, _build_mobility_copilot_state,
    _render_mobility_copilot_state, _route_avg_risk_for_copilot,
)
from core.local_reroute import (
    _coord_at_route_km, _resolve_critical_coords, _route_passes_danger,
    _polyline_cumulative_km, _nearest_route_km_to_coord,
    _polyline_prefix_until_km, _polyline_suffix_from_km,
    _polyline_segment_between_km, _dedupe_polyline,
    _splice_local_reroute, _accept_copilot_reroute,
    _min_distance_polyline_to_coord_km, _local_detour_waypoints_around_point,
    _apply_new_local_reroute_to_session, _accept_copilot_rest,
)
from ui.route_panels import (
    _render_route_forecast, _co2_factor_g_per_km,
    _estimate_hazard_penalty_equiv_km, _render_env_social_impact,
    _render_safety_quiz,
)
from ui.streamlit_map import _cluster_danger_markers, make_full_map
from ui.traffic_view_tomtom import render_traffic_view_tomtom
from core.legal_route_filter import (
    normalize_mode, validate_route_for_mode, filter_routes_for_mode,
    is_reasonable_detour, detour_limit_text, find_legal_routes_with_fallback, is_reasonable_motorbike_avoid_expressway, motorbike_avoid_expressway_limit_text,
)
try:
    from core.speed_limit import SpeedLimitEngine
    _SPEED_LIMIT_OK = True
except Exception:
    SpeedLimitEngine = None
    _SPEED_LIMIT_OK = False

                                                                    
                                         
try:
    from core.tomtom_speed_limit import get_speed_limit_from_tomtom
    _TOMTOM_SPEED_LIMIT_OK = True
except Exception:
    get_speed_limit_from_tomtom = None
    _TOMTOM_SPEED_LIMIT_OK = False

                                                                                       
                                                                               
try:
    from core.goong_speed_limit import (
        get_speed_limit_from_goong,
        get_goong_speed_limits_on_route,
    )
    _GOONG_SPEED_LIMIT_OK = True
except Exception:
    get_speed_limit_from_goong = None
    get_goong_speed_limits_on_route = None
    _GOONG_SPEED_LIMIT_OK = False
                                              

st.set_page_config(
    page_title="RANav-X",
    page_icon=str(FAVICON_PATH),
    layout="wide",
    initial_sidebar_state="expanded"
)

load_global_styles()

st.markdown("""
<style>

/* FIX MOBILE: hạ nút đóng/mở sidebar xuống để không bị fact trên cùng che */
@media (max-width: 760px) {
    div[data-testid="collapsedControl"] {
        top: 48px !important;
        z-index: 2147483700 !important;
    }

    section[data-testid="stSidebar"] button[data-testid="baseButton-headerNoPadding"],
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-headerNoPadding"],
    button[data-testid="baseButton-headerNoPadding"],
    button[data-testid="stBaseButton-headerNoPadding"],
    button[title="Close sidebar"],
    button[title="Open sidebar"],
    button[aria-label="Close sidebar"],
    button[aria-label="Open sidebar"],
    button[aria-label="Show sidebar navigation"],
    button[aria-label="Hide sidebar navigation"] {
        transform: translateY(36px) !important;
        z-index: 2147483700 !important;
    }

    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 34px !important;
    }
}

</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* tripsmart mobile compact placement final */
@media (max-width: 760px) {
    .main .block-container { padding-bottom: 72px !important; }
}
</style>
""", unsafe_allow_html=True)


                                                                               
                                                                  
                                                                               
st.markdown("""
<style>
.stApp,
section.main,
main,
div[data-testid="stAppViewContainer"],
div[data-testid="stMain"],
div[data-testid="stMainBlockContainer"],
div[data-testid="stVerticalBlock"],
div[data-testid="stElementContainer"],
div[data-testid="stSidebar"],
section[data-testid="stSidebar"],
div[data-testid="stSidebarContent"],
iframe,
[data-testid="stIFrame"] {
    opacity: 1 !important;
    filter: none !important;
}
button,
button:disabled,
input,
input:disabled,
textarea,
textarea:disabled,
select,
select:disabled,
div[aria-disabled="true"],
*[disabled] {
    opacity: 1 !important;
    filter: none !important;
}
div[data-testid="stStatusWidget"],
div[data-testid="stDecoration"] {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
}
</style>
""", unsafe_allow_html=True)

# FIX: chỉ đổi màu chữ 3 chỗ trong SOS sidebar (Tên người thân, Số điện thoại, Số SOS đã lưu)
st.markdown("""
<style>
/* 1) Label ô nhập Tên người thân + Số điện thoại trong sidebar */
section[data-testid="stSidebar"] div[data-testid="stTextInput"] label,
section[data-testid="stSidebar"] div[data-testid="stTextInput"] label p {
    color: #ffffff !important;
    font-weight: 800 !important;
}

/* 2) Chữ/số người dùng nhập trong 2 ô input */
section[data-testid="stSidebar"] div[data-testid="stTextInput"] input {
    color: #111827 !important;
    font-weight: 700 !important;
}

/* Placeholder: VD: Mẹ, VD: 098... */
section[data-testid="stSidebar"] div[data-testid="stTextInput"] input::placeholder {
    color: #6b7280 !important;
    opacity: 1 !important;
}

/* 3) Chữ dòng Số SOS đã lưu */
section[data-testid="stSidebar"] details summary,
section[data-testid="stSidebar"] details summary p {
    color: #ffffff !important;
    font-weight: 800 !important;
}
</style>
""", unsafe_allow_html=True)



try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from core.routing         import Router
    from core.risk_engine     import RiskEngine
    from core.human_aware     import HumanAwareRouter
    from core.reroute         import RerouteEngine
    from features.sos         import SOSHandler
    from features.crowdsource import CrowdsourceEngine
    from features.poi         import POIEngine
    from features.memory_trail   import MemoryTrailEngine
    from features.disaster_route import DisasterRouteEngine
    from api.weather_api import WeatherAPI
    from api.maps_api    import MapsAPI
    from api.ai_engine   import AIEngine
    from core.route_risk_forecast import analyze_route_risk_by_time
    MODULES_OK = True
except Exception as e:
    MODULES_OK = False; IMPORT_ERROR = str(e)

@st.cache_resource
def init_engines():
    return (Router(), RiskEngine(), HumanAwareRouter(),
            SOSHandler(), CrowdsourceEngine(), POIEngine(),
            MemoryTrailEngine(), WeatherAPI(), MapsAPI(), AIEngine())

                                             
                                                                   
RED_RISK_THRESHOLD = 0.90
ORANGE_RISK_THRESHOLD = 0.65
YELLOW_RISK_THRESHOLD = 0.40










import math


                                                                               
                    
                                                                               
def _effective_sliding_departure_dt(planned_departure_dt, now_dt=None, nav_active=False):
    """
    Giờ xuất phát hiệu lực cho dự báo ETA.

    - Nếu giờ xuất phát người dùng chọn còn ở tương lai: giữ nguyên giờ đó.
    - Nếu giờ xuất phát đã qua mà người dùng chưa bắt đầu/không di chuyển: trượt mốc xuất phát về hiện tại.
      Nhờ vậy ETA từng đoạn tự lùi về sau sau mỗi nhịp 5 phút.
    - Nếu đang dẫn đường bằng GPS: cũng dùng hiện tại làm mốc, vì ETA phải tính từ vị trí/thời điểm hiện tại.
    """
    try:
        now_dt = (now_dt or datetime.now()).replace(second=0, microsecond=0)
        if planned_departure_dt is None:
            return now_dt
        if not hasattr(planned_departure_dt, 'replace'):
            return now_dt
        planned = planned_departure_dt.replace(second=0, microsecond=0)
        if nav_active:
            return now_dt
                                                                                       
                                           
        if planned <= now_dt:
            return now_dt
        return planned
    except Exception:
        return (now_dt or datetime.now()).replace(second=0, microsecond=0)










                                                                               
                             
                                                                               

                                                                              
                                                                              
                                                                       
                                                                               
AVG_SPEED_KMH_BY_MODE = {
    "car": 40.0,
    "motorbike": 40.0,
}
























def _run_auto_eta_update(router, risk_engine, weather_api, dest_fallback, mode_fallback, now_ts=None):
    """Tính lại tuyến còn lại + ETA + AI Risk Forecast từ GPS hiện tại."""
    import time as _time
    if now_ts is None:
        now_ts = _time.time()
    ss = st.session_state
    if not ss.get("nav_active") or ss.get("nav_arrived"):
        return False

    g_lat = ss.get("nav_gps_lat")
    g_lon = ss.get("nav_gps_lon")
    g_ts  = ss.get("nav_gps_ts", 0.0)
    gps_age = now_ts - g_ts if g_ts else 999999
    if g_lat is None or g_lon is None:
        ss["auto_eta_status"] = "⚠️ Chưa có GPS hợp lệ — hãy bật GPS trên bản đồ."
        return False
    if gps_age > GPS_MAX_AGE_SEC:
        ss["auto_eta_status"] = "⚠️ GPS cũ hơn 5 phút — chờ tín hiệu GPS mới."
        return False

    dest = ss.get("nav_dest", dest_fallback)
    mode = ss.get("nav_mode", mode_fallback)
    try:
        rem_route = router.get_route((float(g_lat), float(g_lon)), dest, mode=mode)
        _apply_avg_speed_timing(rem_route, mode)
        if not rem_route or not rem_route.get("polyline"):
            ss["auto_eta_status"] = "⚠️ Không tính được tuyến còn lại từ GPS hiện tại."
            return False
        rem_poly = rem_route.get("polyline", [])
        now_dt = datetime.now()
        dist_rem = float(_get_route_distance_km(rem_route) or 0.0)
        total_sec = _duration_seconds_by_distance_mode(dist_rem, mode) or _get_route_duration_seconds(rem_route)
        arrival = (now_dt + timedelta(seconds=total_sec)).strftime("%H:%M") if total_sec else "?"

        ss["nav_polyline"] = rem_poly
        ss["nav_steps"] = rem_route.get("steps", [])
        ss["nav_progress_idx"] = 0
        ss["nav_max_progress"] = 0
        ss["nav_offroute"] = False
        ss["nav_reroute_pl"] = None
        ss["nav_distance_left_osrm"] = dist_rem

        ss["auto_eta_last_ts"]       = now_ts
        ss["auto_eta_distance_km"]   = dist_rem
        ss["auto_eta_duration_text"] = rem_route.get("duration_text") or _format_duration_from_seconds(total_sec)
        ss["auto_eta_arrival"]       = arrival
        ss["auto_eta_updated_at"]    = now_dt.strftime("%H:%M:%S")
        ss["auto_eta_status"]        = "✅ Đã cập nhật ETA theo GPS hiện tại."

        try:
            ml_model = init_ml_model()
            if ml_model is not None and getattr(ml_model, "is_ready", False):
                forecast, _, _ = _compute_route_forecast(
                    rem_poly, rem_route, now_dt, risk_engine, ml_model, weather_api
                )
                ss["auto_eta_forecast"] = forecast
                ss["auto_eta_ai_ready"] = True
                ss["auto_eta_ai_status"] = "✅ đã cập nhật"
            else:
                ss["auto_eta_forecast"] = None
                ss["auto_eta_ai_ready"] = False
                ss["auto_eta_ai_status"] = "⚠️ chưa sẵn sàng"
        except Exception as e:
            ss["auto_eta_forecast"] = None
            ss["auto_eta_ai_ready"] = False
            ss["auto_eta_ai_status"] = f"⚠️ lỗi: {e}"
        return True
    except Exception as e:
        ss["auto_eta_status"] = f"⚠️ Lỗi cập nhật ETA tự động: {e}"
        return False








                                                                                       




                                                                             
                                                                                
                                                                              
                                                                               

                                                
                                                              
                                                                                  





































                                                                               
                                                                       
                                                                               




































                                                                               
                                                                           
                                                                                   
                                                                               










                                                                               
                                       
                                                                               
def _ts_route_signature(polyline):
    """Chữ ký nhẹ để so tuyến cũ/tuyến mới."""
    try:
        pts = polyline or []
        if not pts:
            return ()
        step = max(1, int(len(pts) / 24))
        sig = []
        for p in pts[::step]:
            try:
                sig.append((round(float(p[0]), 4), round(float(p[1]), 4)))
            except Exception:
                pass
        if pts:
            last = (round(float(pts[-1][0]), 4), round(float(pts[-1][1]), 4))
            if not sig or sig[-1] != last:
                sig.append(last)
        return tuple(sig)
    except Exception:
        return ()


def _ts_route_changed_enough(old_route, new_route, incident_lat=None, incident_lon=None):
    """
    Tuyến vòng phải khác tuyến cũ đủ rõ.
    Nếu router trả lại gần như tuyến cũ/direct fallback thì không coi là đổi tuyến.
    """
    try:
        old_poly = (old_route or {}).get("polyline") or []
        new_poly = (new_route or {}).get("polyline") or []
        if not old_poly or not new_poly:
            return bool(new_poly)

        if _ts_route_signature(old_poly) != _ts_route_signature(new_poly):
                                                                    
            old_km = float(_get_route_distance_km(old_route) or _distance_km_from_polyline(old_poly) or 0.0)
            new_km = float(_get_route_distance_km(new_route) or _distance_km_from_polyline(new_poly) or 0.0)
            if old_km > 0 and abs(new_km - old_km) / max(old_km, 1.0) >= 0.01:
                return True

            if incident_lat is not None and incident_lon is not None:
                old_d = _min_distance_polyline_to_coord_km(old_poly, incident_lat, incident_lon, sample_step=2)
                new_d = _min_distance_polyline_to_coord_km(new_poly, incident_lat, incident_lon, sample_step=2)
                if new_d >= old_d + 0.20:
                    return True

                                                         
            if new_route.get("reroute_waypoints"):
                return True

        return False
    except Exception:
        return True


                                                                   
                                                                                        
_TS_REROUTE_ANCHORS = {
    "dalat_center": (11.9404, 108.4583),
    "mimosa_dalat": (11.8890, 108.5060),
    "tuyen_lam": (11.8900, 108.4140),
    "lien_khuong": (11.7500, 108.3730),
    "duc_trong": (11.7350, 108.3730),
    "di_linh": (11.5800, 108.0700),
    "bao_loc": (11.5489, 107.8077),
    "madaguoi": (11.3890, 107.5320),
    "dau_giay": (10.9300, 107.2440),
    "long_khanh": (10.9330, 107.2500),
    "ba_ria": (10.4960, 107.1680),
    "vung_tau": (10.4114, 107.1362),
    "hcm_east": (10.8231, 106.8120),
    "phan_thiet": (10.9333, 108.1000),
    "phan_rang": (11.5639, 108.9880),
    "nha_trang": (12.2388, 109.1967),
}


def _ts_destination_point(lat, lon, distance_km, bearing_deg):
    """Tạo waypoint quanh sự cố theo bán kính + hướng, format trả về (lat, lon)."""
    try:
        R = 6371.0
        brng = math.radians(float(bearing_deg))
        d = float(distance_km) / R
        lat1 = math.radians(float(lat))
        lon1 = math.radians(float(lon))
        lat2 = math.asin(
            math.sin(lat1) * math.cos(d)
            + math.cos(lat1) * math.sin(d) * math.cos(brng)
        )
        lon2 = lon1 + math.atan2(
            math.sin(brng) * math.sin(d) * math.cos(lat1),
            math.cos(d) - math.sin(lat1) * math.sin(lat2),
        )
        return (math.degrees(lat2), math.degrees(lon2))
    except Exception:
        return (lat, lon)


def _ts_in_vn_bbox_light(lat, lon):
    """Lọc thô để không gửi waypoint quá lệch ra ngoài vùng Việt Nam."""
    try:
        lat = float(lat); lon = float(lon)
        return 8.18 <= lat <= 23.39 and 102.14 <= lon <= 109.47
    except Exception:
        return False


def _ts_candidate_road_anchors(origin, dest, ilat, ilon, avoid_r):
    """Chọn anchor gần sự cố/tuyến để OSRM snap vào đường thật thay vì rừng/hồ."""
    out = []
    try:
        base_km = max(25.0, float(avoid_r or 3.0) * 8.0)
        od_km = max(1.0, _haversine_km(origin[0], origin[1], dest[0], dest[1]))
        for _name, pos in _TS_REROUTE_ANCHORS.items():
            lat, lon = pos
            d_inc = _haversine_km(float(ilat), float(ilon), lat, lon)
            d_o = _haversine_km(origin[0], origin[1], lat, lon)
            d_d = _haversine_km(dest[0], dest[1], lat, lon)
            detour = (d_o + d_d) / od_km
            if d_inc <= base_km and detour <= 1.85:
                out.append((d_inc, detour, pos))
        out.sort(key=lambda x: (x[1], x[0]))
        return [x[2] for x in out[:10]]
    except Exception:
        return []


def _ts_incident_clearance(polyline, ilat, ilon):
    try:
        return float(_min_distance_polyline_to_coord_km(polyline or [], ilat, ilon, sample_step=2) or 0.0)
    except Exception:
        return 0.0


def _ts_route_detour_ratio(old_route, new_route):
    try:
        old_km = float(_get_route_distance_km(old_route or {}) or _distance_km_from_polyline((old_route or {}).get("polyline") or []) or 0.0)
        new_km = float(_get_route_distance_km(new_route or {}) or _distance_km_from_polyline((new_route or {}).get("polyline") or []) or 0.0)
        if old_km <= 0 or new_km <= 0:
            return 1.0
        return new_km / old_km
    except Exception:
        return 1.0




def _ts_find_best_incident_reroute(router, origin, dest, ilat, ilon, mode_r, avoid_r, old_route):
    """
    FAST ONE-CLICK REROUTE BY RANGE.

    Yêu cầu mới:
    - Bấm 1 lần là thử đủ candidate trong khoảng đã chọn.
    - Có 3 mức:
        1 km  -> thử tuyến vòng nhỏ trong vùng 1–5 km
        5 km  -> thử tuyến vòng vừa trong vùng 5–20 km
        20 km -> thử tuyến vòng xa, >20 km
    - Không gọi router.reroute_around_incident() kiểu tuần tự lâu nữa.
      Thay vào đó tự tạo waypoint quanh sự cố rồi gọi router.get_route() song song.
    - Chọn tuyến NGẮN NHẤT trong các tuyến vòng hợp lệ.
    - Vẫn thay luôn tuyến hiện tại, không mở map phụ.
    """
    import time as _time
    import concurrent.futures as _futures

    origin = (float(origin[0]), float(origin[1]))
    dest = (float(dest[0]), float(dest[1]))
    ilat = float(ilat)
    ilon = float(ilon)

    try:
        level = float(avoid_r or 1.0)
    except Exception:
        level = 1.0

                                           
    if level >= 20:
        range_label = ">20 km"
        waypoint_radii = [20.0, 26.0, 34.0, 45.0, 60.0]
        min_clearance_km = 2.5
        max_detour_ratio = 3.20
        timeout_sec = 10.0
        max_workers = 10
    elif level >= 5:
        range_label = "5–20 km"
        waypoint_radii = [5.0, 7.5, 10.0, 14.0, 18.0, 20.0]
        min_clearance_km = 1.2
        max_detour_ratio = 2.45
        timeout_sec = 8.0
        max_workers = 10
    else:
        range_label = "1–5 km"
        waypoint_radii = [1.0, 1.5, 2.2, 3.2, 4.2, 5.0]
        min_clearance_km = 0.45
        max_detour_ratio = 1.85
        timeout_sec = 6.5
        max_workers = 8

    old_poly = (old_route or {}).get("polyline") or []
    old_km = float(
        _get_route_distance_km(old_route or {})
        or _distance_km_from_polyline(old_poly)
        or 0.0
    )
    old_clearance = _ts_incident_clearance(old_poly, ilat, ilon) if old_poly else 0.0

                                                                                    
                                                                             
    required_clearance = max(min_clearance_km, min(old_clearance + 0.25, min_clearance_km + 0.8))

    def _route_distance(rt):
        return float(
            _get_route_distance_km(rt or {})
            or _distance_km_from_polyline((rt or {}).get("polyline") or [])
            or 0.0
        )

    def _route_duration(rt):
        try:
            return float((rt or {}).get("duration_min") or 999999.0)
        except Exception:
            return 999999.0

    def _candidate_from_route(rt, source, waypoints, radius_used):
        """Chuẩn hóa candidate và lọc tuyến đi qua vùng chỉ định."""
        try:
            if not rt or rt.get("fallback") or rt.get("reroute_failed"):
                return None
            poly = rt.get("polyline") or []
            if len(poly) < 2:
                return None

            dist_km = _route_distance(rt)
            if old_km > 0 and dist_km > old_km * max_detour_ratio:
                return None

            clearance = _ts_incident_clearance(poly, ilat, ilon)
            if clearance < required_clearance:
                return None

            changed = _ts_route_changed_enough(old_route, rt, ilat, ilon)
            has_wp = bool(waypoints or rt.get("reroute_waypoints"))
            if old_clearance < required_clearance and not changed and not has_wp:
                return None

            item = dict(rt)
            item.update({
                "rerouted": True,
                "manual_incident_reroute": True,
                "manual_avoid_radius_km": float(radius_used),
                "manual_avoid_range_label": range_label,
                "manual_incident_clearance_km": float(clearance),
                "incident_clearance_km": round(float(clearance), 3),
                "reroute_source": source,
                "reroute_waypoints": list(waypoints or []),
                "detour_ratio": round(dist_km / max(old_km, 1.0), 3) if old_km else 1.0,
                "hard_avoid": True,
                "soft_avoid": True,
                "label": f"🔄 Tuyến vòng {range_label} ngắn nhất",
                "__manual_reroute_changed": changed,
                "__manual_reroute_direct_like": False,
            })
            return item
        except Exception:
            return None

                                                                                           
                                       
    jobs = []
    bearings = (0, 45, 90, 135, 180, 225, 270, 315)

    for radius in waypoint_radii:
        for bearing in bearings:
            wp = _ts_destination_point(ilat, ilon, radius, bearing)
            if _ts_in_vn_bbox_light(wp[0], wp[1]):
                jobs.append(("single", radius, [wp]))

                                                                                  
    for radius in waypoint_radii[:4]:
        for b1, b2 in ((45, 90), (90, 135), (225, 270), (270, 315), (0, 45), (180, 225)):
            wp1 = _ts_destination_point(ilat, ilon, radius, b1)
            wp2 = _ts_destination_point(ilat, ilon, radius, b2)
            if _ts_in_vn_bbox_light(wp1[0], wp1[1]) and _ts_in_vn_bbox_light(wp2[0], wp2[1]):
                jobs.append(("arc", radius, [wp1, wp2]))

                                                                                                    
    try:
        anchors = _ts_candidate_road_anchors(origin, dest, ilat, ilon, max(3.0, min(20.0, level)))[:8]
        for anchor in anchors:
                                                                                              
            d_anchor = _haversine_km(anchor[0], anchor[1], ilat, ilon)
            if level < 5 and d_anchor <= 8:
                jobs.append(("anchor", d_anchor, [anchor]))
            elif 5 <= level < 20 and 4 <= d_anchor <= 28:
                jobs.append(("anchor", d_anchor, [anchor]))
            elif level >= 20 and d_anchor >= 12:
                jobs.append(("anchor", d_anchor, [anchor]))
    except Exception:
        pass

                                                              
    jobs.sort(key=lambda j: (float(j[1]), 0 if j[0] == "single" else 1 if j[0] == "arc" else 2))

                                                        
    jobs = jobs[:70]

    def _run_job(job):
        kind, radius, wps = job
        try:
            rt = router.get_route(origin, dest, mode=mode_r, waypoints=wps)
            return _candidate_from_route(rt, kind, wps, radius)
        except Exception as e:
            return ("ERR", f"{kind}/{radius:g}: {e}")

    valid = []
    errors = []
    started = _time.time()

                                                                              
    executor = _futures.ThreadPoolExecutor(max_workers=max_workers)
    futures = [executor.submit(_run_job, job) for job in jobs]

    try:
        for fut in _futures.as_completed(futures, timeout=timeout_sec):
            remain = timeout_sec - (_time.time() - started)
            if remain <= 0:
                break
            try:
                res = fut.result(timeout=max(0.01, remain))
                if isinstance(res, tuple) and res and res[0] == "ERR":
                    errors.append(res[1])
                    continue
                if res:
                    valid.append(res)

                                                                            
                                                       
                    if len(valid) >= 4:
                        best_now = min(valid, key=lambda r: (_route_distance(r), _route_duration(r)))
                        if old_km <= 0 or _route_distance(best_now) <= old_km * 1.15:
                            break
            except Exception as e:
                errors.append(str(e))
    except Exception:
        pass
    finally:
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass

    if not valid:
        return None, (
            f"Chưa tìm được tuyến vòng trong khoảng {range_label} sau khoảng {timeout_sec:g}s. "
            "Hãy chọn khoảng lớn hơn hoặc kiểm tra lại vị trí sự cố. "
            "Nếu khu vực chỉ có một trục đường thì không thể tạo tuyến vòng thật."
        )

                                                       
    valid.sort(key=lambda rt: (_route_distance(rt), _route_duration(rt)))
    best = valid[0]
    _apply_avg_speed_timing(best, mode_r)

    best_dist = _route_distance(best)
    clearance = float(best.get("manual_incident_clearance_km") or 0.0)
    detour = float(best.get("detour_ratio") or (best_dist / max(old_km, 1.0)))
    elapsed = _time.time() - started

    return best, (
        f"Đã chọn tuyến vòng ngắn nhất trong khoảng {range_label}; "
        f"tìm thấy {len(valid)} tuyến hợp lệ sau {elapsed:.1f}s, "
        f"cách khu vực chỉ định khoảng {clearance:.1f} km, "
        f"quãng đường {best_dist:.1f} km, độ vòng {detour:.2f}x."
    )


def _ts_apply_manual_incident_reroute_to_session(new_rt, origin, dest, mode_r, ilat, ilon, avoid_r):
    """
    Áp dụng tuyến vòng vào tuyến chính.
    Đây là phần thiếu khiến trước đó bấm 'Tính tuyến vòng' chỉ hiện map phụ,
    còn bản đồ chính/route state không đổi.
    """
    try:
        if not new_rt or not new_rt.get("polyline"):
            return False, "Không có polyline tuyến vòng để áp dụng."

        ss = st.session_state
        new_rt = dict(new_rt)
        poly = new_rt.get("polyline") or []

                                                                              
        ss["last_routes"] = [new_rt]
        ss["last_selected"] = 0
        ss["selected_route_idx"] = 0
        ss["last_origin"] = origin
        ss["last_dest"] = dest
        ss["last_mode"] = mode_r
        ss["last_incident_reroute"] = new_rt
        ss["last_polyline"] = poly
        ss["last_route_km"] = _get_route_distance_km(new_rt)

                                                                             
        ss["nav_polyline"] = poly
        ss["nav_steps"] = new_rt.get("steps", ss.get("nav_steps", []))
        ss["nav_progress_idx"] = 0
        ss["nav_max_progress"] = 0
        ss["nav_offroute"] = False
        ss["nav_reroute_pl"] = None
        ss["nav_dest"] = dest
        ss["nav_mode"] = mode_r
        ss["nav_distance_left_osrm"] = _get_route_distance_km(new_rt)

                                                                   
        for k in [
            "last_compared", "route_view_cache", "route_view_cache_key",
            "last_route_risk_forecast", "last_danger_markers", "last_rest_stops",
            "auto_eta_forecast", "copilot_critical_segment",
            "last_route_fuel_stations_all", "last_route_fuel_stations",
            "next_fuel_stations", "last_route_fuel_key", "__active_fuel_route_key",
            "__fuel_fetch_future", "__fuel_fetch_key",
            "last_incident_preview_route", "manual_reroute_preview_html",
            "reroute_html", "reroute_preview", "new_rt_preview",
        ]:
            ss.pop(k, None)

        try:
            if isinstance(ss.get("__fuel_route_cache"), dict):
                ss["__fuel_route_cache"] = {}
        except Exception:
            pass

        try:
            _clear_route_view_cache()
        except Exception:
            pass

                                                                   
        try:
            _backup_trip_route_state("manual_incident_reroute_applied")
        except Exception:
            pass
        try:
            _persist_current_route_snapshot()
        except Exception:
            pass

        ss["manual_reroute_applied_msg"] = (
            f"✅ Đã thay tuyến hiện tại bằng tuyến tránh sự cố "
            f"(bán kính {float(new_rt.get('manual_avoid_radius_km') or avoid_r):g} km)."
        )
        return True, ss["manual_reroute_applied_msg"]
    except Exception as e:
        return False, f"Lỗi áp dụng tuyến vòng: {e}"



def resolve_location(txt, maps_api):
    """Dùng cho các tab không cần chọn (thời tiết, sơ tán, v.v.)."""
    if not txt: return None, None
    if "," in txt:
        try:
            p = txt.split(","); return float(p[0].strip()), float(p[1].strip())
        except: pass
    c = maps_api.geocode(txt)
    return c if c else (None, None)


def resolve_location_candidates(txt, maps_api):
    """
    Trả về danh sách ứng viên địa điểm cho txt.
    Dùng geocode_candidates() nếu maps_api hỗ trợ; fallback về geocode() đơn.
    Kết quả: list of {"name", "address", "lat", "lon"}
    """
    if not txt:
        return []
                                     
    if "," in txt:
        try:
            p = txt.split(",")
            lat, lon = float(p[0].strip()), float(p[1].strip())
            return [{"name": txt, "address": txt, "lat": lat, "lon": lon}]
        except:
            pass
                       
    if hasattr(maps_api, "geocode_candidates"):
        try:
            results = maps_api.geocode_candidates(txt, limit=6)
            if results:
                return results
        except Exception:
            pass
                               
    c = maps_api.geocode(txt)
    if c:
        lat, lon = c
        return [{"name": txt, "address": txt, "lat": lat, "lon": lon}]
    return []




def _candidate_needs_manual_confirm(c: dict) -> bool:
    """Bắt xác nhận thủ công nếu geocoder chỉ trả kết quả gần đúng khác số nhà."""
    return isinstance(c, dict) and c.get("match_status") == "near_address_mismatch"


def _candidate_label(c: dict) -> str:
    """Label selectbox: cảnh báo rõ khi chỉ là near match, không exact số nhà."""
    base = f"{c.get('name', '')} — {c.get('address', '')}"
    if _candidate_needs_manual_confirm(c):
        hn = c.get("requested_house_number") or ""
        return f"⚠️ Gần đúng, không khớp số nhà {hn}: {base}"
    if c.get("match_status") == "exact_house_number":
        return f"✅ Khớp số nhà: {base}"
    return base


def _show_address_match_warnings(label: str, candidates: list):
    """Hiện cảnh báo nếu API không tìm được đúng số nhà người dùng nhập."""
    if not candidates:
        return
    bad = [c for c in candidates if _candidate_needs_manual_confirm(c)]
    if not bad:
        return
    hn = bad[0].get("requested_house_number") or ""
    st.warning(
        f"⚠️ **{label}: không tìm thấy chính xác số nhà {hn}.** "
        "App sẽ không tự thay bằng số nhà khác. "
        "Bạn hãy chọn thủ công kết quả gần nhất bên dưới, hoặc nhập tọa độ/ghim pin nếu cần chính xác."
    )

def _handle_unknown_location(label: str, name: str, maps_api, coord_key: str) -> bool:
    """
    Hiện UI hướng dẫn khi không tìm được địa danh.
    User nhập tọa độ → lưu vào user_aliases.json → lần sau tự động tìm thấy.
    Trả True nếu user đã nhập tọa độ hợp lệ và lưu thành công.
    """
    st.warning(
        f"⚠️ Không tìm thấy **{name}** trong cơ sở dữ liệu bản đồ.\n\n"
        "Địa danh nhỏ hoặc địa phương thường không có trong OSM. "
        "Bạn có thể tra tọa độ trên Google Maps rồi nhập vào đây — "
        "app sẽ **nhớ vĩnh viễn** cho lần sau."
    )
    with st.expander("📌 Cách lấy tọa độ từ Google Maps", expanded=True):
        st.markdown(
            "1. Mở **[Google Maps](https://maps.google.com)** trên điện thoại hoặc máy tính\n"
            f"2. Tìm **{name}**\n"
            "3. Bấm giữ (hoặc click chuột phải) vào đúng vị trí trên bản đồ\n"
            "4. Tọa độ dạng `11.xxx, 107.xxx` sẽ hiện ở thanh tìm kiếm — copy lại\n"
            "5. Dán vào ô bên dưới"
        )
        coord_input = st.text_input(
            f"Tọa độ của **{name}** (dán vào đây):",
            placeholder="Ví dụ: 11.4240, 107.6460",
            key=coord_key,
        )
        if coord_input:
            try:
                parts = coord_input.replace(";", ",").split(",")
                lat, lon = float(parts[0].strip()), float(parts[1].strip())
                if not (8.0 <= lat <= 23.4 and 102.1 <= lon <= 109.5):
                    st.error("❌ Tọa độ nằm ngoài lãnh thổ Việt Nam. Kiểm tra lại.")
                    return False
                if maps_api.save_user_alias(name, lat, lon):
                    st.success(
                        f"✅ Đã lưu **{name}** → ({lat:.4f}, {lon:.4f}). "
                        "Lần sau app tự tìm thấy ngay!"
                    )
                                                                          
                    st.session_state[f"resolved_{coord_key}"] = {"name": name, "lat": lat, "lon": lon}
                    return True
                else:
                    st.error("❌ Lưu thất bại. Kiểm tra quyền ghi file.")
            except (ValueError, IndexError):
                st.error("❌ Định dạng sai. Nhập đúng dạng `lat, lon` — ví dụ: `11.4240, 107.6460`")
    return False



                                                                               
                                                   
                                                                               


                                                                              
                                                                           
                                                                               
                                                                              
_TS_SOS_CONTACTS_BACKUP_KEY = "__ts_sos_family_contacts_persistent"
_TS_SOS_CONTACTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tripsmart_sos_contacts.json")


def _ts_sos_clean_contact(name, phone):
    """Chuẩn hóa 1 contact SOS, trả None nếu thiếu số."""
    try:
        n = str(name or "").strip() or "Người thân"
        p = str(phone or "").strip()
        if not p:
            return None
        return {"name": n, "phone": p}
    except Exception:
        return None


def _ts_sos_contact_id(contact):
    """Khóa chống trùng theo số điện thoại đã normalize."""
    try:
        phone = contact.get("phone") if isinstance(contact, dict) else ""
        norm = _sos_normalize_phone_for_sms(phone) or str(phone or "").strip()
        return str(norm).strip()
    except Exception:
        try:
            return str((contact or {}).get("phone", "")).strip()
        except Exception:
            return ""


def _ts_sos_dedupe_contacts(contacts):
    """Lọc contact rỗng/trùng, giữ đúng thứ tự nhập."""
    out = []
    seen = set()
    for c in contacts or []:
        if not isinstance(c, dict):
            continue
        clean = _ts_sos_clean_contact(c.get("name"), c.get("phone"))
        if not clean:
            continue
        cid = _ts_sos_contact_id(clean)
        if not cid or cid in seen:
            continue
        seen.add(cid)
        out.append(clean)
    return out


def _ts_sos_load_contacts_file():
    """Đọc contact SOS từ file local ẩn. Không làm sập app nếu file lỗi."""
    try:
        if not os.path.exists(_TS_SOS_CONTACTS_FILE):
            return []
        with open(_TS_SOS_CONTACTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data = data.get("contacts", [])
        return _ts_sos_dedupe_contacts(data if isinstance(data, list) else [])
    except Exception:
        return []


def _ts_sos_save_contacts_file(contacts):
    """Ghi contact SOS vào file local để không mất khi đổi menu bằng link HTML."""
    try:
        cleaned = _ts_sos_dedupe_contacts(contacts)
        with open(_TS_SOS_CONTACTS_FILE, "w", encoding="utf-8") as f:
            json.dump({"contacts": cleaned}, f, ensure_ascii=False, indent=2)
        return cleaned
    except Exception:
        return _ts_sos_dedupe_contacts(contacts)


def _ts_sos_save_contacts_backup(contacts):
    """Lưu danh sách số người thân vào session + file local."""
    cleaned = _ts_sos_dedupe_contacts(contacts)
    try:
        if cleaned:
            st.session_state[_TS_SOS_CONTACTS_BACKUP_KEY] = cleaned
    except Exception:
        pass
    try:
        if cleaned:
            _ts_sos_save_contacts_file(cleaned)
    except Exception:
        pass
    return cleaned


def _ts_sos_read_contacts_backup():
    """Đọc backup SOS từ session trước, nếu rỗng thì đọc file local."""
    try:
        session_contacts = _ts_sos_dedupe_contacts(st.session_state.get(_TS_SOS_CONTACTS_BACKUP_KEY, []))
        if session_contacts:
            return session_contacts
    except Exception:
        pass
    return _ts_sos_load_contacts_file()


def _ts_sos_restore_to_module(contacts):
    """Khôi phục vào module floating_sos để các phần code cũ vẫn dùng được."""
    restored = []
    for c in _ts_sos_dedupe_contacts(contacts):
        try:
            _sos_add_family_contact(c.get("name") or "Người thân", c.get("phone") or "")
        except Exception:
            pass
    try:
        restored = _sos_get_family_contacts() or []
    except Exception:
        restored = []
    return _ts_sos_dedupe_contacts(restored or contacts)


def _ts_sos_remember_added_contact(name, phone):
    """Gọi ngay sau khi bấm thêm số để đảm bảo số không mất khi qua Tìm đường."""
    new_c = _ts_sos_clean_contact(name, phone)
    if not new_c:
        return []
    merged = []
    try:
        _sos_init_state()
    except Exception:
        pass
    try:
        merged.extend(_sos_get_family_contacts() or [])
    except Exception:
        pass
    merged.extend(_ts_sos_read_contacts_backup())
    merged.append(new_c)
    return _ts_sos_save_contacts_backup(merged)


def _ts_sos_get_family_contacts_safe():
    """
    Lấy contact SOS theo cách chắc chắn:
    1) ưu tiên backup/file local nếu đã tồn tại để thao tác xóa từng số có hiệu lực ngay,
    2) nếu chưa có backup/file thì đọc module floating_sos hiện tại,
    3) đồng bộ lại vào backup để không mất khi đổi menu.
    """
    try:
        _sos_init_state()
    except Exception:
        pass

                                                                      
                                                                                             
    try:
        has_authoritative_backup = (
            _TS_SOS_CONTACTS_BACKUP_KEY in st.session_state
            or os.path.exists(_TS_SOS_CONTACTS_FILE)
        )
        if has_authoritative_backup:
            backup = _ts_sos_read_contacts_backup()
            return _ts_sos_overwrite_contacts_everywhere(backup)
    except Exception:
        pass

    current = []
    try:
        current = _sos_get_family_contacts() or []
    except Exception:
        current = []

    if current:
        return _ts_sos_save_contacts_backup(current)

    backup = _ts_sos_read_contacts_backup()
    if not backup:
        return []

    restored = _ts_sos_restore_to_module(backup)
    return _ts_sos_save_contacts_backup(restored or backup)


def _ts_sos_has_family_contact():
    """True nếu đã có ít nhất 1 số người thân hợp lệ."""
    return bool(_ts_sos_get_family_contacts_safe())


def _ts_sos_overwrite_contacts_everywhere(contacts):
    """
    Ghi đè danh sách SOS theo đúng danh sách còn lại.
    Chỉ tác động vào dữ liệu số người thân SOS, không đụng GPS/map/routing/ETA.
    """
    cleaned = _ts_sos_dedupe_contacts(contacts or [])

                                          
    try:
        st.session_state[_TS_SOS_CONTACTS_BACKUP_KEY] = cleaned
    except Exception:
        pass

                                                     
    try:
        with open(_TS_SOS_CONTACTS_FILE, "w", encoding="utf-8") as f:
            json.dump({"contacts": cleaned}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

                                                                                     
                                                                              
    try:
        likely_keys = [
            "sos_family_contacts",
            "family_contacts",
            "emergency_contacts",
            "sos_contacts",
            "floating_sos_family_contacts",
            "__sos_family_contacts",
        ]
        for k in likely_keys:
            if k in st.session_state:
                st.session_state[k] = cleaned
    except Exception:
        pass

    return cleaned


def _ts_sos_delete_contact_by_id(contact_id):
    """Xóa đúng 1 số SOS theo contact_id đã normalize."""
    try:
        cid = str(contact_id or "").strip()
        contacts = _ts_sos_get_family_contacts_safe() or []
        kept = []
        for c in contacts:
            if _ts_sos_contact_id(c) != cid:
                kept.append(c)
        return _ts_sos_overwrite_contacts_everywhere(kept)
    except Exception:
        return _ts_sos_get_family_contacts_safe() or []






















                                                                               
                                        
                                                                               
                                                                          
                                                                    
_TS_CROWD_REPORT_TTL_SECONDS = {
    "traffic_jam": 1 * 60 * 60,                                      
    "accident": 2 * 60 * 60,                                                    
    "flood": 6 * 60 * 60,                                                            
    "landslide": 3 * 24 * 60 * 60,                                             
    "bad_road": 7 * 24 * 60 * 60,                                 
    "construction": 14 * 24 * 60 * 60,                                     
    "roadwork": 14 * 24 * 60 * 60,
    "work": 14 * 24 * 60 * 60,
}


def _ts_crowd_report_ttl_seconds(report_type):
    """Trả về thời gian hiệu lực theo loại báo cáo cộng đồng."""
    try:
        t = str(report_type or "").strip().lower()
        if not t:
            return 6 * 60 * 60
        if t in _TS_CROWD_REPORT_TTL_SECONDS:
            return _TS_CROWD_REPORT_TTL_SECONDS[t]
                                                                                                 
        if "traffic" in t or "jam" in t or "tắc" in t or "tac" in t:
            return _TS_CROWD_REPORT_TTL_SECONDS["traffic_jam"]
        if "accident" in t or "tai" in t or "crash" in t:
            return _TS_CROWD_REPORT_TTL_SECONDS["accident"]
        if "flood" in t or "ngap" in t or "ngập" in t:
            return _TS_CROWD_REPORT_TTL_SECONDS["flood"]
        if "landslide" in t or "sat" in t or "sạt" in t or "lo" in t or "lở" in t:
            return _TS_CROWD_REPORT_TTL_SECONDS["landslide"]
        if "bad" in t or "road" in t or "xấu" in t or "xau" in t:
            return _TS_CROWD_REPORT_TTL_SECONDS["bad_road"]
        if "construction" in t or "roadwork" in t or "thi" in t or "cong" in t or "công" in t:
            return _TS_CROWD_REPORT_TTL_SECONDS["construction"]
    except Exception:
        pass
                                                              
    return 6 * 60 * 60


def _ts_parse_report_created_ts(report):
    """Cố gắng đọc thời điểm tạo báo cáo từ nhiều định dạng/key khác nhau."""
    try:
        if not isinstance(report, dict):
            return None
        keys = (
            "created_at", "created", "submitted_at", "timestamp", "time",
            "datetime", "date", "ts", "created_ts", "reported_at"
        )
        for k in keys:
            v = report.get(k)
            if v in (None, ""):
                continue
            if isinstance(v, (int, float)):
                ts = float(v)
                                                  
                if ts > 10_000_000_000:
                    ts = ts / 1000.0
                return ts
            s = str(v).strip()
            if not s:
                continue
                                  
            try:
                ts = float(s)
                if ts > 10_000_000_000:
                    ts = ts / 1000.0
                return ts
            except Exception:
                pass
                           
            try:
                dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
                return dt.timestamp()
            except Exception:
                pass
                                                       
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
                try:
                    return datetime.strptime(s, fmt).timestamp()
                except Exception:
                    continue
    except Exception:
        pass
    return None


def _ts_format_ttl(seconds):
    """Format thời gian ngắn gọn để hiển thị trong UI."""
    try:
        sec = max(0, int(seconds))
        if sec < 60:
            return f"{sec} giây"
        if sec < 3600:
            return f"{sec // 60} phút"
        if sec < 86400:
            h = sec // 3600
            m = (sec % 3600) // 60
            return f"{h} giờ" + (f" {m} phút" if m else "")
        d = sec // 86400
        h = (sec % 86400) // 3600
        return f"{d} ngày" + (f" {h} giờ" if h else "")
    except Exception:
        return "?"


def _ts_crowd_report_expiry_state(report, now_ts=None):
    """Trả về trạng thái hết hạn của một báo cáo cộng đồng."""
    try:
        now_ts = now_ts or datetime.now().timestamp()
        ttl = _ts_crowd_report_ttl_seconds((report or {}).get("type"))
        created_ts = _ts_parse_report_created_ts(report or {})
        if created_ts is None:
                                                                                                  
            return {
                "expired": False,
                "ttl_seconds": ttl,
                "created_ts": None,
                "remaining_seconds": None,
                "label": f"thời hạn tham khảo {_ts_format_ttl(ttl)}",
            }
        remaining = float(created_ts + ttl - now_ts)
        return {
            "expired": remaining <= 0,
            "ttl_seconds": ttl,
            "created_ts": created_ts,
            "remaining_seconds": remaining,
            "label": ("đã hết hiệu lực" if remaining <= 0 else f"còn hiệu lực khoảng {_ts_format_ttl(remaining)}"),
        }
    except Exception:
        return {"expired": False, "ttl_seconds": None, "created_ts": None, "remaining_seconds": None, "label": ""}


def _ts_filter_active_crowd_reports(reports, crowd_engine=None, current_user="user_001"):
    """
    Lọc báo cáo đã hết hiệu lực khỏi UI.
    Nếu báo cáo cũ là của user hiện tại và engine cho phép xóa, thử xóa mềm trong dữ liệu.
    """
    active, expired = [], []
    now_ts = datetime.now().timestamp()
    for r in reports or []:
        state = _ts_crowd_report_expiry_state(r, now_ts=now_ts)
        try:
            r["__expiry_label"] = state.get("label") or ""
        except Exception:
            pass
        if state.get("expired"):
            expired.append(r)
                                                                                 
                                                                                            
            try:
                if crowd_engine is not None and r.get("user_id") == current_user and r.get("id"):
                    crowd_engine.delete_report(r.get("id"), current_user)
            except Exception:
                pass
        else:
            active.append(r)
    return active, expired


def _ts_crowd_report_ttl_note():
    return (
        "Thời gian hiệu lực tự động: 🚗 tắc đường 1 giờ; 🚨 tai nạn 2 giờ; "
        "🌊 ngập nước 6 giờ; ⛰️ sạt lở 3 ngày; ⚠️ đường xấu 7 ngày; 🚧 thi công 14 ngày."
    )

                                                                               
                                                     
                                                                               
CO2_G_PER_KM_BY_MODE = {
    "car": 180.0,                                                    
    "motorbike": 75.0,                                 
}













                                                                               
          
                                                                               




                                                                               
                                                      
                                                                               
APP_NAV_GROUPS = [
    ("🚗 Đi đường", [
        ("🗺️  Tìm đường", "Tìm tuyến"),
        ("🚦  Kiểm tra kẹt xe", "Traffic live"),
        ("🧠  Trợ lý an toàn", "Nên làm gì"),
        ("🏛️  Điểm tham quan", "Gợi ý điểm"),
        ("📔  Ký ức hành trình", "Lưu kỷ niệm"),
    ]),
    ("🌦️ Thời tiết & điểm đến", [
        ("🌤️  Thời tiết", "Xem mưa"),
        ("🌪️  Sơ tán thiên tai", "Đường tránh"),
    ]),
    ("🆘 An toàn khẩn cấp", [
        ("🆘  SOS Khẩn cấp", "Gửi SOS"),
        ("⚠️  Kiểm tra rủi ro", "Xem nguy hiểm"),
    ]),
    ("👥 Cộng đồng", [
        ("📍  Báo cáo cộng đồng", "Báo sự cố"),
    ]),
]

APP_HOME_CARDS = [
    ("🗺️", "Tìm đường", "Tìm tuyến", "🗺️  Tìm đường", "#e3f2fd"),
    ("🆘", "SOS", "Gửi khẩn", "🆘  SOS Khẩn cấp", "#ffebee"),
    ("🚦", "Kẹt xe", "Traffic live", "🚦  Kiểm tra kẹt xe", "#fff7ed"),
    ("🌤️", "Thời tiết", "Xem mưa", "🌤️  Thời tiết", "#e0f7fa"),
    ("⚠️", "Rủi ro", "Xem nguy hiểm", "⚠️  Kiểm tra rủi ro", "#fff8e1"),
    ("🧠", "Trợ lý an toàn", "Nên làm gì", "🧠  Trợ lý an toàn", "#f3e5f5"),
    ("📍", "Cộng đồng", "Báo sự cố", "📍  Báo cáo cộng đồng", "#f1f8e9"),
    ("🏛️", "Điểm đến", "Gợi ý điểm", "🏛️  Điểm tham quan", "#ede7f6"),
]


def _inject_accessible_ui_css():
    """CSS bổ sung để app trực quan hơn nhưng không đụng logic cũ."""
    st.markdown("""
    <style>
    .ts-hero{background:linear-gradient(135deg,#eef7ff,#fff6f6);border:1px solid #e7edf7;border-radius:24px;padding:22px 24px;margin:6px 0 18px 0;box-shadow:0 8px 22px rgba(15,35,60,.06)}
    .ts-hero h1{margin:0;font-size:2.05rem;line-height:1.2}
    .ts-hero p{margin:.45rem 0 0 0;color:#5f6673;font-size:1rem}
    .ts-section-title{font-size:1.35rem;font-weight:800;margin:18px 0 12px;color:#30323d}
    .ts-card{min-height:132px;border-radius:24px;padding:18px 14px;text-align:center;background:white;border:1px solid #edf0f7;box-shadow:0 8px 20px rgba(20,35,60,.07);transition:.15s ease;margin-bottom:10px;cursor:pointer}
    .ts-card:hover{transform:translateY(-2px);box-shadow:0 12px 26px rgba(20,35,60,.10);border-color:#9ec5ff}
    .ts-card-link{text-decoration:none!important;color:inherit!important;display:block}
    .ts-card-link:hover{text-decoration:none!important;color:inherit!important}
    .ts-icon{width:64px;height:64px;border-radius:20px;margin:0 auto 10px;display:flex;align-items:center;justify-content:center;font-size:2rem}
    .ts-card-title{font-size:1.02rem;font-weight:800;color:#252733;margin-bottom:4px}
    .ts-card-desc{font-size:.86rem;color:#747b88;font-weight:600}
    .ts-tip{background:#f7f9ff;border-left:5px solid #3b82f6;border-radius:14px;padding:12px 14px;margin:8px 0;color:#384152}
    section[data-testid="stSidebar"] .stButton>button{border-radius:14px;min-height:42px;font-weight:700;text-align:left;border:1px solid rgba(255,255,255,.18);background:rgba(255,255,255,.08);color:white;width:100%}
    section[data-testid="stSidebar"] .stButton>button:hover{background:rgba(255,255,255,.18);border-color:rgba(255,255,255,.35)}
    div[data-testid="stButton"]>button{border-radius:14px;font-weight:700}
    @media (max-width: 760px){.ts-hero h1{font-size:1.55rem}.ts-card{min-height:118px}.ts-icon{width:56px;height:56px;font-size:1.75rem}}
    </style>
    """, unsafe_allow_html=True)



                                                                               
                         
                                                                               
def _fuel_route_cache_key(polyline, corridor_m=3000, max_results=160):
    """Cache key ổn định theo tuyến gốc, không phụ thuộc GPS/nav_active."""
    try:
        import hashlib, json as _json
        pts = polyline or []
        if not pts:
            return "empty"
        step = max(1, int(len(pts) / 80))
        sample = []
        for p in pts[::step]:
            try:
                sample.append([round(float(p[0]), 5), round(float(p[1]), 5)])
            except Exception:
                pass
        if pts and sample[-1] != [round(float(pts[-1][0]), 5), round(float(pts[-1][1]), 5)]:
            sample.append([round(float(pts[-1][0]), 5), round(float(pts[-1][1]), 5)])
        raw = _json.dumps({"pts": sample, "corridor_m": int(corridor_m), "max_results": int(max_results)}, separators=(",", ":"))
        return hashlib.md5(raw.encode("utf-8")).hexdigest()
    except Exception:
        return f"fuel_{len(polyline or [])}_{corridor_m}_{max_results}"

@st.cache_resource
def _fuel_fetch_executor():
    import concurrent.futures
    return concurrent.futures.ThreadPoolExecutor(max_workers=2)

def _get_fuel_stations_nonblocking(poi_engine, polyline, corridor_m=300, max_results=20, wait_sec=4.0):
    """
    Lấy cây xăng không chặn UI, cache theo TỪNG TUYẾN.

    FINAL FIX:
    - Tuyệt đối không dùng last_route_fuel_stations_all của tuyến cũ cho tuyến mới.
    - Khi route_key đổi, xóa dữ liệu cây xăng tạm của tuyến trước.
    - Nếu Overpass chưa trả kết quả cho tuyến mới, trả [] để fallback tạo marker mới theo polyline mới.
    """
    import concurrent.futures
    ss = st.session_state
    if not polyline:
        return []

    key = _fuel_route_cache_key(polyline, corridor_m=corridor_m, max_results=max_results)
    prev_key = ss.get("last_route_fuel_key")

                                                            
    if prev_key and prev_key != key:
        ss.pop("last_route_fuel_stations_all", None)
        ss.pop("last_route_fuel_stations", None)
        ss.pop("next_fuel_stations", None)
        ss["fuel_along_route_count"] = 0
        if ss.get("__fuel_fetch_key") != key:
            ss["__fuel_fetch_future"] = None
            ss["__fuel_fetch_key"] = None

    ss["__active_fuel_route_key"] = key

    cache = ss.setdefault("__fuel_route_cache", {})
    if isinstance(cache, dict) and key in cache:
        fuels = cache.get(key) or []
        ss["last_route_fuel_key"] = key
        if fuels:
            ss["last_route_fuel_stations_all"] = fuels
        return fuels

    fut = ss.get("__fuel_fetch_future")
    fut_key = ss.get("__fuel_fetch_key")

                                                                                  
    if fut is not None and fut_key == key:
        try:
            if fut.done():
                fuels = fut.result() or []
                cache[key] = fuels
                ss["__fuel_route_cache"] = cache
                ss["__fuel_fetch_future"] = None
                ss["last_route_fuel_key"] = key
                if fuels:
                    ss["last_route_fuel_stations_all"] = fuels
                return fuels

                                                              
            if ss.get("last_route_fuel_key") == key:
                return ss.get("last_route_fuel_stations_all", [])
            return []
        except Exception as e:
            ss["fuel_along_route_error"] = str(e)
            ss["__fuel_fetch_future"] = None
            if ss.get("last_route_fuel_key") == key:
                return ss.get("last_route_fuel_stations_all", [])
            return []

                                                              
    if fut is not None and fut_key != key:
        ss["__fuel_fetch_future"] = None
        ss["__fuel_fetch_key"] = None

                                                
    poly_copy = [[float(p[0]), float(p[1])] for p in (polyline or []) if len(p) >= 2]
    def _fetch():
        return poi_engine.get_fuel_stations_on_route(
            poly_copy,
            corridor_m=int(corridor_m),
            max_results=int(max_results),
            current_position=None,                                            
            only_upcoming=False,
        )

    try:
        fut = _fuel_fetch_executor().submit(_fetch)
        ss["__fuel_fetch_future"] = fut
        ss["__fuel_fetch_key"] = key
        ss["last_route_fuel_key"] = key
        try:
            fuels = fut.result(timeout=float(wait_sec))
            fuels = fuels or []
            cache[key] = fuels
            ss["__fuel_route_cache"] = cache
            ss["__fuel_fetch_future"] = None
            ss["last_route_fuel_key"] = key
            if fuels:
                ss["last_route_fuel_stations_all"] = fuels
            return fuels
        except concurrent.futures.TimeoutError:
            ss["fuel_along_route_pending"] = True
                                                                                                      
            return ss.get("last_route_fuel_stations_all", []) if ss.get("last_route_fuel_key") == key else []
    except Exception as e:
        ss["fuel_along_route_error"] = str(e)
        return ss.get("last_route_fuel_stations_all", []) if ss.get("last_route_fuel_key") == key else []



                                                                               
                                  
                                                                               
def _ts_get_fuel_lat_lon(item):
    """Đọc lat/lon linh hoạt từ nhiều format POI khác nhau."""
    try:
        if not isinstance(item, dict):
            return None, None
        lat = item.get("lat", item.get("latitude", item.get("center_lat")))
        lon = item.get("lon", item.get("lng", item.get("longitude", item.get("center_lon"))))
        if lat is None and isinstance(item.get("location"), dict):
            lat = item["location"].get("lat")
            lon = item["location"].get("lon", item["location"].get("lng"))
        if lat is None or lon is None:
            return None, None
        return float(lat), float(lon)
    except Exception:
        return None, None


def _ts_normalize_fuel_marker(item, idx=1, fallback=False):
    """Chuẩn hóa cây xăng để cả make_full_map và lớp JS đều nhận ra."""
    try:
        item = dict(item or {})
        lat, lon = _ts_get_fuel_lat_lon(item)
        if lat is None or lon is None:
            return None

        name = (
            item.get("name")
            or item.get("brand")
            or item.get("operator")
            or item.get("label")
            or ("Điểm kiểm tra nhiên liệu" if fallback else "Cây xăng")
        )
        out = dict(item)
        out.update({
            "lat": float(lat),
            "lon": float(lon),
            "lng": float(lon),
            "name": str(name),
            "label": str(name),
            "type": "fuel",
            "category": "fuel",
            "kind": "fuel",
            "amenity": "fuel",
            "icon": "⛽",
            "emoji": "⛽",
            "is_fuel": True,
            "fuel": True,
            "fallback": bool(fallback or item.get("fallback")),
            "verified": not bool(fallback or item.get("fallback")),
        })
        if out.get("route_km") is None:
            out["route_km"] = item.get("km", idx * 1.0)
        if out.get("dist_from_route_m") is None:
            out["dist_from_route_m"] = item.get("distance_m", 0 if fallback else item.get("dist_from_route_m"))
        return out
    except Exception:
        return None



def _ts_nearest_route_km_for_marker(polyline, lat, lon):
    """Tính km gần nhất trên tuyến cho marker nhiên liệu."""
    try:
        pts = polyline or []
        if not pts:
            return 0.0
        lat = float(lat); lon = float(lon)
        best_d = 999999.0
        best_km = 0.0
        km = 0.0
        prev = None
        step = max(1, int(len(pts) / 900))
        sampled = list(range(0, len(pts), step))
        if sampled[-1] != len(pts) - 1:
            sampled.append(len(pts) - 1)

                                                             
        last_idx = sampled[0]
        last_pt = pts[last_idx]
        km_at_idx = {last_idx: 0.0}
        running = 0.0
        for idx in sampled[1:]:
            p = pts[idx]
            try:
                running += _haversine_km(float(last_pt[1]), float(last_pt[0]), float(p[1]), float(p[0]))
            except Exception:
                pass
            km_at_idx[idx] = running
            last_pt = p

        for idx in sampled:
            p = pts[idx]
            try:
                d = _haversine_km(lat, lon, float(p[1]), float(p[0]))
                if d < best_d:
                    best_d = d
                    best_km = km_at_idx.get(idx, 0.0)
            except Exception:
                pass
        return float(best_km)
    except Exception:
        return 0.0


def _ts_enrich_fuel_route_km(fuels, polyline):
    """Bổ sung route_km thật cho cây xăng nếu POIEngine thiếu hoặc route_km sai."""
    out = []
    for i, f in enumerate(fuels or [], 1):
        nf = _ts_normalize_fuel_marker(f, i, fallback=bool((f or {}).get("fallback")) if isinstance(f, dict) else False)
        if not nf:
            continue
        try:
            lat, lon = _ts_get_fuel_lat_lon(nf)
            rk = nf.get("route_km")
                                                                                       
                                                                     
            real_km = _ts_nearest_route_km_for_marker(polyline, lat, lon)
            if real_km is not None:
                nf["route_km"] = float(real_km)
        except Exception:
            pass
        out.append(nf)
    return out


def _ts_pick_spaced_along_route(items, target_km=50.0, tol_km=5.0, start_km=0.0):
    """
    Chọn CÂY XĂNG THẬT rải dọc tuyến, ưu tiên khoảng cách 50±5km.

    Nguyên tắc mới:
    - Không sinh marker giả / fallback.
    - Ưu tiên tìm cây xăng thật trong cửa sổ 50±5km.
    - Nếu không có, nới cửa sổ lên 50±10km.
    - Nếu vẫn không có, nới tiếp lên 50±20km.
    - Nếu đoạn đó thật sự không có cây xăng trong các cửa sổ trên,
      lấy cây xăng thật tiếp theo ở xa hơn để không bịa dữ liệu.
    """
    if not items:
        return []

    items = sorted(items, key=lambda x: float(x.get("route_km") or 0.0))
    n = len(items)
    selected = []

                                                                              
    first_window = [it for it in items if float(it.get("route_km") or 0.0) <= start_km + target_km + 20.0]
    first = first_window[0] if first_window else items[0]
    selected.append(first)
    last_km = float(first.get("route_km") or 0.0)
    idx = items.index(first) + 1

                                                        
    tolerances = []
    for t in (tol_km, 10.0, 20.0):
        try:
            t = float(t)
        except Exception:
            continue
        if t not in tolerances:
            tolerances.append(t)

    while idx < n:
        remaining = items[idx:]
        window_target = last_km + float(target_km)
        best = None

        for t in tolerances:
            lo, hi = window_target - t, window_target + t
            candidates = [it for it in remaining if lo <= float(it.get("route_km") or 0.0) <= hi]
            if candidates:
                best = min(candidates, key=lambda it: abs(float(it.get("route_km") or 0.0) - window_target))
                break

                                                                 
                                                        
        if best is None:
            after = [it for it in remaining if float(it.get("route_km") or 0.0) > window_target + 20.0]
            if not after:
                break
            best = after[0]

        selected.append(best)
        last_km = float(best.get("route_km") or 0.0)
        idx = items.index(best) + 1

    return selected





def _ts_current_route_km_from_gps(polyline, current_position):
    """
    Tính vị trí GPS hiện tại theo km trên tuyến.
    Dùng để biết cây xăng nào đã đi qua.
    """
    try:
        if not polyline or not current_position:
            return None
        lat, lon = float(current_position[0]), float(current_position[1])
        return float(_ts_nearest_route_km_for_marker(polyline, lat, lon))
    except Exception:
        return None


def _ts_next_fuel_after_gps_progress(fuel_stations, polyline, current_position=None, max_results=2, passed_margin_km=0.30):
    """
    Lọc cây xăng phía trước theo GPS:
    - Khi GPS vượt quá route_km của cây xăng khoảng 300m, cây đó bị loại.
    - Cây tiếp theo tự lên đầu danh sách.
    - Không phụ thuộc vào poi_engine.get_next_fuel_stations() nữa vì hàm đó dễ giữ cây cũ.
    """
    try:
        fuels = _ts_enrich_fuel_route_km(fuel_stations or [], polyline)
        fuels = [f for f in fuels if f]
        fuels.sort(key=lambda x: float(x.get("route_km") or 0.0))

        if not fuels:
            st.session_state["fuel_current_route_km"] = None
            return []

        cur_km = _ts_current_route_km_from_gps(polyline, current_position)
        st.session_state["fuel_current_route_km"] = cur_km

        if cur_km is None:
            out = fuels[:int(max_results)]
            st.session_state["next_fuel_stations"] = out
            return out

                                                                                   
        ahead = []
        passed = []
        for f in fuels:
            rk = float(f.get("route_km") or 0.0)
            if rk >= float(cur_km) + float(passed_margin_km):
                ahead.append(f)
            else:
                passed.append(f)

        st.session_state["fuel_passed_count"] = len(passed)
        st.session_state["fuel_next_update_note"] = (
            f"GPS km {float(cur_km):.1f}; đã bỏ qua {len(passed)} điểm nhiên liệu phía sau."
        )

        out = ahead[:int(max_results)]
        st.session_state["next_fuel_stations"] = out
        return out
    except Exception as e:
        st.session_state["fuel_next_update_error"] = str(e)
        out = (fuel_stations or [])[:int(max_results)]
        st.session_state["next_fuel_stations"] = out
        return out




def _ts_route_fuel_fallbacks(polyline, max_results=6, target_km=50.0, fixed_kms=None):
    """
    Fallback 100% hiển thị marker nhiên liệu nếu OSM/Overpass không trả dữ liệu,
    hoặc để lấp các đoạn trống dài hơn target_km giữa các cây xăng thật.
    Đây là điểm nhắc kiểm tra nhiên liệu trên tuyến, KHÔNG giả mạo là cây xăng thật.

    fixed_kms: nếu truyền vào, tạo marker đúng tại các mốc km này (dùng để
    lấp khoảng trống cụ thể) thay vì tự sinh mốc đều theo target_km.
    """
    out = []
    try:
        if not polyline or len(polyline) < 2:
            return out
        total_km = float(_distance_km_from_polyline(polyline) or 0.0)
        if total_km <= 0:
            return out

        if fixed_kms:
            kms = [k for k in fixed_kms if 0.0 <= k <= total_km][:max_results]
        elif total_km < 30:
            kms = [max(1.0, total_km * 0.5)]
        else:
            step = float(target_km)
            first = min(step * 0.4, max(6.0, total_km * 0.18))
            kms = []
            k = first
            while k < max(5.0, total_km - 5.0) and len(kms) < int(max_results):
                kms.append(k)
                k += step
            if not kms:
                kms = [max(1.0, total_km * 0.5)]

        for i, km in enumerate(kms[:max_results], 1):
            try:
                lat, lon = _coord_at_route_km(polyline, km)
                if lat is None or lon is None:
                    continue
                out.append(_ts_normalize_fuel_marker({
                    "lat": lat,
                    "lon": lon,
                    "name": f"Điểm kiểm tra nhiên liệu {i}",
                    "label": "Điểm kiểm tra nhiên liệu",
                    "route_km": float(km),
                    "desc": "Dữ liệu cây xăng thực chưa tải được; đây là điểm nhắc kiểm tra nhiên liệu trên tuyến.",
                    "note": "fallback_unverified",
                }, idx=i, fallback=True))
            except Exception:
                continue
        return [x for x in out if x]
    except Exception:
        return []


def _ts_ensure_visible_fuel_markers(fuel_stations, polyline, max_results=24,
                                    target_km=50.0, tol_km=5.0):
    """
    Chỉ trả về CÂY XĂNG THẬT đã lấy được từ POI/Overpass.

    Cơ chế mới theo yêu cầu:
    - Tắt hẳn marker giả / fallback "Điểm kiểm tra nhiên liệu".
    - Ưu tiên phân bố cây xăng thật theo khoảng 50±5km.
    - Nếu không có cây xăng thật trong 50±5km, nới lên 50±10km.
    - Nếu vẫn không có, nới lên 50±20km.
    - Nếu đoạn nào thật sự không có dữ liệu cây xăng thật, bỏ trống đoạn đó
      thay vì tạo marker giả dễ gây hiểu lầm.
    """
    try:
        total_km = float(_distance_km_from_polyline(polyline) or 0.0)
        needed = int(total_km // max(1.0, (target_km - 20.0))) + 3
        max_results = max(int(max_results), needed)
    except Exception:
        max_results = int(max_results or 24)

    cleaned = []
    try:
        for i, f in enumerate(fuel_stations or [], 1):
            if not isinstance(f, dict):
                continue
                                                                                         
            if f.get("fallback") or f.get("note") == "fallback_unverified":
                continue
            nf = _ts_normalize_fuel_marker(f, i, fallback=False)
            if nf:
                nf["fallback"] = False
                nf["verified"] = True
                cleaned.append(nf)
    except Exception:
        cleaned = []

    if not cleaned:
                                                                    
        return [], False

                                                                                  
                                                                                          
                                                                                  
                                                                                                 
    real_pool = _ts_enrich_fuel_route_km(cleaned, polyline)
    real_pool.sort(key=lambda x: float(x.get("route_km") or 0.0))

    real_only = []
    seen = set()
    for f in real_pool:
        try:
            if f.get("fallback") or f.get("note") == "fallback_unverified":
                continue
            lat, lon = _ts_get_fuel_lat_lon(f)
            if lat is None or lon is None:
                continue
                                                     
            key = (round(float(lat), 4), round(float(lon), 4))
            if key in seen:
                continue
            seen.add(key)
            nf = dict(f)
            nf["fallback"] = False
            nf["verified"] = True
            real_only.append(nf)
        except Exception:
            continue

    real_only.sort(key=lambda x: float(x.get("route_km") or 0.0))
    return real_only[:int(max_results)], False

def _ts_inject_fuel_markers_html(map_html, fuel_markers):
    """
    Thêm một lớp marker ⛽ bằng JS trực tiếp vào Folium HTML.
    Như vậy dù ui.streamlit_map.py không nhận format POI, marker vẫn hiện.
    """
    try:
        if not map_html or not fuel_markers:
            return map_html

        import json as _json
        import re as _re

        markers = []
        for i, f in enumerate(fuel_markers or [], 1):
            try:
                lat, lon = _ts_get_fuel_lat_lon(f)
                if lat is None or lon is None:
                    continue
                markers.append({
                    "lat": float(lat),
                    "lon": float(lon),
                    "name": str(f.get("name") or f.get("label") or f"Cây xăng {i}"),
                    "route_km": float(f.get("route_km") or 0.0),
                    "fallback": bool(f.get("fallback")),
                    "verified": bool(f.get("verified", not f.get("fallback"))),
                    "operator": str(f.get("operator") or f.get("brand") or ""),
                    "dist_m": f.get("dist_from_route_m"),
                    "desc": str(f.get("desc") or ""),
                })
            except Exception:
                continue

        if not markers:
            return map_html

        m = _re.search(r"var\s+(map_[A-Za-z0-9_]+)\s*=\s*L\.map", map_html)
        map_var = m.group(1) if m else ""

        payload = _json.dumps(markers, ensure_ascii=False)
        map_ref_expr = (
            f'(typeof {map_var} !== "undefined" ? {map_var} : (window["{map_var}"] || findLeafletMap()))'
            if map_var else "findLeafletMap()"
        )

        js = f"""
<script>
(function() {{
  const FUEL_MARKERS = {payload};
  const ROUTE_FUEL_KEY = FUEL_MARKERS.map(f => `${Number(f.lat).toFixed(4)},${Number(f.lon).toFixed(4)}`).join("|");
  const LAYER_KEY = "__tripsmartGuaranteedFuelLayer_" + ROUTE_FUEL_KEY;

  function esc(s) {{
    return String(s || "").replace(/[&<>"']/g, function(c) {{
      return ({{"&":"&amp;","<":"&lt;",">":"&gt;","\\\\\\"":"&quot;","'":"&#39;"}})[c] || c;
    }});
  }}

  function findLeafletMap() {{
    try {{
      for (const k of Object.keys(window)) {{
        const v = window[k];
        if (v && window.L && v instanceof L.Map) return v;
      }}
    }} catch(e) {{}}
    try {{
      const el = document.querySelector(".folium-map, .leaflet-container");
      if (el) {{
        for (const k of Object.keys(window)) {{
          const v = window[k];
          if (v && v._container === el) return v;
        }}
      }}
    }} catch(e) {{}}
    return null;
  }}

  function fuelIcon(isFallback) {{
    const bg = isFallback ? "#f59e0b" : "#ef4444";
    const border = isFallback ? "#fff7ed" : "#ffffff";
    return L.divIcon({{
      html: `<div style="width:30px;height:30px;border-radius:50%;background:${{bg}};border:3px solid ${{border}};display:flex;align-items:center;justify-content:center;box-shadow:0 4px 12px rgba(0,0,0,.35);font-size:16px;color:white;">⛽</div>`,
      className: "tripsmart-guaranteed-fuel-icon",
      iconSize: [30, 30],
      iconAnchor: [15, 15],
      popupAnchor: [0, -15]
    }});
  }}

  function addFuelLayer() {{
    if (!window.L) return;
    const map = {map_ref_expr};
    if (!map) return;

    if (window[LAYER_KEY]) {{
      try {{ map.removeLayer(window[LAYER_KEY]); }} catch(e) {{}}
    }}

    const layer = L.layerGroup();
    let realCount = 0;
    let fallbackCount = 0;

    for (const f of FUEL_MARKERS) {{
      if (!Number.isFinite(f.lat) || !Number.isFinite(f.lon)) continue;
      if (f.fallback) fallbackCount += 1; else realCount += 1;
      const title = f.fallback ? "Điểm kiểm tra nhiên liệu" : (f.name || "Cây xăng");
      const km = f.route_km ? `km ${{Number(f.route_km).toFixed(1)}}` : "";
      const warn = f.fallback
        ? `<div style="margin-top:6px;color:#92400e"><b>Chưa xác minh:</b> OSM/Overpass chưa trả cây xăng thật, đây là điểm nhắc kiểm tra nhiên liệu.</div>`
        : `<div style="margin-top:6px;color:#166534">Dữ liệu cây xăng từ POI/OSM nếu có.</div>`;
      const popup = `
        <div style="min-width:210px">
          <b>⛽ ${{esc(title)}}</b><br>
          <span>${{esc(km)}}</span>
          ${{f.operator ? `<br><span>Đơn vị: ${{esc(f.operator)}}</span>` : ""}}
          ${{warn}}
        </div>`;
      L.marker([f.lat, f.lon], {{
        icon: fuelIcon(!!f.fallback),
        zIndexOffset: 1200,
        title: title
      }}).bindPopup(popup).addTo(layer);
    }}

    layer.addTo(map);
    window[LAYER_KEY] = layer;

    try {{
      const box = document.querySelector(".leaflet-top.leaflet-left");
      if (box && !document.querySelector(".ts-fuel-status-control")) {{
        const div = L.DomUtil.create("div", "leaflet-control ts-fuel-status-control");
        div.style.cssText = "background:rgba(255,255,255,.92);padding:8px 10px;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.22);font:600 12px system-ui;line-height:1.35;max-width:260px;";
        div.innerHTML = realCount
          ? `⛽ <b>Cây xăng dọc tuyến</b><br>Đã hiển thị ${{realCount}} điểm.`
          : `⛽ <b>Điểm nhiên liệu dự phòng</b><br>Chưa có dữ liệu OSM; đã hiển thị điểm nhắc kiểm tra.`;
        box.appendChild(div);
      }}
    }} catch(e) {{}}
  }}

  setTimeout(addFuelLayer, 250);
  setTimeout(addFuelLayer, 1200);
}})();
</script>
"""
        if "</body>" in map_html:
            return map_html.replace("</body>", js + "\n</body>")
        return map_html + js
    except Exception:
        return map_html



def _backup_trip_route_state(reason: str = ""):
    """
    Lưu route + cache phân tích ngay trong session_state.

    Lý do cần thêm lớp backup này:
    - Streamlit rerun toàn app khi đổi sidebar/menu/tab.
    - Snapshot cũ chỉ giữ tuyến, không chắc giữ cả route_view_cache.
    - Nếu cache mất, quay lại Tìm đường sẽ chạy lại phân tích nguy hiểm rất lâu.
    """
    try:
        if not st.session_state.get("last_routes"):
            return

        keys = [
            "last_origin", "last_dest", "last_mode", "last_routes", "last_selected",
            "last_compared", "last_route_risk_forecast", "last_danger_markers",
            "last_rest_stops", "last_weather_text", "last_poi_style",
            "route_runtime_options",
            "route_view_cache", "route_view_cache_key",
            "nav_active", "nav_arrived", "nav_polyline", "nav_dest", "nav_mode",
            "nav_distance_left_osrm", "auto_eta_forecast", "auto_eta_distance_km",
            "auto_eta_duration_text", "auto_eta_arrival",
        ]
        backup = {}
        for k in keys:
            if k in st.session_state:
                backup[k] = st.session_state.get(k)
        backup["reason"] = reason
        backup["ts"] = datetime.now().isoformat()
        st.session_state["__last_good_trip_route_state"] = backup
    except Exception:
        pass


def _restore_trip_route_state_if_needed():
    """
    Khôi phục tuyến/cache nếu đổi menu làm rơi state.
    Nếu tuyến còn nhưng cache phân tích bị mất, khôi phục riêng cache để quay lại Tìm đường không phải load lại.
    """
    try:
        backup = st.session_state.get("__last_good_trip_route_state")
        if not isinstance(backup, dict) or not backup.get("last_routes"):
            return False

        restored = False

                                         
        if not st.session_state.get("last_routes"):
            for k, v in backup.items():
                if k in {"reason", "ts"}:
                    continue
                st.session_state[k] = v
            restored = True

                                                                              
                                                             
        else:
            cache_keys = ["route_view_cache", "route_view_cache_key", "last_compared",
                          "last_route_risk_forecast", "last_danger_markers", "last_rest_stops",
                          "auto_eta_forecast", "auto_eta_distance_km", "auto_eta_duration_text",
                          "auto_eta_arrival"]
            for k in cache_keys:
                if k in backup and not st.session_state.get(k):
                    st.session_state[k] = backup.get(k)
                    restored = True

                                                                                         
            try:
                b_cache = backup.get("route_view_cache")
                b_key = backup.get("route_view_cache_key")
                cur_cache = st.session_state.get("route_view_cache")
                if isinstance(b_cache, dict) and b_key:
                    if not isinstance(cur_cache, dict):
                        st.session_state["route_view_cache"] = dict(b_cache)
                        st.session_state["route_view_cache_key"] = b_key
                        restored = True
                    elif b_key not in cur_cache and b_key in b_cache:
                        cur_cache[b_key] = b_cache[b_key]
                        st.session_state["route_view_cache"] = cur_cache
                        st.session_state["route_view_cache_key"] = b_key
                        restored = True
            except Exception:
                pass

        if restored:
                                                                                               
            for k in [
                "pending_origin_cands", "pending_dest_cands", "pending_route_options",
                "sel_origin", "sel_dest", "__route_search_in_progress",
            ]:
                st.session_state.pop(k, None)

            st.session_state["__route_restored_from_tab_backup"] = True
            return True

        return False
    except Exception:
        return False


def _go_menu(menu_name: str):
                                                                                  
    try:
        _backup_trip_route_state("go_menu")
    except Exception:
        pass
    try:
        _persist_current_route_snapshot()
    except Exception:
        pass
                                                                              
                                                               
    if st.session_state.get("last_routes"):
        st.session_state["__route_tab_return_rerun"] = True
    st.session_state["app_menu"] = menu_name
    st.rerun()


def _render_sidebar_button(menu_name: str, short_desc: str, key: str):
    active = st.session_state.get("app_menu", "🏠  Trang chủ") == menu_name
    prefix = "● " if active else "○ "
    label = f"{prefix}{menu_name.strip()} · {short_desc}"
    if st.button(label, key=key, use_container_width=True):
        _go_menu(menu_name)


def _home_card_html(icon, title, desc, target, bg):
    """Tạo thẻ tiện ích có thể bấm trực tiếp vào biểu tượng/thẻ, không cần nút Mở riêng."""
    href = "?go=" + quote(str(target), safe="")
    return (
        f'<a class="ts-card-link" href="{href}" target="_self">'
        f'<div class="ts-card">'
        f'<div class="ts-icon" style="background:{bg}">{icon}</div>'
        f'<div class="ts-card-title">{title}</div>'
        f'<div class="ts-card-desc">{desc}</div>'
        f'</div></a>'
    )


def _render_home_dashboard():
    """Trang chủ dạng tiện ích trực quan như app điện thoại."""
                                                                                                      
    try:
        _backup_trip_route_state("home_dashboard")
    except Exception:
        pass
    try:
        _persist_current_route_snapshot()
    except Exception:
        pass
    c1, c2 = st.columns([1, 8])

    with c1:
        st.image(str(FAVICON_PATH), width=150)

    with c2:
        st.markdown(
            """
            <div class="ts-hero">
                <h1 style="margin-top: 4px;">RANav-X</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="ts-section-title">🔥 Tiện ích nổi bật</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    for idx, (icon, title, desc, target, bg) in enumerate(APP_HOME_CARDS[:4]):
        with cols[idx % 4]:
            st.markdown(_home_card_html(icon, title, desc, target, bg), unsafe_allow_html=True)

    st.markdown('<div class="ts-section-title">⭐ Tất cả chức năng</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    for idx, (icon, title, desc, target, bg) in enumerate(APP_HOME_CARDS[4:]):
        with cols[idx % 4]:
            st.markdown(_home_card_html(icon, title, desc, target, bg), unsafe_allow_html=True)

    st.markdown(
        '<div class="ts-tip">💡 <b>Cách dùng nhanh:</b> Tìm đường → bật GPS → theo dõi Trợ lý an toàn → dùng SOS khi gặp sự cố.</div>',
        unsafe_allow_html=True,
    )



def _render_copilot_standalone(router, risk_engine, weather_api):
    """Trang riêng cho thẻ Trợ lý an toàn, không trỏ nhầm về Tìm đường."""
    st.title("🧠 Trợ lý an toàn hành trình")
    st.caption("Nên đi tiếp, nghỉ, hay đổi tuyến.")

    if not st.session_state.get("last_routes"):
        st.markdown(
            '<div class="alert-info">🗺️ Hãy tìm đường trước để Trợ lý an toàn có tuyến, ETA và dữ liệu rủi ro để phân tích.</div>',
            unsafe_allow_html=True,
        )
        if st.button("🗺️ Đi tới Tìm đường", type="primary", use_container_width=True, key="copilot_go_to_route"):
            _go_menu("🗺️  Tìm đường")
        return

    routes = st.session_state.get("last_routes", [])
    selected = min(int(st.session_state.get("last_selected", 0) or 0), max(0, len(routes) - 1))
    route = dict(routes[selected] if routes else {})
    mode = st.session_state.get("nav_mode") or st.session_state.get("last_mode", "car")

    if st.session_state.get("nav_active") and st.session_state.get("nav_polyline"):
        route["polyline"] = st.session_state.get("nav_polyline")
        route["distance_km"] = (
            st.session_state.get("nav_distance_left_osrm")
            or st.session_state.get("auto_eta_distance_km")
            or _get_route_distance_km(route)
        )
        _apply_avg_speed_timing(route, mode)

    forecast = st.session_state.get("auto_eta_forecast") or st.session_state.get("last_route_risk_forecast") or {}
    danger_markers = st.session_state.get("last_danger_markers") or []
    rest_stops = st.session_state.get("last_rest_stops") or []

    copilot = _build_mobility_copilot_state(
        forecast=forecast,
        route=route,
        danger_markers=danger_markers,
        rest_stops=rest_stops,
        mode=mode,
        nav_active=bool(st.session_state.get("nav_active") and not st.session_state.get("nav_arrived")),
    )
    st.session_state["copilot_critical_segment"] = copilot.get("critical_segment") or {}
    _render_mobility_copilot_state(copilot)

    if st.session_state.get("copilot_last_action"):
        st.info(st.session_state.get("copilot_last_action"))

    if copilot.get("has_red_decision"):
        st.markdown("**Hành động đề xuất**")
        cpa, cpb, cpc, cpd = st.columns(4)
        with cpa:
            if st.button("✅ Đồng ý đổi tuyến", key="copilot_page_accept_reroute", use_container_width=True):
                ok, msg = _accept_copilot_reroute(
                    router=router,
                    risk_engine=risk_engine,
                    weather_api=weather_api,
                    mode_fallback=mode,
                    route_fallback=route,
                )
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.warning(msg)
        with cpb:
            if st.button("⏸️ Nghỉ 15 phút", key="copilot_page_rest_15", use_container_width=True):
                st.session_state["copilot_pending_rest_min"] = 15
        with cpc:
            if st.button("⏸️ Nghỉ 30 phút", key="copilot_page_rest_30", use_container_width=True):
                st.session_state["copilot_pending_rest_min"] = 30
        with cpd:
            if st.button("⚠️ Vẫn đi tiếp", key="copilot_page_continue", use_container_width=True):
                import time as _time
                st.session_state["copilot_dismiss_until"] = _time.time() + 10 * 60
                st.session_state["copilot_last_action"] = "⚠️ Bạn đã chọn vẫn đi tiếp. App sẽ tiếp tục giám sát rủi ro phía trước."
                st.info(st.session_state["copilot_last_action"])
    else:
        st.caption("Chưa có chấm đỏ ≥ 85% trên phần tuyến phía trước, nên app không hiện nút đổi tuyến/nghỉ để tránh gây rối.")

    pending_rest = st.session_state.get("copilot_pending_rest_min")
    if pending_rest:
        st.warning(f"Bạn có chắc muốn nghỉ {pending_rest} phút rồi cập nhật lại ETA và AI Risk Forecast không?")
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button("✅ Xác nhận nghỉ và cập nhật", key="copilot_page_confirm_rest", use_container_width=True):
                ok, msg = _accept_copilot_rest(
                    router=router,
                    risk_engine=risk_engine,
                    weather_api=weather_api,
                    mode_fallback=mode,
                    delay_min=int(pending_rest),
                )
                st.session_state["copilot_pending_rest_min"] = None
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.warning(msg)
        with cc2:
            if st.button("❌ Hủy", key="copilot_page_cancel_rest", use_container_width=True):
                st.session_state["copilot_pending_rest_min"] = None
                st.rerun()

    st.caption("Trợ lý an toàn không tự đổi tuyến. App chỉ đổi tuyến hoặc cập nhật ETA khi bạn xác nhận.")



def _render_sos_contacts_manager_compact(prefix: str = "sidebar_sos_family"):
    """
    Form SOS cực gọn cho sidebar hẹp:
    chỉ còn ô tên, ô số điện thoại và nút dấu +.
    Không hiện chú thích dài để tránh phải kéo sâu trên điện thoại.
    """
    try:
        _sos_init_state()
    except Exception:
        pass

    with st.form(f"{prefix}_compact_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([1.05, 1.05, 0.42])
        with c1:
            name = st.text_input(
                "Tên người thân",
                placeholder="VD: Mẹ",
                key=f"{prefix}_compact_name",
                label_visibility="visible",
            )
        with c2:
            phone = st.text_input(
                "Số điện thoại",
                placeholder="VD: 098...",
                key=f"{prefix}_compact_phone",
                label_visibility="visible",
            )
        with c3:
                                              
            st.markdown("<div style='height: 1.75rem'></div>", unsafe_allow_html=True)
            submitted = st.form_submit_button(
                "➕",
                use_container_width=True,
                help="Thêm số người thân",
            )

    if submitted:
        if not str(name or "").strip() or not str(phone or "").strip():
            st.warning("Nhập đủ tên và số điện thoại.")
            return
        try:
            result = _sos_add_family_contact(name, phone)
            ok, msg = True, "Đã thêm số người thân."
            if isinstance(result, tuple):
                if len(result) >= 1:
                    ok = bool(result[0])
                if len(result) >= 2:
                    msg = str(result[1])
            elif isinstance(result, bool):
                ok = result
            if ok:
                                             
                                                                                     
                                                                                       
                try:
                    _ts_sos_remember_added_contact(name, phone)
                except Exception:
                    pass
                try:
                    if st.session_state.get("last_routes"):
                        _persist_current_route_snapshot()
                except Exception:
                    pass
                st.session_state["__sos_contact_submit_rerun"] = True
                st.success(msg)
            else:
                st.warning(msg)
        except Exception as e:
            st.warning(f"Không thêm được số: {e}")


                                                                               
                                           
                                                                               
def _render_compact_floating_sos_button(prefix: str = "global_float_sos"):
    """
    SOS nổi cực gọn cho điện thoại:
    - Chỉ còn 1 nút: 🆘 GỬI SOS
    - Không hiện GPS/status/chú thích trong card nổi.
    - Vẫn mở SMS tới tất cả số người thân đã lưu.
    """
    try:
        import html as _html
        _sos_init_state()

        contacts = _ts_sos_get_family_contacts_safe() or []
        numbers = ",".join(
            _sos_normalize_phone_for_sms(c.get("phone"))
            for c in contacts
            if c and c.get("phone")
        )

        lat = st.session_state.get("nav_gps_lat")
        lon = st.session_state.get("nav_gps_lon")

                                                                                     
        try:
            if (lat is None or lon is None) and st.session_state.get("last_origin"):
                lat, lon = st.session_state.get("last_origin")
        except Exception:
            pass

        try:
            lat_f = float(lat) if lat is not None else None
            lon_f = float(lon) if lon is not None else None
        except Exception:
            lat_f = lon_f = None

        if lat_f is not None and lon_f is not None:
            msg = _sos_message_template("Khẩn cấp", lat_f, lon_f, "Tôi cần giúp đỡ ngay.")
        else:
            msg = "🆘 Tôi cần giúp đỡ ngay. Hiện chưa lấy được GPS chính xác."

        if numbers:
            href = _sos_build_sms_link(numbers, msg)
            onclick = ""
        else:
            href = "#"
            onclick = "alert('Bạn chưa nhập số người thân trong sidebar.'); return false;"

        href = _html.escape(str(href), quote=True)
        onclick = _html.escape(str(onclick), quote=True)

        st.markdown(
            f"""
            <style>
            .ts-compact-sos-btn {{
                position: fixed;
                left: 10px;
                bottom: calc(env(safe-area-inset-bottom, 0px) + 10px);
                z-index: 2147483600;
                width: 108px;
                height: 48px;
                border-radius: 18px;
                background: linear-gradient(135deg, #ff3b3b, #ff6b6b);
                color: #fff !important;
                display: flex;
                align-items: center;
                justify-content: center;
                text-decoration: none !important;
                font-weight: 900;
                font-size: 13px;
                letter-spacing: .01em;
                box-shadow: 0 10px 26px rgba(220, 38, 38, .38);
                border: 2px solid rgba(255,255,255,.9);
                -webkit-tap-highlight-color: transparent;
            }}
            .ts-compact-sos-btn:active {{
                transform: scale(.97);
            }}
            @media (max-width: 760px) {{
                .ts-compact-sos-btn {{
                    width: 94px;
                    height: 42px;
                    left: 8px;
                    bottom: calc(env(safe-area-inset-bottom, 0px) + 8px);
                    border-radius: 16px;
                    font-size: 12px;
                }}
            }}
            </style>
            <a class="ts-compact-sos-btn" href="{href}" onclick="{onclick}">🆘 GỬI SOS</a>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
                                          
        pass


def _render_safety_quiz(key_prefix: str = "safety_quiz"):
    """
    Micro fact cực gọn:
    - Chỉ hiện fact.
    - Không hiện category, tiêu đề, "Không cần trả lời", "tự đổi sau 5 phút".
    - Card nhỏ hơn và né nút SOS ở điện thoại.
    """
    try:
        import time as _time
        import html as _html

        try:
            from core.microlearning import (
                FACT_HISTORY_KEY, build_micro_context, load_fact_bank,
                remember_fact, select_micro_fact,
            )
        except Exception:
            return

        route_risk_forecast = st.session_state.get("last_route_risk_forecast") or st.session_state.get("route_risk_forecast")
        danger_markers = st.session_state.get("last_danger_markers") or st.session_state.get("danger_markers") or []
        mode = st.session_state.get("last_mode") or st.session_state.get("mode") or "car"
        weather_text = st.session_state.get("last_weather_text") or st.session_state.get("weather_desc") or ""
        speed_kmh = st.session_state.get("gps_speed_kmh") or st.session_state.get("current_speed_kmh")

        context = build_micro_context(
            mode=mode,
            weather_text=weather_text,
            route_risk_forecast=route_risk_forecast,
            danger_markers=danger_markers,
            speed_kmh=speed_kmh,
        )

        facts = load_fact_bank()
        recent_ids = st.session_state.get(FACT_HISTORY_KEY, [])
        current_bucket = int(_time.time() // 300)
        fact_key = f"{key_prefix}_compact_fact_b{current_bucket}"
        st.session_state.pop(f"{key_prefix}_compact_fact_b{current_bucket - 1}", None)

        fact = st.session_state.get(fact_key)
        if not fact:
            fact = select_micro_fact(context=context, recent_ids=recent_ids, facts=facts, language="vi")
            if fact:
                st.session_state[fact_key] = fact
                remember_fact(st.session_state, str(fact.get("id", "")))

        if not fact:
            return

        fact_text = str(fact.get("text", "")).strip()
        if not fact_text:
            return

        fact_text = _html.escape(fact_text)

        st.markdown(
            f"""
            <style>
            .tripsmart-microfact-float,
            .tripsmart-microfact-title,
            .tripsmart-microfact-meta {{
                display: none !important;
            }}
            .ts-fact-shell {{
                position: fixed;
                inset: auto;
                z-index: 2147483100;
                margin: 0;
                padding: 0;
            }}
            .ts-fact-shell > summary {{
                list-style: none;
            }}
            .ts-fact-shell > summary::-webkit-details-marker {{
                display: none;
            }}
            .ts-fact-toggle-btn {{
                position: fixed;
                right: 7px;
                top: calc(env(safe-area-inset-top, 0px) + 6px);
                z-index: 2147483200;
                width: 24px;
                height: 24px;
                border-radius: 999px;
                border: 1px solid rgba(255,255,255,.86);
                background: rgba(17, 24, 39, .84);
                color: #fff;
                display: flex;
                align-items: center;
                justify-content: center;
                box-shadow: 0 6px 16px rgba(15,23,42,.22);
                cursor: pointer;
                user-select: none;
                -webkit-tap-highlight-color: transparent;
            }}
            .ts-fact-shell[open] .ts-fact-toggle-btn::after {{
                content: "×";
                font-size: 16px;
                line-height: 1;
                font-weight: 900;
            }}
            .ts-fact-shell:not([open]) .ts-fact-toggle-btn::after {{
                content: "💡";
                font-size: 13px;
                line-height: 1;
            }}
            .ts-fact-shell:not([open]) .ts-fact-compact {{
                display: none !important;
            }}
            .ts-fact-toggle-btn:active {{
                transform: scale(.94);
            }}
            .ts-fact-compact {{
                position: fixed;
                left: 10px;
                right: 10px;
                top: calc(env(safe-area-inset-top, 0px) + 8px);
                z-index: 2147483000;
                max-width: none;
                width: auto;
                background: rgba(255,255,255,.97);
                color: #1f2937;
                border: 1px solid rgba(255, 71, 87, .20);
                border-left: 4px solid #ff4757;
                border-radius: 14px;
                box-shadow: 0 8px 22px rgba(15, 23, 42, .14);
                padding: 8px 11px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                font-size: 13px;
                line-height: 1.28;
                font-weight: 700;
                pointer-events: none;
            }}
            @media (max-width: 760px) {{
                .ts-fact-compact {{
                    left: 8px;
                    right: 38px;
                    top: calc(env(safe-area-inset-top, 0px) + 6px);
                    max-width: none;
                    padding: 7px 9px;
                    font-size: 12.5px;
                    line-height: 1.25;
                    border-radius: 12px;
                }}
            }}
            </style>
            <details class="ts-fact-shell" open>
                <summary class="ts-fact-toggle-btn" aria-label="Đóng mở mẹo"></summary>
                <div class="ts-fact-compact">💡 {fact_text}</div>
            </details>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        pass


                                                                               
         
                                                                               
_inject_accessible_ui_css()
if "app_menu" not in st.session_state:
    st.session_state["app_menu"] = "🏠  Trang chủ"

                                                                                   
try:
    _go_qp = st.query_params.get("go", None)
    if _go_qp:
        _go_target = unquote(_go_qp)
        _valid_targets = {"🏠  Trang chủ"}
        for _group_title, _items in APP_NAV_GROUPS:
            for _target, _desc in _items:
                _valid_targets.add(_target)
        _valid_targets.add("🤖  AI Risk Model")
        if _go_target in _valid_targets:
                                                                         
                                                                                      
            try:
                _backup_trip_route_state("query_param_go")
            except Exception:
                pass
            try:
                _persist_current_route_snapshot()
            except Exception:
                pass
            if st.session_state.get("last_routes"):
                st.session_state["__route_tab_return_rerun"] = True
            st.session_state["app_menu"] = _go_target
        try:
            del st.query_params["go"]
        except Exception:
            pass
except Exception:
    pass

menu = st.session_state.get("app_menu", "🏠  Trang chủ")
                                                                                             
                                                                                                                  
try:
    if st.session_state.get("last_routes") and not st.session_state.get("__route_search_in_progress"):
        _backup_trip_route_state("top_keepalive")
        _persist_current_route_snapshot()
except Exception:
    pass
                                                                                               
                                                                        
_restore_trip_route_state_if_needed()
if "Tìm đường" in menu or "Trợ lý an toàn" in menu:
    _restore_route_snapshot_if_needed()
    _restore_trip_route_state_if_needed()

                                       
                                                                                       
                                                                                                
try:
    if st.session_state.get("nav_active") and not st.session_state.get("nav_arrived"):
        _sync_nav_gps_from_browser()
except Exception:
    pass

with st.sidebar:
    c1, c2 = st.columns([1, 4])
    with c1:
        st.image(str(FAVICON_PATH), width=38)
    with c2:
        st.markdown("## RANav-X")
                                                           
                                                                        
    _render_sos_contacts_manager_compact(prefix="sidebar_sos_family")
    try:
        _ts_saved_sos_contacts = _ts_sos_get_family_contacts_safe()
        if _ts_saved_sos_contacts:
            with st.expander(f"✅ Số SOS đã lưu ({len(_ts_saved_sos_contacts)})", expanded=False):
                for _idx, _c in enumerate(_ts_saved_sos_contacts):
                    _cid = _ts_sos_contact_id(_c)
                    _name = str((_c or {}).get("name") or "Người thân")
                    _phone = str((_c or {}).get("phone") or "")
                    _c1, _c2 = st.columns([4, 1])
                    with _c1:
                        st.markdown(
                            f"""
                            <div style="color:#ffffff;font-weight:800;line-height:1.25;">
                                {_name}<br>
                                <span style="color:#ffffff;font-family:monospace;font-weight:800;">{_phone}</span>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    with _c2:
                        if st.button("🗑️", key=f"del_sos_contact_{_idx}_{_cid}", help="Xóa số SOS này"):
                            _ts_sos_delete_contact_by_id(_cid)
                            st.success("✅ Đã xóa số SOS.")
                            st.rerun()
    except Exception as _e:
        st.caption(f"Không đọc được danh sách SOS: {_e}")

    st.divider()

    if st.button("🏠  Trang chủ · Tất cả", key="nav_home", use_container_width=True):
        _go_menu("🏠  Trang chủ")
    st.divider()

    st.markdown("### Tiện ích")
    for gi, (group_title, items) in enumerate(APP_NAV_GROUPS):
        with st.expander(group_title, expanded=(gi == 0)):
            for ii, (target, desc) in enumerate(items):
                _render_sidebar_button(target, desc, key=f"nav_group_{gi}_{ii}")

    st.divider()
    with st.expander("⚙️ Công cụ nâng cao", expanded=False):
        _render_sidebar_button("🤖  AI Risk Model", "AI chi tiết", key="nav_ai_admin")

    st.divider()
    st.markdown("**📞 Khẩn cấp**")
    st.markdown("🚓 Công an: **113**")
    st.markdown("🚒 Cứu hỏa: **114**")
    st.markdown("🚑 Cấp cứu: **115**")
    st.markdown("🏔️ Cứu nạn: **1800 599 920**")
    st.divider()
                                                                         
    if "maps_api" in dir():                                        
        _saved = maps_api.list_user_aliases() if hasattr(maps_api, "list_user_aliases") else []
        label = f"📌 Địa danh đã lưu ({len(_saved)})" if _saved else "📌 Địa danh đã lưu"
        with st.expander(label, expanded=False):
            if not _saved:
                st.caption("Chưa có địa danh nào. Khi tìm không thấy, app sẽ hỏi bạn nhập tọa độ và lưu lại ở đây.")
            else:
                for item in _saved:
                    c1, c2 = st.columns([3, 1])
                    c1.markdown(f"**{item['name']}**  \n`{item['lat']:.4f}, {item['lon']:.4f}`")
                    if c2.button("🗑️", key=f"del_alias_{item['name']}", help="Xoá"):
                        maps_api.delete_user_alias(item["name"])
                        st.rerun()

                                                                        
_render_compact_floating_sos_button(prefix="global_float_sos")

                                                                               
                                                                                
                                                                                            
try:
    import time as _ts_5min_time
    TRIPSMART_5MIN_REFRESH_SEC = 300
    _tripsmart_5min_bucket = int(_ts_5min_time.time() // TRIPSMART_5MIN_REFRESH_SEC)
    st.session_state["__tripsmart_5min_bucket"] = _tripsmart_5min_bucket
    st.session_state["__tripsmart_5min_refresh_warning"] = ""
    if _AUTOREFRESH_OK and st_autorefresh is not None and st.session_state.get("last_routes"):
        st_autorefresh(
            interval=TRIPSMART_5MIN_REFRESH_SEC * 1000,
            key="tripsmart_safe_eta_5min_refresh",
        )

                    
                                                                              
                                                                                            
                                                                                      
                                                                                        
except Exception:
    _tripsmart_5min_bucket = int(datetime.now().timestamp() // 300)
    st.session_state["__tripsmart_5min_bucket"] = _tripsmart_5min_bucket

                                                                   
_render_safety_quiz(key_prefix="global_micro_fact")

if not MODULES_OK:
    st.error(f"❌ Không load được module: `{IMPORT_ERROR}`")
    st.stop()

(router, risk_engine, human_router,
 sos, crowd, poi_engine, memory,
 weather_api, maps_api, ai_engine) = init_engines()

from core.reroute         import RerouteEngine
from features.disaster_route import DisasterRouteEngine
reroute  = RerouteEngine(router, risk_engine)
disaster = DisasterRouteEngine(router, risk_engine)

                                                                               
@st.cache_resource
def init_ml_model():
    try:
        from core.ml_risk_model import MLRiskModel
        return MLRiskModel()
    except Exception as e:
        return None

@st.cache_resource
def init_speed_limit_engine():
    """Speed Limit Layer: đọc maxspeed từ OSM. Nếu không có maxspeed thì UI hiện Không có thông tin."""
    if not _SPEED_LIMIT_OK or SpeedLimitEngine is None:
        return None
    try:
        return SpeedLimitEngine()
    except Exception:
        return None


def _update_tomtom_speed_limit_from_gps(force=False):
    """
    Lấy tốc độ tối đa hợp pháp từ TomTom Snap to Roads theo GPS hiện tại.

    - Không gọi API mỗi lần rerun: cache 60 giây.
    - Nếu chưa có GPS hoặc TomTom không có dữ liệu, trả None và lưu trạng thái rõ ràng.
    - Không thay thế OSM speed_segments trên bản đồ; chỉ bổ sung tốc độ tối đa tại vị trí hiện tại.
    """
    import time as _time

    if not _TOMTOM_SPEED_LIMIT_OK or get_speed_limit_from_tomtom is None:
        st.session_state["tomtom_speed_limit_status"] = "Chưa load được core.tomtom_speed_limit"
        return None

    lat = st.session_state.get("nav_gps_lat")
    lon = st.session_state.get("nav_gps_lon")
    if lat is None or lon is None:
        st.session_state["tomtom_speed_limit_status"] = "Chưa có GPS"
        return None

    now = _time.time()

                                                                                      
                                                         
    try:
        if not force and now < float(st.session_state.get("nav_skip_heavy_until", 0) or 0):
            st.session_state["tomtom_speed_limit_status"] = "Đang chờ GPS ổn định"
            return st.session_state.get("tomtom_speed_limit_data")
    except Exception:
        pass

    last_check = float(st.session_state.get("tomtom_speed_limit_last_check", 0) or 0)
    if not force and now - last_check < 60:
        return st.session_state.get("tomtom_speed_limit_data")

    try:
        data = get_speed_limit_from_tomtom(float(lat), float(lon))
    except Exception as e:
        data = {
            "ok": False,
            "speed_limit": None,
            "unit": "km/h",
            "message": f"Lỗi gọi TomTom: {e}",
        }

    st.session_state["tomtom_speed_limit_data"] = data
    st.session_state["tomtom_speed_limit_last_check"] = now

    if data and data.get("ok"):
        st.session_state["tomtom_speed_limit_value"] = data.get("speed_limit")
        st.session_state["tomtom_speed_limit_unit"] = data.get("unit", "km/h")
        st.session_state["tomtom_speed_limit_status"] = "OK"
    else:
        st.session_state["tomtom_speed_limit_value"] = None
        st.session_state["tomtom_speed_limit_unit"] = "km/h"
        st.session_state["tomtom_speed_limit_status"] = (data or {}).get("message", "Không có dữ liệu")

    return data




def _get_route_speed_segments(polyline, mode, corridor_m=120, sample_every_km=1.5, max_results=120):
    """
    Speed limit dọc tuyến:
    1) Ưu tiên Goong Speed Limit API bằng GOONG_API_KEY đã có.
    2) Nếu Goong lỗi/không có dữ liệu thì fallback về OSM SpeedLimitEngine cũ.
    Chỉ thay lớp dữ liệu tốc độ, không thay routing/map/SOS/ETA.
    """
    speed_segments = []
    errors = []

                                                                        
    if _GOONG_SPEED_LIMIT_OK and get_goong_speed_limits_on_route is not None:
        try:
            speed_segments = get_goong_speed_limits_on_route(
                polyline,
                mode=mode,
                sample_every_km=1.5,
                max_points=180,
                max_workers=8,
            )
            if speed_segments:
                st.session_state["speed_limit_source"] = "Goong Speed Limit"
                st.session_state.pop("speed_limit_error", None)
                return speed_segments[:max_results]
        except Exception as e:
            errors.append(f"Goong: {e}")

                                        
    try:
        speed_engine = init_speed_limit_engine()
        if speed_engine is not None:
            speed_segments = speed_engine.get_speed_limits_on_route(
                polyline,
                mode=mode,
                corridor_m=corridor_m,
                sample_every_km=sample_every_km,
                max_results=max_results,
            )
            if speed_segments:
                st.session_state["speed_limit_source"] = "OSM maxspeed"
                st.session_state.pop("speed_limit_error", None)
                return speed_segments
    except Exception as e:
        errors.append(f"OSM: {e}")

    if errors:
        st.session_state["speed_limit_error"] = " | ".join(errors)
    st.session_state["speed_limit_source"] = "Không có dữ liệu"
    return []


def _update_current_speed_limit_from_gps(force=False):
    """
    Tốc độ tối đa tại GPS hiện tại:
    - Ưu tiên Goong Speed Limit.
    - Nếu Goong không có dữ liệu thì fallback TomTom cũ.
    - Cache 60 giây để không gọi API liên tục khi GPS cập nhật.
    """
    import time as _time

    lat = st.session_state.get("nav_gps_lat")
    lon = st.session_state.get("nav_gps_lon")
    if lat is None or lon is None:
        st.session_state["current_speed_limit_value"] = None
        st.session_state["current_speed_limit_source"] = ""
        st.session_state["current_speed_limit_status"] = "Chưa có GPS"
        return None

    now = _time.time()

    try:
        if not force and now < float(st.session_state.get("nav_skip_heavy_until", 0) or 0):
            st.session_state["current_speed_limit_status"] = "Đang chờ GPS ổn định"
            return st.session_state.get("current_speed_limit_data")
    except Exception:
        pass

    last_check = float(st.session_state.get("current_speed_limit_last_check", 0) or 0)
    if not force and now - last_check < 60:
        return st.session_state.get("current_speed_limit_data")

    data = None

                    
    if _GOONG_SPEED_LIMIT_OK and get_speed_limit_from_goong is not None:
        try:
            data = get_speed_limit_from_goong(float(lat), float(lon))
        except Exception as e:
            data = {"ok": False, "speed_limit": None, "message": f"Lỗi gọi Goong: {e}", "source": "goong_speed_limit"}

        if data and data.get("ok") and data.get("speed_limit") is not None:
            st.session_state["current_speed_limit_data"] = data
            st.session_state["current_speed_limit_last_check"] = now
            st.session_state["current_speed_limit_value"] = data.get("speed_limit")
            st.session_state["current_speed_limit_unit"] = data.get("unit", "km/h")
            st.session_state["current_speed_limit_source"] = "Goong"
            st.session_state["current_speed_limit_status"] = "OK"
            return data

                           
    tomtom_data = _update_tomtom_speed_limit_from_gps(force=force)
    st.session_state["current_speed_limit_data"] = tomtom_data
    st.session_state["current_speed_limit_last_check"] = now

    if tomtom_data and tomtom_data.get("ok") and tomtom_data.get("speed_limit") is not None:
        st.session_state["current_speed_limit_value"] = tomtom_data.get("speed_limit")
        st.session_state["current_speed_limit_unit"] = tomtom_data.get("unit", "km/h")
        st.session_state["current_speed_limit_source"] = "TomTom"
        st.session_state["current_speed_limit_status"] = "OK"
    else:
        st.session_state["current_speed_limit_value"] = None
        st.session_state["current_speed_limit_unit"] = "km/h"
        st.session_state["current_speed_limit_source"] = ""
        st.session_state["current_speed_limit_status"] = (
            (data or {}).get("message")
            or (tomtom_data or {}).get("message")
            or "Không có dữ liệu"
        )

    return st.session_state.get("current_speed_limit_data")


def _format_current_speed_limit_text():
    """Chuẩn hóa text hiển thị tốc độ tối đa ưu tiên Goong, fallback TomTom."""
    value = st.session_state.get("current_speed_limit_value")
    unit = st.session_state.get("current_speed_limit_unit", "km/h")
    source = st.session_state.get("current_speed_limit_source", "")
    status = st.session_state.get("current_speed_limit_status", "")

    if value is None:
        return "Chưa có dữ liệu" if not status else f"Chưa có dữ liệu ({status})"

    try:
        value_txt = f"{float(value):.0f}"
    except Exception:
        value_txt = str(value)

    suffix = f" · {source}" if source else ""
    return f"{value_txt} {unit}{suffix}"


                                                                                 
              
                                                                                 
if "Trang chủ" in menu:
    _render_home_dashboard()
elif "Trợ lý an toàn" in menu:
    _render_copilot_standalone(router, risk_engine, weather_api)
elif "Kiểm tra kẹt xe" in menu:
    render_traffic_view_tomtom(height=760)
elif "Tìm đường" in menu:
    st.title("🗺️ Tìm đường thông minh")
    st.caption("🆘 Trước khi bắt đầu dẫn đường GPS, hãy nhập số người thân ở sidebar để dùng SOS nhanh khi có sự cố.")

    with st.expander("🔎 Sửa điểm đi/đến và tìm tuyến khác", expanded=not bool(st.session_state.get("last_routes"))):
                                                                                  
                                                                                     
                                                                             
        components.html(_build_gps_preload_html(interval_ms=1000, hidden=True), height=1, scrolling=False)

        _gps_ready = _read_latest_gps_from_browser(max_age_sec=600, key="gps_origin_ready_probe")
        if _gps_ready:
            st.session_state["gps_origin_ready"] = _gps_ready

        _use_my_loc = st.button(
            "📡 Dùng vị trí GPS của tôi làm điểm xuất phát",
            key="btn_use_gps_origin",
            help="App tự xin GPS khi mở trang; bấm 1 lần để dùng tọa độ mới nhất đã lưu.",
        )
        if _use_my_loc:
            if not _JSEVAL_OK:
                st.error("Thiếu thư viện `streamlit-js-eval`. Chạy: `pip install streamlit-js-eval`")
            else:
                _gps_payload = _read_latest_gps_from_browser(max_age_sec=600, key="gps_origin_button_read")

                                                                                                             
                if not _gps_payload and get_geolocation is not None:
                    with st.spinner("📡 Đang lấy GPS lần đầu…"):
                        _geo_origin = get_geolocation()
                    if _geo_origin and isinstance(_geo_origin, dict):
                        _c = _geo_origin.get("coords", {})
                        _lat_o = _c.get("latitude")
                        _lon_o = _c.get("longitude")
                        if _lat_o is not None and _lon_o is not None:
                            _gps_payload = {
                                "lat": float(_lat_o),
                                "lon": float(_lon_o),
                                "acc": _c.get("accuracy"),
                                "source": "get_geolocation_click",
                            }

                if _gps_payload:
                    _lat_o = float(_gps_payload["lat"])
                    _lon_o = float(_gps_payload["lon"])
                    _acc_o = _gps_payload.get("acc")
                    _gps_str = f"{_lat_o:.6f},{_lon_o:.6f}"
                    st.session_state["origin_from_gps"] = _gps_str
                    st.session_state["input_origin"] = _gps_str
                    st.session_state["nav_gps_lat"] = _lat_o
                    st.session_state["nav_gps_lon"] = _lon_o
                    st.session_state["nav_gps_ts"] = _gps_payload.get("ts", 0.0) or 0.0
                    st.session_state["nav_gps_source"] = _gps_payload.get("source", "origin_oneclick")
                    _acc_txt = f" (±{float(_acc_o):.0f}m)" if _acc_o else ""
                    st.success(f"✅ GPS: {_lat_o:.5f}, {_lon_o:.5f}{_acc_txt} — đã điền vào ô xuất phát.")
                else:
                    st.warning("⏳ Đang xin GPS. Hãy bấm **Cho phép vị trí** trên trình duyệt, đợi 1–3 giây rồi bấm lại nếu đây là lần cấp quyền đầu tiên.")

        col1, col2 = st.columns(2)
        with col1:
            origin_input = st.text_input(
                "📍 Điểm xuất phát",
                placeholder="VD: TP.HCM  hoặc  10.77,106.69",
                key="input_origin",
            )
        with col2:
            dest_input = st.text_input("🏁 Điểm đến", placeholder="VD: Đà Lạt  hoặc  11.94,108.44")

        r2a, r2b, r2c, r2d = st.columns(4)
        with r2a:
            mode = st.selectbox("🚗 Phương tiện", ["car", "motorbike"],
                format_func=lambda x:{"car":"🚗 Ô tô","motorbike":"🏍️ Xe máy"}[x])
        with r2b:
            poi_style = st.selectbox("🏖️ Địa điểm dọc đường",
                ["all","food","adventure","culture","relaxation","family"],
                format_func=lambda x:{
                    "all":"🌐 Tất cả","food":"🍜 Ăn uống","adventure":"🏔️ Thiên nhiên",
                    "culture":"🏛️ Văn hoá","relaxation":"🏖️ Nghỉ dưỡng","family":"👨‍👩‍👧 Gia đình"}[x])
        with r2c:
            show_alt = st.checkbox("🔀 Tuyến thay thế", value=False)
        with r2d:
            departure_time = st.time_input("🕒 Giờ xuất phát", value=datetime.now().time())
            departure_dt = datetime.combine(date.today(), departure_time)

                                                                                  
                                                                                       
        _default_eta_speed = _default_avg_speed_kmh_by_mode(mode)
        if "eta_custom_speed_enabled" not in st.session_state:
            st.session_state["eta_custom_speed_enabled"] = False
        if "eta_custom_speed_kmh" not in st.session_state:
            st.session_state["eta_custom_speed_kmh"] = _default_eta_speed

        with st.expander("⚙️ Tùy chọn ETA", expanded=False):
            st.checkbox(
                "Tùy chỉnh tốc độ trung bình để tính ETA",
                key="eta_custom_speed_enabled",
                help=(
                    "Tắt: app tự dùng tốc độ theo phương tiện. "
                    "Bật: mọi ETA và AI Risk Forecast sẽ dùng tốc độ bạn nhập."
                ),
            )
            if st.session_state.get("eta_custom_speed_enabled"):
                st.number_input(
                    "Tốc độ trung bình dùng để tính ETA (km/h)",
                    min_value=1.0, max_value=120.0, step=1.0,
                    value=float(st.session_state.get("eta_custom_speed_kmh") or _default_eta_speed),
                    key="eta_custom_speed_kmh",
                    help="Áp dụng cho thời gian tuyến, Auto ETA, reroute và AI Risk Forecast.",
                )
                st.caption(f"Đang dùng tốc độ tùy chỉnh: {_format_speed_label(mode)}.")
            else:
                st.session_state["eta_custom_speed_kmh"] = _default_eta_speed
                st.caption(f"Đang dùng tốc độ mặc định theo phương tiện: {_format_default_speed_label(mode)}.")

                                                                          
                                                                                                             
        age = 30
        travel_hour = int(departure_dt.hour)
        motion_sick = False
        has_children = False
        stress_level = 2
        use_human = False

        run_search = st.button("🔍 Tìm đường", type="primary", use_container_width=True)

                                                                                     
        if run_search:
            if not origin_input or not dest_input:
                st.warning("Nhập điểm xuất phát và điểm đến."); st.stop()

            with st.spinner("📡 Tìm địa điểm..."):
                origin_cands = resolve_location_candidates(origin_input, maps_api)
                dest_cands   = resolve_location_candidates(dest_input,   maps_api)

            if not origin_cands:
                if not _handle_unknown_location("Điểm xuất phát", origin_input, maps_api, "coord_origin"):
                    st.stop()
                resolved = st.session_state.get("resolved_coord_origin")
                if not resolved: st.stop()
                origin_cands = [resolved]

            if not dest_cands:
                if not _handle_unknown_location("Điểm đến", dest_input, maps_api, "coord_dest"):
                    st.stop()
                resolved = st.session_state.get("resolved_coord_dest")
                if not resolved: st.stop()
                dest_cands = [resolved]

                                                       
            st.session_state["pending_origin_cands"] = origin_cands
            st.session_state["pending_dest_cands"]   = dest_cands
                                                                  
                                                                                                             
            st.session_state["pending_route_options"] = {
                "mode": mode,
                "poi_style": poi_style,
                "departure_dt_iso": departure_dt.isoformat(),
                "show_alt": bool(show_alt),
                "use_human": bool(use_human),
                "age": int(age),
                "travel_hour": int(travel_hour),
                "motion_sick": bool(motion_sick),
                "has_children": bool(has_children),
                "stress_level": int(stress_level),
                "eta_custom_speed_enabled": bool(st.session_state.get("eta_custom_speed_enabled", False)),
                "eta_custom_speed_kmh": float(st.session_state.get("eta_custom_speed_kmh") or _default_eta_speed),
            }
                                                                                                    
            st.session_state.pop("last_routes", None)
            st.session_state.pop("active_route_state", None)
            st.session_state.pop("route_state_snapshot", None)
            st.session_state.pop("__last_good_route_snapshot", None)
            st.session_state.pop("__route_keepalive_ok", None)
            _clear_route_snapshot_from_browser_session()
            st.session_state["__route_search_in_progress"] = True
            _clear_route_view_cache()
                                                                                               
            for _k in [
                "__last_good_trip_route_state", "__route_tab_return_rerun",
                "__route_restored_from_tab_backup", "__sos_contact_submit_rerun",
            ]:
                st.session_state.pop(_k, None)

                                                                                  
        _o_cands = st.session_state.get("pending_origin_cands")
        _d_cands = st.session_state.get("pending_dest_cands")

        confirm_pressed = False
        if _o_cands and _d_cands and not st.session_state.get("last_routes"):
                                                                              
                                                                            
            origin_mismatch = any(_candidate_needs_manual_confirm(c) for c in _o_cands)
            dest_mismatch   = any(_candidate_needs_manual_confirm(c) for c in _d_cands)
            needs_confirm = (len(_o_cands) > 1) or (len(_d_cands) > 1) or origin_mismatch or dest_mismatch

            _show_address_match_warnings("Điểm xuất phát", _o_cands)
            if len(_o_cands) > 1 or origin_mismatch:
                title = "**📍 Điểm xuất phát** — Chọn đúng kết quả:" if origin_mismatch else "**📍 Điểm xuất phát** — Tìm thấy nhiều nơi trùng tên:"
                st.markdown(title)
                o_opts = [_candidate_label(c) for c in _o_cands]
                _oi = st.selectbox("Chọn điểm xuất phát", range(len(o_opts)),
                                   format_func=lambda i: o_opts[i], key="sel_origin")
            else:
                _oi = 0

            _show_address_match_warnings("Điểm đến", _d_cands)
            if len(_d_cands) > 1 or dest_mismatch:
                title = "**🏁 Điểm đến** — Chọn đúng kết quả:" if dest_mismatch else "**🏁 Điểm đến** — Tìm thấy nhiều nơi trùng tên:"
                st.markdown(title)
                d_opts = [_candidate_label(c) for c in _d_cands]
                _di = st.selectbox("Chọn điểm đến", range(len(d_opts)),
                                   format_func=lambda i: d_opts[i], key="sel_dest")
            else:
                _di = 0

            if needs_confirm:
                confirm_pressed = st.button("✅ Xác nhận và tìm đường", type="primary")
                if not confirm_pressed:
                    if origin_mismatch or dest_mismatch:
                        st.info("👆 API không tìm thấy đúng số nhà. Hãy chọn thủ công kết quả gần nhất, hoặc nhập tọa độ chính xác rồi bấm lại.")
                    else:
                        st.info("👆 Chọn đúng địa điểm rồi bấm **Xác nhận và tìm đường**.")
                    st.stop()
            else:
                confirm_pressed = True                                         

                                                                                   
        if st.session_state.get("last_routes"):
            lat1, lon1 = st.session_state["last_origin"]
            lat2, lon2 = st.session_state["last_dest"]
            mode       = st.session_state.get("last_mode", mode)
            routes     = st.session_state.get("last_routes", [])

        elif confirm_pressed and _o_cands and _d_cands:
            _oi = st.session_state.get("sel_origin", 0)
            _di = st.session_state.get("sel_dest",   0)
            lat1 = _o_cands[_oi]["lat"];  lon1 = _o_cands[_oi]["lon"]
            lat2 = _d_cands[_di]["lat"];  lon2 = _d_cands[_di]["lon"]

            _opts = st.session_state.get("pending_route_options") or {}
            mode = _opts.get("mode", mode)
            poi_style = _opts.get("poi_style", poi_style)
            departure_dt = _parse_session_datetime(_opts.get("departure_dt_iso"), departure_dt)
            show_alt = bool(_opts.get("show_alt", show_alt))
            use_human = bool(_opts.get("use_human", use_human))
            age = int(_opts.get("age", age))
            travel_hour = int(_opts.get("travel_hour", travel_hour))
            motion_sick = bool(_opts.get("motion_sick", motion_sick))
            has_children = bool(_opts.get("has_children", has_children))
            stress_level = int(_opts.get("stress_level", stress_level))
                                                                                   
                                                                                                    
            st.session_state["_route_eta_speed_override_active"] = True
            st.session_state["_route_eta_custom_speed_enabled"] = bool(_opts.get("eta_custom_speed_enabled", st.session_state.get("eta_custom_speed_enabled", False)))
            st.session_state["_route_eta_custom_speed_kmh"] = float(_opts.get("eta_custom_speed_kmh", st.session_state.get("eta_custom_speed_kmh") or _default_avg_speed_kmh_by_mode(mode)))

            if not lat1 or not lat2:
                st.error("❌ Không lấy được tọa độ. Thử `10.77,106.69`"); st.stop()

                                    
                                                                                                
                                                                                        
                                                                                       
            if normalize_mode(mode) == "motorbike":
                with st.spinner("🏍️ Tính tuyến hợp lệ cho xe máy..."):
                    try:
                        fb_valid, fb_rejected, fb_attempts = find_legal_routes_with_fallback(
                            router,
                            (lat1, lon1),
                            (lat2, lon2),
                            mode=mode,
                            count=3,
                            prefer_alternatives=True,
                        )
                    except TypeError:
                                                                                                       
                        fb_valid, fb_rejected, fb_attempts = find_legal_routes_with_fallback(
                            router,
                            (lat1, lon1),
                            (lat2, lon2),
                            mode=mode,
                            count=3,
                        )

                routes = list(fb_valid or [])
                rejected_routes = list(fb_rejected or [])

                if routes:
                    st.success("✅ Đã tìm được tuyến phù hợp cho xe máy.")
                else:
                    st.error("❌ Chưa tìm được tuyến hợp lệ cho xe máy.")
                    with st.expander("Các lần app đã thử tìm tuyến khác", expanded=True):
                        for _a in fb_attempts or []:
                            st.write("- " + str(_a))
                    with st.expander("Chi tiết tuyến bị loại", expanded=False):
                        for idx, rr in enumerate(rejected_routes or [], 1):
                            st.write(f"Tuyến {idx}: " + "; ".join(rr.get("legal_issues") or []))
                    st.stop()

            else:
                with st.spinner("🛣️ Tính tuyến (OSRM)..."):
                    if show_alt:
                        routes = router.get_alternative_routes((lat1, lon1), (lat2, lon2), mode=mode, count=3)
                    else:
                        r = router.get_route((lat1, lon1), (lat2, lon2), mode=mode)
                        routes = [r] if r else []

                if not routes:
                    st.error("❌ Không tìm được tuyến.")
                    st.stop()

                                                                            
                valid_routes, rejected_routes = filter_routes_for_mode(routes, mode)
                if rejected_routes:
                    _first_issue = (rejected_routes[0].get("legal_issues") or ["Tuyến không phù hợp với phương tiện đã chọn."])[0]
                    st.warning(f"⚖️ Đã loại {len(rejected_routes)} tuyến không hợp lệ với phương tiện: {_first_issue}")

                routes = valid_routes
                if not routes:
                    st.error("❌ Chưa tìm được tuyến hợp lệ với phương tiện đã chọn.")
                    with st.expander("Chi tiết tuyến bị loại", expanded=False):
                        for idx, rr in enumerate(rejected_routes, 1):
                            st.write(f"Tuyến {idx}: " + "; ".join(rr.get("legal_issues") or []))
                    st.stop()

                                                             
                                                                          
                                                                     
            _apply_avg_speed_timing_to_routes(routes, mode)

            labels = ["🚀 Nhanh nhất","⛽ Tiết kiệm","🌿 Cảnh đẹp"]
            for i, rt in enumerate(routes):
                if "label" not in rt:
                    rt["label"] = labels[i] if i < len(labels) else f"Tuyến {i+1}"

            _save_route_runtime_options(mode, poi_style, departure_dt, use_human, age, travel_hour, motion_sick, has_children, stress_level)
            st.session_state.update({
                "last_origin": (lat1,lon1), "last_dest": (lat2,lon2),
                "last_mode": mode, "last_routes": routes,
            })
                                                                                                                        
            _clear_pending_route_search_state()
            st.session_state.pop("__route_search_in_progress", None)
            _backup_trip_route_state("route_computed")
            _persist_current_route_snapshot()

    if st.session_state.get("last_routes"):
        lat1, lon1 = st.session_state["last_origin"]
        lat2, lon2 = st.session_state["last_dest"]
        mode       = st.session_state.get("last_mode", mode)
        routes     = st.session_state.get("last_routes", [])
        poi_style, departure_dt, use_human, age, travel_hour, motion_sick, has_children, stress_level = _restore_route_runtime_options(
            poi_style, departure_dt, use_human, age, travel_hour, motion_sick, has_children, stress_level
        )
                                                         
                                                                                      
                                                                 
        _forecast_now_dt = datetime.now().replace(second=0, microsecond=0)
        _forecast_reference_dt = _effective_sliding_departure_dt(
            departure_dt,
            now_dt=_forecast_now_dt,
            nav_active=bool(st.session_state.get("nav_active") and not st.session_state.get("nav_arrived")),
        )
        _forecast_refresh_bucket = int(st.session_state.get("__tripsmart_5min_bucket", int(_forecast_reference_dt.timestamp() // 300)))
        st.session_state["last_effective_departure_dt_iso"] = _forecast_reference_dt.isoformat()
                                                                                    
        use_human = False
        _apply_avg_speed_timing_to_routes(routes, mode)
        _persist_current_route_snapshot()

        selected = st.session_state.get("last_selected", 0)

                                                                            
        if len(routes) > 1:
            with st.spinner("📊 Đang so sánh các tuyến đường..."):
                compared = risk_engine.compare_routes(routes)
                st.session_state["last_compared"] = compared

            fastest  = next((r for r in compared if r.get("tag") == "fastest"),  None)
            safest   = next((r for r in compared if r.get("tag") == "safest"),   None)
            balanced = next((r for r in compared if r.get("tag") == "balanced"), None)

                                                                           
            hint_cols = st.columns(3)
            for col, item, css_cls in zip(
                hint_cols,
                [fastest, safest, balanced],
                ["tag-fastest", "tag-safest", "tag-balanced"],
            ):
                if not item:
                    continue
                dur_h = int(item["duration_min"] // 60)
                dur_m = int(item["duration_min"] % 60)
                dur_txt = item.get("duration_text") or (f"{dur_h}h {dur_m}p" if dur_h else f"{dur_m} phút")
                risk_pct = f"{item['avg_risk_score']:.0%}"
                risk_cls = ("risk-low" if item["avg_risk_score"] < YELLOW_RISK_THRESHOLD
                            else "risk-mid" if item["avg_risk_score"] < RED_RISK_THRESHOLD else "risk-high")
                col.markdown(
                    f'<div style="border-radius:12px;padding:14px 16px;'
                    f'background:#fafafa;border:1.5px solid #ddd;margin-bottom:4px">'
                    f'<div class="{css_cls}" style="display:inline-block;margin-bottom:8px">'
                    f'{item["tag_label"]}</div><br>'
                    f'<b>{item["label"]}</b><br>'
                    f'📏 {item.get("distance_text","?")} &nbsp;·&nbsp; ⏱️ {dur_txt}<br>'
                    f'<span class="{risk_cls}">Rủi ro TB: {risk_pct}</span>'
                    f' &nbsp;·&nbsp; {item["danger_count"]} vùng nguy hiểm'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                                                                           
            st.markdown("#### 📊 Bảng so sánh chi tiết tuyến đường")
            TAG_CSS = {"fastest":"tag-fastest","safest":"tag-safest",
                       "balanced":"tag-balanced","other":"tag-other"}
            rows_html = ""
            for r in compared:
                tag_css  = TAG_CSS.get(r.get("tag","other"), "tag-other")
                risk_s   = r["avg_risk_score"]
                risk_cls = ("risk-low" if risk_s < YELLOW_RISK_THRESHOLD
                            else "risk-mid" if risk_s < RED_RISK_THRESHOLD else "risk-high")
                risk_icon = _risk_level_icon(risk_s)
                dur_h = int(r["duration_min"] // 60)
                dur_m = int(r["duration_min"] % 60)
                dur_txt  = r.get("duration_text") or (f"{dur_h}h {dur_m}p" if dur_h else f"{dur_m} phút")
                dist_txt = r.get("distance_text") or f"{r['distance_km']:.0f} km"
                row_cls  = "compare-winner" if r.get("tag") in ("fastest","safest","balanced") else ""
                rows_html += (
                    f'<tr class="{row_cls}">'
                    f'<td style="text-align:left;font-weight:600">{r["label"]}</td>'
                    f'<td>{dist_txt}</td>'
                    f'<td>⏱️ {dur_txt}</td>'
                    f'<td><span class="{risk_cls}">{risk_icon} {risk_s:.0%}</span></td>'
                    f'<td>{r["danger_count"]} vùng</td>'
                    f'<td><span class="{risk_cls}">{r["ai_label"]}</span></td>'
                    f'<td><span class="{tag_css}">{r["tag_label"]}</span></td>'
                    f'</tr>'
                )
            st.markdown(
                f'<table class="compare-table"><thead><tr>'
                f'<th style="text-align:left">Tuyến</th>'
                f'<th>Khoảng cách</th><th>Thời gian</th>'
                f'<th>Rủi ro TB</th><th>Vùng nguy hiểm</th>'
                f'<th>AI đánh giá</th><th>Gợi ý</th>'
                f'</tr></thead><tbody>{rows_html}</tbody></table>',
                unsafe_allow_html=True,
            )
            st.caption("💡 Chọn tuyến phù hợp với nhu cầu bên dưới.")
            st.divider()

                                                                           
            if "last_selected" not in st.session_state:
                _bal = next((r["route_index"] for r in compared if r.get("tag") == "balanced"), None)
                _saf = next((r["route_index"] for r in compared if r.get("tag") == "safest"),   None)
                selected = _bal if _bal is not None else (_saf or 0)

            def _fmt_route(i):
                if "last_compared" in st.session_state:
                    m = next((r for r in st.session_state["last_compared"]
                              if r["route_index"] == i), None)
                    if m:
                        return f"{m['tag_label']}  {routes[i]['label']}  ·  {routes[i].get('duration_text','?')}"
                return routes[i]["label"]

            selected = st.selectbox(
                "🗺️ Chọn tuyến để xem chi tiết",
                range(len(routes)),
                index=min(selected, len(routes) - 1),
                format_func=_fmt_route,
                key="route_selector",
            )
        else:
            selected = 0

        st.session_state["last_selected"] = selected

        route       = routes[selected]
        is_fallback = route.get("fallback", False)
        polyline    = route.get("polyline", [])

        profile = None
        if use_human:
            profile = human_router.build_profile(
                age, travel_hour, motion_sick, stress_level, has_children)
            route = human_router.adjust_route_score(route, profile)

                                                                                     
        _view_cache_key = _route_cache_key(polyline, route, mode, poi_style, departure_dt, selected)
                                                                                           
                                                                                                 
        if _view_cache_key:
                                                                                          
                                                                           
                                                                                            
            _view_cache_key = f"{_view_cache_key}|stable_analysis"
        _view_cache = st.session_state.get("route_view_cache") or {}
        _cached_view = _view_cache.get(_view_cache_key) if _view_cache_key else None

                                                                 
                                                                                           
                                                                                         
                                                                              
        if (
            not _cached_view
            and (
                st.session_state.get("__sos_contact_submit_rerun")
                or st.session_state.get("__route_tab_return_rerun")
                or st.session_state.get("__route_restored_from_tab_backup")
            )
        ):
            _last_cache_key = st.session_state.get("route_view_cache_key")
            if _last_cache_key and isinstance(_view_cache, dict):
                _cached_view = _view_cache.get(_last_cache_key)
                if _cached_view and _view_cache_key:
                    _view_cache[_view_cache_key] = _cached_view
                    st.session_state["route_view_cache"] = _view_cache
                    st.session_state["route_view_cache_key"] = _view_cache_key

        if _cached_view:
            colored_segs = _cached_view.get("colored_segs", [])
            analysis = _cached_view.get("analysis", {})
            danger_markers_raw = _cached_view.get("danger_markers_raw", [])
            danger_markers = _cached_view.get("danger_markers", [])
            rest_stops = _cached_view.get("rest_stops", [])
            route_risk_forecast = _cached_view.get("route_risk_forecast")
            warn_msg = _cached_view.get("warn_msg")

                                                                                                      
            try:
                _cached_forecast_bucket = int(_cached_view.get("forecast_bucket", -1) or -1)
            except Exception:
                _cached_forecast_bucket = -1

            if _cached_forecast_bucket != int(_forecast_refresh_bucket):
                try:
                    ml_model_route = init_ml_model()
                    if ml_model_route is not None and ml_model_route.is_ready:
                        _new_forecast, _tds, _new_warn = _compute_route_forecast(
                            polyline, route, _forecast_reference_dt, risk_engine, ml_model_route, weather_api,
                        )
                        route_risk_forecast = _new_forecast
                        warn_msg = _new_warn
                        _cached_view["route_risk_forecast"] = route_risk_forecast
                        _cached_view["warn_msg"] = warn_msg
                        _cached_view["forecast_bucket"] = int(_forecast_refresh_bucket)
                        if _view_cache_key:
                            _view_cache[_view_cache_key] = _cached_view
                            st.session_state["route_view_cache"] = _view_cache
                except Exception as e:
                                                                               
                                                                         
                    st.session_state["silent_eta_update_error"] = str(e)

            if warn_msg:
                st.caption(warn_msg)
                                                                            
        else:
            with st.spinner("🎨 Tô màu rủi ro từng đoạn..."):
                colored_segs = risk_engine.score_polyline_segments(polyline)

            with st.spinner("🔍 Phân tích nguy hiểm..."):
                                                                            
                _cmp_cache = st.session_state.get("last_compared")
                _cmp_match = next((r for r in _cmp_cache
                                   if r.get("route_index") == selected), None) if _cmp_cache else None
                if _cmp_match and "danger_segments" in _cmp_match:
                    analysis = {
                        "danger_segments" : _cmp_match["danger_segments"],
                        "rest_suggestions": risk_engine._suggest_rest_stops(polyline),
                        "avg_score"       : _cmp_match["avg_risk_score"],
                        "safe_to_proceed" : _cmp_match["avg_risk_score"] < 0.50,
                        "summary"         : _cmp_match.get("analysis_summary", ""),
                    }
                else:
                    analysis = risk_engine.analyze_route(polyline)
                danger_markers_raw = analysis.get("danger_segments",  [])
                danger_markers     = _cluster_danger_markers(
                    danger_markers_raw,
                    max_gap_km=2.0,
                    min_score=0.45,
                    max_items=8,
                )
                rest_stops         = analysis.get("rest_suggestions", [])

            with st.spinner("🤖 Dự báo rủi ro theo thời gian di chuyển..."):
                ml_model_route = init_ml_model()
                route_risk_forecast = None
                warn_msg = None
                if ml_model_route is not None and ml_model_route.is_ready:
                    try:
                        route_risk_forecast, _tds, warn_msg = _compute_route_forecast(
                            polyline, route, _forecast_reference_dt, risk_engine, ml_model_route, weather_api,
                        )
                        if warn_msg:
                            st.warning(warn_msg)
                    except Exception as e:
                        st.warning(f"⚠️ Không thể dự báo rủi ro theo thời gian: {e}")
                        route_risk_forecast = None
                else:
                    st.caption("ℹ️ AI Risk Model chưa sẵn sàng — bỏ qua dự báo rủi ro theo thời gian.")

            with st.spinner("📍 Tìm địa điểm dọc đường..."):
                pois = poi_engine.get_pois_on_route(polyline, style=poi_style, buffer_km=8.0, max_results=12)

                                                                                           
                                                                              
                                                                                
                                                                  
            fuel_stations = _get_fuel_stations_nonblocking(
                poi_engine,
                polyline,
                corridor_m=3000,
                max_results=160,
                wait_sec=12.0,
            )

            with st.spinner("🚦 Lấy giới hạn tốc độ từ Goong/OSM..."):
                                                                                                    
                                                                                 
                speed_segments = _get_route_speed_segments(
                    polyline,
                    mode=mode,
                    corridor_m=120,
                    sample_every_km=1.5,
                    max_results=120,
                )

            if _view_cache_key:
                _existing_route_view_cache = st.session_state.get("route_view_cache") or {}
                if not isinstance(_existing_route_view_cache, dict):
                    _existing_route_view_cache = {}
                _existing_route_view_cache[_view_cache_key] = {
                    "colored_segs": colored_segs,
                    "analysis": analysis,
                    "danger_markers_raw": danger_markers_raw,
                    "danger_markers": danger_markers,
                    "rest_stops": rest_stops,
                    "route_risk_forecast": route_risk_forecast,
                    "forecast_bucket": int(_forecast_refresh_bucket),
                    "warn_msg": warn_msg,
                    "pois": pois,
                    "fuel_stations": fuel_stations,
                    "speed_segments": speed_segments,
                }
                                                                                     
                try:
                    if len(_existing_route_view_cache) > 4:
                        for _old_key in list(_existing_route_view_cache.keys())[:-4]:
                            _existing_route_view_cache.pop(_old_key, None)
                except Exception:
                    pass
                st.session_state["route_view_cache"] = _existing_route_view_cache
                st.session_state["route_view_cache_key"] = _view_cache_key
                _backup_trip_route_state("route_analysis_cached")

        if _cached_view:
            pois = _cached_view.get("pois", [])
            fuel_stations = _cached_view.get("fuel_stations", [])
            if fuel_stations:
                st.session_state["last_route_fuel_stations_all"] = fuel_stations
            speed_segments = _cached_view.get("speed_segments", [])
        else:
            fuel_stations = locals().get("fuel_stations", [])
            speed_segments = locals().get("speed_segments", [])

                                                                                       
        st.session_state.pop("__sos_contact_submit_rerun", None)
        st.session_state.pop("__route_tab_return_rerun", None)
        st.session_state.pop("__route_restored_from_tab_backup", None)
        try:
            _backup_trip_route_state("route_display_ready")
        except Exception:
            pass

                                                                               
                                                                                                
        if not fuel_stations and polyline:
            fuel_stations = _get_fuel_stations_nonblocking(
                poi_engine,
                polyline,
                corridor_m=3000,
                max_results=160,
                wait_sec=8.0,
            )
            st.session_state["fuel_along_route_count"] = len(fuel_stations or [])
            if fuel_stations and _view_cache_key and st.session_state.get("route_view_cache"):
                try:
                    st.session_state["route_view_cache"][_view_cache_key]["fuel_stations"] = fuel_stations
                except Exception:
                    pass

                                                                                                                         
        if not speed_segments and polyline:
            speed_segments = _get_route_speed_segments(
                polyline,
                mode=mode,
                corridor_m=120,
                sample_every_km=1.5,
                max_results=120,
            )
            if speed_segments and _view_cache_key and st.session_state.get("route_view_cache"):
                try:
                    st.session_state["route_view_cache"][_view_cache_key]["speed_segments"] = speed_segments
                except Exception:
                    pass

                                                                          
                                                                
        _current_fuel_route_key = _fuel_route_cache_key(polyline, corridor_m=3000, max_results=160)
        if st.session_state.get("last_route_fuel_key") not in (None, _current_fuel_route_key):
            st.session_state.pop("last_route_fuel_stations_all", None)
            st.session_state.pop("next_fuel_stations", None)
            fuel_stations = []

                         
                                                              
                                                                                                  
                                                                   
        fuel_stations, __fuel_is_fallback = _ts_ensure_visible_fuel_markers(
            fuel_stations,
            polyline,
            max_results=24,
        )

                                               
                                                                          
                                                                           
        _current_gps_for_fuel = None
        if st.session_state.get("nav_gps_lat") is not None and st.session_state.get("nav_gps_lon") is not None:
            _current_gps_for_fuel = (float(st.session_state.get("nav_gps_lat")), float(st.session_state.get("nav_gps_lon")))

        next_fuel_stations = _ts_next_fuel_after_gps_progress(
            fuel_stations,
            polyline,
            current_position=_current_gps_for_fuel,
            max_results=2,
            passed_margin_km=0.30,
        )
        if not next_fuel_stations:
            next_fuel_stations = (fuel_stations or [])[:2]
            st.session_state["next_fuel_stations"] = next_fuel_stations

        st.session_state["fuel_visible_count"] = len(fuel_stations or [])
        st.session_state["fuel_visible_fallback"] = bool(__fuel_is_fallback)

        rpts = crowd.get_nearby_reports(lat1, lon1, 60)

                                              
        st.session_state["last_danger_markers"] = danger_markers
        st.session_state["last_rest_stops"] = rest_stops
        st.session_state["last_route_risk_forecast"] = route_risk_forecast
        st.session_state["last_route_km"] = route.get("distance_km", 0)
        st.session_state["last_polyline"]  = polyline
                                                                                     
        _persist_current_route_snapshot()
                                                
        if st.session_state.get("_prev_selected") != selected:
            st.session_state["iot_step"] = 0
            st.session_state["_prev_selected"] = selected

                                                                                     
                                                                                 
                                                                                           
        try:
            _fc_for_quick_copilot = st.session_state.get("auto_eta_forecast") or route_risk_forecast or {}
            _route_for_quick = dict(route or {})
            if st.session_state.get("nav_active") and st.session_state.get("nav_polyline"):
                _route_for_quick["polyline"] = st.session_state.get("nav_polyline")
                _route_for_quick["distance_km"] = (
                    st.session_state.get("nav_distance_left_osrm")
                    or st.session_state.get("auto_eta_distance_km")
                    or _get_route_distance_km(route)
                )
                _apply_avg_speed_timing(_route_for_quick, st.session_state.get("nav_mode", mode))
            _quick_copilot = _build_mobility_copilot_state(
                forecast=_fc_for_quick_copilot,
                route=_route_for_quick,
                danger_markers=danger_markers,
                rest_stops=rest_stops,
                mode=st.session_state.get("nav_mode", mode),
                nav_active=bool(st.session_state.get("nav_active") and not st.session_state.get("nav_arrived")),
            )
        except Exception:
            _quick_copilot = {
                "safety_score": 0,
                "safety_label": "Chưa xác định",
                "recommendation": "Theo dõi tuyến đường và thời tiết trước khi di chuyển.",
                "has_red_decision": False,
                "critical_segment": None,
            }

        _has_red_decision = bool(_quick_copilot.get("has_red_decision") or _quick_copilot.get("critical_segment"))
        _safe_score = int(_quick_copilot.get("safety_score") or 0)
        _rec_text = _quick_copilot.get("recommendation") or "Có thể tiếp tục, hãy theo dõi tuyến đường."
        _status_icon = "🔴" if _has_red_decision else "✅"
        _status_title = "Có điểm đỏ cần xử lý" if _has_red_decision else "Tuyến đã sẵn sàng"
        _status_border = "#ef4444" if _has_red_decision else "#22c55e"
        _origin_label = str(st.session_state.get("input_origin") or globals().get("origin_input", "") or f"{lat1:.4f},{lon1:.4f}")
        _dest_label = str(globals().get("dest_input", "") or f"{lat2:.4f},{lon2:.4f}")
        if len(_origin_label) > 36:
            _origin_label = _origin_label[:33] + "..."
        if len(_dest_label) > 36:
            _dest_label = _dest_label[:33] + "..."

        st.markdown(f"""
        <div style="border:1px solid #e8ecf3;border-left:7px solid {_status_border};
                    border-radius:18px;padding:18px 22px;margin:18px 0 12px 0;
                    background:linear-gradient(135deg,#ffffff 0%,#f8fbff 100%);
                    box-shadow:0 8px 24px rgba(15,23,42,.06);">
          <div style="display:flex;justify-content:space-between;gap:18px;align-items:flex-start;flex-wrap:wrap;">
            <div style="min-width:260px;flex:1;">
              <div style="font-size:1.15rem;font-weight:800;color:#1f2937;margin-bottom:6px;">
                {_status_icon} {_status_title}
              </div>
              <div style="font-size:1rem;color:#374151;font-weight:650;margin-bottom:8px;">
                {_origin_label} <span style="color:#9ca3af">→</span> {_dest_label}
              </div>
              <div style="color:#6b7280;font-size:.94rem;line-height:1.5;">
                🧠 <b>Khuyến nghị:</b> {_rec_text}
              </div>
            </div>
            <div style="display:flex;gap:12px;flex-wrap:wrap;justify-content:flex-end;">
              <div style="background:#f1f5f9;border-radius:14px;padding:12px 16px;min-width:125px;text-align:center;">
                <div style="font-size:.78rem;color:#64748b;font-weight:700;">Khoảng cách</div>
                <div style="font-size:1.28rem;font-weight:800;color:#0f172a;">{route.get('distance_text','?')}</div>
              </div>
              <div style="background:#f1f5f9;border-radius:14px;padding:12px 16px;min-width:125px;text-align:center;">
                <div style="font-size:.78rem;color:#64748b;font-weight:700;">Thời gian</div>
                <div style="font-size:1.28rem;font-weight:800;color:#0f172a;">{route.get('duration_text','?')}</div>
              </div>
              <div style="background:#f1f5f9;border-radius:14px;padding:12px 16px;min-width:125px;text-align:center;">
                <div style="font-size:.78rem;color:#64748b;font-weight:700;">An toàn</div>
                <div style="font-size:1.28rem;font-weight:800;color:#0f172a;">{_safe_score}/100</div>
              </div>
              <div style="background:#f1f5f9;border-radius:14px;padding:12px 16px;min-width:125px;text-align:center;">
                <div style="font-size:.78rem;color:#64748b;font-weight:700;">Cần chú ý</div>
                <div style="font-size:1.28rem;font-weight:800;color:#0f172a;">{len(danger_markers)}</div>
              </div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        if is_fallback:
            st.warning(f"⚠️ {route.get('note','')}  \nKiểm tra kết nối internet.")

                                                                                               
        with st.expander("📊 Xem đầy đủ thông tin tuyến, AI và chú giải", expanded=False):
            m1,m2,m3,m4,m5 = st.columns(5)
            m1.metric("📏 Khoảng cách",       route.get("distance_text","?"))
            m2.metric("⏱️ Thời gian",         route.get("duration_text","?"), help=f"Tính theo tốc độ TB {_format_speed_label(mode)}")
            m3.metric("🚨 Vùng trọng yếu",    len(danger_markers),
                      delta=f"lọc từ {len(danger_markers_raw)} điểm" if len(danger_markers_raw) != len(danger_markers) else None)
            m4.metric("☕ Điểm dừng nghỉ",    len(rest_stops))
            m5.metric("📍 Địa điểm",          len(pois))
            st.caption(f"⏱️ ETA đang tính theo tốc độ trung bình: {_format_speed_label(mode)} ({'ô tô' if mode == 'car' else 'xe máy'}).")

            if not is_fallback:
                st.info(f"✅ Tuyến thực tế từ **OSRM** · {len(polyline)} điểm GPS")

            if profile:
                st.markdown(f'<div class="alert-info">🧠 <b>{profile["summary"]}</b></div>', unsafe_allow_html=True)
                for a in profile.get("alerts",[]):
                    st.markdown(f'<div class="alert-warning">{a}</div>', unsafe_allow_html=True)

            st.markdown(f'<div class="summary-bar">🛡️ <b>Tóm tắt:</b> &nbsp;{analysis.get("summary","")}</div>',
                        unsafe_allow_html=True)

            if route_risk_forecast:
                _render_route_forecast(route_risk_forecast, _forecast_reference_dt, title="Dự báo rủi ro theo hành trình (ETA tự trượt)")

            st.markdown("""
            <div class="legend-grad">
              <span>🔵 An toàn</span><div class="grad-bar"></div><span>🔴 Nguy hiểm</span>
              &nbsp;|&nbsp; 🟢 Điểm nghỉ &nbsp;|&nbsp; 📍 POI &nbsp;|&nbsp; ⚠️ Cộng đồng
              &nbsp;|&nbsp; 🟡🟠🔴⚪ Dự báo rủi ro theo giờ đi qua
            </div>""", unsafe_allow_html=True)

                                                                                      
        if _has_red_decision:
            _quick_crit = _quick_copilot.get("critical_segment") or {}
            st.markdown(
                f'<div class="alert-danger">'
                f'🔴 <b>Điểm rất nguy hiểm phía trước:</b> '
                f'{_quick_crit.get("label", "Đoạn rủi ro cao")} · ETA {_quick_crit.get("eta_text", "?")} · '
                f'điểm {_quick_crit.get("score", 0):.0%}. '
                f'Mở <b>🧠 Trợ lý an toàn</b> bên dưới bản đồ để chọn đổi tuyến / nghỉ / vẫn đi tiếp.'
                f'</div>',
                unsafe_allow_html=True,
            )

                                                                               
                                                                     
                                                                                         
        if True:
            _col_nav1, _col_nav2 = st.columns([3, 1])
            with _col_nav1:
                if not st.session_state.get("nav_active"):
                    if st.button(
                        "▶️ Bắt đầu dẫn đường theo GPS",
                        type="primary",
                        use_container_width=True,
                        key="btn_start_live_nav",
                    ):
                        if not _ts_sos_has_family_contact():
                            st.warning("⚠️ Vui lòng nhập ít nhất 1 số điện thoại người thân trong sidebar trước khi bắt đầu dẫn đường GPS để dùng SOS nhanh khi có sự cố.")
                            st.stop()
                        st.session_state["nav_active"]        = True
                        st.session_state["nav_polyline"]      = polyline
                        st.session_state["nav_risk_segs"]     = []
                        st.session_state["nav_dest"]          = (lat2, lon2)
                        st.session_state["nav_dest_name"]     = st.session_state.get("last_dest_name", f"{lat2:.4f},{lon2:.4f}")
                        st.session_state["nav_origin"]        = (lat1, lon1)
                        st.session_state["nav_mode"]          = mode
                        st.session_state["nav_progress_idx"]  = 0
                        st.session_state["nav_max_progress"]  = 0
                        st.session_state["nav_offroute"]      = False
                        st.session_state["nav_reroute_pl"]    = None
                        st.session_state["nav_reroute_risk"]  = None
                        st.session_state["nav_last_reroute"]  = 0.0
                                                                
                                                                                     
                                                                                           
                        st.session_state["nav_gps_lat"]       = None
                        st.session_state["nav_gps_lon"]       = None
                        st.session_state["nav_gps_ts"]        = 0.0
                        st.session_state["nav_gps_source"]    = "waiting_browser_gps"
                        st.session_state["nav_arrived"]       = False
                        st.session_state["nav_steps"]         = route.get("steps", [])
                        st.session_state["nav_distance_left"] = route.get("distance_km", 0)
                        st.session_state["nav_distance_left_osrm"] = route.get("distance_km", 0)
                        st.session_state["nav_step_text"]     = ""
                        import time as _nav_start_time
                                                                                                            
                                                                                                 
                        st.session_state["auto_eta_last_ts"] = _nav_start_time.time()
                        st.session_state["auto_eta_status"] = ""
                        st.session_state["nav_skip_heavy_until"] = _nav_start_time.time() + 20
                        for _eta_k in [
                            "auto_eta_distance_km", "auto_eta_duration_text",
                            "auto_eta_arrival", "auto_eta_updated_at", "auto_eta_forecast",
                            "auto_eta_ai_ready", "auto_eta_ai_status",
                        ]:
                            st.session_state.pop(_eta_k, None)
                        st.rerun()
                else:
                    if st.button(
                        "⏹️ Dừng dẫn đường",
                        type="secondary",
                        use_container_width=True,
                        key="btn_stop_live_nav",
                    ):
                        for _k in list(st.session_state.keys()):
                            if _k.startswith("nav_"):
                                del st.session_state[_k]
                        st.rerun()
            with _col_nav2:
                st.caption("🛣️ Dẫn đường thời gian thực với GPS thật")

                                                                                  
        _maybe_schedule_nav_rerun()

        if st.session_state.get("nav_active") and not st.session_state.get("nav_arrived"):
            import time as _nav_time_mod
            _sync_nav_gps_from_browser(_nav_time_mod.time())

                                                                               
                                                                               
                                                                        
                                                                                   
        gps_position = None
        if st.session_state.get("nav_active") and not st.session_state.get("nav_arrived"):
            ss = st.session_state

                                                                                                
                                                                                      
            g_lat = ss.get("nav_gps_lat")
            g_lon = ss.get("nav_gps_lon")

            if g_lat is not None and g_lon is not None:
                nav_polyline = ss.get("nav_polyline") or polyline
                dest_lat, dest_lon = ss.get("nav_dest", (lat2, lon2))

                             
                if _hav(g_lat, g_lon, dest_lat, dest_lon) < 0.05:
                    ss["nav_arrived"] = True
                    st.success("🎉 Bạn đã đến điểm đến!")

                                                     
                if _LIVE_NAV_OK and nav_polyline:
                    snap = _snap_to_route(g_lat, g_lon, nav_polyline)
                else:
                    snap = _find_nearest_segment(g_lat, g_lon, nav_polyline) if nav_polyline else {"segment_idx": 0, "dist_km": 0}
                    snap["idx"] = snap.get("idx", snap.get("segment_idx", 0))
                snap_idx = snap["idx"]
                off_dist = snap["dist_km"]

                if snap_idx >= ss.get("nav_max_progress", 0) - 2:
                    ss["nav_max_progress"] = max(ss.get("nav_max_progress", 0), snap_idx)
                    ss["nav_progress_idx"] = snap_idx
                else:
                    ss["nav_progress_idx"] = snap_idx

                                                       
                is_offroute = ss.get("nav_offroute", False)
                if off_dist > 0.025 and not is_offroute:
                    ss["nav_offroute"] = True
                    is_offroute = True
                if off_dist <= 0.05 and is_offroute:
                    ss["nav_offroute"]     = False
                    ss["nav_reroute_pl"]   = None
                    ss["nav_reroute_risk"] = None
                    is_offroute = False

                import time as _time
                now = _time.time()
                need_reroute = (
                    is_offroute
                    and ss.get("nav_reroute_pl") is None
                    and (now - ss.get("nav_last_reroute", 0.0)) > 15
                )
                if need_reroute:
                                                                                            
                    new_pl, new_risk, new_steps, _summary = _do_reroute(
                        router, risk_engine, g_lat, g_lon, dest_lat, dest_lon,
                        ss.get("nav_mode", mode),
                    )
                    if new_pl:
                        ss["nav_polyline"]     = new_pl
                        ss["nav_risk_segs"]    = new_risk
                        ss["nav_steps"]        = new_steps
                        ss["nav_progress_idx"] = 0
                        ss["nav_max_progress"] = 0
                        ss["nav_offroute"]     = False
                        ss["nav_reroute_pl"]   = None
                        ss["nav_last_reroute"] = now
                        try:
                            ss["nav_distance_left_osrm"] = float((_summary or {}).get("distance_km") or ss.get("nav_distance_left_osrm") or 0)
                        except Exception:
                            pass
                        nav_polyline = new_pl
                        is_offroute = False

                gps_position = {
                    "lat": g_lat,
                    "lon": g_lon,
                    "progress_idx": ss.get("nav_progress_idx", 0),
                    "off_route": is_offroute,
                    "reroute_polyline": ss.get("nav_reroute_pl"),
                }

                                                                                           
                _gps_progress_polyline = nav_polyline
            else:
                _gps_progress_polyline = polyline
        else:
            _gps_progress_polyline = polyline

                                                                              
        import time as _time_mod
        _ss = st.session_state
        _now_ts = _time_mod.time()

        if _ss.get("nav_active") and not _ss.get("nav_arrived"):
            _last_eta_ts = float(_ss.get("auto_eta_last_ts", 0.0) or 0.0)
            _due_for_eta = (_now_ts - _last_eta_ts) >= AUTO_ETA_INTERVAL_SEC
            _gps_ts_for_eta = float(_ss.get("nav_gps_ts", 0.0) or 0.0)
            _gps_age_for_eta = (_now_ts - _gps_ts_for_eta) if _gps_ts_for_eta else 999999
            _skip_heavy = _now_ts < float(_ss.get("nav_skip_heavy_until", 0) or 0)

                                                                                                        
                                                                                                  
            if _due_for_eta and _gps_ts_for_eta > 0 and _gps_age_for_eta <= GPS_MAX_AGE_SEC and not _skip_heavy:
                _run_auto_eta_update(
                    router=router,
                    risk_engine=risk_engine,
                    weather_api=weather_api,
                    dest_fallback=(lat2, lon2),
                    mode_fallback=mode,
                    now_ts=_now_ts,
                )
            elif _skip_heavy:
                _ss["auto_eta_status"] = ""
            elif _gps_ts_for_eta <= 0:
                _ss["auto_eta_status"] = ""

                                                                              
        if _ss.get("nav_active") and not _ss.get("nav_arrived"):
            if _ss.get("auto_eta_last_ts", 0) > 0:
                _ai_status = _ss.get("auto_eta_ai_status") or ("✅ đã cập nhật" if _ss.get("auto_eta_ai_ready") else "⚠️ chưa sẵn sàng")
                _fc_now = _ss.get("auto_eta_forecast")
                _risk_txt = f"⚠️ Rủi ro: {_fc_now.get('overall_label','?')}" if _fc_now else ""
                _dist_val = _ss.get("auto_eta_distance_km")
                _dist_txt = f"{float(_dist_val):.1f} km" if _dist_val is not None else "?"
                st.markdown(
                    f'<div class="summary-bar" style="font-size:.85rem;padding:10px 16px">'
                    f'⏱️ <b>ETA tự động</b> · cập nhật mỗi 5 phút &nbsp;|&nbsp; '
                    f'📍 GPS: {_ss.get("nav_gps_source","?")} &nbsp;|&nbsp; '
                    f'🕒 Cập nhật lần cuối: {_ss.get("auto_eta_updated_at","—")} &nbsp;|&nbsp; '
                    f'🚗 Còn lại: {_dist_txt} &nbsp;|&nbsp; '
                    f'🏁 Dự kiến đến: {_ss.get("auto_eta_arrival","?")} &nbsp;|&nbsp; '
                    f'⚙️ Tốc độ ETA: {_format_speed_label(_ss.get("nav_mode", mode))} &nbsp;|&nbsp; '
                    f'🤖 AI Risk Model: {_ai_status}'
                    + (f' &nbsp;|&nbsp; {_risk_txt}' if _risk_txt else '') +
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                _status = _ss.get("auto_eta_status", "⏳ Đang chờ GPS thật để cập nhật ETA lần đầu.")
                st.caption(_status)


                                                                                             
        if st.session_state.get("nav_active") and st.session_state.get("nav_polyline"):
            _gps_progress_polyline = st.session_state.get("nav_polyline")

        if st.session_state.get("manual_reroute_applied_msg"):
            st.success(st.session_state.pop("manual_reroute_applied_msg") + " Tuyến cũ đã bị thay")

                                                                          
        st.subheader("🗺️ Bản đồ hành trình")
        if st.session_state.get("fuel_visible_fallback"):
            st.caption(
                "⛽ Đang chờ dữ liệu cây xăng thật từ OSM/Overpass — các điểm ⛽ màu "
                "cam trên bản đồ chỉ là điểm nhắc kiểm tra nhiên liệu (chưa xác minh), "
                "không phải cây xăng có thật."
            )
        _nav_active = st.session_state.get("nav_active", False)
                                                                                        
        if st.session_state.get("last_incident_reroute") and len(st.session_state.get("last_routes") or []) == 1:
            alt_routes_other = []
        else:
            alt_routes_other = [rt for i,rt in enumerate(routes) if i != selected]
        _map_fuel_route_key = _fuel_route_cache_key(polyline, corridor_m=3000, max_results=160)
        _route_cached_fuel = (
            st.session_state.get("last_route_fuel_stations_all", [])
            if st.session_state.get("last_route_fuel_key") == _map_fuel_route_key
            else []
        )
        fuel_stations_for_map = fuel_stations or _route_cached_fuel
        fuel_stations_for_map, __fuel_map_is_fallback = _ts_ensure_visible_fuel_markers(
            fuel_stations_for_map,
            polyline,
            max_results=80,
        )
        if fuel_stations_for_map and not __fuel_map_is_fallback:
            st.session_state["last_route_fuel_key"] = _map_fuel_route_key
            st.session_state["last_route_fuel_stations_all"] = fuel_stations_for_map

        map_html = make_full_map(
            lat1, lon1, lat2, lon2,
            colored_segments=colored_segs,
            route_polyline=_gps_progress_polyline if gps_position else polyline,
            alt_routes=alt_routes_other,
            danger_markers=danger_markers,
            rest_suggestions=rest_stops,
            pois=((fuel_stations_for_map or []) + pois),
            reports=rpts,
            forecast_segments=(st.session_state.get("auto_eta_forecast") or route_risk_forecast or {}).get("segments"),
            gps_position=gps_position,
            enable_live_gps=_nav_active,
            dest_lat=lat2,
            dest_lon=lon2,
            avg_speed_kmh=float(_avg_speed_kmh_by_mode(mode) or 40.0),
            speed_segments=speed_segments,
        )
                                                                                                   
        map_html = _ts_inject_fuel_markers_html(map_html, fuel_stations_for_map)
        components.html(map_html, height=620, scrolling=False)

                                                                                          
                                                        
        if not gps_position and st.session_state.get("nav_gps_lat") is not None and st.session_state.get("nav_gps_lon") is not None:
            _update_current_speed_limit_from_gps()                                                                     
        if gps_position:
                                                                                         
            _dist_left_osrm = st.session_state.get("nav_distance_left_osrm")
            _dist_left_txt = f"{float(_dist_left_osrm):.1f} km" if _dist_left_osrm is not None else "Đang cập nhật"
            _gps_ts = st.session_state.get("nav_gps_ts", 0.0)
            _gps_age_txt = "GPS mới" if _gps_ts else "chờ GPS thật"

                                                                                     
            _update_current_speed_limit_from_gps()
            _tomtom_speed_txt = _format_current_speed_limit_text()

            h1, h2, h3, h4 = st.columns(4)
            h1.metric("📍 Còn lại", _dist_left_txt)
            h2.metric("📡 Lệch tuyến", "Có" if gps_position["off_route"] else "Không")
            h3.metric("🛰️ GPS", _gps_age_txt)
            h4.metric("🚘 Tốc độ tối đa", _tomtom_speed_txt)

                                                                                
                                                                              
                                                      
        if st.session_state.get("nav_active") and not st.session_state.get("nav_arrived"):
            st.info("📡 GPS đang chạy — bấm **📡 Bật GPS** trên bản đồ. Marker chạy liên tục bằng JS; ETA/AI Forecast tự đồng bộ 5 phút/lần.")

                                                                                         

                                                                                
        with st.expander("📌 Công cụ hành trình", expanded=False):
                                                                     
                                                                                    
            st.markdown("---")
            st.markdown("### 📌 Công cụ hành trình")

            _tool_tab_copilot, _tool_tab_risk, _tool_tab_rest, _tool_tab_poi, _tool_tab_steps, _tool_tab_iot, _tool_tab_reroute, _tool_tab_eta, _tool_tab_impact = st.tabs([
                "🧠 AI Mobility Copilot",
                f"⚠️ Rủi ro ({len(danger_markers)})",
                f"☕ Điểm nghỉ ({len(rest_stops)})",
                f"⛽ Cây xăng ({len(next_fuel_stations)}) / 📍 Địa điểm ({len(pois)})",
                "📋 Chỉ đường",
                "🚨 GPS / IoT",
                "🔄 Tuyến vòng",
                "⏱️ ETA & AI Forecast",
                "🌱 Tác động & Mẹo ngắn",
            ])
            with _tool_tab_copilot:
                                                                                                           
                _fc_for_copilot = st.session_state.get("auto_eta_forecast") or route_risk_forecast or {}
                _route_for_copilot = dict(route or {})
                if st.session_state.get("nav_active") and st.session_state.get("nav_polyline"):
                    _route_for_copilot["polyline"] = st.session_state.get("nav_polyline")
                    _route_for_copilot["distance_km"] = st.session_state.get("nav_distance_left_osrm") or st.session_state.get("auto_eta_distance_km") or _get_route_distance_km(route)
                    _apply_avg_speed_timing(_route_for_copilot, st.session_state.get("nav_mode", mode))

                _copilot = _build_mobility_copilot_state(
                    forecast=_fc_for_copilot,
                    route=_route_for_copilot,
                    danger_markers=danger_markers,
                    rest_stops=rest_stops,
                    mode=st.session_state.get("nav_mode", mode),
                    nav_active=bool(st.session_state.get("nav_active") and not st.session_state.get("nav_arrived")),
                )
                _crit = _copilot.get("critical_segment") or {}
                st.session_state["copilot_critical_segment"] = _crit
                _render_mobility_copilot_state(_copilot)

                if st.session_state.get("copilot_last_action"):
                    st.info(st.session_state.get("copilot_last_action"))

                if _copilot.get("has_red_decision"):
                    st.markdown("**Hành động đề xuất**")
                    cpa, cpb, cpc, cpd = st.columns(4)
                    with cpa:
                        if st.button("✅ Đồng ý đổi tuyến", key="copilot_accept_reroute", use_container_width=True):
                            ok, msg = _accept_copilot_reroute(
                                router=router,
                                risk_engine=risk_engine,
                                weather_api=weather_api,
                                mode_fallback=mode,
                                route_fallback=_route_for_copilot,
                            )
                            if ok:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.warning(msg)
                    with cpb:
                        if st.button("⏸️ Nghỉ 15 phút", key="copilot_rest_15", use_container_width=True):
                            st.session_state["copilot_pending_rest_min"] = 15
                    with cpc:
                        if st.button("⏸️ Nghỉ 30 phút", key="copilot_rest_30", use_container_width=True):
                            st.session_state["copilot_pending_rest_min"] = 30
                    with cpd:
                        if st.button("⚠️ Vẫn đi tiếp", key="copilot_continue", use_container_width=True):
                            import time as _time
                            st.session_state["copilot_dismiss_until"] = _time.time() + 10 * 60
                            st.session_state["copilot_last_action"] = "⚠️ Bạn đã chọn vẫn đi tiếp. App sẽ tiếp tục giám sát rủi ro phía trước."
                            st.info(st.session_state["copilot_last_action"])
                else:
                    st.caption("Chưa có chấm đỏ ≥ 85% trên phần tuyến phía trước, nên app không hiện nút đổi tuyến/nghỉ để tránh gây rối.")

                _pending_rest = st.session_state.get("copilot_pending_rest_min")
                if _pending_rest:
                    st.warning(f"Bạn có chắc muốn nghỉ {_pending_rest} phút rồi cập nhật lại ETA và AI Risk Forecast không?")
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        if st.button("✅ Xác nhận nghỉ và cập nhật", key="copilot_confirm_rest", use_container_width=True):
                            ok, msg = _accept_copilot_rest(
                                router=router,
                                risk_engine=risk_engine,
                                weather_api=weather_api,
                                mode_fallback=mode,
                                delay_min=int(_pending_rest),
                            )
                            st.session_state["copilot_pending_rest_min"] = None
                            if ok:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.warning(msg)
                    with cc2:
                        if st.button("❌ Hủy", key="copilot_cancel_rest", use_container_width=True):
                            st.session_state["copilot_pending_rest_min"] = None
                            st.rerun()

                st.caption("Copilot không tự đổi tuyến. Hệ thống phát hiện nguy cơ → giải thích lý do → hỏi ý kiến → chỉ cập nhật tuyến/ETA/AI Forecast khi bạn xác nhận.")

            with _tool_tab_risk:
                if not danger_markers:
                    st.markdown('<div class="alert-success">✅ Không phát hiện vùng nguy hiểm trọng yếu.</div>',
                                unsafe_allow_html=True)
                else:
                    if len(danger_markers_raw) != len(danger_markers):
                        st.caption(f"Đã gom/lọc từ {len(danger_markers_raw)} điểm rủi ro thành {len(danger_markers)} vùng trọng yếu.")
                for seg in danger_markers:
                    sc  = seg.get("score", 0)
                    css = _risk_alert_css(sc)
                    km_label = seg.get("km_text") or f"km {seg.get('route_km',0):.0f}"
                    avg_txt = f" · TB {seg.get('avg_score', sc):.0%}" if seg.get("cluster_count", 1) > 1 else ""
                    st.markdown(
                        f'<div class="{css}"><b>{seg.get("icon","⚠️")} {seg.get("label","")}</b>'
                        f'<span style="float:right;font-size:.83rem">{_risk_level_icon(sc)} {sc:.0%}{avg_txt} · {km_label}</span>'
                        f'<br>{seg.get("desc","")}</div>', unsafe_allow_html=True)

            with _tool_tab_rest:
                if not rest_stops: st.info("Không có điểm dừng nghỉ.")
                for rs in rest_stops:
                    st.markdown(
                        f'<div class="alert-success"><b>{rs.get("icon","☕")} {rs.get("name","")}</b>'
                        f'<span style="float:right;font-size:.83rem">km {rs.get("route_km",0):.0f}</span>'
                        f'<br>{rs.get("desc","")}</div>', unsafe_allow_html=True)

            with _tool_tab_poi:
                EMOJI2 = {"fuel":"⛽","food":"🍜","nature":"🌿","scenic":"📸","culture":"🏛️",
                          "relaxation":"🏖️","ecotourism":"🌲","attraction":"⭐"}

                st.markdown("#### ⛽ 2 cây xăng tiếp theo trên đúng tuyến")
                st.caption("Chỉ lấy cây xăng nằm trong hành lang 300m quanh tuyến OSRM, loại bỏ cây xăng lệch hẻm/đường vòng xa.")
                if not next_fuel_stations:
                    st.info("Chưa tìm thấy cây xăng nằm sát tuyến. Có thể Overpass/OSM chưa có dữ liệu khu vực này.")
                for idx, fuel in enumerate(next_fuel_stations, 1):
                    dist_m = fuel.get("dist_from_route_m")
                    dist_txt = f"{dist_m} m" if dist_m is not None else f"{fuel.get('dist_from_route_km',0)} km"
                    with st.expander(f"⛽ {idx}. **{fuel.get('name','Cây xăng')}** — km {fuel.get('route_km',0):.1f} · cách tuyến {dist_txt}", expanded=(idx == 1)):
                        c1, c2 = st.columns([3,1])
                        with c1:
                            if fuel.get("operator"):
                                st.markdown(f"**Đơn vị:** {fuel.get('operator')}")
                            st.caption("🏷️ fuel, gas_station · search along route")
                            st.markdown("Cây xăng này nằm gần tuyến đang đi, không phải kết quả gần GPS nhưng lệch vào hẻm.")
                        with c2:
                            st.metric("Vị trí", f"km {fuel.get('route_km',0):.1f}")
                            st.metric("Cách tuyến", dist_txt)

                st.markdown("#### 📍 Địa điểm gợi ý dọc đường")
                if not pois: st.info("Không tìm thấy địa điểm. Thử '🌐 Tất cả'.")
                for poi in pois:
                    cat = poi.get("category","attraction")
                    emoji = EMOJI2.get(cat,"📍")
                    with st.expander(f"{emoji} **{poi['name']}** — km {poi.get('route_km',0):.0f} · ⭐{poi.get('rating','?')} · {poi.get('type','')}"):
                        c1,c2 = st.columns([3,1])
                        with c1:
                            st.markdown(f"**{poi.get('province','')}**")
                            st.caption("🏷️ " + ", ".join(poi.get("tags",[])))
                            story = ai_engine.generate_cultural_story(poi["name"],poi.get("province",""),poi.get("tags",[]))
                            st.markdown(f"*{story}*")
                        with c2:
                            st.metric("Vị trí", f"km {poi.get('route_km',0):.0f}")
                            st.metric("Cách tuyến", f"{poi.get('dist_from_route_km',0)} km")

            with _tool_tab_steps:
                steps = route.get("steps",[])
                if not steps: st.info("Không có hướng dẫn (tuyến fallback).")
                for i,s in enumerate(steps,1):
                    st.markdown(
                        f'<div class="step-box"><b>{i}.</b> {s["instruction"]} '
                        f'<span style="color:#888;font-size:.8em">— {s["distance_km"]} km · {s["duration_min"]} phút</span></div>',
                        unsafe_allow_html=True)

            with _tool_tab_iot:
                                                                                           
                if st.session_state.get("last_routes") and st.session_state.get("last_danger_markers"):
                    st.divider()
                    st.subheader("🚨 Cảnh báo IoT theo GPS thật")

                    _iot_dangers  = st.session_state.get("last_danger_markers", [])
                    _iot_total_km = st.session_state.get("last_route_km", 0) or 1
                    _iot_polyline = st.session_state.get("last_polyline", [])

                                                                                          
                    _iot_mode = st.radio(
                        "Chế độ hoạt động",
                        ["📡 GPS tự động (điện thoại)", "🕹️ Mô phỏng thủ công"],
                        horizontal=True,
                        key="iot_mode_radio",
                    )
                    _use_gps = (_iot_mode == "📡 GPS tự động (điện thoại)")

                                                                                             
                                        
                                                                                             
                    if _use_gps:
                        st.caption(
                            "📱 App sử dụng GPS điện thoại để tự động xác định vị trí và cảnh báo nguy hiểm "
                            "theo tuyến đang chọn. Bấm **Bật GPS tự động** → trình duyệt sẽ hỏi quyền vị trí "
                            "*(chỉ hỏi 1 lần)*, sau đó cập nhật mỗi 5 giây."
                        )

                                                                                           
                        gps_html = _build_gps_component_html(interval_ms=5000)
                        components.html(gps_html, height=72, scrolling=False)

                                                                                           
                                                                                        
                                                                                          
                                                                       
                        gps_col1, gps_col2 = st.columns([3, 1])
                        with gps_col1:
                            _gps_input = st.text_input(
                                "📍 Tọa độ GPS hiện tại (tự điền hoặc nhập tay)",
                                value=st.session_state.get("gps_manual_input", ""),
                                placeholder="VD: 11.9404, 108.4583",
                                key="gps_coord_input",
                            )
                        with gps_col2:
                            st.markdown("<br>", unsafe_allow_html=True)
                            if st.button("🔄 Cập nhật vị trí", key="gps_refresh", use_container_width=True):
                                st.session_state["gps_manual_input"] = _gps_input
                                st.rerun()

                                                                                       
                        st.markdown("""
            <script>
            window.addEventListener('message', function(e) {
              if (e.data && e.data.type === 'tripsmart_gps') {
                var p = e.data.payload;
                var coord = p.lat.toFixed(6) + ', ' + p.lon.toFixed(6);
                var inputs = window.parent.document.querySelectorAll('input[type="text"]');
                for (var i = 0; i < inputs.length; i++) {
                  var inp = inputs[i];
                  if (inp.placeholder && inp.placeholder.includes('lat,lon') || inp.placeholder.includes('9404')) {
                    inp.value = coord;
                    inp.dispatchEvent(new Event('input', {bubbles:true}));
                    break;
                  }
                }
              }
            });
            </script>""", unsafe_allow_html=True)

                                          
                        _gps_lat = _gps_lon = None
                        _gps_raw = st.session_state.get("gps_manual_input", "") or _gps_input
                        if _gps_raw and "," in _gps_raw:
                            try:
                                _parts = _gps_raw.replace(" ", "").split(",")
                                _gps_lat, _gps_lon = float(_parts[0]), float(_parts[1])
                            except Exception:
                                pass

                        if _gps_lat is not None:
                                                                                          
                            _iot = _calc_iot_state_from_gps(_gps_lat, _gps_lon, _iot_dangers, _iot_total_km)
                            _state        = _iot["state"]
                            _nd           = _iot["nearest_danger"]
                            _nearest_dist = _iot["nearest_dist"]
                            _next_d       = _iot["next_danger"]
                            _next_dist    = _iot["next_danger_dist"]
                            _cur_score    = _iot["cur_score"]

                                                                
                            _seg_info = _find_nearest_segment(_gps_lat, _gps_lon, _iot_polyline) if _iot_polyline else {}
                            _progress_ratio = _seg_info.get("progress_ratio", 0.0)

                                            
                            _STATE_MAP = {
                                "safe"   : ("#43a047","#f1f8e9","🟢 XANH — An toàn",   "🔕 TẮT","AN TOÀN",
                                            "✅ Hành trình bình thường. Tiếp tục quan sát biển báo và điều kiện đường."),
                                "warning": ("#f9a825","#fffde7","🟡 VÀNG — Cảnh báo",  "🔕 TẮT","CẢNH BÁO",
                                            "⚠️ Chú ý quan sát, giữ tốc độ an toàn, chuẩn bị vào vùng rủi ro."),
                                "danger" : ("#e53935","#fff5f5","🔴 ĐỎ — Nguy hiểm", "🔊 BẬT — Phát tiếng cảnh báo!","NGUY HIỂM",
                                            "⛔ Giảm tốc độ ngay, tăng cự ly với xe trước, sẵn sàng dừng khẩn cấp."),
                            }
                            _led_color,_bg,_led_label,_buzzer,_state_text,_rec = _STATE_MAP[_state]
                            _border = _led_color

                            st.progress(_progress_ratio,
                                        text=f"🚗 Tiến trình trên tuyến: {_progress_ratio:.0%} · GPS: {_gps_lat:.5f}, {_gps_lon:.5f}")

                            st.markdown(
                                f'<div style="background:{_bg};border:2.5px solid {_border};border-radius:14px;'
                                f'padding:18px 22px;margin:12px 0">'
                                f'<div style="display:flex;align-items:center;gap:14px;margin-bottom:14px">'
                                f'<div style="width:56px;height:56px;border-radius:50%;background:{_led_color};'
                                f'box-shadow:0 0 24px {_led_color};flex-shrink:0"></div>'
                                f'<div><div style="font-size:1.35rem;font-weight:700;color:{_border}">'
                                f'⚡ TRẠNG THÁI: {_state_text}</div>'
                                f'<div style="font-size:.86rem;color:#555">'
                                f'📡 GPS: {_gps_lat:.5f}, {_gps_lon:.5f}</div></div></div>'

                                f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:14px">'

                                f'<div style="background:white;border-radius:10px;padding:12px;text-align:center;border:1.5px solid {_border}30">'
                                f'<div style="font-size:.75rem;color:#888;margin-bottom:4px">💡 LED MÔ PHỎNG</div>'
                                f'<div style="font-weight:700;color:{_led_color};font-size:.93rem">{_led_label}</div></div>'

                                f'<div style="background:white;border-radius:10px;padding:12px;text-align:center;border:1.5px solid {_border}30">'
                                f'<div style="font-size:.75rem;color:#888;margin-bottom:4px">🔔 BUZZER MÔ PHỎNG</div>'
                                f'<div style="font-weight:700;font-size:.93rem">{_buzzer}</div></div>'

                                f'<div style="background:white;border-radius:10px;padding:12px;text-align:center;border:1.5px solid {_border}30">'
                                f'<div style="font-size:.75rem;color:#888;margin-bottom:4px">📡 NGUY HIỂM GẦN NHẤT</div>'
                                f'<div style="font-weight:700;font-size:.93rem">'
                                + (f'≈ {_nearest_dist:.2f} km' if _nearest_dist < 900 else '✅ Không có') +
                                f'</div></div></div>'

                                + (
                                    f'<div style="background:#fff3e0;border-radius:8px;padding:10px 14px;margin-bottom:10px">'
                                    f'⚠️ <b>Vùng sắp tới:</b> {_next_d.get("icon","⚠️")} '
                                    f'<b>{_next_d.get("label","")}</b> · {_next_dist:.1f} km'
                                    f' · Rủi ro {_next_d.get("score",0):.0%}'
                                    f'<br><span style="font-size:.82rem;color:#555">{_next_d.get("desc","")}</span></div>'
                                    if _next_d and _next_dist < 900 else
                                    '<div style="background:#e8f5e9;border-radius:8px;padding:10px 14px;margin-bottom:10px">'
                                    '✅ <b>Không có vùng nguy hiểm nào phía trước.</b></div>'
                                )

                                + f'<div style="font-size:.92rem;padding:8px 4px"><b>🧭 Khuyến nghị:</b> {_rec}</div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

                                                                                          
                                                                                      
                                                                         

                        else:
                            st.info("📡 Bấm **Bật GPS tự động** ở trên để lấy vị trí, "
                                    "hoặc nhập tọa độ thủ công vào ô `lat,lon` rồi bấm **Cập nhật vị trí**.")

                                                                                             
                                                                       
                                                                                             
                    else:
                        st.caption(
                            "🕹️ Mô phỏng xe di chuyển từng bước trên tuyến. "
                            "Bấm **▶️ Tiếp theo** để tiến đến điểm kế tiếp."
                        )
                        _sim_dangers = sorted(_iot_dangers, key=lambda x: x.get("route_km", 0))
                        _sim_steps   = [{"label":"🟢 Xuất phát","route_km":0.0,"score":0.0,
                                         "type":"start","icon":"🚦","desc":"Bắt đầu hành trình."}]
                        _sim_steps  += _sim_dangers
                        _sim_steps  += [{"label":"🏁 Điểm đến","route_km":float(_iot_total_km),
                                         "score":0.0,"type":"end","icon":"🏁","desc":"Đã đến điểm đến."}]

                        if "iot_step" not in st.session_state:
                            st.session_state["iot_step"] = 0
                        _cur_idx = max(0, min(int(st.session_state.get("iot_step",0)), len(_sim_steps)-1))
                        _cur_pt  = _sim_steps[_cur_idx]

                        _next_danger = next((_p for _p in _sim_steps[_cur_idx+1:] if _p.get("score",0)>=0.40), None)
                        _dist_to_danger = (_next_danger["route_km"] - _cur_pt.get("route_km",0)
                                           if _next_danger else 999.0)
                        _cur_score = float(_cur_pt.get("score",0))

                        if _cur_score >= RED_RISK_THRESHOLD:
                            _led_color="#e53935";_bg="#fff5f5";_border="#e53935"
                            _led_label="🔴 ĐỎ — Nguy hiểm";_buzzer="🔊 BẬT — Phát tiếng cảnh báo!"
                            _state_text="NGUY HIỂM"
                            _rec="⛔ Giảm tốc độ ngay, tăng cự ly với xe trước, sẵn sàng dừng khẩn cấp."
                        elif _cur_score >= ORANGE_RISK_THRESHOLD or _dist_to_danger < 5.0:
                            _led_color="#f9a825";_bg="#fffde7";_border="#f9a825"
                            _led_label="🟡 VÀNG — Cảnh báo";_buzzer="🔕 TẮT"
                            _state_text="CẢNH BÁO"
                            _rec="⚠️ Chú ý quan sát, giữ tốc độ an toàn, chuẩn bị vào vùng rủi ro."
                        else:
                            _led_color="#43a047";_bg="#f1f8e9";_border="#43a047"
                            _led_label="🟢 XANH — An toàn";_buzzer="🔕 TẮT"
                            _state_text="AN TOÀN"
                            _rec="✅ Hành trình bình thường. Tiếp tục quan sát biển báo và điều kiện đường."

                        btn1,btn2,btn3,btn4 = st.columns(4)
                        with btn1:
                            if st.button("▶️ Bắt đầu / Tiếp theo", type="primary", key="iot_next", use_container_width=True):
                                if _cur_idx < len(_sim_steps)-1: st.session_state["iot_step"] = _cur_idx+1
                                st.rerun()
                        with btn2:
                            if st.button("⏮️ Quay lại", key="iot_prev", use_container_width=True):
                                if _cur_idx > 0: st.session_state["iot_step"] = _cur_idx-1
                                st.rerun()
                        with btn3:
                            if st.button("⏭️ Nhảy đến nguy hiểm", key="iot_jump", use_container_width=True):
                                _di = next((i for i,p in enumerate(_sim_steps) if p.get("score",0)>=RED_RISK_THRESHOLD), None)
                                if _di is not None: st.session_state["iot_step"] = _di
                                st.rerun()
                        with btn4:
                            if st.button("🔄 Reset", key="iot_reset", use_container_width=True):
                                st.session_state["iot_step"] = 0; st.rerun()

                        st.progress(_cur_idx/max(1,len(_sim_steps)-1),
                                    text=f"Bước {_cur_idx+1}/{len(_sim_steps)} · km {_cur_pt.get('route_km',0):.1f}")

                        st.markdown(
                            f'<div style="background:{_bg};border:2.5px solid {_border};border-radius:14px;'
                            f'padding:18px 22px;margin:12px 0">'
                            f'<div style="display:flex;align-items:center;gap:14px;margin-bottom:14px">'
                            f'<div style="width:52px;height:52px;border-radius:50%;background:{_led_color};'
                            f'box-shadow:0 0 18px {_led_color};flex-shrink:0"></div>'
                            f'<div><div style="font-size:1.35rem;font-weight:700;color:{_border}">⚡ TRẠNG THÁI: {_state_text}</div>'
                            f'<div style="font-size:.88rem;color:#555">📍 {_cur_pt.get("icon","📍")} '
                            f'{_cur_pt.get("label","—")} · km {_cur_pt.get("route_km",0):.1f}</div></div></div>'

                            f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:14px">'
                            f'<div style="background:white;border-radius:10px;padding:12px;text-align:center;border:1.5px solid {_border}30">'
                            f'<div style="font-size:.75rem;color:#888;margin-bottom:4px">💡 LED MÔ PHỎNG</div>'
                            f'<div style="font-weight:700;color:{_led_color};font-size:.95rem">{_led_label}</div></div>'
                            f'<div style="background:white;border-radius:10px;padding:12px;text-align:center;border:1.5px solid {_border}30">'
                            f'<div style="font-size:.75rem;color:#888;margin-bottom:4px">🔔 BUZZER MÔ PHỎNG</div>'
                            f'<div style="font-weight:700;font-size:.95rem">{_buzzer}</div></div>'
                            f'<div style="background:white;border-radius:10px;padding:12px;text-align:center;border:1.5px solid {_border}30">'
                            f'<div style="font-size:.75rem;color:#888;margin-bottom:4px">📡 NGUY HIỂM PHÍA TRƯỚC</div>'
                            f'<div style="font-weight:700;font-size:.95rem">'
                            + (f'≈ {_dist_to_danger:.1f} km' if _dist_to_danger < 900 else '✅ Không có') +
                            f'</div></div></div>'
                            + (
                                f'<div style="background:#fff3e0;border-radius:8px;padding:10px 14px;margin-bottom:10px">'
                                f'⚠️ <b>Vùng sắp tới:</b> {_next_danger.get("icon","⚠️")} '
                                f'<b>{_next_danger.get("label","")}</b> · km {_next_danger.get("route_km",0):.0f}'
                                f' · Rủi ro {_next_danger.get("score",0):.0%}'
                                f'<br><span style="font-size:.83rem;color:#555">{_next_danger.get("desc","")}</span></div>'
                                if _next_danger else
                                '<div style="background:#e8f5e9;border-radius:8px;padding:10px 14px;margin-bottom:10px">'
                                '✅ <b>Không có vùng nguy hiểm nào phía trước.</b></div>'
                            )
                            + f'<div style="font-size:.92rem;padding:8px 4px"><b>🧭 Khuyến nghị:</b> {_rec}</div></div>',
                            unsafe_allow_html=True,
                        )

                        with st.expander(f"📋 Toàn bộ {len(_sim_steps)} điểm mô phỏng", expanded=False):
                            for i,pt in enumerate(_sim_steps):
                                sc = pt.get("score",0)
                                dot = _risk_level_icon(sc)
                                active = "background:#e3f2fd;border-left:4px solid #1976d2;font-weight:700" if i==_cur_idx else ""
                                st.markdown(
                                    f'<div class="step-box" style="{active}">'
                                    f'{dot} <b>Bước {i+1}</b> · {pt.get("icon","📍")} {pt.get("label","—")} '
                                    f'· km {pt.get("route_km",0):.1f}'
                                    + (f' · Rủi ro {sc:.0%}' if sc>0 else '')
                                    + f'</div>', unsafe_allow_html=True)

            with _tool_tab_reroute:
                                                                                           
                if st.session_state.get("last_routes"):
                    st.divider()
                    st.subheader("🔄 Tránh sự cố — Thay tuyến hiện tại")
                    st.markdown('<div class="reroute-box">Nhập vị trí sự cố; app sẽ tìm tuyến mới và thay luôn tuyến hiện tại, không mở map phụ.</div>',
                                unsafe_allow_html=True)
                    rc1,rc2 = st.columns(2)
                    with rc1:
                        incident_loc = st.text_input("📍 Vị trí sự cố", placeholder="VD: 11.2,107.38", key="inc_loc")
                    with rc2:
                        _avoid_choice = st.radio(
                            "Chọn khoảng tuyến vòng",
                            ["1 km", "5 km", "20 km"],
                            horizontal=True,
                            key="avoid_r_choice",
                            help="1 km: tìm trong khoảng 1–5 km; 5 km: tìm 5–20 km; 20 km: tìm tuyến vòng xa hơn 20 km."
                        )
                        avoid_r = {"1 km": 1.0, "5 km": 5.0, "20 km": 20.0}.get(_avoid_choice, 1.0)
                        st.caption("1 km → tìm 1–5 km · 5 km → tìm 5–20 km · 20 km → tìm >20 km")

                    if st.button("🔄 Tìm tuyến vòng 1 lần", type="secondary", key="btn_reroute"):
                        if not incident_loc:
                            st.warning("Nhập vị trí sự cố trước.")
                        else:
                            with st.spinner("Đang tính..."):
                                ilat, ilon = resolve_location(incident_loc, maps_api)
                            if not ilat:
                                st.error("❌ Không tìm được vị trí sự cố.")
                            else:
                                origin = st.session_state["last_origin"]
                                dest   = st.session_state["last_dest"]
                                mode_r = st.session_state["last_mode"]
                                old_route = (st.session_state.get("last_routes") or [{}])[st.session_state.get("last_selected", 0)]

                                with st.spinner("🛣️ Đang tìm tuyến vòng theo khoảng đã chọn..."):
                                    new_rt, explain = _ts_find_best_incident_reroute(
                                        router=router,
                                        origin=origin,
                                        dest=dest,
                                        ilat=ilat,
                                        ilon=ilon,
                                        mode_r=mode_r,
                                        avoid_r=avoid_r,
                                        old_route=old_route,
                                    )

                                if new_rt and not new_rt.get("fallback"):
                                    ok, msg = _ts_apply_manual_incident_reroute_to_session(
                                        new_rt=new_rt,
                                        origin=origin,
                                        dest=dest,
                                        mode_r=mode_r,
                                        ilat=ilat,
                                        ilon=ilon,
                                        avoid_r=avoid_r,
                                    )
                                    if ok:
                                        st.success(msg + " " + explain)
                                        st.rerun()
                                    else:
                                        st.error(msg)
                                else:
                                    st.warning(
                                        "❌ Không tìm được tuyến vòng khác tuyến cũ. "
                                        "Khu vực này có thể chỉ có một trục đường khả dụng, "
                                        "hoặc waypoint tránh không thể snap vào đường. "
                                        + str(explain)
                                    )

            with _tool_tab_eta:
                                                                                              
                st.subheader("⏱️ ETA tự động & AI Risk Forecast")
                if st.session_state.get("auto_eta_last_ts", 0):
                    _fc_auto = st.session_state.get("auto_eta_forecast")
                    st.success(
                        f"ETA tự động đã cập nhật lúc {st.session_state.get('auto_eta_updated_at','—')} · "
                        f"Còn lại {float(st.session_state.get('auto_eta_distance_km', 0) or 0):.1f} km · "
                        f"Dự kiến đến {st.session_state.get('auto_eta_arrival','?')}"
                    )
                    if _fc_auto:
                        _render_route_forecast(_fc_auto, datetime.now(), title="AI Risk Forecast theo GPS hiện tại")
                    else:
                        st.info("AI Risk Model chưa có forecast tự động hoặc chưa sẵn sàng.")
                else:
                    st.info(st.session_state.get("auto_eta_status", "Chưa có ETA tự động. Bật GPS trên bản đồ để app cập nhật lần đầu."))

                with st.expander("🛠️ Công cụ ETA thủ công / debug", expanded=False):
                    if st.session_state.get("last_routes"):
                        st.divider()
                        st.subheader("🔄 Cập nhật ETA — Dự báo rủi ro theo vị trí hiện tại")
                        st.markdown(
                            '<div class="reroute-box">Nếu bạn nghỉ lâu hoặc đi nhanh/chậm hơn dự kiến, '
                            'ETA ban đầu sẽ lệch. Nhập vị trí hiện tại để tính lại tuyến còn lại '
                            'và dự báo rủi ro theo giờ thực tế (giờ hiện tại).</div>',
                            unsafe_allow_html=True,
                        )

                        ec1, ec2 = st.columns([3, 1])
                        with ec1:
                            current_loc_input = st.text_input(
                                "📍 Vị trí hiện tại của bạn",
                                placeholder="VD: 11.50,108.07  hoặc  Đèo Bảo Lộc",
                                key="current_loc_eta",
                            )
                        with ec2:
                            recalc_btn = st.button("🔄 Tính lại ETA", type="primary", use_container_width=True, key="btn_recalc_eta")

                        if recalc_btn:
                            if not current_loc_input:
                                st.warning("Nhập vị trí hiện tại trước.")
                            else:
                                with st.spinner("📡 Xác định vị trí hiện tại..."):
                                    cur_lat, cur_lon = resolve_location(current_loc_input, maps_api)

                                if not cur_lat:
                                    st.error("❌ Không tìm được vị trí hiện tại. Thử dạng `lat,lon`, VD: `11.50,108.07`.")
                                else:
                                    dest_r = st.session_state["last_dest"]
                                    mode_r = st.session_state["last_mode"]

                                    with st.spinner("🛣️ Tính tuyến còn lại (OSRM)..."):
                                        remaining_rt = router.get_route((cur_lat, cur_lon), dest_r, mode=mode_r)
                                        _apply_avg_speed_timing(remaining_rt, mode_r)

                                    if not remaining_rt or not remaining_rt.get("polyline"):
                                        st.error("❌ Không tính được tuyến còn lại từ vị trí này.")
                                    else:
                                        now_dt = datetime.now()
                                        remaining_polyline = remaining_rt.get("polyline", [])

                                        with st.spinner("🤖 Dự báo lại rủi ro theo ETA mới..."):
                                            ml_model_eta = init_ml_model()
                                            new_forecast, new_tds, new_warn = _compute_route_forecast(
                                                remaining_polyline, remaining_rt, now_dt,
                                                risk_engine, ml_model_eta, weather_api,
                                            )

                                        eta_dest_text = (
                                            (now_dt + timedelta(seconds=new_tds)).strftime('%H:%M')
                                            if new_tds else '?'
                                        )
                                        st.success(
                                            f"✅ Tuyến còn lại: 📏 {remaining_rt.get('distance_text','?')} · "
                                            f"⏱️ {remaining_rt.get('duration_text','?')} · "
                                            f"ETA đến đích: {eta_dest_text}"
                                        )

                                                                             
                                        if route_risk_forecast:
                                            old_level = route_risk_forecast["overall_level"]
                                            new_level = new_forecast["overall_level"] if new_forecast else "unknown"
                                            order = {"low": 0, "medium": 1, "high": 2, "very_high": 3, "unknown": 0}
                                            if order.get(new_level, 0) > order.get(old_level, 0):
                                                st.markdown(
                                                    '<div class="alert-danger">⚠️ Mức rủi ro tổng thể của phần tuyến còn lại '
                                                    f'đã <b>tăng</b> so với dự báo ban đầu '
                                                    f'({route_risk_forecast["overall_label"]} → '
                                                    f'{new_forecast["overall_label"] if new_forecast else "?"}). '
                                                    'Cân nhắc xem tuyến vòng ở trên.</div>',
                                                    unsafe_allow_html=True,
                                                )
                                            elif order.get(new_level, 0) < order.get(old_level, 0):
                                                st.markdown(
                                                    '<div class="alert-success">✅ Mức rủi ro tổng thể của phần tuyến còn lại '
                                                    f'đã <b>giảm</b> so với dự báo ban đầu '
                                                    f'({route_risk_forecast["overall_label"]} → '
                                                    f'{new_forecast["overall_label"] if new_forecast else "?"}).</div>',
                                                    unsafe_allow_html=True,
                                                )

                                        if new_warn:
                                            st.warning(new_warn)

                                        if new_forecast:
                                            _render_route_forecast(
                                                new_forecast, now_dt,
                                                title="Dự báo rủi ro tuyến còn lại (cập nhật theo vị trí hiện tại)",
                                            )
                                        else:
                                            st.caption("ℹ️ AI Risk Model chưa sẵn sàng — không thể dự báo lại.")

                                        with st.spinner("🎨 Vẽ bản đồ tuyến còn lại..."):
                                            remaining_colored = risk_engine.score_polyline_segments(remaining_polyline)
                                            remaining_analysis = risk_engine.analyze_route(remaining_polyline)

                                        remaining_map_html = make_full_map(
                                            cur_lat, cur_lon, dest_r[0], dest_r[1],
                                            colored_segments=remaining_colored,
                                            route_polyline=remaining_polyline,
                                            danger_markers=_cluster_danger_markers(
                                                remaining_analysis.get("danger_segments", []), max_items=8),
                                            rest_suggestions=remaining_analysis.get("rest_suggestions", []),
                                            forecast_segments=new_forecast.get("segments") if new_forecast else None,
                                        )
                                        components.html(remaining_map_html, height=520, scrolling=False)

            with _tool_tab_impact:
                _latest_reroute = st.session_state.get("last_incident_reroute")
                _render_env_social_impact(route, danger_markers, st.session_state.get("last_mode", mode), reroute_route=_latest_reroute)
                st.divider()
                st.caption("💡 Mẹo ngắn đang hiển thị nổi ở góc trái dưới màn hình và tự đổi sau 5 phút.")


                                                                                     
                           
                                                                                     
elif "Học luật" in menu:
    st.title("📚 Mẹo an toàn & Net Zero")
    st.markdown(
        '<div class="alert-info">🌱 Module giáo dục tự chọn gắn với Net Zero, an sinh xã hội và tư duy phản biện. '
        'Hiển thị mẹo/fact ngắn theo ngữ cảnh, không pop-up và không bắt trả lời khi đang dùng app.</div>',
        unsafe_allow_html=True,
    )
    _render_safety_quiz(key_prefix=f"standalone_quiz_{st.session_state.get('__tripsmart_5min_bucket', 0)}")


                                                                                 
                    
                                                                                 
elif "rủi ro" in menu:
    st.title("⚠️ Kiểm tra rủi ro khu vực")
    loc_inp = st.text_input("📍 Địa điểm", placeholder="VD: Đà Lạt hoặc 11.94,108.44")
    if st.button("🔍 Phân tích", type="primary"):
        with st.spinner("Đang phân tích..."):
            lat,lon = resolve_location(loc_inp, maps_api)
        if not lat:
            st.error("❌ Không tìm được.")
        else:
            risk = risk_engine.analyze_point(lat, lon)
            wr   = weather_api.get_weather_risk(lat, lon)
            st.success(f"Tại `{lat:.4f}, {lon:.4f}`")
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Tổng thể",    f"{risk_color(risk['overall_score'])} {risk['overall_score']:.0%}")
            c2.metric("🏔️ Địa chất", f"{risk_color(risk['geological'])} {risk['geological']:.0%}")
            c3.metric("🌊 Lũ lụt",   f"{risk_color(risk['flood'])} {risk['flood']:.0%}")
            c4.metric("⛰️ Sạt lở",   f"{risk_color(risk['landslide'])} {risk['landslide']:.0%}")

            sc  = risk["overall_score"]
            col = "red" if sc >= RED_RISK_THRESHOLD else "orange" if sc >= YELLOW_RISK_THRESHOLD else "green"
            mm  = folium.Map([lat,lon], zoom_start=11,
                tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", attr="© OSM")
            folium.CircleMarker([lat,lon], radius=25, color=col,
                fill=True, fill_opacity=0.2, weight=2).add_to(mm)
            folium.Marker([lat,lon],
                icon=folium.Icon(color=col, icon="map-marker"),
                popup=f"Rủi ro: {sc:.0%}").add_to(mm)
            components.html(mm._repr_html_(), height=380, scrolling=False)

            col_r,col_w = st.columns(2)
            with col_r:
                st.subheader("🚨 Cảnh báo địa lý")
                for a in risk.get("alerts",[]): st.markdown(f'<div class="alert-danger">{a}</div>',unsafe_allow_html=True)
                if not risk.get("alerts"): st.markdown('<div class="alert-success">✅ Khu vực an toàn</div>',unsafe_allow_html=True)
            with col_w:
                st.subheader("🌤️ Rủi ro thời tiết")
                for a in wr.get("alerts",[]): st.markdown(f'<div class="alert-warning">{a}</div>',unsafe_allow_html=True)
                if not wr.get("alerts"): st.markdown('<div class="alert-success">✅ Thời tiết ổn định</div>',unsafe_allow_html=True)
                w = wr.get("weather",{})
                if w.get("temp_c"):
                    st.caption(f"🌡️ {w['temp_c']}°C · {w.get('description','')} · 💨 {w.get('wind_speed_ms',0)} m/s")


                                                                                 
        
                                                                                 
elif "SOS" in menu:
    st.title("🆘 SOS Khẩn cấp")
    st.markdown('<div class="alert-danger">⚠️ Chỉ dùng khi thực sự có tình huống khẩn cấp!</div>',unsafe_allow_html=True)

                                                                                             
                                                                      
    try:
        components.html(_build_gps_preload_html(interval_ms=1000, hidden=True), height=1, scrolling=False)
    except Exception:
        pass

    if "sos_location_input" not in st.session_state:
        st.session_state["sos_location_input"] = ""

    col_a,col_b = st.columns(2)
    with col_a:
        etype=st.selectbox("Loại khẩn cấp",["accident","medical","fire","stranded","general"],
            format_func=lambda x:{"accident":"🚗 Tai nạn","medical":"🏥 Cấp cứu",
                                   "fire":"🔥 Cháy","stranded":"🏔️ Mắc kẹt","general":"🚨 Khác"}[x])

        gps_col1, gps_col2 = st.columns([1, 1])
        with gps_col1:
            use_sos_gps = st.button("📡 Lấy vị trí hiện tại", key="btn_sos_use_current_gps", use_container_width=True)
        with gps_col2:
            if st.session_state.get("nav_gps_lat") is not None and st.session_state.get("nav_gps_lon") is not None:
                st.caption(f"GPS gần nhất: {float(st.session_state['nav_gps_lat']):.5f}, {float(st.session_state['nav_gps_lon']):.5f}")
            else:
                st.caption("Bấm nút để xin quyền GPS")

        if use_sos_gps:
            if not _JSEVAL_OK:
                st.error("Thiếu thư viện `streamlit-js-eval`. Chạy: `pip install streamlit-js-eval`")
            else:
                _gps_payload = None
                try:
                    _gps_payload = _read_latest_gps_from_browser(max_age_sec=600, key="sos_gps_button_read")
                except Exception:
                    _gps_payload = None

                                                                                           
                if not _gps_payload and get_geolocation is not None:
                    with st.spinner("📡 Đang lấy GPS hiện tại…"):
                        _geo = get_geolocation()
                    if _geo and isinstance(_geo, dict):
                        _coords = _geo.get("coords", {})
                        _lat = _coords.get("latitude")
                        _lon = _coords.get("longitude")
                        if _lat is not None and _lon is not None:
                            _gps_payload = {
                                "lat": float(_lat),
                                "lon": float(_lon),
                                "acc": _coords.get("accuracy"),
                                "ts": 0.0,
                                "source": "sos_get_geolocation_click",
                            }

                if _gps_payload:
                    _lat = float(_gps_payload["lat"])
                    _lon = float(_gps_payload["lon"])
                    _acc = _gps_payload.get("acc")
                    st.session_state["sos_location_input"] = f"{_lat:.6f},{_lon:.6f}"
                    st.session_state["nav_gps_lat"] = _lat
                    st.session_state["nav_gps_lon"] = _lon
                    st.session_state["nav_gps_ts"] = _gps_payload.get("ts", 0.0) or 0.0
                    st.session_state["nav_gps_source"] = _gps_payload.get("source", "sos_button")
                    _acc_txt = f" ±{float(_acc):.0f}m" if _acc else ""
                    st.success(f"✅ Đã lấy vị trí hiện tại: {_lat:.5f}, {_lon:.5f}{_acc_txt}")
                else:
                    st.warning("⏳ Chưa lấy được GPS. Hãy bấm Cho phép vị trí trên trình duyệt, đợi 1–3 giây rồi bấm lại.")

        loc_sos=st.text_input("📍 Vị trí", key="sos_location_input", placeholder="Bấm 'Lấy vị trí hiện tại' hoặc nhập địa chỉ/tọa độ")
        msg=st.text_area("Mô tả",height=80)
    with col_b:
        st.markdown("### 📞 Số khẩn cấp VN")
        st.table({"Dịch vụ":["🚓 Công an","🚒 Cứu hỏa","🚑 Cấp cứu","🏔️ Cứu nạn"],
                  "Số":["113","114","115","1800 599 920"]})
    if st.button("🆘 KÍCH HOẠT SOS",type="primary",use_container_width=True):
        lat,lon=resolve_location(loc_sos,maps_api) if loc_sos else (None,None)

                                                                                                               
        if (not lat or not lon) and st.session_state.get("nav_gps_lat") is not None and st.session_state.get("nav_gps_lon") is not None:
            lat, lon = float(st.session_state["nav_gps_lat"]), float(st.session_state["nav_gps_lon"])

        if not lat or not lon:
            st.error("❌ Chưa có vị trí SOS hợp lệ. Hãy bấm **📡 Lấy vị trí hiện tại** hoặc nhập tọa độ/địa chỉ trước khi kích hoạt SOS.")
            st.stop()

        result=sos.trigger_sos(lat,lon,"user_001",etype,msg)
        st.error("🔴 SOS ĐÃ KÍCH HOẠT!")
        st.code(f"ID: {result['sos_id']}\nVị trí: {result['location_url']}")
        for c in result["contacts"]: st.markdown(f"**{c['name']}**: 📞 `{c['number']}`")
        for inst in result["instructions"]: st.markdown(f'<div class="step-box">{inst}</div>',unsafe_allow_html=True)
        st.code(result["message_template"])
        _contacts = _ts_sos_get_family_contacts_safe()
        if _contacts:
            _numbers = ",".join(_sos_normalize_phone_for_sms(c.get("phone")) for c in _contacts)
            _sms_body = _sos_message_template({"accident":"Tai nạn","medical":"Cấp cứu y tế","fire":"Cháy","stranded":"Mắc kẹt","general":"Khẩn cấp khác"}.get(etype, etype), lat, lon, msg)
            st.link_button("📨 Mở SMS gửi tất cả số người thân", _sos_build_sms_link(_numbers, _sms_body), use_container_width=True)
        else:
            st.warning("Bạn chưa nhập số người thân trong sidebar nên chưa thể mở SMS gửi người thân.")


                                                                                 
                      
                                                                                 
elif "cộng đồng" in menu:
    st.title("📍 Báo cáo cộng đồng")

                                                                           
                                                                                             
    try:
        components.html(_build_gps_preload_html(interval_ms=1000, hidden=True), height=1, scrolling=False)
    except Exception:
        pass
    if "crowd_report_location_input" not in st.session_state:
        st.session_state["crowd_report_location_input"] = ""

    tab1,tab2=st.tabs(["Xem báo cáo","Gửi báo cáo"])
    with tab1:
        loc_inp=st.text_input("📍 Vị trí trung tâm"); radius=st.slider("Bán kính (km)",5,100,30)
        if st.button("🔍 Tìm báo cáo"):
            lat,lon=resolve_location(loc_inp,maps_api)
            if lat:
                reports_raw=crowd.get_nearby_reports(lat,lon,radius)
                reports, expired_reports = _ts_filter_active_crowd_reports(reports_raw, crowd_engine=crowd, current_user="user_001")
                st.info(f"Tìm thấy **{len(reports)}** báo cáo còn hiệu lực trong {radius} km")
                if expired_reports:
                    st.caption(f"🕒 Đã ẩn/tự dọn {len(expired_reports)} báo cáo hết hiệu lực. " + _ts_crowd_report_ttl_note())
                else:
                    st.caption(_ts_crowd_report_ttl_note())
                if reports:
                    mm=folium.Map([lat,lon],zoom_start=11,
                        tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",attr="© OSM")
                    RI={"accident":("red","exclamation-sign"),"flood":("blue","tint"),
                        "traffic_jam":("orange","road"),"bad_road":("orange","warning-sign"),
                        "landslide":("darkred","ban-circle")}
                    for r in reports:
                        c,ic=RI.get(r["type"],("gray","info-sign"))
                        folium.Marker([r["lat"],r["lon"]],
                            popup=folium.Popup(f"<b>{r['icon']} {r['label']}</b><br>{r.get('description','')}",max_width=200),
                            tooltip=f"{r['icon']} {r['label']} – {r['distance_km']} km",
                            icon=folium.Icon(color=c,icon=ic,prefix="glyphicon"),
                        ).add_to(mm)
                    components.html(mm._repr_html_(),height=420,scrolling=False)
                for r in reports[:10]:
                    st.markdown(f"**{r['icon']} {r['label']}** — {r['distance_km']} km")
                    _expiry_label = r.get("__expiry_label") or ""
                    _expiry_suffix = f" · 🕒 {_expiry_label}" if _expiry_label else ""
                    st.caption(f"{r.get('description','')} · 👍 {r.get('upvotes',0)}{_expiry_suffix}")
                    if r.get("user_id") == "user_001":
                        can_delete, delete_msg = crowd.can_delete_report(r, "user_001")
                        if can_delete:
                            st.caption("🗑️ Bạn có thể tự xóa báo cáo này trong 15 phút đầu")
                            if st.button("Xóa báo cáo", key=f"del_{r['id']}"):
                                result = crowd.delete_report(r["id"], "user_001")
                                if result.get("success"):
                                    st.success("✅ Đã xóa báo cáo")
                                    st.rerun()
                                else:
                                    st.error(result.get("error", "Không thể xóa báo cáo"))
                        else:
                            st.caption(f"🔒 {delete_msg}")
    with tab2:
        gps_col1, gps_col2 = st.columns([1, 2])
        with gps_col1:
            use_crowd_gps = st.button("📡 Lấy vị trí hiện tại", key="btn_crowd_use_current_gps", use_container_width=True)
        with gps_col2:
            if st.session_state.get("nav_gps_lat") is not None and st.session_state.get("nav_gps_lon") is not None:
                st.caption(f"GPS gần nhất: {float(st.session_state['nav_gps_lat']):.5f}, {float(st.session_state['nav_gps_lon']):.5f}")
            else:
                st.caption("Bấm nút để xin quyền GPS cho vị trí báo cáo")

        if use_crowd_gps:
            if not _JSEVAL_OK:
                st.error("Thiếu thư viện `streamlit-js-eval`. Chạy: `pip install streamlit-js-eval`")
            else:
                _gps_payload = None
                try:
                    _gps_payload = _read_latest_gps_from_browser(max_age_sec=600, key="crowd_gps_button_read")
                except Exception:
                    _gps_payload = None

                                                                                       
                if not _gps_payload and get_geolocation is not None:
                    with st.spinner("📡 Đang lấy GPS hiện tại…"):
                        _geo = get_geolocation()
                    if _geo and isinstance(_geo, dict):
                        _coords = _geo.get("coords", {})
                        _lat = _coords.get("latitude")
                        _lon = _coords.get("longitude")
                        if _lat is not None and _lon is not None:
                            _gps_payload = {
                                "lat": float(_lat),
                                "lon": float(_lon),
                                "acc": _coords.get("accuracy"),
                                "ts": 0.0,
                                "source": "crowd_get_geolocation_click",
                            }

                if _gps_payload:
                    _lat = float(_gps_payload["lat"])
                    _lon = float(_gps_payload["lon"])
                    _acc = _gps_payload.get("acc")
                    st.session_state["crowd_report_location_input"] = f"{_lat:.6f},{_lon:.6f}"
                    st.session_state["nav_gps_lat"] = _lat
                    st.session_state["nav_gps_lon"] = _lon
                    st.session_state["nav_gps_ts"] = _gps_payload.get("ts", 0.0) or 0.0
                    st.session_state["nav_gps_source"] = _gps_payload.get("source", "crowd_report_button")
                    _acc_txt = f" ±{float(_acc):.0f}m" if _acc else ""
                    st.success(f"✅ Đã lấy vị trí báo cáo: {_lat:.5f}, {_lon:.5f}{_acc_txt}")
                else:
                    st.warning("⏳ Chưa lấy được GPS. Hãy bấm Cho phép vị trí trên trình duyệt, đợi 1–3 giây rồi bấm lại.")

        r_loc=st.text_input("📍 Vị trí sự cố", key="crowd_report_location_input", placeholder="Bấm 'Lấy vị trí hiện tại' hoặc nhập địa chỉ/tọa độ")

                                                                      
                                                                                            
                                                                      
        _crowd_report_types = getattr(crowd, "REPORT_TYPES", {}) or {}
        _crowd_exclude_words = (
            "trạm xăng", "tram xang", "xăng", "xang", "fuel", "gas", "gas_station",
            "điểm nghỉ", "diem nghi", "nghỉ tốt", "nghi tot", "rest", "rest_stop", "rest_area",
        )
        _crowd_type_options = []
        for _k, _meta in _crowd_report_types.items():
            _label = str((_meta or {}).get("label", _k))
            _text = f"{_k} {_label}".lower()
            if any(_bad in _text for _bad in _crowd_exclude_words):
                continue
            _crowd_type_options.append(_k)
        if not _crowd_type_options:
            _crowd_type_options = list(_crowd_report_types.keys())

        r_type=st.selectbox("Loại sự cố", _crowd_type_options,
            format_func=lambda x:f"{crowd.REPORT_TYPES[x]['icon']} {crowd.REPORT_TYPES[x]['label']}")
        r_desc=st.text_area("Mô tả",height=80); r_sev=st.slider("Mức độ",1,5,3)
        if st.button("📤 Gửi báo cáo",type="primary"):
            lat,lon=resolve_location(r_loc,maps_api) if r_loc else (None,None)

                                                                                                   
            if (not lat or not lon) and st.session_state.get("nav_gps_lat") is not None and st.session_state.get("nav_gps_lon") is not None:
                lat, lon = float(st.session_state["nav_gps_lat"]), float(st.session_state["nav_gps_lon"])

            if not lat or not lon:
                st.error("❌ Chưa có vị trí báo cáo hợp lệ. Hãy bấm **📡 Lấy vị trí hiện tại** hoặc nhập tọa độ/địa chỉ trước khi gửi.")
            else:
                res=crowd.submit_report(lat,lon,r_type,"user_001",r_desc,r_sev)
                if res["success"]: st.success(f"✅ ID: `{res['report_id']}`")
                else: st.error(res.get("error","Lỗi"))


                                                                                 
                   
                                                                                 
elif "tham quan" in menu:
    st.title("🏛️ Gợi ý điểm tham quan")
    st.caption("Tìm quanh điểm cụ thể. Để xem dọc hành trình → vào **Tìm đường**.")
    loc_inp=st.text_input("📍 Vị trí")
    style=st.selectbox("Phong cách",["all","adventure","culture","food","relaxation","family"],
        format_func=lambda x:{"all":"🌐 Tất cả","adventure":"🏔️ Mạo hiểm","culture":"🏛️ Văn hoá",
            "food":"🍜 Ẩm thực","relaxation":"🏖️ Nghỉ dưỡng","family":"👨‍👩‍👧 Gia đình"}[x])
    radius=st.slider("Bán kính (km)",10,200,50)
    if st.button("🔍 Tìm",type="primary"):
        lat,lon=resolve_location(loc_inp,maps_api)
        if lat:
            pois=poi_engine.get_pois_near_point(lat,lon,style=style,radius_km=radius)
            if not pois: st.info("Không tìm thấy.")
            else:
                mm=folium.Map([lat,lon],zoom_start=9,
                    tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",attr="© OSM")
                folium.Marker([lat,lon],tooltip="Vị trí",
                    icon=folium.Icon(color="green",icon="user",prefix="glyphicon")).add_to(mm)
                for p in pois:
                    folium.Marker([p["lat"],p["lon"]],
                        popup=folium.Popup(f"<b>{p['name']}</b><br>⭐{p.get('rating','?')}",max_width=180),
                        tooltip=f"⭐ {p['name']}",
                        icon=folium.Icon(color="blue",icon="star",prefix="glyphicon"),
                    ).add_to(mm)
                components.html(mm._repr_html_(),height=400,scrolling=False)
                for p in pois:
                    with st.expander(f"📍 {p['name']} — ⭐{p.get('rating','?')} · {p.get('dist_from_route_km','?')} km"):
                        c1,c2=st.columns([2,1])
                        with c1:
                            story=ai_engine.generate_cultural_story(p["name"],p.get("province",""),p.get("tags",[]))
                            st.markdown(f"*{story}*")
                        with c2:
                            st.metric("Khoảng cách",f"{p.get('dist_from_route_km','?')} km")
                            st.metric("Rating",f"{p.get('rating','?')}/5")


                                                                                 
                     
                                                                                 
elif "Ký ức" in menu:
    from features.camera_component import get_camera_html
    import os

    EMOTION_LABELS = {1:"😞", 2:"😐", 3:"😊", 4:"😄", 5:"🤩"}

    st.title("📔 Ký ức hành trình")

    tab_new, tab_add, tab_view = st.tabs([
        "▶️ Bắt đầu hành trình",
        "📌 Thêm điểm dừng & Media",
        "📂 Xem hành trình cũ",
    ])

                                                                                
                            
                                                                                
    with tab_new:
        st.subheader("Tạo hành trình mới")
        c1, c2 = st.columns(2)
        with c1:
            trip_title = st.text_input("Tên chuyến đi", "Hành trình của tôi")
            orig_name  = st.text_input("📍 Điểm xuất phát")
        with c2:
            dest_name = st.text_input("🏁 Điểm đến")
            st.text_area("Ghi chú ban đầu (tuỳ chọn)", height=68)

        if st.button("▶️ Bắt đầu hành trình", type="primary", use_container_width=True):
            trip = memory.start_trip("user_001", trip_title, orig_name, dest_name)
            st.session_state["current_trip_id"] = trip["trip_id"]
            st.success(f"✅ Hành trình **{trip_title}** đã bắt đầu!")
            st.info("Chuyển sang tab **📌 Thêm điểm dừng & Media** để ghi lại kỷ niệm.")

        cur_id = st.session_state.get("current_trip_id")
        if cur_id:
            cur = memory.get_trip(cur_id)
            if cur:
                st.divider()
                st.markdown(
                    f'<div class="alert-info">🚗 Đang ghi: <b>{cur["title"]}</b> '
                    f'({cur.get("origin","?")} → {cur.get("destination","?")})'
                    f'<br>ID: <code>{cur_id}</code></div>',
                    unsafe_allow_html=True)
                s = cur.get("summary", {})
                mc1, mc2, mc3 = st.columns(3)
                mc1.metric("Điểm dừng", s.get("total_checkpoints", 0))
                mc2.metric("Cảm xúc TB", f"{s.get('avg_emotion',0):.1f}/5")
                mc3.metric("Ảnh/Video",  s.get("total_media", 0))
                if st.button("⏹ Kết thúc hành trình", type="secondary"):
                    st.session_state.pop("current_trip_id", None)
                    st.success("✅ Đã kết thúc và lưu hành trình.")
                    st.rerun()

                                                                                
                                     
                                                                                
    with tab_add:
        cur_id = st.session_state.get("current_trip_id")
        if not cur_id:
            st.warning("⚠️ Chưa có hành trình đang chạy. Vào tab **▶️ Bắt đầu** trước.")
        else:
            cur = memory.get_trip(cur_id)
            st.markdown(
                f'<div class="alert-info">📍 Hành trình: <b>{cur["title"]}</b> '
                f'— <code>{cur_id}</code></div>',
                unsafe_allow_html=True)

                                                                            
            with st.expander("📝 Thông tin điểm dừng", expanded=True):
                fc1, fc2 = st.columns(2)
                with fc1:
                    cp_loc  = st.text_input("📍 Vị trí",
                        placeholder="VD: Đà Lạt hoặc 11.94,108.44", key="cp_loc")
                    cp_name = st.text_input("Tên địa điểm", key="cp_name")
                    cp_note = st.text_area("Ghi chú / cảm nhận", height=80, key="cp_note")
                with fc2:
                    cp_emotion = st.select_slider(
                        "Cảm xúc lúc này",
                        options=[1, 2, 3, 4, 5],
                        format_func=lambda v: {
                            1:"😞 Buồn", 2:"😐 Bình thường",
                            3:"😊 Vui",  4:"😄 Rất vui", 5:"🤩 Tuyệt vời!"}[v],
                        value=3, key="cp_emo")
                    cp_music   = st.text_input("🎵 Nhạc đang nghe", key="cp_music")
                    cp_weather = st.selectbox("🌤️ Thời tiết",
                        ["☀️ Nắng","🌤️ Có mây","🌧️ Mưa nhỏ",
                         "⛈️ Mưa to","🌫️ Sương mù","❄️ Lạnh"],
                        key="cp_weather")

                                                                            
            st.subheader("📷 Chụp ảnh & Quay video")

            cam_tab, upload_tab = st.tabs(["📷 Camera trực tiếp", "📁 Upload file"])

            with cam_tab:
                                     
                st.markdown(
                    '<div class="alert-info" style="margin-bottom:8px">'
                    '<b>Bước 1:</b> Chụp ảnh hoặc quay video — file sẽ tự tải về máy bạn.</div>',
                    unsafe_allow_html=True)
                components.html(get_camera_html(), height=500, scrolling=False)

                                                
                st.markdown(
                    '<div class="alert-success" style="margin-top:10px">'
                    '<b>Bước 2:</b> Upload file vừa tải về để lưu vào ký ức hành trình.</div>',
                    unsafe_allow_html=True)
                cam_uploads = st.file_uploader(
                    "📂 Chọn ảnh/video vừa tải về (tripsmart_photo_... hoặc tripsmart_video_...)",
                    type=["jpg","jpeg","png","webp","mp4","webm","mov"],
                    accept_multiple_files=True,
                    key="cam_uploads")

                if cam_uploads:
                    st.success(f"✅ Đã chọn {len(cam_uploads)} file")
                    prev_cols = st.columns(min(len(cam_uploads), 4))
                    for i, uf in enumerate(cam_uploads[:4]):
                        with prev_cols[i]:
                            if uf.type.startswith("image"):
                                st.image(uf, use_container_width=True)
                            else:
                                st.video(uf)
                            st.caption(uf.name)

            with upload_tab:
                st.caption("Upload ảnh hoặc video từ thư viện máy / điện thoại.")
                lib_uploads = st.file_uploader(
                    "📁 Chọn ảnh hoặc video",
                    type=["jpg","jpeg","png","webp","mp4","mov","webm","avi"],
                    accept_multiple_files=True,
                    key="lib_uploads")

                if lib_uploads:
                    st.success(f"✅ Đã chọn {len(lib_uploads)} file")
                    prev_cols = st.columns(min(len(lib_uploads), 4))
                    for i, uf in enumerate(lib_uploads[:4]):
                        with prev_cols[i]:
                            if uf.type.startswith("image"):
                                st.image(uf, use_container_width=True)
                            else:
                                st.video(uf)
                            st.caption(uf.name)

                                                                           
            st.divider()
            if st.button("💾 Lưu điểm dừng vào ký ức", type="primary",
                         use_container_width=True, key="btn_save_cp"):

                lat, lon = resolve_location(cp_loc, maps_api)
                if not lat:
                    st.error("❌ Không tìm được vị trí. Thử nhập dạng `lat,lon`.")
                else:
                    saved_media = []

                                                      
                    all_files = list(st.session_state.get("cam_uploads") or []) + \
                                list(st.session_state.get("lib_uploads") or [])

                    for uf in all_files:
                        try:
                            uf.seek(0)
                            fp = memory.save_media_file(cur_id, uf)
                            saved_media.append(fp)
                        except Exception as e:
                            st.warning(f"Lỗi lưu {uf.name}: {e}")

                    cp = memory.add_checkpoint(
                        trip_id    = cur_id,
                        lat        = lat,
                        lon        = lon,
                        name       = cp_name or cp_loc,
                        emotion    = cp_emotion,
                        note       = cp_note,
                        weather    = cp_weather,
                        speed_kmh  = 0,
                        music      = cp_music,
                        media_paths= saved_media,
                    )

                    n = len(saved_media)
                    st.success(
                        f"✅ Đã lưu **{cp_name or cp_loc}** "
                        f"{EMOTION_LABELS.get(cp_emotion,'😊')}  \n"
                        + (f"📎 {n} file media đã lưu vào ký ức." if n
                           else "📝 Ghi chú đã lưu (không có media)."))
                    st.rerun()

                                                                                
                               
                                                                                
    with tab_view:
        st.subheader("Tất cả hành trình đã lưu")
        trips = memory.get_user_trips("user_001")

        if not trips:
            st.info("Chưa có hành trình nào. Tạo hành trình ở tab **▶️ Bắt đầu**!")
        else:
            for t in trips:
                s          = t.get("summary", {})
                is_current = t["trip_id"] == st.session_state.get("current_trip_id")
                badge      = " 🟢 *Đang chạy*" if is_current else ""

                with st.expander(
                    f"📅 **{t['title']}**{badge}  —  "
                    f"{t.get('origin','?')} → {t.get('destination','?')}  "
                    f"| {s.get('mood_summary','')}  "
                    f"| {s.get('total_checkpoints',0)} điểm  "
                    f"| 📎 {s.get('total_media',0)} media",
                    expanded=is_current,
                ):
                                                                                             
                    _head_l, _head_r = st.columns([5, 1.25])
                    with _head_l:
                        st.markdown(f"**{t['title']}**{badge}")
                    with _head_r:
                        _confirm_key = f"confirm_delete_trip_{t['trip_id']}"
                        if st.button("🗑️ Xóa", key=f"quick_del_trip_{t['trip_id']}", type="secondary", use_container_width=True):
                            st.session_state[_confirm_key] = True

                    if st.session_state.get(_confirm_key):
                        st.warning("Xác nhận xóa ký ức này? Dữ liệu đã xóa không khôi phục trong app.")
                        _dc1, _dc2 = st.columns(2)
                        with _dc1:
                            if st.button("✅ Xóa thật", key=f"confirm_del_trip_yes_{t['trip_id']}", use_container_width=True):
                                memory.delete_trip(t["trip_id"])
                                if is_current:
                                    st.session_state.pop("current_trip_id", None)
                                st.session_state.pop(_confirm_key, None)
                                st.success("✅ Đã xóa ký ức hành trình.")
                                st.rerun()
                        with _dc2:
                            if st.button("Hủy", key=f"confirm_del_trip_no_{t['trip_id']}", use_container_width=True):
                                st.session_state.pop(_confirm_key, None)
                                st.rerun()

                    hc1, hc2, hc3, hc4 = st.columns(4)
                    hc1.metric("Điểm dừng",  s.get("total_checkpoints", 0))
                    hc2.metric("Cảm xúc TB", f"{s.get('avg_emotion',0):.1f}/5")
                    hc3.metric("Ảnh/Video",  s.get("total_media", 0))
                    hc4.metric("Khoảnh khắc đẹp", s.get("best_emotion",""))

                    if s.get("best_moment"):
                        st.success(f"🌟 **{s['best_moment']}** — khoảnh khắc tuyệt nhất")

                    recap = ai_engine.generate_trip_recap(t)
                    if recap:
                        st.markdown(f"*{recap}*")

                    st.divider()

                                         
                    checkpoints = t.get("checkpoints", [])
                    if not checkpoints:
                        st.info("Chưa có điểm dừng nào.")
                    else:
                        st.markdown(f"**🗺️ Hành trình ({len(checkpoints)} điểm dừng)**")
                        for i, cp in enumerate(checkpoints):
                            emo   = cp.get("emotion_label", "😊")
                            ts    = cp.get("timestamp","")[:16].replace("T"," ")
                            media = cp.get("media", [])

                            cc1, cc2 = st.columns([3, 1])
                            with cc1:
                                parts = [f"🕐 {ts}"]
                                if cp.get("weather"): parts.append(f"🌤️ {cp['weather']}")
                                if cp.get("music"):   parts.append(f"🎵 *{cp['music']}*")
                                st.markdown(
                                    f"**{i+1}. {emo} {cp.get('name','Điểm dừng')}**  \n"
                                    + " &nbsp;|&nbsp; ".join(parts))
                                if cp.get("note"):
                                    st.caption(f"💬 {cp['note']}")
                            with cc2:
                                st.caption(
                                    f"📍 {cp.get('lat',0):.4f}, {cp.get('lon',0):.4f}")
                                if media:
                                    st.caption(f"📎 {len(media)} file")

                                                
                            if media:
                                img_files = [f for f in media if any(
                                    f.lower().endswith(x)
                                    for x in [".jpg",".jpeg",".png",".webp"])]
                                vid_files = [f for f in media if any(
                                    f.lower().endswith(x)
                                    for x in [".mp4",".webm",".mov",".avi"])]

                                if img_files:
                                    cols = st.columns(min(len(img_files), 4))
                                    for j, fp in enumerate(img_files[:4]):
                                        with cols[j]:
                                            if os.path.exists(fp):
                                                st.image(fp, use_container_width=True,
                                                         caption=os.path.basename(fp))
                                            else:
                                                st.caption("⚠️ File không tồn tại")

                                for fp in vid_files[:2]:
                                    if os.path.exists(fp):
                                        st.video(fp)
                                        st.caption(f"🎬 {os.path.basename(fp)}")
                                    else:
                                        st.caption("⚠️ File không tồn tại")

                                              
                            if i < len(checkpoints) - 1:
                                st.markdown(
                                    '<div style="border-left:2px dashed #334155;'
                                    'margin:4px 0 4px 14px;height:18px"></div>',
                                    unsafe_allow_html=True)

                                                                                   

                                                                                 
                     
                                                                                 
elif "thiên tai" in menu or "Sơ tán" in menu:
    st.title("🌪️ Sơ tán thiên tai")
    st.markdown('<div class="alert-danger">🚨 Tìm tuyến sơ tán đến vùng an toàn gần nhất</div>',unsafe_allow_html=True)
    loc_inp=st.text_input("📍 Vị trí hiện tại")
    mode=st.selectbox("Phương tiện",["car","motorbike"],
        format_func=lambda x:{"car":"🚗 Ô tô","motorbike":"🏍️ Xe máy"}[x])
    for z in disaster.get_all_safe_zones():
        st.caption(f"🏠 **{z['name']}** ({z['province']}) — {z['capacity']} người")
    if st.button("🚨 Tìm tuyến sơ tán",type="primary"):
        lat,lon=resolve_location(loc_inp,maps_api)
        if not lat: st.error("❌ Không tìm được vị trí.")
        else:
            with st.spinner("Đang tính..."):
                result=disaster.find_evacuation_route(lat,lon,mode)
            if result.get("error"): st.error(result["error"])
            else:
                zone=result["safe_zone"]; rt=result["route"]
                st.success(f"🏠 **{zone['name']}** — {zone['distance_km']} km")
                if rt:
                    c1,c2=st.columns(2)
                    c1.metric("📏 Khoảng cách",rt.get("distance_text","?"))
                    c2.metric("⏱️ Thời gian",rt.get("duration_text","?"))
                colored=risk_engine.score_polyline_segments(rt.get("polyline",[]) if rt else [])
                evac_html=make_full_map(lat,lon,zone["lat"],zone["lon"],
                    colored_segments=colored,
                    route_polyline=rt.get("polyline",[]) if rt else [],
                    danger_markers=[],rest_suggestions=[],pois=[])
                components.html(evac_html,height=450,scrolling=False)
                for w in result.get("warnings",[]): st.markdown(f'<div class="alert-danger">{w}</div>',unsafe_allow_html=True)
                for inst in result.get("instructions",[]): st.markdown(f'<div class="step-box">{inst}</div>',unsafe_allow_html=True)


                                                                                 
              
                                                                                 
elif "Thời tiết" in menu:
    st.title("🌤️ Thời tiết & Rủi ro")
    loc_inp=st.text_input("📍 Địa điểm",placeholder="VD: Đà Lạt")
    if st.button("🔍 Xem thời tiết",type="primary"):
        lat,lon=resolve_location(loc_inp,maps_api) if loc_inp else (11.9404,108.4383)
        if not lat: lat,lon=11.9404,108.4383
        with st.spinner("Đang tải..."): wr=weather_api.get_weather_risk(lat,lon)
        w=wr.get("weather",{}); rs=wr.get("risk_score",0)
        c1,c2,c3,c4=st.columns(4)
        temp=w.get("temp_c")
        feels=w.get("feels_like_c")
        humidity=w.get("humidity_pct")
        wind=w.get("wind_speed_ms")
        c1.metric("🌡️ Nhiệt độ",f"{temp}°C" if temp is not None else "N/A")
        c2.metric("🌡️ Cảm giác",f"{feels}°C" if feels is not None else "N/A")
        c3.metric("💧 Độ ẩm",f"{humidity}%" if humidity is not None else "N/A")
        c4.metric("💨 Gió",f"{wind} m/s" if wind is not None else "N/A")
        st.metric("⚠️ Rủi ro",f"{risk_color(rs)} {rs:.0%}")
        st.caption(w.get("description") or "Không lấy được dữ liệu thời tiết")
        st.caption(f"Nguồn dữ liệu: {w.get('source','unknown')}")
        for a in wr.get("alerts",[]): st.markdown(f'<div class="alert-warning">{a}</div>',unsafe_allow_html=True)
        if not wr.get("alerts"): st.markdown('<div class="alert-success">✅ Thời tiết ổn định</div>',unsafe_allow_html=True)
        forecast=weather_api.get_forecast(lat,lon,3)
        if forecast:
            st.subheader("📅 Dự báo 3 ngày")
            fc_cols=st.columns(min(len(forecast[:3]),3))
            for i,f in enumerate(forecast[:3]):
                with fc_cols[i]:
                    st.markdown(f"**{f.get('datetime','')[:10]}**")
                    st.metric("Nhiệt độ",f"{f.get('temp_c','?')}°C")
                    st.caption(f.get("description",""))

                                                                                 
                    
                                                                                 
elif "AI Risk Model" in menu:
    st.title("🤖 AI Risk Model — Random Forest")
    st.markdown(
        '<div class="alert-info">🧠 Mô hình Random Forest dự đoán rủi ro địa lý '
        'dựa trên dữ liệu vùng nguy hiểm Việt Nam</div>',
        unsafe_allow_html=True,
    )

    ml_model = init_ml_model()

    if ml_model is None:
        st.error("❌ Không thể load module `core.ml_risk_model`. Kiểm tra lại cài đặt.")
        st.stop()

                                                                              
    if not ml_model.is_ready:
        st.warning(f"⚠️ Model chưa sẵn sàng: {ml_model.error}")
        if st.button("🔄 Thử train lại"):
            with st.spinner("Đang train model..."):
                ml_model.retrain()
            st.rerun()
        st.stop()

                                                                               
    metrics = ml_model.metrics
    if metrics:
        st.subheader("📊 Hiệu suất mô hình")
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("🎯 Accuracy",    f"{metrics.get('accuracy', 0):.1%}")
        mc2.metric("📐 F1 Macro",    f"{metrics.get('f1_macro', 0):.1%}")
        mc3.metric("⚖️ F1 Weighted", f"{metrics.get('f1_weighted', 0):.1%}")
        mc4.metric("🔁 CV F1",       f"{metrics.get('cv_f1_mean', 0):.1%} ± {metrics.get('cv_f1_std', 0):.1%}")

        ms1, ms2 = st.columns(2)
        ms1.caption(f"📦 Tổng mẫu train: **{metrics.get('n_samples', '?')}**  |  "
                    f"Train: {metrics.get('n_train','?')} / Test: {metrics.get('n_test','?')}")
        ms2.caption(f"🗺️ Số vùng rủi ro: **{metrics.get('n_zones','?')}**  "
                    f"(trong đó từ CSV: {metrics.get('n_csv_zones','?')})")

                                  
        feat_imp = metrics.get("feature_importance", {})
        if feat_imp:
            import pandas as pd
            st.subheader("🔑 Các yếu tố ảnh hưởng nhiều nhất")
            sorted_feats = sorted(feat_imp.items(), key=lambda x: x[1], reverse=True)[:8]
            feat_names_vn = {
                "dist_nearest_km":   "📏 Khoảng cách vùng nguy hiểm",
                "nearest_score":     "⚠️ Điểm rủi ro gần nhất",
                "is_landslide_zone": "🪨 Vùng sạt lở",
                "is_flood_zone":     "🌊 Vùng lũ lụt",
                "is_bad_road_zone":  "🚧 Vùng đường xấu",
                "is_geological_zone":"🏔️ Vùng địa chất yếu",
                "zone_count_5km":    "🔢 Số vùng nguy hiểm (5km)",
                "max_score_10km":    "📈 Score cao nhất (10km)",
                "lat_normalized":    "🧭 Vĩ độ (chuẩn hóa)",
                "lon_normalized":    "🧭 Kinh độ (chuẩn hóa)",
                "lat":               "📍 Vĩ độ",
                "lon":               "📍 Kinh độ",
            }
            df_feat = pd.DataFrame(
                [(feat_names_vn.get(k, k), v) for k, v in sorted_feats],
                columns=["Yếu tố", "Mức độ ảnh hưởng"]
            )
            st.bar_chart(df_feat.set_index("Yếu tố"), use_container_width=True, height=280)

    st.divider()

                                                                              
    st.subheader("🔍 Dự đoán rủi ro tại toạ độ")
    pred_col1, pred_col2 = st.columns(2)

    with pred_col1:
        pred_loc = st.text_input(
            "📍 Địa điểm hoặc toạ độ",
            placeholder="VD: Đà Lạt  hoặc  11.94, 108.44",
            key="ai_pred_loc",
        )

    with pred_col2:
        use_quick = st.selectbox("⚡ Chọn nhanh", [
            "— Nhập thủ công —",
            "TP.HCM (10.77, 106.69)",
            "Hà Nội (21.03, 105.83)",
            "Đà Lạt (11.94, 108.44)",
            "Sa Pa (22.33, 103.84) ⚠️ sạt lở",
            "Đồng Tháp (10.34, 105.32) ⚠️ lũ",
            "Đà Nẵng (16.07, 108.22)",
            "Huế (16.46, 107.59)",
            "Quy Nhơn (13.77, 109.22)",
        ], key="ai_quick")

                        
    _quick_coords = {
        "TP.HCM (10.77, 106.69)":              (10.77, 106.69),
        "Hà Nội (21.03, 105.83)":              (21.03, 105.83),
        "Đà Lạt (11.94, 108.44)":              (11.94, 108.44),
        "Sa Pa (22.33, 103.84) ⚠️ sạt lở":    (22.33, 103.84),
        "Đồng Tháp (10.34, 105.32) ⚠️ lũ":   (10.34, 105.32),
        "Đà Nẵng (16.07, 108.22)":             (16.07, 108.22),
        "Huế (16.46, 107.59)":                 (16.46, 107.59),
        "Quy Nhơn (13.77, 109.22)":            (13.77, 109.22),
    }

    pred_lat, pred_lon = None, None
    quick_val = st.session_state.get("ai_quick", "— Nhập thủ công —")
    if quick_val in _quick_coords:
        pred_lat, pred_lon = _quick_coords[quick_val]

    if st.button("🤖 Dự đoán rủi ro AI", type="primary", key="ai_predict_btn"):
                                                        
        if pred_lat is None:
            loc_txt = pred_loc.strip()
            if "," in loc_txt:
                try:
                    parts = loc_txt.split(",")
                    pred_lat, pred_lon = float(parts[0].strip()), float(parts[1].strip())
                except ValueError:
                    pass
            if pred_lat is None:
                         
                coords = resolve_location(loc_txt, maps_api)
                if coords and coords[0]:
                    pred_lat, pred_lon = coords

        if pred_lat is None:
            st.error("❌ Không xác định được toạ độ. Hãy nhập dạng `lat, lon` hoặc chọn thành phố nhanh.")
        else:
            with st.spinner("🧠 AI đang phân tích..."):
                result = ml_model.predict(pred_lat, pred_lon)

            if result.get("error"):
                st.error(f"❌ {result['error']}")
            else:
                                                                             
                color   = result["color"]
                emoji   = result["emoji"]
                label   = result["label"]
                conf    = result["confidence"]
                proba   = result.get("proba_pct", {})

                alert_cls = {
                    "Cao":       "alert-danger",
                    "Trung bình":"alert-warning",
                    "Thấp":      "alert-success",
                }.get(label, "alert-info")

                st.markdown(
                    f'<div class="{alert_cls}" style="font-size:1.15rem;padding:14px 18px">'
                    f'{emoji} <b>Mức rủi ro AI dự đoán: {label}</b> &nbsp;·&nbsp; '
                    f'Độ tin cậy: <b>{conf:.0%}</b>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.caption(f"📍 Toạ độ phân tích: `{pred_lat:.4f}, {pred_lon:.4f}`")

                                                                             
                st.subheader("📊 Xác suất từng mức rủi ro")
                pc1, pc2, pc3 = st.columns(3)
                p_vals = result.get("proba", [0, 0, 0])
                pc1.metric("🟢 Thấp",       proba.get("Thấp",       "—"), delta=f"{p_vals[0]:.0%}" if p_vals else None)
                pc2.metric("🟡 Trung bình",  proba.get("Trung bình", "—"), delta=f"{p_vals[1]:.0%}" if p_vals else None)
                pc3.metric("🔴 Cao",         proba.get("Cao",        "—"), delta=f"{p_vals[2]:.0%}" if p_vals else None)

                                                                            
                top_feats = result.get("top_features", [])
                if top_feats:
                    st.subheader("🔬 Yếu tố ảnh hưởng tại vị trí này")
                    feat_names_vn2 = {
                        "dist_nearest_km":   "📏 Khoảng cách vùng nguy hiểm gần nhất",
                        "nearest_score":     "⚠️ Điểm rủi ro vùng gần nhất",
                        "is_landslide_zone": "🪨 Nằm trong vùng sạt lở",
                        "is_flood_zone":     "🌊 Nằm trong vùng lũ lụt",
                        "is_bad_road_zone":  "🚧 Nằm trong vùng đường xấu",
                        "is_geological_zone":"🏔️ Nằm trong vùng địa chất yếu",
                        "zone_count_5km":    "🔢 Số vùng nguy hiểm trong 5km",
                        "max_score_10km":    "📈 Điểm rủi ro cao nhất trong 10km",
                        "lat_normalized":    "🧭 Vĩ độ (vị trí Bắc-Nam)",
                        "lon_normalized":    "🧭 Kinh độ (vị trí Đông-Tây)",
                        "lat":               "📍 Vĩ độ",
                        "lon":               "📍 Kinh độ",
                    }
                    for feat in top_feats:
                        fname   = feat_names_vn2.get(feat["name"], feat["name"])
                        imp_pct = feat["importance"] * 100
                        val     = feat["value"]
                        bar_w   = int(imp_pct * 3)                       
                                                     
                        if feat["name"] in ("is_landslide_zone","is_flood_zone",
                                            "is_bad_road_zone","is_geological_zone"):
                            val_txt = "✅ Có" if val >= 0.5 else "❌ Không"
                        elif feat["name"] == "dist_nearest_km":
                            val_txt = f"{val:.1f} km"
                        elif feat["name"] == "zone_count_5km":
                            val_txt = f"{int(val)} vùng"
                        elif feat["name"] in ("nearest_score","max_score_10km"):
                            val_txt = f"{val:.0%}"
                        else:
                            val_txt = f"{val:.3f}"

                        st.markdown(
                            f"<div style='display:flex;align-items:center;gap:10px;"
                            f"margin:4px 0;font-size:.88rem'>"
                            f"<div style='width:230px'>{fname}</div>"
                            f"<div style='background:{color};height:10px;width:{bar_w}px;"
                            f"border-radius:5px;min-width:4px'></div>"
                            f"<div style='color:#555;min-width:80px'>{imp_pct:.1f}% ảnh hưởng</div>"
                            f"<div style='color:#334;font-weight:600'>{val_txt}</div>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

    st.divider()

                                                                              
    with st.expander("⚙️ Tùy chọn nâng cao", expanded=False):
        st.markdown("**🔄 Huấn luyện lại mô hình**")
        st.caption(
            "Nếu bạn vừa thêm dữ liệu mới vào `data/risk_points_vietnam.csv`, "
            "hãy retrain để model học thêm."
        )
        if st.button("🔁 Retrain ngay", key="ai_retrain"):
            with st.spinner("Đang huấn luyện lại mô hình Random Forest..."):
                result_rt = ml_model.retrain()
            if "error" in result_rt:
                st.error(f"❌ {result_rt['error']}")
            else:
                st.success(
                    f"✅ Retrain xong!  "
                    f"Accuracy: **{result_rt.get('accuracy',0):.1%}**  |  "
                    f"F1 macro: **{result_rt.get('f1_macro',0):.1%}**"
                )
                st.rerun()