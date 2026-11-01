# core/local_reroute.py
# Đổi tuyến cục bộ quanh điểm đỏ: chỉ thay đoạn trong bán kính 10km quanh điểm đỏ.

import math
from datetime import datetime, timedelta

import streamlit as st

from core.route_state import _persist_current_route_snapshot
from core.route_calc import (
    RED_RISK_THRESHOLD,
    _haversine_km,
    _distance_km_from_polyline,
    _get_route_distance_km,
    _apply_avg_speed_timing,
    _format_duration_from_seconds,
    _get_route_duration_seconds,
    _compute_route_forecast,
    _clear_route_view_cache,
)
from core.copilot import _copilot_segment_score, _route_avg_risk_for_copilot
from core.legal_route_filter import validate_route_for_mode, is_reasonable_detour, detour_limit_text

def _coord_at_route_km(polyline, target_km):
    """Quy đổi route_km của AI Forecast thành tọa độ thật trên polyline [lon, lat]."""
    try:
        if not polyline or target_km is None:
            return None, None
        target = max(0.0, float(target_km))
        acc = 0.0
        prev = polyline[0]
        if target <= 0:
            return float(prev[1]), float(prev[0])
        for cur in polyline[1:]:
            seg_km = _haversine_km(prev[1], prev[0], cur[1], cur[0])
            if acc + seg_km >= target:
                t = (target - acc) / max(seg_km, 1e-9)
                lon = prev[0] + (cur[0] - prev[0]) * t
                lat = prev[1] + (cur[1] - prev[1]) * t
                return float(lat), float(lon)
            acc += seg_km
            prev = cur
        return float(polyline[-1][1]), float(polyline[-1][0])
    except Exception:
        return None, None


def _resolve_critical_coords(crit_seg, danger_markers, g_lat, g_lon, route_polyline=None):
    """
    FIX #2: Lấy tọa độ thực của điểm nguy hiểm cần tránh.
    Ưu tiên: lat/lon trong segment → tra cứu danger_markers gần nhất theo route_km
    → điểm đỏ gần nhất theo khoảng cách thực từ GPS.
    Trả về (lat, lon) hoặc (None, None) nếu không tìm được.
    """
    crit = crit_seg or {}
    # A) segment đã có tọa độ
    ilat = crit.get("lat") or crit.get("center_lat")
    ilon = crit.get("lon") or crit.get("center_lon")
    if ilat is not None and ilon is not None:
        return float(ilat), float(ilon)

    # A2) Nếu AI Forecast chỉ có route_km, quy đổi route_km → lat/lon trên polyline.
    route_km_target = crit.get("route_km")
    if route_km_target is not None and route_polyline:
        plat, plon = _coord_at_route_km(route_polyline, route_km_target)
        if plat is not None and plon is not None:
            return plat, plon

    # B) Tìm trong danger_markers điểm đỏ gần route_km của segment
    if route_km_target is not None and danger_markers:
        best, best_diff = None, 999.0
        for d in danger_markers:
            dlat = d.get("lat") or d.get("center_lat")
            dlon = d.get("lon") or d.get("center_lon")
            if dlat is None or dlon is None:
                continue
            rkm = d.get("route_km")
            if rkm is not None:
                diff = abs(float(rkm) - float(route_km_target))
                if diff < best_diff:
                    best_diff = diff
                    best = d
        if best and best_diff <= 15.0:
            return float(best.get("lat") or best.get("center_lat")), \
                   float(best.get("lon") or best.get("center_lon"))

    # C) Điểm đỏ (score >= 85%) gần GPS nhất phía trước
    if danger_markers and g_lat is not None and g_lon is not None:
        red_pts = [(d, _haversine_km(g_lat, g_lon,
                        float(d.get("lat") or d.get("center_lat") or g_lat),
                        float(d.get("lon") or d.get("center_lon") or g_lon)))
                   for d in danger_markers
                   if (d.get("lat") or d.get("center_lat")) and float(d.get("score", 0)) >= RED_RISK_THRESHOLD]
        if red_pts:
            red_pts.sort(key=lambda x: x[1])
            nearest = red_pts[0][0]
            return (float(nearest.get("lat") or nearest.get("center_lat")),
                    float(nearest.get("lon") or nearest.get("center_lon")))

    return None, None


def _route_passes_danger(polyline, danger_markers, threshold_score=RED_RISK_THRESHOLD, check_radius_km=1.5):
    """
    FIX #3: Kiểm tra tuyến mới có còn đi qua vùng nguy hiểm cao không.
    Trả về (passes: bool, max_score: float, count: int).
    """
    if not polyline or not danger_markers:
        return False, 0.0, 0
    red_markers = [d for d in danger_markers
                   if float(d.get("score", 0)) >= threshold_score
                   and (d.get("lat") or d.get("center_lat"))]
    if not red_markers:
        return False, 0.0, 0

    max_score = 0.0
    hit_count = 0
    # Lấy mẫu polyline (mỗi 5 điểm) để không quá chậm
    sample = polyline[::5] + ([polyline[-1]] if polyline else [])
    for d in red_markers:
        dlat = float(d.get("lat") or d.get("center_lat"))
        dlon = float(d.get("lon") or d.get("center_lon"))
        dscore = float(d.get("score", 0))
        for pt in sample:
            pt_lat, pt_lon = pt[1], pt[0]  # polyline là [lon, lat]
            if _haversine_km(pt_lat, pt_lon, dlat, dlon) <= check_radius_km:
                hit_count += 1
                max_score = max(max_score, dscore)
                break  # đủ 1 điểm trên tuyến là tính là "đi qua"
    return hit_count > 0, max_score, hit_count



def _polyline_cumulative_km(polyline):
    """Trả về list khoảng cách cộng dồn theo polyline [lon, lat]."""
    try:
        if not polyline:
            return []
        cum = [0.0]
        total = 0.0
        for a, b in zip(polyline[:-1], polyline[1:]):
            try:
                total += _haversine_km(float(a[1]), float(a[0]), float(b[1]), float(b[0]))
            except Exception:
                total += 0.0
            cum.append(total)
        return cum
    except Exception:
        return []


def _nearest_route_km_to_coord(polyline, lat, lon):
    """Tìm km gần nhất trên tuyến với tọa độ lat/lon, dùng để xác định vị trí điểm đỏ trên route."""
    try:
        if not polyline:
            return 0.0
        cum = _polyline_cumulative_km(polyline)
        best_i, best_d = 0, 10**9
        for i, pt in enumerate(polyline):
            try:
                d = _haversine_km(float(lat), float(lon), float(pt[1]), float(pt[0]))
            except Exception:
                d = 10**9
            if d < best_d:
                best_d, best_i = d, i
        return float(cum[best_i] if best_i < len(cum) else 0.0)
    except Exception:
        return 0.0


def _polyline_prefix_until_km(polyline, km):
    """Lấy phần polyline từ đầu tuyến đến km chỉ định, có nội suy điểm cắt."""
    try:
        if not polyline:
            return []
        km = max(0.0, float(km or 0.0))
        total = _distance_km_from_polyline(polyline)
        if km <= 0:
            return [[float(polyline[0][0]), float(polyline[0][1])]]
        if km >= total:
            return [[float(x[0]), float(x[1])] for x in polyline]
        pts = [[float(polyline[0][0]), float(polyline[0][1])]]
        acc = 0.0
        prev = polyline[0]
        for cur in polyline[1:]:
            seg = _haversine_km(float(prev[1]), float(prev[0]), float(cur[1]), float(cur[0]))
            if acc + seg < km:
                pts.append([float(cur[0]), float(cur[1])])
                acc += seg
                prev = cur
                continue
            lat, lon = _coord_at_route_km(polyline, km)
            if lat is not None and lon is not None:
                pts.append([float(lon), float(lat)])
            break
        return pts
    except Exception:
        return [[float(x[0]), float(x[1])] for x in (polyline or [])]


def _polyline_suffix_from_km(polyline, km):
    """Lấy phần polyline từ km chỉ định đến cuối tuyến, có nội suy điểm cắt."""
    try:
        if not polyline:
            return []
        km = max(0.0, float(km or 0.0))
        total = _distance_km_from_polyline(polyline)
        if km <= 0:
            return [[float(x[0]), float(x[1])] for x in polyline]
        if km >= total:
            return [[float(polyline[-1][0]), float(polyline[-1][1])]]
        pts = []
        lat, lon = _coord_at_route_km(polyline, km)
        if lat is not None and lon is not None:
            pts.append([float(lon), float(lat)])
        cum = _polyline_cumulative_km(polyline)
        for i, pt in enumerate(polyline):
            if i < len(cum) and cum[i] > km:
                pts.append([float(pt[0]), float(pt[1])])
        if not pts or pts[-1] != [float(polyline[-1][0]), float(polyline[-1][1])]:
            pts.append([float(polyline[-1][0]), float(polyline[-1][1])])
        return pts
    except Exception:
        return [[float(x[0]), float(x[1])] for x in (polyline or [])]


def _polyline_segment_between_km(polyline, start_km, end_km):
    """Lấy đoạn polyline nằm giữa start_km và end_km để so sánh đoạn cục bộ."""
    try:
        start_km = max(0.0, float(start_km or 0.0))
        end_km = max(start_km, float(end_km or start_km))
        if not polyline:
            return []
        total = _distance_km_from_polyline(polyline)
        start_km = min(start_km, total)
        end_km = min(end_km, total)
        pts = []
        slat, slon = _coord_at_route_km(polyline, start_km)
        elat, elon = _coord_at_route_km(polyline, end_km)
        if slat is not None and slon is not None:
            pts.append([float(slon), float(slat)])
        cum = _polyline_cumulative_km(polyline)
        for i, pt in enumerate(polyline):
            if i < len(cum) and start_km < cum[i] < end_km:
                pts.append([float(pt[0]), float(pt[1])])
        if elat is not None and elon is not None:
            pts.append([float(elon), float(elat)])
        return _dedupe_polyline(pts)
    except Exception:
        return []


def _dedupe_polyline(polyline, precision=6):
    """Xóa các điểm liền kề trùng nhau để Folium/OSRM không lỗi."""
    out = []
    last = None
    for p in polyline or []:
        try:
            cur = [float(p[0]), float(p[1])]
            key = (round(cur[0], precision), round(cur[1], precision))
            if key != last:
                out.append(cur)
                last = key
        except Exception:
            continue
    return out


def _splice_local_reroute(old_polyline, local_polyline, entry_km, exit_km):
    """Ghép: đầu tuyến cũ + tuyến vòng cục bộ quanh điểm đỏ + cuối tuyến cũ."""
    prefix = _polyline_prefix_until_km(old_polyline, entry_km)
    suffix = _polyline_suffix_from_km(old_polyline, exit_km)
    return _dedupe_polyline((prefix or []) + (local_polyline or []) + (suffix or []))




def _min_distance_polyline_to_coord_km(polyline, lat, lon, sample_step=1):
    """Khoảng cách nhỏ nhất từ polyline [lon,lat] tới tọa độ lat/lon."""
    try:
        if not polyline:
            return 999999.0
        best = 999999.0
        step = max(1, int(sample_step or 1))
        pts = list(polyline[::step])
        if polyline and polyline[-1] not in pts:
            pts.append(polyline[-1])
        for p in pts:
            try:
                best = min(
                    best,
                    _haversine_km(
                        float(p[1]), float(p[0]),
                        float(lat), float(lon),
                    ),
                )
            except Exception:
                pass
        return float(best)
    except Exception:
        return 999999.0


def _local_detour_waypoints_around_point(lat, lon, radius_km=5.0):
    """Sinh các waypoint vòng quanh điểm đỏ để router thử tuyến né điểm đỏ."""
    try:
        import math as _math
        lat = float(lat)
        lon = float(lon)
        radius_km = float(radius_km)
        out = []

        # 8 hướng chính quanh điểm đỏ.
        for bearing in [0, 45, 90, 135, 180, 225, 270, 315]:
            br = _math.radians(bearing)
            dlat = (radius_km / 111.32) * _math.cos(br)
            dlon = (
                radius_km
                / max(20.0, 111.32 * _math.cos(_math.radians(lat)))
            ) * _math.sin(br)
            out.append((lat + dlat, lon + dlon))
        return out
    except Exception:
        return []


def _apply_new_local_reroute_to_session(new_rt, mode, local_km, combined_km, entry_km, exit_km, avoid_label, chosen_name, risk_engine, weather_api):
    """Cập nhật toàn bộ session để rerun hiển thị tuyến mới ngay."""
    ss = st.session_state
    rem_poly = new_rt.get("polyline", [])

    ss["nav_polyline"] = rem_poly
    ss["nav_steps"] = new_rt.get("steps", ss.get("nav_steps", []))
    ss["nav_progress_idx"] = 0
    ss["nav_max_progress"] = 0
    ss["nav_offroute"] = False
    ss["nav_reroute_pl"] = None
    ss["nav_distance_left_osrm"] = _get_route_distance_km(new_rt)

    ss["last_incident_reroute"] = new_rt
    ss["last_routes"] = [new_rt]
    ss["last_selected"] = 0
    ss["last_polyline"] = rem_poly
    ss["last_route_km"] = _get_route_distance_km(new_rt)
    ss["route_selector"] = 0
    ss["_prev_selected"] = None
    ss["__copilot_reroute_applied"] = True
    ss["__force_route_rerender"] = True
    ss.pop("__last_good_trip_route_state", None)

    # Xóa mọi cache/phân tích tuyến cũ để map và Copilot buộc tính lại theo polyline mới.
    for _k in [
        "last_compared", "route_view_cache", "route_view_cache_key",
        "last_danger_markers", "last_danger_markers_raw", "last_rest_stops",
        "last_route_risk_forecast", "auto_eta_forecast",
        "copilot_critical_segment",
    ]:
        ss.pop(_k, None)
    _clear_route_view_cache()

    now_dt = datetime.now()
    total_sec = _get_route_duration_seconds(new_rt)
    ss["auto_eta_last_ts"] = __import__("time").time()
    ss["auto_eta_distance_km"] = _get_route_distance_km(new_rt)
    ss["auto_eta_duration_text"] = new_rt.get("duration_text") or _format_duration_from_seconds(total_sec)
    ss["auto_eta_arrival"] = (now_dt + timedelta(seconds=total_sec)).strftime("%H:%M") if total_sec else "?"
    ss["auto_eta_updated_at"] = now_dt.strftime("%H:%M:%S")
    ss["auto_eta_status"] = "✅ Đã đổi đoạn tuyến cục bộ quanh điểm đỏ và cập nhật ETA."
    ss["copilot_last_action"] = (
        f"✅ Đã đổi {chosen_name}. Chỉ thay đoạn km {entry_km:.1f}–{exit_km:.1f} "
        f"quanh {avoid_label}; các đoạn xa điểm đỏ được giữ nguyên."
    )
    ss["__copilot_reroute_nonce"] = int(ss.get("__copilot_reroute_nonce", 0)) + 1

    try:
        import __main__ as _main_app
        _init_ml_model_fn = getattr(_main_app, "init_ml_model", None)
        ml_model = _init_ml_model_fn() if callable(_init_ml_model_fn) else None
        if ml_model is not None and getattr(ml_model, "is_ready", False):
            fc, _, _ = _compute_route_forecast(rem_poly, new_rt, now_dt, risk_engine, ml_model, weather_api)
            ss["auto_eta_forecast"] = fc
            ss["last_route_risk_forecast"] = fc
            ss["auto_eta_ai_ready"] = True
            ss["auto_eta_ai_status"] = "✅ đã cập nhật sau đổi tuyến cục bộ"
    except Exception as e:
        ss["auto_eta_ai_status"] = f"⚠️ lỗi AI forecast sau đổi tuyến cục bộ: {e}"

    _persist_current_route_snapshot()
    return True, (
        f"Đã đổi tuyến cục bộ quanh điểm đỏ: chỉ thay đoạn km {entry_km:.1f}–{exit_km:.1f} "
        f"(vùng 10 km quanh điểm đỏ), giữ nguyên các đoạn xa. "
        f"Đoạn vòng mới dài {local_km:.1f} km; tổng tuyến {combined_km:.1f} km."
    )


def _accept_copilot_reroute(router, risk_engine, weather_api, mode_fallback, route_fallback=None):
    """
    Đổi tuyến theo Copilot khi có chấm đỏ >= RED_RISK_THRESHOLD.

    Bản gọn, chỉ còn một định nghĩa:
    - Thử đổi đoạn cục bộ quanh điểm đỏ với bán kính 10 / 15 / 20 / 30 km.
    - Nếu local không né được, thử đổi toàn tuyến qua waypoint vòng tránh.
    - Không nhận tuyến gần như trùng tuyến cũ hoặc vẫn đi sát điểm đỏ.
    - Sau khi đổi thành công, cập nhật session_state đầy đủ để app.py rerun vẽ lại map.
    """
    ss = st.session_state
    mode = ss.get("nav_mode") or ss.get("last_mode") or mode_fallback
    route_fallback = route_fallback or {}

    # Ưu tiên tuyến đang hiển thị trong app, không lấy cache cũ.
    orig_route = dict(route_fallback or {})
    if not orig_route.get("polyline"):
        if ss.get("last_routes"):
            try:
                orig_route = dict(ss["last_routes"][int(ss.get("last_selected", 0) or 0)])
            except Exception:
                orig_route = dict(ss["last_routes"][0])
    orig_polyline = orig_route.get("polyline") or ss.get("nav_polyline") or ss.get("last_polyline") or []
    if not orig_polyline or len(orig_polyline) < 2:
        return False, "Chưa có tuyến hiện tại để đổi tuyến."

    crit = ss.get("copilot_critical_segment") or {}
    if _copilot_segment_score(crit) < RED_RISK_THRESHOLD:
        return False, "Hiện chưa có chấm đỏ đủ ngưỡng nên chưa cần đổi tuyến."

    g_lat = ss.get("nav_gps_lat")
    g_lon = ss.get("nav_gps_lon")
    all_danger = ss.get("last_danger_markers") or []
    avoid_lat, avoid_lon = _resolve_critical_coords(
        crit, all_danger, g_lat, g_lon, route_polyline=orig_polyline
    )
    if avoid_lat is None or avoid_lon is None:
        return False, "Copilot chưa xác định được tọa độ điểm đỏ để né."

    total_old_km = _distance_km_from_polyline(orig_polyline)
    red_route_km = crit.get("route_km")
    if red_route_km is None:
        red_route_km = _nearest_route_km_to_coord(orig_polyline, avoid_lat, avoid_lon)
    red_route_km = max(0.0, min(float(red_route_km or 0.0), total_old_km))

    avoid_label = crit.get("hazard_label") or crit.get("label") or "điểm đỏ"
    old_min_red_dist = _min_distance_polyline_to_coord_km(orig_polyline, avoid_lat, avoid_lon)

    rejected = []
    accepted = []

    def _route_signature(poly):
        try:
            step = max(1, int(len(poly) / 80))
            return tuple((round(float(p[0]), 3), round(float(p[1]), 3)) for p in poly[::step])
        except Exception:
            return tuple()

    old_sig_set = set(_route_signature(orig_polyline))

    def _overlap_ratio(poly):
        new_set = set(_route_signature(poly))
        if not new_set:
            return 1.0
        return len(new_set & old_sig_set) / max(1, len(new_set))

    def _consider_candidate(name, new_route, local_km, entry_km, exit_km, radius_km):
        if not new_route or not new_route.get("polyline"):
            return
        new_poly = new_route.get("polyline") or []
        if len(new_poly) < 2:
            rejected.append(f"{name}: polyline rỗng")
            return

        combined_km = _distance_km_from_polyline(new_poly)
        if total_old_km and not is_reasonable_detour(total_old_km, combined_km):
            rejected.append(f"{name}: tuyến vòng quá xa ({combined_km:.1f} km; giới hạn {detour_limit_text(total_old_km)})")
            return

        legal_ok, legal_issues = validate_route_for_mode(new_route, mode)
        if not legal_ok:
            rejected.append(f"{name}: không hợp lệ phương tiện ({'; '.join(legal_issues)})")
            return

        min_red_dist = _min_distance_polyline_to_coord_km(new_poly, avoid_lat, avoid_lon)
        overlap = _overlap_ratio(new_poly)

        # Không nhận tuyến vẫn đi sát điểm đỏ. Ngưỡng 0.8 km đủ thực tế cho đường núi/OSRM.
        if min_red_dist < max(0.8, old_min_red_dist + 0.15):
            rejected.append(f"{name}: vẫn quá gần điểm đỏ ({min_red_dist:.2f} km)")
            return

        if overlap > 0.985:
            rejected.append(f"{name}: gần như trùng tuyến cũ ({overlap:.0%})")
            return

        avg_risk, _analysis = _route_avg_risk_for_copilot(new_route, risk_engine)
        new_route["local_reroute_applied"] = True
        new_route["local_reroute_radius_km"] = radius_km
        new_route["local_reroute_entry_km"] = entry_km
        new_route["local_reroute_exit_km"] = exit_km
        new_route["local_reroute_red_km"] = red_route_km
        new_route["local_reroute_label"] = avoid_label
        new_route["local_reroute_min_red_dist_km"] = round(min_red_dist, 3)
        new_route["reroute_source_label"] = name
        _apply_avg_speed_timing(new_route, mode)

        # Ưu tiên: xa điểm đỏ hơn, risk thấp hơn, overlap thấp hơn, tuyến ngắn hơn.
        accepted.append((-min_red_dist, avg_risk, overlap, combined_km, local_km, entry_km, exit_km, name, new_route))

    try:
        # A) Đổi cục bộ quanh điểm đỏ: 10km trước/sau trước, nếu không được thì mở rộng.
        for local_radius_km in [10.0, 15.0, 20.0, 30.0]:
            entry_km = max(0.0, red_route_km - local_radius_km)
            exit_km = min(total_old_km, red_route_km + local_radius_km)
            if exit_km - entry_km < 1.0:
                continue

            entry_lat, entry_lon = _coord_at_route_km(orig_polyline, entry_km)
            exit_lat, exit_lon = _coord_at_route_km(orig_polyline, exit_km)
            if entry_lat is None or entry_lon is None or exit_lat is None or exit_lon is None:
                continue

            def _build_combined(local_rt, source_name):
                local_poly = (local_rt or {}).get("polyline") or []
                if not local_poly:
                    return None, 0.0
                local_km = _get_route_distance_km(local_rt) or _distance_km_from_polyline(local_poly)
                old_local = _polyline_segment_between_km(orig_polyline, entry_km, exit_km)
                old_local_km = _distance_km_from_polyline(old_local)
                if old_local_km and local_km > max(old_local_km * 3.8, old_local_km + 45.0):
                    rejected.append(f"{source_name}: đoạn cục bộ quá dài ({local_km:.1f}/{old_local_km:.1f} km)")
                    return None, local_km
                combined_poly = _splice_local_reroute(orig_polyline, local_poly, entry_km, exit_km)
                if not combined_poly:
                    return None, local_km
                new_route = dict(orig_route or {})
                new_route["polyline"] = combined_poly
                new_route["distance_km"] = _distance_km_from_polyline(combined_poly)
                new_route["distance_text"] = f"{new_route['distance_km']:.1f} km"
                if local_rt.get("steps"):
                    new_route["local_reroute_steps"] = local_rt.get("steps", [])
                return new_route, local_km

            # 1) router.reroute_around_incident
            if hasattr(router, "reroute_around_incident"):
                for avoid_radius in [1.0, 1.5, 2.5, 3.5, 5.0, 7.5, 10.0, 12.0]:
                    try:
                        local_rt = router.reroute_around_incident(
                            (float(entry_lat), float(entry_lon)),
                            (float(exit_lat), float(exit_lon)),
                            float(avoid_lat), float(avoid_lon),
                            mode=mode,
                            avoid_radius_km=avoid_radius,
                        )
                        new_route, local_km = _build_combined(local_rt, f"local incident {avoid_radius:g}km")
                        if new_route:
                            _consider_candidate(
                                f"đổi cục bộ {local_radius_km:g}km / né {avoid_radius:g}km",
                                new_route, local_km, entry_km, exit_km, local_radius_km
                            )
                    except Exception as e:
                        rejected.append(f"reroute_around_incident lỗi: {e}")

            # 2) Waypoint vòng quanh điểm đỏ
            for radius in [2.0, 4.0, 6.0, 8.0, 10.0, 15.0, 20.0]:
                for wp in _local_detour_waypoints_around_point(avoid_lat, avoid_lon, radius):
                    try:
                        local_rt = router.get_route(
                            (float(entry_lat), float(entry_lon)),
                            (float(exit_lat), float(exit_lon)),
                            mode=mode,
                            waypoints=[wp],
                        )
                        new_route, local_km = _build_combined(local_rt, f"waypoint {radius:g}km")
                        if new_route:
                            _consider_candidate(
                                f"đổi cục bộ {local_radius_km:g}km qua waypoint {radius:g}km",
                                new_route, local_km, entry_km, exit_km, local_radius_km
                            )
                    except Exception:
                        pass

            if accepted:
                break

        # B) Fallback: đổi toàn tuyến qua waypoint né điểm đỏ nếu local không có đường thay thế.
        if not accepted:
            start_lat, start_lon = float(orig_polyline[0][1]), float(orig_polyline[0][0])
            end_lat, end_lon = float(orig_polyline[-1][1]), float(orig_polyline[-1][0])
            for radius in [5.0, 8.0, 12.0, 18.0, 25.0, 35.0]:
                for wp in _local_detour_waypoints_around_point(avoid_lat, avoid_lon, radius):
                    try:
                        full_rt = router.get_route(
                            (start_lat, start_lon),
                            (end_lat, end_lon),
                            mode=mode,
                            waypoints=[wp],
                        )
                        if full_rt and full_rt.get("polyline"):
                            _apply_avg_speed_timing(full_rt, mode)
                            full_rt = dict(full_rt)
                            full_rt["label"] = "🔄 Tuyến thay thế né điểm đỏ"
                            _consider_candidate(
                                f"đổi toàn tuyến qua waypoint {radius:g}km",
                                full_rt,
                                _get_route_distance_km(full_rt),
                                0.0,
                                total_old_km,
                                radius,
                            )
                    except Exception:
                        pass
                if accepted:
                    break

        if not accepted:
            detail = "; ".join(rejected[:8]) if rejected else "không có ứng viên tuyến vòng"
            return False, f"Chưa tìm được tuyến khác né điểm đỏ. Lý do: {detail}"

        accepted.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
        neg_min_red_dist, avg_risk, overlap, combined_km, local_km, entry_km, exit_km, chosen_name, new_rt = accepted[0]

        ok, msg = _apply_new_local_reroute_to_session(
            new_rt, mode, float(local_km or 0), float(combined_km or _get_route_distance_km(new_rt)),
            float(entry_km), float(exit_km), avoid_label, chosen_name, risk_engine, weather_api,
        )
        if ok:
            msg += f" Tuyến mới cách điểm đỏ khoảng {abs(neg_min_red_dist):.1f} km."
        return ok, msg

    except Exception as e:
        return False, f"Lỗi đổi tuyến né điểm đỏ: {e}"



def _accept_copilot_rest(router, risk_engine, weather_api, mode_fallback, delay_min=15):
    """Sau khi người dùng đã xác nhận nghỉ: dời giờ xuất phát lại, chạy lại AI forecast theo ETA mới."""
    ss = st.session_state
    mode = ss.get("nav_mode") or ss.get("last_mode") or mode_fallback
    poly = ss.get("nav_polyline") or ss.get("last_polyline") or []
    if not poly:
        return False, "Chưa có tuyến để cập nhật sau khi nghỉ."
    dist = ss.get("nav_distance_left_osrm") or ss.get("auto_eta_distance_km") or ss.get("last_route_km") or _distance_km_from_polyline(poly)
    route_tmp = {"polyline": poly, "distance_km": float(dist or 0), "steps": ss.get("nav_steps", [])}
    _apply_avg_speed_timing(route_tmp, mode)
    start_dt = datetime.now() + timedelta(minutes=int(delay_min))
    total_sec = _get_route_duration_seconds(route_tmp)
    ss["auto_eta_last_ts"] = __import__("time").time()
    ss["auto_eta_distance_km"] = _get_route_distance_km(route_tmp)
    ss["auto_eta_duration_text"] = route_tmp.get("duration_text")
    ss["auto_eta_arrival"] = (start_dt + timedelta(seconds=total_sec)).strftime("%H:%M") if total_sec else "?"
    ss["auto_eta_updated_at"] = datetime.now().strftime("%H:%M:%S")
    ss["auto_eta_status"] = f"✅ Đã xác nhận nghỉ {delay_min} phút và cập nhật ETA."
    ss["copilot_last_action"] = f"⏸️ Đã xác nhận nghỉ {delay_min} phút rồi cập nhật lại dự báo."
    try:
        import __main__ as _main_app
        _init_ml_model_fn = getattr(_main_app, "init_ml_model", None)
        ml_model = _init_ml_model_fn() if callable(_init_ml_model_fn) else None
        if ml_model is not None and getattr(ml_model, "is_ready", False):
            fc, _, _ = _compute_route_forecast(poly, route_tmp, start_dt, risk_engine, ml_model, weather_api)
            ss["auto_eta_forecast"] = fc
            ss["auto_eta_ai_ready"] = True
            ss["auto_eta_ai_status"] = f"✅ đã cập nhật sau nghỉ {delay_min} phút"
    except Exception as e:
        ss["auto_eta_ai_status"] = f"⚠️ lỗi AI forecast sau nghỉ: {e}"
    return True, f"Đã cập nhật dự báo sau khi nghỉ {delay_min} phút."
