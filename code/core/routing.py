import math
import requests
from typing import List, Dict, Tuple, Optional

try:
    from utils.helpers import haversine_distance, format_distance, format_duration
    from utils.logger import setup_logger
    logger = setup_logger(__name__)
except Exception:
    import logging
    logger = logging.getLogger(__name__)

    def haversine_distance(lat1, lon1, lat2, lon2):
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        return R * 2 * math.asin(math.sqrt(max(0, a)))

    def format_distance(km):
        return f"{km:.1f} km"

    def format_duration(m):
        h = int(m) // 60
        mn = int(m) % 60
        return f"{h}h {mn}p" if h else f"{mn} phút"


# ─────────────────────────────────────────────────────────────────────────────
# CẤU HÌNH OSRM
# ─────────────────────────────────────────────────────────────────────────────

OSRM_BASE = "http://router.project-osrm.org/route/v1"

OSRM_PROFILES = {
    "car": "driving",
    "motorbike": "driving",
    "bike": "cycling",
    "walk": "foot",
}


# ─────────────────────────────────────────────────────────────────────────────
# BOUNDING BOX VIỆT NAM
# Lưu ý: bbox chỉ là vòng lọc thô, KHÔNG đủ để kết luận nằm trong biên giới VN.
# Vì bbox của Việt Nam vẫn chứa một phần Lào/Campuchia.
# ─────────────────────────────────────────────────────────────────────────────

VN_BBOX = {
    "lat_min": 8.18,
    "lat_max": 23.39,
    "lon_min": 102.14,
    "lon_max": 109.47,
}


def _in_vn_bbox(lat: float, lon: float) -> bool:
    return (
        VN_BBOX["lat_min"] <= lat <= VN_BBOX["lat_max"]
        and VN_BBOX["lon_min"] <= lon <= VN_BBOX["lon_max"]
    )


# Một dải "xương sống" giao thông trong Việt Nam, dùng để phát hiện tuyến bị kéo
# sâu về phía Tây qua Lào/Campuchia mà bbox không bắt được.
# Không dùng shapely để tránh lỗi thiếu module.
VN_CORRIDOR_ANCHORS = [
    (22.82, 104.98),   # Lào Cai
    (21.0245, 105.8412),  # Hà Nội
    (20.45, 106.34),   # Nam Định/Ninh Bình
    (19.80, 105.78),   # Thanh Hóa
    (18.6796, 105.6813),  # Vinh
    (17.48, 106.60),   # Đồng Hới
    (16.4637, 107.5909),  # Huế
    (16.0544, 108.2022),  # Đà Nẵng
    (15.12, 108.80),   # Quảng Ngãi
    (13.7765, 109.2237),  # Quy Nhơn
    (12.2388, 109.1967),  # Nha Trang
    (11.5639, 108.9880),  # Phan Rang
    (11.94, 108.44),   # Đà Lạt
    (10.98, 108.26),   # Bình Thuận
    (10.7769, 106.7009),  # TP.HCM
    (10.0452, 105.7469),  # Cần Thơ
    (9.60, 105.97),    # Sóc Trăng
    (9.18, 105.15),    # Cà Mau
]

# Hub bắt buộc trong VN. Giữ danh sách gần code cũ nhưng dùng theo logic code 2:
# ưu tiên các hub theo trục Bắc - Nam, không lọc quá chặt bằng detour/lateral.
VN_HUBS = {
    "hanoi": (21.0245, 105.8412),
    "vinh": (18.6796, 105.6813),
    "hue": (16.4637, 107.5909),
    "danang": (16.0544, 108.2022),
    "quinhon": (13.7765, 109.2237),
    "nhatrang": (12.2388, 109.1967),
    "phanrang": (11.5639, 108.9880),
    "dalat": (11.9404, 108.4583),
    "phanthiet": (10.9333, 108.1000),
    "hcm": (10.7769, 106.7009),
    "cantho": (10.0452, 105.7469),
}

# Anchor địa phương dùng riêng cho tính tuyến vòng sự cố.
# Mục tiêu: khi waypoint hình tròn quanh sự cố bị OSRM snap lệch/không có đường,
# app vẫn có các điểm mồi nằm trên các trục đường thật để thoát vùng sự cố.
# Danh sách này không ép mọi tuyến đi qua đây; chỉ được xét trong reroute và
# được lọc bằng detour nên không gây vòng xa nếu không phù hợp.
REROUTE_ANCHORS = {
    # Lâm Đồng / Tây Nguyên
    "dalat_center": (11.9404, 108.4583),
    "mimosa_dalat": (11.8890, 108.5060),
    "tuyen_lam": (11.8900, 108.4140),
    "lien_khuong": (11.7500, 108.3730),
    "duc_trong": (11.7350, 108.3730),
    "di_linh": (11.5800, 108.0700),
    "bao_loc": (11.5489, 107.8077),
    "madaguoi": (11.3890, 107.5320),

    # Đông Nam Bộ / hướng Vũng Tàu - TP.HCM
    "dau_giay": (10.9300, 107.2440),
    "long_khanh": (10.9330, 107.2500),
    "ba_ria": (10.4960, 107.1680),
    "vung_tau": (10.4114, 107.1362),
    "hcm_east": (10.8231, 106.8120),

    # Nam Trung Bộ, dùng khi tuyến cần né từ Tây Nguyên xuống biển
    "phan_thiet": (10.9333, 108.1000),
    "phan_rang": (11.5639, 108.9880),
    "nha_trang": (12.2388, 109.1967),
}


def _point_to_segment_distance_km(p: Tuple[float, float],
                                  a: Tuple[float, float],
                                  b: Tuple[float, float]) -> float:
    """Khoảng cách xấp xỉ từ điểm p đến đoạn ab theo phép chiếu phẳng cục bộ."""
    lat, lon = p
    lat1, lon1 = a
    lat2, lon2 = b

    mean_lat = math.radians((lat + lat1 + lat2) / 3.0)
    km_per_deg_lat = 111.32
    km_per_deg_lon = 111.32 * max(0.2, math.cos(mean_lat))

    px = lon * km_per_deg_lon
    py = lat * km_per_deg_lat
    ax = lon1 * km_per_deg_lon
    ay = lat1 * km_per_deg_lat
    bx = lon2 * km_per_deg_lon
    by = lat2 * km_per_deg_lat

    dx = bx - ax
    dy = by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)

    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    cx = ax + t * dx
    cy = ay + t * dy
    return math.hypot(px - cx, py - cy)


def _distance_to_vn_corridor_km(lat: float, lon: float) -> float:
    p = (lat, lon)
    best = float("inf")
    for i in range(len(VN_CORRIDOR_ANCHORS) - 1):
        best = min(
            best,
            _point_to_segment_distance_km(
                p,
                VN_CORRIDOR_ANCHORS[i],
                VN_CORRIDOR_ANCHORS[i + 1],
            ),
        )
    return best


def _min_safe_lon_by_lat(lat: float) -> float:
    """
    Biên Tây xấp xỉ của phần đất liền Việt Nam theo vĩ độ.

    Mục tiêu của bảng này không phải thay thế bản đồ biên giới chính xác, mà là
    chặn các tuyến OSRM bị kéo sâu sang Lào/Campuchia trong khi vẫn cho phép
    các tuyến hợp lệ ở Tây Nguyên, Đông Nam Bộ và miền Tây.
    """
    table = [
        (9.8, 104.55),
        (10.6, 104.85),
        (11.1, 105.80),
        (12.3, 106.55),
        (13.5, 107.05),
        (14.8, 107.10),
        (16.2, 106.45),
        (17.5, 105.85),
        (19.4, 104.55),
        (21.5, 103.60),
        (23.5, 102.10),
    ]

    prev_lat, prev_lon = table[0]
    if lat <= prev_lat:
        return prev_lon

    for cur_lat, cur_lon in table[1:]:
        if lat <= cur_lat:
            t = (lat - prev_lat) / max(1e-9, cur_lat - prev_lat)
            return prev_lon + t * (cur_lon - prev_lon)
        prev_lat, prev_lon = cur_lat, cur_lon

    return table[-1][1]


def _in_vn_safe(lat: float, lon: float) -> bool:
    """
    Kiểm tra an toàn không dùng shapely.

    V3 dùng khoảng cách tới hành lang giao thông VN nên đôi khi đánh dấu nhầm
    tuyến hợp lệ ở Lâm Đồng/Bảo Lộc/Đạ Tẻh là không an toàn, làm app phải ghim
    hub xa và tạo vòng lớn. V4 chuyển sang biên Tây xấp xỉ theo vĩ độ: ít ép
    tuyến hơn, nhưng vẫn chặn đoạn đi sâu sang Campuchia/Lào.
    """
    if not _in_vn_bbox(lat, lon):
        return False

    west_limit = _min_safe_lon_by_lat(lat)

    # Cho phép một biên sai số nhỏ vì dữ liệu đường/bản đồ có thể lệch vài km.
    return lon >= west_limit - 0.08


def _densify_polyline(polyline: List[List[float]], max_step_km: float = 8.0) -> List[List[float]]:
    """Chèn thêm điểm giữa các segment dài để không bỏ sót đoạn cắt biên."""
    if not polyline:
        return []

    dense = [polyline[0]]
    for p1, p2 in zip(polyline, polyline[1:]):
        lon1, lat1 = p1
        lon2, lat2 = p2
        d = haversine_distance(lat1, lon1, lat2, lon2)
        n = max(1, int(math.ceil(d / max_step_km)))
        for k in range(1, n + 1):
            t = k / n
            dense.append([
                lon1 + (lon2 - lon1) * t,
                lat1 + (lat2 - lat1) * t,
            ])
    return dense


def _polyline_in_vn_ratio(polyline: List[List[float]]) -> float:
    """Tỉ lệ điểm nằm trong vùng VN an toàn. Polyline format: [[lon, lat], ...]."""
    if not polyline:
        return 1.0

    dense = _densify_polyline(polyline)
    inside = sum(1 for lon, lat in dense if _in_vn_safe(lat, lon))
    return inside / len(dense)


def _route_crosses_border(polyline: List[List[float]], min_ratio: float = 0.985) -> bool:
    """
    True nếu tuyến có dấu hiệu ra khỏi lãnh thổ VN.

    Dùng ngưỡng rất cao vì yêu cầu của app là: nếu tồn tại tuyến nội địa thì không
    hiển thị tuyến qua nước ngoài.
    """
    if not polyline:
        return False

    dense = _densify_polyline(polyline)
    if not dense:
        return False

    outside_count = sum(1 for lon, lat in dense if not _in_vn_safe(lat, lon))
    ratio = 1.0 - outside_count / len(dense)

    # Chỉ cần có một chuỗi nhiều điểm liên tiếp ở ngoài là xem như vượt biên.
    consecutive_outside = 0
    for lon, lat in dense:
        if _in_vn_safe(lat, lon):
            consecutive_outside = 0
        else:
            consecutive_outside += 1
            if consecutive_outside >= 3:
                return True

    return ratio < min_ratio


def _select_waypoints(origin: Tuple[float, float],
                      destination: Tuple[float, float],
                      max_hubs: int = 3,
                      force: bool = False) -> List[Tuple[float, float]]:
    """
    Chọn waypoint VN theo kiểu thích nghi.

    Khác v3: không tự ghim hub cho mọi tuyến. Chỉ thêm hub khi tuyến dài/nguy
    cơ cao hoặc khi get_route đã phát hiện direct route vượt biên. Điều này giữ
    tuyến vòng cục bộ ngắn như code cũ, nhưng vẫn có cơ chế ép trục VN cho các
    tuyến dài như HCM ↔ Hà Nội.
    """
    lat1, lon1 = origin
    lat2, lon2 = destination

    dist_km = haversine_distance(lat1, lon1, lat2, lon2)
    delta_lat = abs(lat1 - lat2)
    delta_lon = abs(lon1 - lon2)

    if not force:
        # Tuyến ngắn/trung bình ở nội tỉnh hoặc Tây Nguyên không nên ghim hub xa.
        if dist_km < 260:
            return []

        # Chỉ tự ghim khi tuyến có xu hướng Bắc-Nam dài.
        if dist_km < 520 and delta_lat < 3.0:
            return []

        # Tuyến chủ yếu Đông-Tây thường không cần hub Bắc-Nam.
        if delta_lon > delta_lat * 1.8 and dist_km < 650:
            return []

    lat_lo = min(lat1, lat2)
    lat_hi = max(lat1, lat2)
    buf = 0.6

    hubs_between = [
        (name, pos)
        for name, pos in VN_HUBS.items()
        if lat_lo - buf <= pos[0] <= lat_hi + buf
    ]

    if not hubs_between:
        return []

    going_south = lat1 > lat2
    hubs_between.sort(key=lambda x: x[1][0], reverse=going_south)

    if force and dist_km > 900:
        max_hubs = max(max_hubs, 5)
    elif force or dist_km > 700:
        max_hubs = max(max_hubs, 4)

    waypoints = []
    for _, pos in hubs_between:
        d_from_origin = haversine_distance(lat1, lon1, pos[0], pos[1])
        d_from_dest = haversine_distance(lat2, lon2, pos[0], pos[1])

        if d_from_origin < 35 or d_from_dest < 35:
            continue

        # Không chọn hub làm đường vòng vô lý. Ngưỡng rộng hơn code 1 để vẫn
        # ghim được tuyến dài, nhưng tránh vòng kiểu ảnh 1.
        d_od = max(1.0, dist_km)
        detour = (d_from_origin + d_from_dest) / d_od
        max_detour = 1.35 if force else 1.22
        if detour > max_detour:
            continue

        if waypoints and haversine_distance(pos[0], pos[1], waypoints[-1][0], waypoints[-1][1]) < 70:
            continue

        waypoints.append(pos)
        if len(waypoints) >= max_hubs:
            break

    return waypoints


# ─────────────────────────────────────────────────────────────────────────────
# HỆ SỐ THỜI GIAN THỰC TẾ VN
# ─────────────────────────────────────────────────────────────────────────────

VN_TIME_FACTORS = {
    "car": {"short": 1.5, "medium": 1.7, "long": 1.8},
    "motorbike": {"short": 1.4, "medium": 1.6, "long": 1.75},
    "bike": {"short": 1.2, "medium": 1.3, "long": 1.4},
    "walk": {"short": 1.1, "medium": 1.1, "long": 1.1},
}


def _distance_category(km: float) -> str:
    if km < 50:
        return "short"
    if km < 200:
        return "medium"
    return "long"


def _apply_vn_factor(duration_min: float, distance_km: float, mode: str) -> float:
    cat = _distance_category(distance_km)
    factor = VN_TIME_FACTORS.get(mode, VN_TIME_FACTORS["car"]).get(cat, 1.7)
    return round(duration_min * factor, 1)


# ─────────────────────────────────────────────────────────────────────────────
# ROUTER
# ─────────────────────────────────────────────────────────────────────────────

class Router:
    def __init__(self):
        logger.info("Router (OSRM + adaptive VN waypoint guard + VN time factor) khởi động")

    # ── PUBLIC API ──────────────────────────────────────────────────────────

    def get_route(self, origin: Tuple[float, float],
                  destination: Tuple[float, float],
                  mode: str = "car",
                  waypoints=None,
                  avoid_zones=None) -> Optional[Dict]:
        """
        Tính tuyến đường, ưu tiên tuyến ngắn hợp lệ trong VN.

        V4 sửa lỗi v3 tạo tuyến quá vòng: thử direct route trước; nếu direct
        không vượt biên thì dùng luôn. Chỉ khi direct route vượt biên mới chèn
        hub VN để ép OSRM đi trong nước.
        """
        user_wps = list(waypoints or [])

        # 1) Luôn thử tuyến tự nhiên trước. Đây là tuyến thường ngắn nhất và
        # đúng với các trường hợp cục bộ như Đạ Tẻh/Bảo Lộc/Đà Lạt.
        route_direct = self._call_osrm(origin, destination, mode, user_wps or None)
        if route_direct and not _route_crosses_border(route_direct.get("polyline", []), min_ratio=0.97):
            route_direct["vn_guard_waypoints"] = []
            return route_direct

        # 2) Nếu direct có dấu hiệu vượt biên thì mới dùng hub nhẹ.
        candidates = []
        if route_direct:
            candidates.append(route_direct)

        vn_wps = _select_waypoints(origin, destination, force=True)
        if vn_wps or user_wps:
            route_hub = self._call_osrm(origin, destination, mode, user_wps + vn_wps)
            if route_hub:
                route_hub["vn_guard_waypoints"] = vn_wps
                candidates.append(route_hub)

        valid_routes = [
            rt for rt in candidates
            if not _route_crosses_border(rt.get("polyline", []), min_ratio=0.97)
        ]

        if valid_routes:
            valid_routes.sort(key=lambda rt: (rt.get("duration_min", 1e18), rt.get("distance_km", 1e18)))
            return valid_routes[0]

        # 3) Tuyến dài vẫn lỗi: thử nhiều chuỗi hub hơn.
        best_route = None
        best_ratio = -1.0
        for rt in candidates:
            ratio = _polyline_in_vn_ratio(rt.get("polyline", []))
            if ratio > best_ratio:
                best_ratio = ratio
                best_route = rt

        if not user_wps:
            logger.warning(f"Direct route có dấu hiệu vượt biên, best_ratio={best_ratio:.1%}; thử force_vn_route")
            route_forced = self._force_vn_route(origin, destination, mode)
            if route_forced and not _route_crosses_border(route_forced.get("polyline", []), min_ratio=0.97):
                return route_forced
            if route_forced and _polyline_in_vn_ratio(route_forced.get("polyline", [])) > best_ratio:
                best_route = route_forced

        # 4) Không trả tuyến nghi ngờ vượt biên.
        if best_route and not _route_crosses_border(best_route.get("polyline", []), min_ratio=0.93):
            return best_route

        fallback = self._fallback_route(origin, destination, mode)
        fallback["note"] = (
            "⚠️ OSRM trả tuyến có dấu hiệu vượt biên. "
            "Ứng dụng đã chặn không hiển thị tuyến đó; đây là ước tính tạm thời."
        )
        fallback["blocked_border_route"] = True
        return fallback

    def get_alternative_routes(self, origin: Tuple[float, float],
                               destination: Tuple[float, float],
                               mode: str = "car",
                               count: int = 3) -> List[Dict]:
        """Trả về tuyến thay thế; ưu tiên tuyến tự nhiên, chỉ dùng hub khi cần."""
        profile = OSRM_PROFILES.get(mode, "driving")

        route_sets = []
        # A. Alternatives tự nhiên trước để tránh vòng xa không cần thiết.
        route_sets.append([])

        # B. Hub chỉ là phương án dự phòng cho tuyến dài/nguy cơ.
        vn_wps = _select_waypoints(origin, destination, force=False)
        if vn_wps:
            route_sets.append(vn_wps)

        labels = ["🚀 Nhanh nhất", "⛽ Tiết kiệm nhiên liệu", "🌿 Cảnh đẹp"]
        routes = []
        seen = set()

        for wps in route_sets:
            coords = self._build_coords(origin, destination, wps)
            url = f"{OSRM_BASE}/{profile}/{coords}"
            params = {
                "overview": "full",
                "geometries": "geojson",
                "steps": "true",
                "alternatives": str(max(0, count - 1)),
            }

            try:
                r = requests.get(url, params=params, timeout=20)
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                logger.error(f"get_alternative_routes lỗi: {e}")
                continue

            for raw in data.get("routes", []):
                parsed = self._parse_osrm_single(raw, mode)
                if _route_crosses_border(parsed.get("polyline", []), min_ratio=0.95):
                    continue

                # Khử trùng lặp tương đối theo distance/duration.
                key = (round(parsed.get("distance_km", 0), 1), round(parsed.get("duration_min", 0), 1))
                if key in seen:
                    continue
                seen.add(key)

                parsed["vn_guard_waypoints"] = wps
                routes.append(parsed)

        routes.sort(key=lambda rt: (rt.get("duration_min", 1e18), rt.get("distance_km", 1e18)))
        for i, rt in enumerate(routes):
            rt["label"] = labels[i] if i < len(labels) else f"Tuyến {i + 1}"

        if not routes:
            fb = self.get_route(origin, destination, mode)
            routes = [fb] if fb else []

        return routes[:count]

    # ── PUBLIC: SO SÁNH TUYẾN ──────────────────────────────────────────────

    def compare_routes(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        mode: str = "car",
        risk_engine=None,
    ) -> List[Dict]:
        """
        So sánh nhiều tuyến và phân loại: nhanh nhất / an toàn nhất / cân bằng.

        Mỗi tuyến trong kết quả được bổ sung các trường:
            comparison_label   : "🚀 Nhanh nhất" / "🛡️ An toàn nhất" / "⚖️ Cân bằng"
            comparison_tag     : "fastest" / "safest" / "balanced"
            avg_risk_score     : rủi ro trung bình (0-1)
            danger_zone_count  : số vùng nguy hiểm trên tuyến
            ai_rating          : "Thấp" / "Trung bình" / "Cao"
            balance_score      : điểm kết hợp tốc độ + an toàn (càng thấp càng tốt)
            rank_reason        : lý do gợi ý

        Trả về danh sách đã sắp xếp: [fastest, safest, balanced] (không trùng
        nếu có ít tuyến hơn).
        """
        # ── 1. Lấy các tuyến thay thế từ OSRM ──────────────────────────────
        routes = self.get_alternative_routes(origin, destination, mode=mode, count=3)
        if not routes:
            fb = self.get_route(origin, destination, mode=mode)
            routes = [fb] if fb else []
        if not routes:
            return []

        # ── 2. Tính chỉ số rủi ro cho từng tuyến ────────────────────────────
        for rt in routes:
            poly = rt.get("polyline", [])

            if risk_engine is not None and poly:
                try:
                    analysis = risk_engine.analyze_route(poly)
                    avg_risk = analysis.get("avg_score", 0.0)
                    danger_count = len(analysis.get("danger_segments", []))
                except Exception:
                    avg_risk = 0.0
                    danger_count = 0
            else:
                # Fallback: ước tính rủi ro đơn giản từ số điểm polyline
                avg_risk = 0.0
                danger_count = 0

            rt["avg_risk_score"]   = round(avg_risk, 3)
            rt["danger_zone_count"] = danger_count

            # AI rating theo ngưỡng
            if avg_risk < 0.35:
                rt["ai_rating"] = "Thấp"
            elif avg_risk < 0.60:
                rt["ai_rating"] = "Trung bình"
            else:
                rt["ai_rating"] = "Cao"

        # ── 3. Chuẩn hoá thời gian và rủi ro để tính điểm cân bằng ─────────
        durations = [rt.get("duration_min", 1) or 1 for rt in routes]
        risks     = [rt["avg_risk_score"] for rt in routes]

        dur_min_val  = min(durations)
        dur_max_val  = max(durations) if max(durations) != dur_min_val else dur_min_val + 1
        risk_min_val = min(risks)
        risk_max_val = max(risks) if max(risks) != risk_min_val else risk_min_val + 0.01

        for rt in routes:
            dur_norm  = (rt.get("duration_min", dur_min_val) - dur_min_val) / (dur_max_val - dur_min_val)
            risk_norm = (rt["avg_risk_score"] - risk_min_val) / (risk_max_val - risk_min_val)
            # 40% trọng số tốc độ, 60% trọng số an toàn
            rt["balance_score"] = round(0.40 * dur_norm + 0.60 * risk_norm, 4)

        # ── 4. Gán nhãn ─────────────────────────────────────────────────────
        # Sắp theo thời gian → fastest
        sorted_by_dur  = sorted(routes, key=lambda r: r.get("duration_min", 1e9))
        # Sắp theo rủi ro  → safest
        sorted_by_risk = sorted(routes, key=lambda r: r["avg_risk_score"])
        # Sắp theo điểm cân bằng → balanced
        sorted_by_bal  = sorted(routes, key=lambda r: r["balance_score"])

        fastest = sorted_by_dur[0]
        safest  = sorted_by_risk[0]
        # Tuyến cân bằng: ưu tiên tuyến không phải fastest hoặc safest
        balanced_candidates = [r for r in sorted_by_bal if r is not fastest and r is not safest]
        balanced = balanced_candidates[0] if balanced_candidates else (
            sorted_by_bal[0] if sorted_by_bal else fastest
        )

        # Tránh nhãn trùng khi chỉ có 1-2 tuyến
        _seen_tags: dict = {}

        def _assign(rt: Dict, tag: str, label: str, reason: str):
            if id(rt) not in _seen_tags:
                _seen_tags[id(rt)] = (tag, label, reason)

        _assign(fastest, "fastest", "🚀 Nhanh nhất",
                "Thời gian di chuyển ngắn nhất, phù hợp khi cần đến nơi sớm.")
        _assign(safest,  "safest",  "🛡️ An toàn nhất",
                "Ít vùng nguy hiểm nhất, phù hợp khi trời mưa / đi đêm / có trẻ nhỏ.")
        _assign(balanced, "balanced", "⚖️ Cân bằng",
                "Không quá dài nhưng vẫn giảm đáng kể rủi ro so với tuyến nhanh nhất.")

        # Gán cho các tuyến còn lại chưa có nhãn
        _fallback_labels = [
            ("extra1", "📍 Tuyến thêm", "Tuyến bổ sung để tham khảo."),
            ("extra2", "📍 Tuyến khác", "Tuyến bổ sung để tham khảo."),
        ]
        _fi = 0
        for rt in routes:
            if id(rt) not in _seen_tags:
                if _fi < len(_fallback_labels):
                    _assign(rt, *_fallback_labels[_fi])
                    _fi += 1

        for rt in routes:
            tag, label, reason = _seen_tags.get(id(rt), ("extra", "📍 Tuyến khác", ""))
            rt["comparison_tag"]   = tag
            rt["comparison_label"] = label
            rt["rank_reason"]      = reason

        # ── 5. Sắp xếp kết quả: fastest → safest → balanced → others ────────
        order = {"fastest": 0, "safest": 1, "balanced": 2}
        routes.sort(key=lambda r: order.get(r["comparison_tag"], 9))

        return routes

    def reroute_around_incident(self,
                                current_pos: Tuple[float, float],
                                destination: Tuple[float, float],
                                incident_lat: float,
                                incident_lon: float,
                                mode: str = "car",
                                avoid_radius_km: float = 2.0) -> Optional[Dict]:
        """
        Tính tuyến vòng tránh sự cố theo kiểu "endpoint-safe".

        Điểm sửa quan trọng so với bản gốc:
        - Nếu sự cố ở gần điểm xuất phát hoặc điểm đến, không bắt tuyến phải
          tránh tuyệt đối ngay từ mét đầu/cuối, vì điều đó làm mọi tuyến đều bị
          loại. Thay vào đó hệ thống chọn hướng thoát vùng nguy hiểm rồi né tốt
          nhất có thể.
        - Nếu không có tuyến tránh tuyệt đối, vẫn trả tuyến khả dụng tốt nhất
          để tới đích, kèm cờ soft_avoid=True thay vì trả None.
        - Thử cả waypoint hình tròn quanh sự cố và anchor đường thật để giảm lỗi
          "OSRM không thể đến waypoint lệch".
        """
        if avoid_radius_km <= 0:
            avoid_radius_km = 1.0

        start_dist = haversine_distance(current_pos[0], current_pos[1], incident_lat, incident_lon)
        dest_dist = haversine_distance(destination[0], destination[1], incident_lat, incident_lon)
        start_inside = start_dist < avoid_radius_km
        dest_inside = dest_dist < avoid_radius_km

        # Nếu endpoint nằm trong vùng tránh, bỏ qua một đoạn đầu/cuối khi đo
        # clearance; nếu không làm vậy thì min distance luôn < radius và mọi
        # tuyến đều bị loại dù tuyến đã thoát vùng ngay sau đó.
        skip_start_km = 0.0
        skip_end_km = 0.0
        if start_inside:
            skip_start_km = min(avoid_radius_km * 1.5, max(1.5, avoid_radius_km - start_dist + 1.5))
        if dest_inside:
            skip_end_km = min(avoid_radius_km * 1.5, max(1.5, avoid_radius_km - dest_dist + 1.5))

        candidates: List[Dict] = []
        seen = set()

        # Tuyến tự nhiên chỉ dùng làm mốc/fallback, không ưu tiên hơn tuyến có waypoint.
        direct_route = self._call_osrm(current_pos, destination, mode, None)
        direct_distance = None
        if direct_route and not _route_crosses_border(direct_route.get("polyline", []), min_ratio=0.95):
            direct_distance = max(1.0, direct_route.get("distance_km", 0) or 1.0)

        def _signature(route: Dict) -> Tuple[float, float, int]:
            return (
                round(route.get("distance_km", 0), 1),
                round(route.get("duration_min", 0), 1),
                len(route.get("polyline", []) or []),
            )

        def _add_candidate(route: Optional[Dict], source: str, waypoints_used: List[Tuple[float, float]]):
            if not route or route.get("fallback"):
                return
            poly = route.get("polyline", [])
            if not poly or len(poly) < 2:
                return
            if _route_crosses_border(poly, min_ratio=0.95):
                return

            sig = _signature(route)
            if sig in seen:
                return
            seen.add(sig)

            stats = self._incident_exposure_stats(
                poly,
                incident_lat,
                incident_lon,
                avoid_radius_km,
                skip_start_km=skip_start_km,
                skip_end_km=skip_end_km,
            )

            distance_km = max(0.1, route.get("distance_km", 0) or 0.1)
            detour_ratio = distance_km / direct_distance if direct_distance else 1.0

            # Hard avoid: đoạn được đánh giá nằm ngoài vùng tránh gần như hoàn toàn.
            hard_avoid = stats["min_clearance_km"] >= avoid_radius_km * 0.95 and stats["exposure_score"] <= 0.05

            # Soft avoid: vẫn có thể đi qua vùng gần sự cố, nhưng đã giảm đáng kể
            # so với việc bắt buộc tránh tuyệt đối. Dùng khi endpoint nằm trong vùng
            # sự cố hoặc khu vực chỉ có một trục đường.
            soft_avoid = (
                hard_avoid
                or stats["min_clearance_km"] >= avoid_radius_km * 0.55
                or stats["inside_ratio"] <= 0.18
                or start_inside
                or dest_inside
            )

            item = dict(route)
            item.update({
                "rerouted": True,
                "label": "🔄 Tuyến vòng tránh sự cố",
                "avoided_incident": {
                    "lat": incident_lat,
                    "lon": incident_lon,
                    "radius_km": avoid_radius_km,
                    "start_inside_avoid_zone": start_inside,
                    "dest_inside_avoid_zone": dest_inside,
                },
                "incident_clearance_km": round(stats["min_clearance_km"], 2),
                "incident_exposure_score": round(stats["exposure_score"], 3),
                "incident_inside_ratio": round(stats["inside_ratio"], 3),
                "reroute_source": source,
                "reroute_waypoints": list(waypoints_used),
                "hard_avoid": hard_avoid,
                "soft_avoid": soft_avoid,
                "detour_ratio": round(detour_ratio, 3),
            })

            if start_inside:
                item["note"] = (
                    "Sự cố nằm gần điểm xuất phát, nên hệ thống chọn hướng thoát "
                    "vùng nguy hiểm rồi né tốt nhất có thể."
                )
            elif dest_inside:
                item["note"] = (
                    "Sự cố nằm gần điểm đến, nên hệ thống ưu tiên tiếp cận an toàn "
                    "nhất có thể thay vì tránh tuyệt đối."
                )
            elif not hard_avoid:
                item["note"] = (
                    "Không tìm được tuyến tránh tuyệt đối trong điều kiện đường hiện có; "
                    "đây là tuyến né tốt nhất để vẫn tới đích."
                )

            candidates.append(item)

        def _try_waypoints(wps: List[Tuple[float, float]], source: str):
            # Bỏ waypoint nằm quá sát sự cố hoặc ngoài vùng VN an toàn.
            clean = []
            for wp in wps:
                if not _in_vn_safe(wp[0], wp[1]):
                    continue
                if haversine_distance(wp[0], wp[1], incident_lat, incident_lon) < avoid_radius_km * 0.75:
                    continue
                clean.append(wp)
            if not clean:
                return

            route = self._call_osrm(current_pos, destination, mode, clean)

            # Nếu route có dấu hiệu vượt biên, thử thêm hub VN như logic gốc.
            if route and _route_crosses_border(route.get("polyline", []), min_ratio=0.95):
                vn_wps = _select_waypoints(current_pos, destination, force=True)
                route = self._call_osrm(current_pos, destination, mode, clean + vn_wps)
                clean = clean + vn_wps

            _add_candidate(route, source, clean)

        # 1) Waypoint quanh sự cố theo nhiều hướng. Khi sự cố gần điểm xuất phát,
        # các waypoint này đóng vai trò "điểm thoát vùng".
        bearing_list = (0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330)
        radius_mults = (1.10, 1.45, 2.0, 2.8, 4.0)
        if start_inside or dest_inside:
            radius_mults = (1.05, 1.35, 1.8, 2.5, 3.5, 5.0)

        for radius_mult in radius_mults:
            radius = max(1.0, avoid_radius_km * radius_mult)
            for bearing_deg in bearing_list:
                waypoint = self._destination_point(incident_lat, incident_lon, radius, bearing_deg)
                _try_waypoints([waypoint], source=f"ring_{radius_mult:.2f}_{bearing_deg}")

        # 2) Anchor đường thật. Hữu ích ở các khu đèo/đô thị nơi waypoint hình tròn
        # rơi vào rừng, hồ hoặc đường không thể snap.
        for anchor in self._candidate_reroute_anchors(current_pos, destination, incident_lat, incident_lon, avoid_radius_km):
            _try_waypoints([anchor], source="road_anchor")

        # 3) Với endpoint gần sự cố, thử phối hợp điểm thoát vùng + anchor để tạo
        # tuyến mới rõ ràng hơn nhưng vẫn không viết lại thuật toán routing.
        if start_inside or dest_inside:
            anchors = self._candidate_reroute_anchors(current_pos, destination, incident_lat, incident_lon, avoid_radius_km)[:6]
            for anchor in anchors:
                for bearing_deg in (45, 90, 135, 225, 270, 315):
                    escape = self._destination_point(incident_lat, incident_lon, avoid_radius_km * 1.25, bearing_deg)
                    _try_waypoints([escape, anchor], source="escape_plus_anchor")

        # 4) Fallback cuối: tuyến tự nhiên vẫn tới đích, nhưng bị đánh dấu soft_avoid
        # để UI có thể cảnh báo thay vì lỗi trắng.
        if direct_route:
            _add_candidate(direct_route, "direct_fallback", [])

        if not candidates:
            logger.warning("Không tìm được tuyến vòng; fallback về get_route thông thường")
            fallback = self.get_route(current_pos, destination, mode)
            if fallback:
                fallback["rerouted"] = False
                fallback["soft_avoid"] = True
                fallback["note"] = "Không tìm được tuyến vòng khả dụng; giữ tuyến tốt nhất để vẫn tới đích."
            return fallback

        def _rank(rt: Dict):
            # Ưu tiên: tránh cứng > tránh mềm > có waypoint thật > ít phơi nhiễm > ít vòng > nhanh.
            has_wp = 1 if rt.get("reroute_waypoints") else 0
            direct_penalty = 1 if rt.get("reroute_source") == "direct_fallback" else 0
            detour_over = max(0.0, rt.get("detour_ratio", 1.0) - 1.0)
            return (
                1 if rt.get("hard_avoid") else 0,
                1 if rt.get("soft_avoid") else 0,
                has_wp,
                -direct_penalty,
                -rt.get("incident_exposure_score", 999),
                -detour_over,
                -rt.get("duration_min", 1e18),
                -rt.get("distance_km", 1e18),
            )

        candidates.sort(key=_rank, reverse=True)
        best = candidates[0]

        if not best.get("hard_avoid"):
            best["soft_avoid"] = True
            best.setdefault(
                "note",
                "Không có tuyến tránh tuyệt đối; hệ thống chọn tuyến né tốt nhất có thể để vẫn tới đích."
            )

        return best

    # ── INTERNAL: OSRM ─────────────────────────────────────────────────────

    def _call_osrm(self, origin: Tuple[float, float],
                   destination: Tuple[float, float],
                   mode: str,
                   waypoints=None) -> Optional[Dict]:
        """Gọi OSRM và trả về dict đã parse, hoặc None nếu lỗi."""
        profile = OSRM_PROFILES.get(mode, "driving")
        coords = self._build_coords(origin, destination, waypoints)
        url = f"{OSRM_BASE}/{profile}/{coords}"
        params = {
            "overview": "full",
            "geometries": "geojson",
            "steps": "true",
            "annotations": "false",
        }

        try:
            r = requests.get(url, params=params, timeout=20)
            r.raise_for_status()
            data = r.json()

            if data.get("code") != "Ok":
                logger.error(f"OSRM lỗi: {data.get('code')}")
                return None

            return self._parse_osrm(data, mode)

        except requests.exceptions.Timeout:
            logger.error("OSRM timeout")
            return None
        except Exception as e:
            logger.error(f"OSRM exception: {e}")
            return None

    def _force_vn_route(self, origin: Tuple[float, float],
                        destination: Tuple[float, float],
                        mode: str) -> Optional[Dict]:
        """
        Thử nhiều tổ hợp hub VN liên tiếp trên trục để ép tuyến đi trong nước.
        Lấy tuyến hợp lệ đầu tiên tốt nhất; nếu chưa có, lấy tuyến có ratio cao nhất.
        """
        lat1, lon1 = origin
        lat2, lon2 = destination

        lat_lo = min(lat1, lat2) - 1.0
        lat_hi = max(lat1, lat2) + 1.0

        candidate_hubs = [
            pos for pos in VN_HUBS.values()
            if lat_lo <= pos[0] <= lat_hi
            and haversine_distance(lat1, lon1, pos[0], pos[1]) > 30
            and haversine_distance(lat2, lon2, pos[0], pos[1]) > 30
        ]

        if not candidate_hubs:
            return None

        going_south = lat1 > lat2
        candidate_hubs.sort(key=lambda p: p[0], reverse=going_south)

        best_route = None
        best_key = (-1.0, -1e18, -1e18)

        # Tổ hợp 1-5 hub liên tiếp. Giữ liên tiếp để tránh OSRM loop bất thường.
        max_chain = min(5, len(candidate_hubs))
        for i in range(len(candidate_hubs)):
            for j in range(i + 1, min(i + max_chain, len(candidate_hubs)) + 1):
                wps = candidate_hubs[i:j]
                rt = self._call_osrm(origin, destination, mode, wps)
                if not rt:
                    continue

                ratio = _polyline_in_vn_ratio(rt.get("polyline", []))
                safe = not _route_crosses_border(rt.get("polyline", []), min_ratio=0.95)

                # Ưu tiên safe, rồi ratio, rồi duration ngắn.
                key = (1.0 if safe else 0.0, ratio, -rt.get("duration_min", 1e18))
                if key > best_key:
                    best_key = key
                    best_route = rt
                    best_route["vn_guard_waypoints"] = list(wps)

                if safe and ratio >= 0.985:
                    return rt

        return best_route

    def _build_coords(self, origin: Tuple[float, float],
                      destination: Tuple[float, float],
                      waypoints=None) -> str:
        """Xây chuỗi tọa độ OSRM; bỏ qua waypoint ngoài vùng VN an toàn."""
        pts = [f"{origin[1]},{origin[0]}"]

        if waypoints:
            for wp in waypoints:
                if _in_vn_safe(wp[0], wp[1]):
                    pts.append(f"{wp[1]},{wp[0]}")
                else:
                    logger.warning(f"Bỏ waypoint ngoài VN/suspect: {wp}")

        pts.append(f"{destination[1]},{destination[0]}")
        return ";".join(pts)

    # ── INTERNAL: PARSE ───────────────────────────────────────────────────

    def _parse_osrm(self, data: Dict, mode: str) -> Dict:
        return self._parse_osrm_single(data["routes"][0], mode)

    def _parse_osrm_single(self, route: Dict, mode: str) -> Dict:
        distance_m = route["distance"]
        duration_s = route["duration"]
        distance_km = round(distance_m / 1000, 2)

        # Giữ ưu điểm code 1: lấy geometry từ steps để polyline chi tiết hơn.
        polyline = self._extract_route_geometry(route)

        raw_min = round(duration_s / 60, 1)
        real_min = _apply_vn_factor(raw_min, distance_km, mode)

        steps = []
        for leg in route.get("legs", []):
            for step in leg.get("steps", []):
                maneuver = step.get("maneuver", {})
                step_dist = step.get("distance", 0)
                step_raw = round(step.get("duration", 0) / 60, 1)
                step_real = _apply_vn_factor(step_raw, step_dist / 1000, mode)
                steps.append({
                    "instruction": self._instruction(maneuver, step),
                    "distance_km": round(step_dist / 1000, 2),
                    "duration_min": step_real,
                })

        return {
            "distance_km": distance_km,
            "duration_min": real_min,
            "duration_min_raw": raw_min,
            "distance_text": format_distance(distance_km),
            "duration_text": format_duration(round(real_min)),
            "polyline": polyline,
            "steps": steps,
            "source": "osrm",
            "vn_ratio": round(_polyline_in_vn_ratio(polyline), 4),
            "crosses_border": _route_crosses_border(polyline, min_ratio=0.95),
        }

    def _extract_route_geometry(self, route: Dict) -> List[List[float]]:
        """
        Lấy geometry từ route-level overview (nguồn đầy đủ nhất, bám đường thực tế
        kể cả đèo nhiều cua) thay vì ghép lại từng step.

        Khi request với overview=full + geometries=geojson, OSRM đã trả toàn bộ
        polyline chi tiết ở route["geometry"]["coordinates"]. Ghép lại từng step
        không thêm độ chính xác mà còn dễ mất điểm ở ranh giới step, khiến tuyến
        "cắt thẳng" qua rừng thay vì đi theo khúc cua đèo thực tế.

        Fallback về step-level chỉ khi route-level geometry thiếu.
        """
        # Nguồn chính: overview geometry của cả route
        route_coords = route.get("geometry", {}).get("coordinates", [])
        if route_coords and len(route_coords) >= 2:
            return route_coords

        # Fallback: ghép từng step
        coords = []
        for leg in route.get("legs", []):
            for step in leg.get("steps", []):
                step_geometry = step.get("geometry", {}).get("coordinates", [])
                if not step_geometry:
                    continue
                if coords and coords[-1] == step_geometry[0]:
                    coords.extend(step_geometry[1:])
                else:
                    coords.extend(step_geometry)
        return coords

    # ── INTERNAL: CHỈ DẪN ─────────────────────────────────────────────────

    def _instruction(self, maneuver: Dict, step: Dict) -> str:
        m_type = maneuver.get("type", "")
        m_mod = maneuver.get("modifier", "")
        name = step.get("name") or "đường không tên"
        dist = step.get("distance", 0)
        dtxt = f"{int(dist)} m" if dist < 1000 else f"{dist / 1000:.1f} km"

        turn_map = {
            "left": "rẽ trái",
            "right": "rẽ phải",
            "slight left": "rẽ nhẹ trái",
            "slight right": "rẽ nhẹ phải",
            "sharp left": "rẽ gắt trái",
            "sharp right": "rẽ gắt phải",
            "straight": "đi thẳng",
            "uturn": "quay đầu",
        }

        if m_type == "depart":
            return f"Xuất phát, đi theo {name} ({dtxt})"
        if m_type == "arrive":
            return "Đã đến điểm đến"
        if m_type in ("turn", "new name"):
            return f"{turn_map.get(m_mod, m_mod).capitalize()} vào {name} ({dtxt})"
        if m_type == "merge":
            return f"Nhập vào {name} ({dtxt})"
        if m_type == "ramp":
            return f"Vào đường dẫn {turn_map.get(m_mod, '')} đến {name} ({dtxt})"
        if m_type == "fork":
            return f"Tại ngã rẽ, đi {turn_map.get(m_mod, '')} theo {name} ({dtxt})"
        if m_type == "end of road":
            return f"Cuối đường, {turn_map.get(m_mod, '')} vào {name} ({dtxt})"
        if m_type == "roundabout":
            return f"Vào vòng xuyến, ra lối thoát số {maneuver.get('exit', 1)} vào {name} ({dtxt})"
        if m_type == "continue":
            return f"Tiếp tục theo {name} ({dtxt})"

        return f"Đi theo {name} ({dtxt})"

    # ── INTERNAL: TIỆN ÍCH ────────────────────────────────────────────────

    def _candidate_reroute_anchors(self,
                                  current_pos: Tuple[float, float],
                                  destination: Tuple[float, float],
                                  incident_lat: float,
                                  incident_lon: float,
                                  avoid_radius_km: float) -> List[Tuple[float, float]]:
        """
        Lọc các anchor đường thật phù hợp cho reroute.
        Chỉ dùng trong tính tuyến vòng, không ảnh hưởng get_route thường.
        """
        base_dist = max(1.0, haversine_distance(current_pos[0], current_pos[1], destination[0], destination[1]))
        out = []
        seen = set()

        lat_min = min(current_pos[0], destination[0], incident_lat) - 1.2
        lat_max = max(current_pos[0], destination[0], incident_lat) + 1.2
        lon_min = min(current_pos[1], destination[1], incident_lon) - 1.2
        lon_max = max(current_pos[1], destination[1], incident_lon) + 1.2

        for _, pos in REROUTE_ANCHORS.items():
            lat, lon = pos
            if not _in_vn_safe(lat, lon):
                continue
            if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
                continue
            if haversine_distance(lat, lon, incident_lat, incident_lon) < avoid_radius_km * 0.8:
                continue

            detour = (
                haversine_distance(current_pos[0], current_pos[1], lat, lon)
                + haversine_distance(lat, lon, destination[0], destination[1])
            ) / base_dist

            # Ngưỡng rộng vì đây chỉ là candidate; rank cuối sẽ loại tuyến quá vòng.
            if detour > 2.35:
                continue

            key = (round(lat, 3), round(lon, 3))
            if key in seen:
                continue
            seen.add(key)
            out.append((lat, lon, detour))

        out.sort(key=lambda x: x[2])
        return [(lat, lon) for lat, lon, _ in out]

    def _incident_exposure_stats(self,
                                 polyline: List[List[float]],
                                 incident_lat: float,
                                 incident_lon: float,
                                 avoid_radius_km: float,
                                 skip_start_km: float = 0.0,
                                 skip_end_km: float = 0.0) -> Dict:
        """
        Đánh giá tuyến còn đi gần sự cố bao nhiêu.
        skip_start_km/skip_end_km dùng cho trường hợp sự cố sát điểm xuất phát/đến.
        """
        if not polyline:
            return {"min_clearance_km": 0.0, "exposure_score": 999.0, "inside_ratio": 1.0}

        dense = _densify_polyline(polyline, max_step_km=1.0)
        if len(dense) < 2:
            lon, lat = dense[0]
            d = haversine_distance(lat, lon, incident_lat, incident_lon)
            return {
                "min_clearance_km": d,
                "exposure_score": max(0.0, avoid_radius_km - d) / max(avoid_radius_km, 1e-6),
                "inside_ratio": 1.0 if d < avoid_radius_km else 0.0,
            }

        cumulative = [0.0]
        total = 0.0
        for p1, p2 in zip(dense, dense[1:]):
            lon1, lat1 = p1
            lon2, lat2 = p2
            total += haversine_distance(lat1, lon1, lat2, lon2)
            cumulative.append(total)

        min_clearance = float("inf")
        exposure = 0.0
        inside = 0
        evaluated = 0

        for (lon, lat), km in zip(dense, cumulative):
            if km < skip_start_km:
                continue
            if total - km < skip_end_km:
                continue
            d = haversine_distance(lat, lon, incident_lat, incident_lon)
            min_clearance = min(min_clearance, d)
            evaluated += 1
            if d < avoid_radius_km:
                inside += 1
                exposure += (avoid_radius_km - d) / max(avoid_radius_km, 1e-6)

        if evaluated == 0:
            for lon, lat in dense:
                d = haversine_distance(lat, lon, incident_lat, incident_lon)
                min_clearance = min(min_clearance, d)
                evaluated += 1
                if d < avoid_radius_km:
                    inside += 1
                    exposure += (avoid_radius_km - d) / max(avoid_radius_km, 1e-6)

        return {
            "min_clearance_km": 0.0 if min_clearance == float("inf") else min_clearance,
            "exposure_score": exposure,
            "inside_ratio": inside / max(1, evaluated),
        }

    def _route_clearance_km(self, polyline: List[List[float]],
                            incident_lat: float,
                            incident_lon: float) -> float:
        """Khoảng cách tối thiểu từ polyline tới điểm sự cố, km."""
        if not polyline:
            return 0.0

        return min(
            haversine_distance(lat, lon, incident_lat, incident_lon)
            for lon, lat in polyline
        )

    def _destination_point(self, lat: float,
                           lon: float,
                           distance_km: float,
                           bearing_deg: float) -> Tuple[float, float]:
        """Tính tọa độ cách (lat, lon) một khoảng theo hướng bearing_deg."""
        R = 6371.0
        d = distance_km / R
        lat1 = math.radians(lat)
        lon1 = math.radians(lon)
        brng = math.radians(bearing_deg)

        lat2 = math.asin(
            math.sin(lat1) * math.cos(d)
            + math.cos(lat1) * math.sin(d) * math.cos(brng)
        )
        lon2 = lon1 + math.atan2(
            math.sin(brng) * math.sin(d) * math.cos(lat1),
            math.cos(d) - math.sin(lat1) * math.sin(lat2),
        )

        return (math.degrees(lat2), math.degrees(lon2))

    def _fallback_route(self, origin: Tuple[float, float],
                        destination: Tuple[float, float],
                        mode: str = "car") -> Dict:
        """Ước tính đường chim bay khi OSRM không khả dụng hoặc route bị chặn."""
        km = haversine_distance(*origin, *destination)
        raw_min = round(km / 40 * 60)
        real_min = _apply_vn_factor(raw_min, km, mode)

        return {
            "distance_km": round(km, 2),
            "duration_min": real_min,
            "duration_min_raw": raw_min,
            "distance_text": format_distance(km),
            "duration_text": format_duration(round(real_min)),
            "polyline": [],
            "steps": [],
            "fallback": True,
            "source": "fallback",
            "note": "⚠️ Không kết nối được OSRM, đây là ước tính đường chim bay.",
        }