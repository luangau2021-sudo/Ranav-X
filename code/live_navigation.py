"""
live_navigation.py — TripSmart Pro · Live Navigation tiện ích
Chỉ chứa các hàm snap GPS và reroute.
Không còn giao diện riêng.
"""
from __future__ import annotations
import math
import time
import streamlit as st

# ─── Hằng số ────────────────────────────────────────────────────────────────
OFFROUTE_THRESHOLD_KM   = 0.08
REROUTE_COOLDOWN_SEC    = 15

# ─── Tiện ích tính khoảng cách ───────────────────────────────────────────────
def _hav(lat1, lon1, lat2, lon2) -> float:
    """Khoảng cách Haversine (km)."""
    R = 6371.0
    d = lambda a, b: math.radians(b - a)
    dlat, dlon = d(lat1, lat2), d(lon1, lon2)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * \
        math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(max(0.0, a)))

def _snap_to_route(gps_lat: float, gps_lon: float, polyline: list) -> dict:
    """
    Tìm điểm gần nhất trên polyline (OSRM: [[lon,lat], ...]).
    Trả về {idx, lat, lon, dist_km, progress_ratio}
    """
    best_idx, best_dist = 0, 999.0
    for i, (lon_p, lat_p) in enumerate(polyline):
        d = _hav(gps_lat, gps_lon, lat_p, lon_p)
        if d < best_dist:
            best_dist, best_idx = d, i
    return {
        "idx"           : best_idx,
        "lat"           : polyline[best_idx][1],
        "lon"           : polyline[best_idx][0],
        "dist_km"       : round(best_dist, 4),
        "progress_ratio": best_idx / max(1, len(polyline) - 1),
    }

def _do_reroute(router, risk_engine, gps_lat, gps_lon, dest_lat, dest_lon, mode):
    """
    Tính tuyến mới từ GPS hiện tại → đích, ưu tiên an toàn nhất.
    Trả về (polyline, risk_segs, steps, summary_dict)
    """
    try:
        # Lấy nhiều phương án nếu có
        if hasattr(router, "get_alternative_routes"):
            result = router.get_alternative_routes(
                (gps_lat, gps_lon),
                (dest_lat, dest_lon),
                mode=mode,
                count=3,
            )
        else:
            result = router.get_route(
                (gps_lat, gps_lon),
                (dest_lat, dest_lon),
                mode=mode,
            )
    except TypeError:
        result = router.get_route(
            (gps_lat, gps_lon),
            (dest_lat, dest_lon),
            mode=mode,
        )

    routes = result if isinstance(result, list) else [result]
    if not routes or not routes[0]:
        return None, None, [], {}

    # Chọn tuyến an toàn nhất
    best_route = routes[0]
    if len(routes) > 1 and risk_engine:
        try:
            enriched = risk_engine.compare_routes(routes)
            safest = min(enriched, key=lambda r: (r.get("avg_risk_score", 1),
                                                   r.get("danger_count", 0)))
            best_route = safest
        except Exception:
            pass

    polyline = best_route.get("polyline", [])
    steps    = best_route.get("steps", [])

    # Phân tích rủi ro tuyến mới
    risk_segs = []
    if risk_engine and polyline:
        try:
            analysis  = risk_engine.analyze_route(polyline)
            danger_sg = analysis.get("danger_segments", [])
            for seg in danger_sg:
                score = seg.get("score", 0)
                color = ("#b71c1c" if score >= 0.70 else
                         "#fb8c00" if score >= 0.55 else
                         "#fdd835" if score >= 0.40 else
                         "#43a047")
                risk_segs.append({
                    "start_idx": seg.get("start_idx", 0),
                    "end_idx"  : seg.get("end_idx",   0),
                    "color"    : color,
                    "score"    : score,
                    "label"    : seg.get("label", ""),
                })
        except Exception:
            pass

    summary = {
        "distance_km" : best_route.get("distance_km", 0),
        "duration_min": best_route.get("duration_min", 0),
        "duration_text": best_route.get("duration_text", ""),
        "distance_text": best_route.get("distance_text", ""),
    }
    return polyline, risk_segs, steps, summary