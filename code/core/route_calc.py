# core/route_calc.py
# Các hàm tính toán dùng chung: risk màu, khoảng cách, ETA, forecast, cache tuyến.

import json
import math
from datetime import datetime, date, time, timedelta

import streamlit as st
from core.route_risk_forecast import analyze_route_risk_by_time

RED_RISK_THRESHOLD = 0.85
ORANGE_RISK_THRESHOLD = 0.65
YELLOW_RISK_THRESHOLD = 0.40

AVG_SPEED_KMH_BY_MODE = {
    "car": 40.0,
    "motorbike": 40.0,
    "bike": 20.0,
    "walk": 5.0,
}

def _risk_score_float(s):
    try:
        return float(s or 0.0)
    except Exception:
        return 0.0


def _risk_level_icon(s):
    s = _risk_score_float(s)
    if s >= RED_RISK_THRESHOLD:
        return "🔴"
    if s >= ORANGE_RISK_THRESHOLD:
        return "🟠"
    if s >= YELLOW_RISK_THRESHOLD:
        return "🟡"
    return "🟢"


def _risk_alert_css(s):
    return "alert-danger" if _risk_score_float(s) >= RED_RISK_THRESHOLD else "alert-warning"


def risk_color(s):
    return _risk_level_icon(s)


def _haversine_km(lat1, lon1, lat2, lon2):
    """Khoảng cách đường chim bay (km) giữa 2 toạ độ."""
    R = 6371.0
    rl = math.radians
    dlat = rl(lat2 - lat1); dlon = rl(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(rl(lat1))*math.cos(rl(lat2))*math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def _find_nearest_segment(gps_lat, gps_lon, polyline):
    """
    Trả về dict: {segment_idx, lat, lon, dist_km, progress_ratio}
    polyline: list [[lon, lat], ...]  (OSRM format — lon trước)
    """
    best_idx, best_dist = 0, 999.0
    for i, pt in enumerate(polyline):
        lon_p, lat_p = pt[0], pt[1]
        d = _haversine_km(gps_lat, gps_lon, lat_p, lon_p)
        if d < best_dist:
            best_dist = d
            best_idx = i
    return {
        "segment_idx"    : best_idx,
        "lat"            : polyline[best_idx][1],
        "lon"            : polyline[best_idx][0],
        "dist_km"        : round(best_dist, 3),
        "progress_ratio" : best_idx / max(1, len(polyline) - 1),
    }


def _calc_iot_state_from_gps(gps_lat, gps_lon, danger_markers, total_km):
    """
    Tính trạng thái IoT (safe/warning/danger) dựa trên GPS thật.
    danger_markers: list dict có keys lat,lon,score,route_km,label,...
    Trả về dict trạng thái đầy đủ.
    """
    # Tìm điểm nguy hiểm gần nhất (theo tọa độ thật)
    nearest_danger = None
    nearest_dist   = 999.0
    for seg in danger_markers:
        seg_lat = seg.get("lat") or seg.get("center_lat")
        seg_lon = seg.get("lon") or seg.get("center_lon")
        if seg_lat is None or seg_lon is None:
            continue
        d = _haversine_km(gps_lat, gps_lon, seg_lat, seg_lon)
        if d < nearest_dist:
            nearest_dist   = d
            nearest_danger = seg

    # Điểm nguy hiểm phía trước (dùng route_km nếu không có tọa độ)
    next_danger  = None
    next_danger_dist = 999.0
    for seg in sorted(danger_markers, key=lambda x: x.get("route_km", 0)):
        seg_lat = seg.get("lat") or seg.get("center_lat")
        seg_lon = seg.get("lon") or seg.get("center_lon")
        if seg_lat and seg_lon:
            d = _haversine_km(gps_lat, gps_lon, seg_lat, seg_lon)
            if d > 0.05:   # Bỏ qua điểm đang đứng trên nó
                next_danger      = seg
                next_danger_dist = d
                break

    cur_score = float(nearest_danger.get("score", 0)) if nearest_danger and nearest_dist < 1.0 else 0.0

    if cur_score >= RED_RISK_THRESHOLD:
        state = "danger"
    elif cur_score >= ORANGE_RISK_THRESHOLD or nearest_dist < 2.0:
        state = "warning"
    elif next_danger_dist < 5.0:
        state = "warning"
    else:
        state = "safe"

    return {
        "state"           : state,
        "nearest_danger"  : nearest_danger,
        "nearest_dist"    : round(nearest_dist, 2),
        "next_danger"     : next_danger,
        "next_danger_dist": round(next_danger_dist, 2),
        "cur_score"       : cur_score,
    }


def _default_avg_speed_kmh_by_mode(mode: str) -> float:
    """Tốc độ ETA mặc định theo phương tiện."""
    return float(AVG_SPEED_KMH_BY_MODE.get(str(mode or "car"), 40.0))


def _avg_speed_kmh_by_mode(mode: str) -> float:
    """
    Tốc độ trung bình dùng riêng cho tính ETA.

    Lưu ý quan trọng cho Streamlit:
    - `eta_custom_speed_enabled` và `eta_custom_speed_kmh` là key của widget.
    - Không được ghi đè các key này sau khi widget đã được tạo trong cùng một lần rerun,
      nếu không sẽ gây StreamlitAPIException.
    - Vì vậy khi đã bấm Tìm đường, app dùng bộ key nội bộ `_route_eta_*` để
      đóng băng tốc độ ETA của tuyến đang hiển thị.
    """
    default_speed = _default_avg_speed_kmh_by_mode(mode)
    try:
        if st.session_state.get("_route_eta_speed_override_active"):
            enabled = bool(st.session_state.get("_route_eta_custom_speed_enabled", False))
            custom_speed = float(st.session_state.get("_route_eta_custom_speed_kmh") or default_speed)
        else:
            enabled = bool(st.session_state.get("eta_custom_speed_enabled", False))
            custom_speed = float(st.session_state.get("eta_custom_speed_kmh") or default_speed)
        if enabled and custom_speed > 0:
            return custom_speed
    except Exception:
        pass
    return default_speed


def _format_speed_label(mode: str) -> str:
    sp = _avg_speed_kmh_by_mode(mode)
    if float(sp).is_integer():
        return f"{int(sp)} km/h"
    return f"{sp:g} km/h"


def _format_default_speed_label(mode: str) -> str:
    sp = _default_avg_speed_kmh_by_mode(mode)
    if float(sp).is_integer():
        return f"{int(sp)} km/h"
    return f"{sp:g} km/h"


def _duration_seconds_by_distance_mode(distance_km, mode: str) -> float:
    """Tính thời gian đi dự kiến từ quãng đường và tốc độ trung bình theo mode."""
    try:
        dist = float(distance_km or 0)
        speed = _avg_speed_kmh_by_mode(mode)
        if dist <= 0 or speed <= 0:
            return 0.0
        return dist / speed * 3600.0
    except Exception:
        return 0.0


def _distance_km_from_polyline(polyline) -> float:
    """Fallback: tính độ dài polyline [lon,lat] bằng haversine nếu route thiếu distance_km."""
    try:
        if not polyline or len(polyline) < 2:
            return 0.0
        total = 0.0
        for a, b in zip(polyline[:-1], polyline[1:]):
            total += _haversine_km(a[1], a[0], b[1], b[0])
        return float(total)
    except Exception:
        return 0.0


def _get_route_distance_km(route: dict) -> float:
    """Lấy quãng đường route theo nhiều nguồn, ưu tiên distance_km từ router."""
    if not isinstance(route, dict):
        return 0.0
    for key in ("distance_km", "distance", "total_distance_km"):
        val = route.get(key)
        if isinstance(val, (int, float)) and float(val) > 0:
            # Nếu key distance có vẻ là mét thì đổi sang km.
            if key == "distance" and float(val) > 1000:
                return float(val) / 1000.0
            return float(val)
    # Parse chuỗi như "153.2 km" nếu có.
    try:
        import re
        txt = str(route.get("distance_text") or "")
        m = re.search(r"(\d+(?:[.,]\d+)?)", txt)
        if m:
            return float(m.group(1).replace(",", "."))
    except Exception:
        pass
    return _distance_km_from_polyline(route.get("polyline") or [])


def _apply_avg_speed_timing(route: dict, mode: str) -> dict:
    """
    Chuẩn hóa duration của route theo tốc độ trung bình đã chọn.
    Giữ lại thời gian OSRM gốc trong osrm_duration_* để không mất dữ liệu cũ.
    """
    if not isinstance(route, dict):
        return route

    dist_km = _get_route_distance_km(route)
    if dist_km > 0:
        route["distance_km"] = dist_km
        route.setdefault("distance_text", f"{dist_km:.1f} km")

    # Lưu OSRM duration gốc 1 lần để tham khảo/debug.
    if "osrm_duration_text" not in route and route.get("duration_text"):
        route["osrm_duration_text"] = route.get("duration_text")
    if "osrm_duration_min" not in route and isinstance(route.get("duration_min"), (int, float)):
        route["osrm_duration_min"] = route.get("duration_min")

    total_sec = _duration_seconds_by_distance_mode(dist_km, mode)
    if total_sec > 0:
        route["duration_seconds"] = total_sec
        route["duration_s"] = total_sec
        route["duration"] = total_sec
        route["duration_min"] = total_sec / 60.0
        route["duration_text"] = _format_duration_from_seconds(total_sec)
        route["avg_speed_kmh"] = _avg_speed_kmh_by_mode(mode)
        route["avg_speed_mode"] = mode
        route["avg_speed_custom"] = bool(st.session_state.get("eta_custom_speed_enabled", False))
        route["duration_source"] = "custom_avg_speed" if route["avg_speed_custom"] else "avg_speed"

        # Nếu step có distance_km thì duration từng step cũng theo cùng tốc độ.
        steps = route.get("steps") or []
        for s in steps:
            try:
                sd = float(s.get("distance_km") or 0)
                ss = _duration_seconds_by_distance_mode(sd, mode)
                if ss > 0:
                    s["duration_min"] = round(ss / 60.0, 1)
                    s["duration_text"] = _format_duration_from_seconds(ss)
            except Exception:
                pass
    return route


def _apply_avg_speed_timing_to_routes(routes, mode: str):
    """Áp dụng ETA theo tốc độ trung bình cho list route, không xoá chức năng cũ."""
    if not routes:
        return routes
    for rt in routes:
        _apply_avg_speed_timing(rt, mode)
    return routes


def _format_duration_from_seconds(seconds):
    try:
        seconds = int(seconds or 0)
    except Exception:
        seconds = 0
    if seconds <= 0:
        return "?"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if h and m:
        return f"{h} giờ {m} phút"
    if h:
        return f"{h} giờ"
    return f"{m} phút"


def _get_route_duration_seconds(route: dict) -> float:
    """
    Lấy tổng thời gian di chuyển của tuyến (giây), thử nhiều nguồn vì
    cấu trúc route trả về từ Router có thể khác nhau:
      1. Các key số giây trực tiếp: duration_seconds, duration_s, duration
         (chỉ nhận nếu giá trị là số > 0)
      2. Cộng duration_min của từng step trong route["steps"]
      3. Parse chuỗi route["duration_text"] dạng "2h 30m" / "45 phút" / "1 giờ 5 phút"
    Trả về 0.0 nếu không tìm được.
    """
    import re

    # 1) Key số trực tiếp
    for key in ("duration_seconds", "duration_s", "duration"):
        val = route.get(key)
        if isinstance(val, (int, float)) and val > 0:
            return float(val)

    # 2) Cộng từ các step
    steps = route.get("steps") or []
    total_min = 0.0
    has_step_duration = False
    for s in steps:
        dm = s.get("duration_min")
        if isinstance(dm, (int, float)):
            total_min += dm
            has_step_duration = True
    if has_step_duration and total_min > 0:
        return total_min * 60.0

    # 3) Parse duration_text, ví dụ: "2h 30m", "1 giờ 5 phút", "45 phút", "1h"
    text = str(route.get("duration_text") or "")
    if text:
        hours = 0.0
        minutes = 0.0
        h_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:h|giờ|g)\b", text, re.IGNORECASE)
        m_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:m|min|phút|p)\b", text, re.IGNORECASE)
        if h_match:
            hours = float(h_match.group(1).replace(",", "."))
        if m_match:
            minutes = float(m_match.group(1).replace(",", "."))
        if hours or minutes:
            return hours * 3600.0 + minutes * 60.0

    return 0.0


def _compute_route_forecast(polyline, route, departure_dt, risk_engine, ml_model_route, weather_api):
    """
    Tính dự báo rủi ro theo thời gian cho một polyline + route dict.
    Trả về (route_risk_forecast_dict_or_None, total_duration_seconds, warning_msg_or_None).
    Không gọi st.* — chỉ tính toán, dùng được cho cả tuyến gốc và tuyến cập nhật ETA.
    """
    if ml_model_route is None or not ml_model_route.is_ready:
        return None, 0.0, None

    total_duration_seconds = _get_route_duration_seconds(route)
    warning_msg = None
    if total_duration_seconds <= 0:
        warning_msg = (
            "⚠️ Không xác định được tổng thời gian di chuyển của tuyến — "
            "ETA dự báo rủi ro sẽ trùng giờ xuất phát cho mọi đoạn."
        )

    forecast = analyze_route_risk_by_time(
        route_coords=polyline,
        total_duration_seconds=float(total_duration_seconds or 0),
        departure_dt=departure_dt,
        risk_engine=risk_engine,
        ml_model=ml_model_route,
        weather_api=weather_api,
    )
    return forecast, total_duration_seconds, warning_msg


def _route_cache_key(polyline, route, mode, poi_style, departure_dt, selected=0):
    """
    Tạo key cache cho phần hiển thị tuyến.
    Nếu người dùng đổi tuyến, đổi tốc độ ETA, đổi giờ xuất phát hoặc đổi POI style
    thì key đổi → app sẽ tính lại. Nếu chỉ chuyển menu rồi quay lại → dùng cache.
    """
    import hashlib
    try:
        pts = polyline or []
        sample = []
        if pts:
            idxs = [0, len(pts)//4, len(pts)//2, (len(pts)*3)//4, len(pts)-1]
            for i in sorted(set(max(0, min(len(pts)-1, x)) for x in idxs)):
                sample.append([round(float(pts[i][0]), 5), round(float(pts[i][1]), 5)])
        payload = {
            "selected": int(selected or 0),
            "n": len(pts),
            "sample": sample,
            "dist": round(float(_get_route_distance_km(route or {}) or 0), 3),
            "dur": round(float(_get_route_duration_seconds(route or {}) or 0), 1),
            "mode": str(mode or ""),
            "poi_style": str(poi_style or ""),
            "speed": round(float(_avg_speed_kmh_by_mode(mode) or 0), 3),
            "departure": departure_dt.strftime("%Y-%m-%d %H:%M") if hasattr(departure_dt, "strftime") else str(departure_dt),
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(raw.encode("utf-8")).hexdigest()
    except Exception:
        return None


def _clear_route_view_cache():
    """Xoá cache khi user bấm tìm tuyến mới để tránh dùng dữ liệu cũ."""
    for _k in ["route_view_cache", "route_view_cache_key"]:
        st.session_state.pop(_k, None)


def _parse_session_datetime(value, fallback):
    """Đọc datetime đã lưu trong session. Nếu lỗi thì dùng fallback."""
    if isinstance(value, datetime):
        return value
    try:
        if value:
            return datetime.fromisoformat(str(value))
    except Exception:
        pass
    return fallback


def _save_route_runtime_options(mode, poi_style, departure_dt, use_human, age, travel_hour, motion_sick, has_children, stress_level):
    """
    Đóng băng các tuỳ chọn tại thời điểm bấm Tìm đường.
    Nhờ vậy khi chuyển qua menu khác rồi quay lại, Streamlit có rerun thì app vẫn
    dùng đúng ngữ cảnh cũ và không kích hoạt phân tích tuyến lại vì default widget đổi.
    """
    st.session_state["last_poi_style"] = poi_style
    st.session_state["last_departure_dt_iso"] = departure_dt.isoformat() if hasattr(departure_dt, "isoformat") else str(departure_dt)
    st.session_state["last_use_human"] = bool(use_human)
    st.session_state["last_human_age"] = int(age)
    st.session_state["last_human_travel_hour"] = int(travel_hour)
    st.session_state["last_human_motion_sick"] = bool(motion_sick)
    st.session_state["last_human_has_children"] = bool(has_children)
    st.session_state["last_human_stress_level"] = int(stress_level)
    st.session_state["last_eta_custom_speed_enabled"] = bool(st.session_state.get("eta_custom_speed_enabled", False))
    st.session_state["last_eta_custom_speed_kmh"] = float(st.session_state.get("eta_custom_speed_kmh") or _default_avg_speed_kmh_by_mode(mode))
    # Key nội bộ dùng khi tính ETA cho tuyến đã lưu; không phải key widget nên an toàn khi rerun.
    st.session_state["_route_eta_speed_override_active"] = True
    st.session_state["_route_eta_custom_speed_enabled"] = bool(st.session_state.get("last_eta_custom_speed_enabled", False))
    st.session_state["_route_eta_custom_speed_kmh"] = float(st.session_state.get("last_eta_custom_speed_kmh") or _default_avg_speed_kmh_by_mode(mode))


def _restore_route_runtime_options(current_poi_style, current_departure_dt, current_use_human, current_age, current_travel_hour, current_motion_sick, current_has_children, current_stress_level):
    """Trả về bộ tuỳ chọn đã đóng băng cho tuyến đang hiển thị."""
    ss = st.session_state
    poi_style = ss.get("last_poi_style", current_poi_style)
    departure_dt = _parse_session_datetime(ss.get("last_departure_dt_iso"), current_departure_dt)
    use_human = bool(ss.get("last_use_human", current_use_human))
    age = int(ss.get("last_human_age", current_age))
    travel_hour = int(ss.get("last_human_travel_hour", current_travel_hour))
    motion_sick = bool(ss.get("last_human_motion_sick", current_motion_sick))
    has_children = bool(ss.get("last_human_has_children", current_has_children))
    stress_level = int(ss.get("last_human_stress_level", current_stress_level))

    # Khôi phục tốc độ ETA đã dùng khi bấm tìm đường bằng key nội bộ,
    # tuyệt đối không ghi vào key widget `eta_custom_speed_enabled` sau khi widget đã tạo.
    if "last_eta_custom_speed_enabled" in ss:
        ss["_route_eta_speed_override_active"] = True
        ss["_route_eta_custom_speed_enabled"] = bool(ss.get("last_eta_custom_speed_enabled"))
    if "last_eta_custom_speed_kmh" in ss:
        ss["_route_eta_custom_speed_kmh"] = float(ss.get("last_eta_custom_speed_kmh") or _default_avg_speed_kmh_by_mode(ss.get("last_mode", "car")))

    return poi_style, departure_dt, use_human, age, travel_hour, motion_sick, has_children, stress_level
