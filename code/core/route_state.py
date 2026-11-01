import os
import json
import copy
from datetime import datetime, date, time

import streamlit as st
import streamlit.components.v1 as components

try:
    from streamlit_js_eval import streamlit_js_eval
    _JSEVAL_OK = True
except ImportError:
    streamlit_js_eval = None
    _JSEVAL_OK = False

# thể làm mất last_routes nếu không đóng gói trạng thái tuyến. Bộ snapshot này
# lưu lại tuyến đã tìm trong session, để quay lại Tìm đường không phải tìm lại.
_ROUTE_SNAPSHOT_KEYS = [
    "last_origin", "last_dest", "last_mode", "last_routes", "last_selected",
    "last_compared", "last_polyline", "last_route_km",
    "last_danger_markers", "last_danger_markers_raw", "last_rest_stops",
    "last_poi_style", "last_departure_dt_iso",
    "last_use_human", "last_human_age", "last_human_travel_hour",
    "last_human_motion_sick", "last_human_has_children", "last_human_stress_level",
    "last_eta_custom_speed_enabled", "last_eta_custom_speed_kmh",
    "_route_eta_speed_override_active", "_route_eta_custom_speed_enabled",
    "_route_eta_custom_speed_kmh",
    "route_view_cache", "route_view_cache_key",
    "nav_active", "nav_arrived", "nav_dest", "nav_mode", "nav_polyline",
    "nav_steps", "nav_distance_left_osrm", "nav_gps_lat", "nav_gps_lon",
    "nav_gps_ts", "nav_gps_source",
    "auto_eta_distance_km", "auto_eta_duration_text", "auto_eta_arrival",
    "auto_eta_updated_at", "auto_eta_status", "auto_eta_forecast",
    "auto_eta_ai_ready", "auto_eta_ai_status",
    "copilot_last_action", "copilot_critical_segment",
]
_ROUTE_FILE_CACHE_KEYS = [
    "last_origin", "last_dest", "last_mode", "last_routes", "last_selected",
    "last_polyline", "last_route_km", "last_poi_style", "last_departure_dt_iso",
    "last_use_human", "last_human_age", "last_human_travel_hour",
    "last_human_motion_sick", "last_human_has_children", "last_human_stress_level",
    "last_eta_custom_speed_enabled", "last_eta_custom_speed_kmh",
]

# Cache trình duyệt chỉ sống trong tab hiện tại.
# sessionStorage GIỮ khi người dùng bấm Trang chủ ↔ Tìm đường,
# nhưng TỰ MẤT khi đóng hẳn tab/trình duyệt. Không dùng localStorage/file lâu dài.
_ROUTE_BROWSER_SESSION_KEY = "tripsmart_active_route_state_v1"


def _json_deep_safe(obj):
    """Chuyển object về dạng ghi JSON an toàn để lưu tạm trong browser sessionStorage."""
    try:
        if obj is None or isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, (datetime, date, time)):
            return obj.isoformat()
        if isinstance(obj, tuple):
            return [_json_deep_safe(x) for x in obj]
        if isinstance(obj, list):
            return [_json_deep_safe(x) for x in obj]
        if isinstance(obj, dict):
            return {str(k): _json_deep_safe(v) for k, v in obj.items()}
        return str(obj)
    except Exception:
        return None


def _save_route_snapshot_to_browser_session(snap: dict):
    """Lưu tuyến vào sessionStorage của tab hiện tại; đóng tab là mất."""
    try:
        if not snap or not snap.get("last_routes"):
            return False
        # Chỉ lưu phần cần để dựng lại tuyến; tránh đưa cache quá lớn vào sessionStorage.
        data = _json_safe_route_snapshot(snap)
        data["__ts"] = datetime.now().isoformat()
        payload = json.dumps(_json_deep_safe(data), ensure_ascii=False)
        components.html(
            f"""
            <script>
            try {{
              window.sessionStorage.setItem({_ROUTE_BROWSER_SESSION_KEY!r}, {json.dumps(payload)});
            }} catch(e) {{}}
            </script>
            """,
            height=0,
        )
        return True
    except Exception:
        return False


def _clear_route_snapshot_from_browser_session():
    """Xoá tuyến tạm trong tab khi người dùng bắt đầu tìm tuyến mới."""
    try:
        components.html(
            f"""
            <script>
            try {{ window.sessionStorage.removeItem({_ROUTE_BROWSER_SESSION_KEY!r}); }} catch(e) {{}}
            </script>
            """,
            height=0,
        )
    except Exception:
        pass


def _load_route_snapshot_from_browser_session():
    """Đọc tuyến từ sessionStorage của tab hiện tại, không đọc file/localStorage."""
    if not (_JSEVAL_OK and streamlit_js_eval is not None):
        return {}
    try:
        raw = streamlit_js_eval(
            js_expressions=f"sessionStorage.getItem('{_ROUTE_BROWSER_SESSION_KEY}')",
            key="load_route_session_storage_v1",
        )
        if not raw:
            return {}
        data = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(data, dict) and data.get("last_routes"):
            return data
    except Exception:
        pass
    return {}


def _route_file_cache_path():
    try:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "tripsmart_last_route_cache.json")
    except Exception:
        return "tripsmart_last_route_cache.json"


def _route_pickle_cache_path():
    try:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "tripsmart_last_route_cache.pkl")
    except Exception:
        return "tripsmart_last_route_cache.pkl"


def _json_safe_route_snapshot(snap: dict):
    """Tạo bản snapshot tối giản có thể ghi JSON; nếu route có object lạ thì bỏ qua an toàn."""
    data = {}
    for k in _ROUTE_FILE_CACHE_KEYS:
        if k in snap:
            data[k] = snap.get(k)
    return data


def _delete_persistent_route_cache():
    """Xoá cache tuyến lưu trên ổ đĩa từ các bản cũ.

    Yêu cầu mới: chỉ giữ tuyến khi người dùng đổi Trang chủ ↔ Tìm đường
    trong cùng một phiên web. Nếu tắt hẳn web rồi mở lại thì phải reset sạch,
    nên tuyệt đối không khôi phục tuyến từ file/local cache lâu dài.
    """
    try:
        for _path in [_route_pickle_cache_path(), _route_file_cache_path()]:
            try:
                if _path and os.path.exists(_path):
                    os.remove(_path)
            except Exception:
                pass
    except Exception:
        pass


def _save_route_snapshot_to_file(snap: dict):
    """Không lưu tuyến ra file nữa.

    Tuyến chỉ được giữ trong st.session_state để đổi trang nội bộ không mất.
    Khi đóng hẳn web/tab rồi mở lại, session mới sẽ trống và app reset đúng yêu cầu.
    """
    _delete_persistent_route_cache()
    return False


def _load_route_snapshot_from_file():
    """Không khôi phục tuyến từ file/cache lâu dài nữa."""
    _delete_persistent_route_cache()
    return {}


def _persist_current_route_snapshot():
    """Lưu trạng thái tuyến đang có để đổi menu không làm mất tuyến.

    Cơ chế mới có 2 lớp, nhưng vẫn reset khi đóng tab:
    1) st.session_state: nhanh nhất khi Streamlit rerun bình thường.
    2) browser sessionStorage: cứu trường hợp bấm thẻ Trang chủ dạng link/query param
       làm Streamlit mất một số key tạm. sessionStorage chỉ sống trong tab hiện tại.
    """
    try:
        import copy
        ss = st.session_state
        if not ss.get("last_routes"):
            return False
        snap = {}
        for k in _ROUTE_SNAPSHOT_KEYS:
            if k in ss:
                try:
                    snap[k] = copy.deepcopy(ss[k])
                except Exception:
                    snap[k] = ss[k]
        if snap.get("last_routes"):
            ss["active_route_state"] = snap
            ss["route_state_snapshot"] = snap
            ss["__last_good_route_snapshot"] = snap
            ss["__route_keepalive_ok"] = True
            _save_route_snapshot_to_browser_session(snap)
            return True
    except Exception:
        pass
    return False


def _restore_route_snapshot_if_needed():
    """Khôi phục tuyến đã tìm khi quay lại Tìm đường/Trợ lý.

    Ưu tiên active_route_state trong session. Nếu session mất key tạm do đổi trang
    bằng query link, đọc lại từ browser sessionStorage của chính tab đó.
    Không dùng file/localStorage, nên đóng hẳn tab là reset sạch.
    """
    _WIDGET_KEYS_SKIP = {
        "input_origin", "eta_custom_speed_enabled", "eta_custom_speed_kmh",
        "route_selector", "sel_origin", "sel_dest",
        "btn_use_gps_origin",
    }
    try:
        import copy
        ss = st.session_state
        if ss.get("last_routes"):
            _persist_current_route_snapshot()
            return False

        # Nếu còn cờ đang search nhưng không còn pending candidates thật, đó là cờ cũ bị sót.
        if ss.get("__route_search_in_progress") and not (ss.get("pending_origin_cands") or ss.get("pending_dest_cands")):
            ss.pop("__route_search_in_progress", None)

        snap = (
            ss.get("active_route_state")
            or ss.get("route_state_snapshot")
            or ss.get("__last_good_route_snapshot")
            or {}
        )
        if not snap.get("last_routes"):
            snap = _load_route_snapshot_from_browser_session() or {}

        if not snap.get("last_routes"):
            return False

        # Có snapshot hợp lệ thì được phép khôi phục, kể cả khi cờ search cũ bị sót.
        ss.pop("__route_search_in_progress", None)
        for k, v in snap.items():
            if k in _WIDGET_KEYS_SKIP or str(k).startswith("__"):
                continue
            try:
                ss[k] = copy.deepcopy(v)
            except Exception:
                ss[k] = v

        ss["active_route_state"] = snap
        ss["route_state_snapshot"] = snap
        ss["__last_good_route_snapshot"] = snap
        # Không để phase chọn địa điểm / pending search che mất tuyến đã restore.
        ss.pop("pending_origin_cands", None)
        ss.pop("pending_dest_cands", None)
        ss.pop("pending_route_options", None)
        return True
    except Exception:
        return False


def _clear_pending_route_search_state():
    """Xoá phase tìm địa điểm sau khi đã có tuyến để quay lại trang không tự tính lại."""
    for _k in ["pending_origin_cands", "pending_dest_cands", "pending_route_options", "sel_origin", "sel_dest"]:
        try:
            st.session_state.pop(_k, None)
        except Exception:
            pass

