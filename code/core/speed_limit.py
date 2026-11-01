# core/speed_limit.py
# Speed Limit Layer cho TripSmart Pro
# Nguồn dữ liệu: OpenStreetMap/Overpass.
# Ưu tiên tốc độ theo phương tiện:
#   car       -> maxspeed:motorcar -> maxspeed:motor_vehicle -> maxspeed
#   motorbike -> maxspeed:motorcycle -> maxspeed:motor_vehicle -> maxspeed
# Nếu đoạn hiện tại không có dữ liệu maxspeed phù hợp thì UI hiện "Không có thông tin".

from __future__ import annotations

import math
import time
import re
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


def _normalize_mode(mode: str | None) -> str:
    m = str(mode or "car").strip().lower()
    if m in {"motorbike", "motorcycle", "moto", "bike_motor", "xe_may", "xe máy"}:
        return "motorbike"
    return "car"


def _hav_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p = math.pi / 180.0
    dlat = (lat2 - lat1) * p
    dlon = (lon2 - lon1) * p
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin(dlon / 2) ** 2
    return r * 2 * math.asin(math.sqrt(max(0.0, a)))


def _route_cumulative_km(polyline: List[List[float]]) -> List[float]:
    out = [0.0]
    total = 0.0
    for a, b in zip(polyline[:-1], polyline[1:]):
        try:
            total += _hav_km(float(a[1]), float(a[0]), float(b[1]), float(b[0]))
        except Exception:
            pass
        out.append(total)
    return out


def _nearest_route_point(polyline: List[List[float]], lat: float, lon: float) -> Tuple[float, float, int]:
    """Trả về (dist_km, route_km, index) tới điểm route gần nhất. Polyline dạng [lon,lat]."""
    if not polyline:
        return 999999.0, 0.0, 0
    cum = _route_cumulative_km(polyline)
    best_d, best_i = 999999.0, 0
    for i, p in enumerate(polyline):
        try:
            d = _hav_km(lat, lon, float(p[1]), float(p[0]))
        except Exception:
            d = 999999.0
        if d < best_d:
            best_d, best_i = d, i
    return best_d, float(cum[best_i] if best_i < len(cum) else 0.0), best_i


def _sample_route_points(polyline: List[List[float]], every_km: float = 1.5, max_points: int = 28) -> List[Tuple[float, float]]:
    """Lấy mẫu điểm trên tuyến để query Overpass around. Trả về [(lat,lon)]."""
    if not polyline:
        return []
    cum = _route_cumulative_km(polyline)
    total = cum[-1] if cum else 0.0
    if total <= 0:
        p = polyline[0]
        return [(float(p[1]), float(p[0]))]

    targets = [0.0]
    step = max(0.5, float(every_km or 1.5))
    t = step
    while t < total:
        targets.append(t)
        t += step
    targets.append(total)

    if len(targets) > max_points:
        targets = [total * i / max(1, max_points - 1) for i in range(max_points)]

    pts = []
    j = 0
    for target in targets:
        while j + 1 < len(cum) and cum[j + 1] < target:
            j += 1
        if j + 1 >= len(polyline):
            p = polyline[-1]
            pts.append((float(p[1]), float(p[0])))
            continue
        a, b = polyline[j], polyline[j + 1]
        seg = max(1e-9, cum[j + 1] - cum[j])
        ratio = (target - cum[j]) / seg
        lon = float(a[0]) + (float(b[0]) - float(a[0])) * ratio
        lat = float(a[1]) + (float(b[1]) - float(a[1])) * ratio
        pts.append((lat, lon))

    uniq, seen = [], set()
    for lat, lon in pts:
        key = (round(lat, 4), round(lon, 4))
        if key not in seen:
            seen.add(key)
            uniq.append((lat, lon))
    return uniq


def _parse_maxspeed_kmh(value: Any) -> Optional[int]:
    """Parse maxspeed OSM sang km/h nếu rõ. Không suy luận nếu thiếu/không rõ."""
    if value is None:
        return None
    s = str(value).strip().lower()
    if not s or s in {"none", "signals", "walk", "variable", "implicit", "default"}:
        return None
    # maxspeed có thể dạng "50", "50 km/h", "30;50", "80 mph", "VN:urban".
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if not m:
        return None
    num = float(m.group(1))
    if "mph" in s:
        num *= 1.60934
    if num <= 0 or num > 180:
        return None
    return int(round(num))


def _select_vehicle_maxspeed(tags: Dict[str, Any], mode: str | None) -> Tuple[Optional[int], str, Any]:
    """Chọn maxspeed theo đúng phương tiện, không tự suy luận.

    Trả về: (speed_kmh, source_tag, raw_value)
    """
    m = _normalize_mode(mode)
    if m == "motorbike":
        candidates = ["maxspeed:motorcycle", "maxspeed:motor_vehicle", "maxspeed"]
    else:
        candidates = ["maxspeed:motorcar", "maxspeed:motor_vehicle", "maxspeed"]

    for key in candidates:
        raw = tags.get(key)
        spd = _parse_maxspeed_kmh(raw)
        if spd is not None:
            return spd, key, raw
    return None, "", None


class SpeedLimitEngine:
    """Lấy speed limit dọc tuyến từ OSM.

    Không có maxspeed phù hợp với phương tiện => không tự đoán.
    UI sẽ hiện "Không có thông tin".
    """

    def __init__(self, cache_ttl_sec: int = 900):
        self.cache_ttl_sec = int(cache_ttl_sec)
        self._cache: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}

    def _cache_key(self, polyline: List[List[float]], mode: str | None) -> str:
        if not polyline:
            return "empty"
        pts = []
        for p in (polyline[:3] + polyline[-3:]):
            try:
                pts.append(f"{float(p[1]):.4f},{float(p[0]):.4f}")
            except Exception:
                pass
        pts.append(str(len(polyline)))
        pts.append(_normalize_mode(mode))
        return "|".join(pts)

    def get_speed_limits_on_route(
        self,
        polyline: List[List[float]],
        mode: str | None = "car",
        corridor_m: int = 120,
        sample_every_km: float = 1.5,
        max_results: int = 120,
    ) -> List[Dict[str, Any]]:
        if not polyline or len(polyline) < 2 or requests is None:
            return []
        mode_norm = _normalize_mode(mode)
        key = self._cache_key(polyline, mode_norm) + f"|{corridor_m}|{sample_every_km}"
        now = time.time()
        if key in self._cache:
            ts, data = self._cache[key]
            if now - ts <= self.cache_ttl_sec:
                return list(data)

        sample_pts = _sample_route_points(polyline, every_km=sample_every_km, max_points=28)
        if not sample_pts:
            return []

        around_m = max(60, int(corridor_m))
        clauses = []
        for lat, lon in sample_pts:
            # Query đủ các tag tốc độ theo phương tiện.
            # Không query toàn bộ highway để giảm tải Overpass.
            clauses.append(f'way(around:{around_m},{lat:.6f},{lon:.6f})["highway"]["maxspeed"];')
            clauses.append(f'way(around:{around_m},{lat:.6f},{lon:.6f})["highway"]["maxspeed:motor_vehicle"];')
            if mode_norm == "motorbike":
                clauses.append(f'way(around:{around_m},{lat:.6f},{lon:.6f})["highway"]["maxspeed:motorcycle"];')
            else:
                clauses.append(f'way(around:{around_m},{lat:.6f},{lon:.6f})["highway"]["maxspeed:motorcar"];')
        query = "[out:json][timeout:25];(" + "".join(clauses) + ");out tags geom qt;"

        elements = []
        for url in OVERPASS_URLS:
            try:
                r = requests.post(url, data={"data": query}, timeout=28)
                r.raise_for_status()
                payload = r.json()
                elements = payload.get("elements", []) or []
                if elements:
                    break
            except Exception:
                continue

        results = []
        seen_way = set()
        for el in elements:
            if el.get("type") != "way":
                continue
            osm_id = el.get("id")
            if osm_id in seen_way:
                continue
            tags = el.get("tags") or {}
            speed, source_tag, raw_value = _select_vehicle_maxspeed(tags, mode_norm)
            if speed is None:
                continue
            geom = el.get("geometry") or []
            if not geom:
                continue

            best = (999999.0, 0.0, 0, None, None)
            step = max(1, len(geom) // 12)
            for gp in geom[::step]:
                try:
                    lat, lon = float(gp.get("lat")), float(gp.get("lon"))
                    d, route_km, idx = _nearest_route_point(polyline, lat, lon)
                    if d < best[0]:
                        best = (d, route_km, idx, lat, lon)
                except Exception:
                    continue
            if best[0] * 1000 > max(around_m * 1.8, 220):
                continue

            results.append({
                "osm_id": osm_id,
                "lat": best[3],
                "lon": best[4],
                "route_km": round(float(best[1]), 3),
                "maxspeed": speed,
                "maxspeed_text": f"{speed} km/h",
                "mode": mode_norm,
                "source_tag": source_tag,
                "raw_maxspeed": raw_value,
                "highway": tags.get("highway", ""),
                "name": tags.get("name", ""),
                "source": "osm_vehicle_maxspeed",
                "distance_from_route_m": round(best[0] * 1000, 1),
            })

        # Gộp way cùng tốc độ rất gần nhau để panel không nhảy liên tục.
        results.sort(key=lambda x: (float(x.get("route_km", 0)), int(x.get("maxspeed", 0))))
        compact: List[Dict[str, Any]] = []
        for item in results:
            if compact:
                prev = compact[-1]
                if (
                    abs(float(item["route_km"]) - float(prev.get("route_km", 0))) < 0.25
                    and item.get("maxspeed") == prev.get("maxspeed")
                    and item.get("source_tag") == prev.get("source_tag")
                ):
                    if item.get("name") and not prev.get("name"):
                        prev["name"] = item.get("name")
                    continue
            compact.append(item)
            if len(compact) >= max_results:
                break

        self._cache[key] = (now, compact)
        return list(compact)


def get_speed_limits_on_route(polyline: List[List[float]], mode: str | None = "car", **kwargs) -> List[Dict[str, Any]]:
    """Helper dùng nhanh nếu không muốn tự tạo engine."""
    return SpeedLimitEngine().get_speed_limits_on_route(polyline, mode=mode, **kwargs)
