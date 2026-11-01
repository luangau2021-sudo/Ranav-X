from typing import List, Dict, Optional, Tuple
from utils.helpers import haversine_distance, load_json
from utils.config import CULTURAL_FILE
from utils.logger import setup_logger
import math
import time
import requests
import json
import os
import unicodedata
import re

logger = setup_logger(__name__)

SAMPLE_POIS = [
    {"id":"poi_001","name":"Hồ Xuân Hương",      "lat":11.9404,"lon":108.4383,"category":"relaxation","tags":["lake","relaxation","scenic"],         "rating":4.7,"province":"Đà Lạt","type":"Hồ"},
    {"id":"poi_002","name":"Thác Datanla",         "lat":11.9049,"lon":108.4483,"category":"nature",    "tags":["waterfall","adventure","nature"],      "rating":4.5,"province":"Đà Lạt","type":"Thác"},
    {"id":"poi_003","name":"Chợ Đà Lạt",           "lat":11.9414,"lon":108.4415,"category":"food",      "tags":["market","food","culture"],             "rating":4.3,"province":"Đà Lạt","type":"Chợ"},
    {"id":"poi_004","name":"Thiền Viện Trúc Lâm",  "lat":11.8998,"lon":108.4141,"category":"culture",   "tags":["temple","culture","scenic"],           "rating":4.8,"province":"Đà Lạt","type":"Thiền viện"},
    {"id":"poi_005","name":"Mũi Né",               "lat":10.9432,"lon":108.2794,"category":"relaxation","tags":["beach","resort","relaxation"],         "rating":4.6,"province":"Bình Thuận","type":"Bãi biển"},
    {"id":"poi_006","name":"Phố cổ Hội An",        "lat":15.8801,"lon":108.3380,"category":"culture",   "tags":["heritage","culture","food","scenic"],  "rating":4.9,"province":"Quảng Nam","type":"Di sản"},
    {"id":"poi_007","name":"Vịnh Hạ Long",         "lat":20.9101,"lon":107.1839,"category":"nature",    "tags":["nature","boat","adventure","scenic"],  "rating":4.9,"province":"Quảng Ninh","type":"Vịnh"},
    {"id":"poi_008","name":"Sapa",                 "lat":22.3364,"lon":103.8438,"category":"adventure", "tags":["mountain","trekking","nature"],        "rating":4.7,"province":"Lào Cai","type":"Núi"},
    {"id":"poi_009","name":"Phong Nha - Kẻ Bàng",  "lat":17.5580,"lon":106.1427,"category":"nature",   "tags":["cave","ecotourism","adventure"],       "rating":4.8,"province":"Quảng Bình","type":"Hang động"},
    {"id":"poi_010","name":"Bà Nà Hills",           "lat":15.9973,"lon":107.9888,"category":"attraction","tags":["attraction","scenic","culture"],       "rating":4.5,"province":"Đà Nẵng","type":"Khu du lịch"},
    {"id":"poi_011","name":"Đảo Phú Quốc",         "lat":10.2897,"lon":103.9840,"category":"relaxation","tags":["beach","resort","relaxation","nature"],"rating":4.7,"province":"Kiên Giang","type":"Đảo"},
    {"id":"poi_012","name":"Ninh Bình – Tràng An", "lat":20.2510,"lon":105.9755,"category":"nature",   "tags":["scenic","boat","culture","ecotourism"], "rating":4.8,"province":"Ninh Bình","type":"Cảnh quan"},
    {"id":"poi_013","name":"Đèo Hải Vân",          "lat":16.2033,"lon":108.0847,"category":"scenic",   "tags":["scenic","mountain","adventure"],        "rating":4.6,"province":"Đà Nẵng","type":"Đèo"},
    {"id":"poi_014","name":"Chùa Bái Đính",        "lat":20.3250,"lon":105.8500,"category":"culture",  "tags":["temple","culture","heritage"],          "rating":4.6,"province":"Ninh Bình","type":"Chùa"},
    {"id":"poi_015","name":"Mekong – Cần Thơ",     "lat":10.0452,"lon":105.7469,"category":"culture",  "tags":["boat","food","culture","ecotourism"],   "rating":4.5,"province":"Cần Thơ","type":"Sông"},
    {"id":"poi_016","name":"Núi Bà Đen",           "lat":11.4167,"lon":106.0830,"category":"culture",  "tags":["mountain","temple","culture"],          "rating":4.4,"province":"Tây Ninh","type":"Núi"},
    {"id":"poi_017","name":"Bến Tre – Dừa nước",   "lat":10.2430,"lon":106.3756,"category":"ecotourism","tags":["ecotourism","boat","food"],            "rating":4.3,"province":"Bến Tre","type":"Sinh thái"},
    {"id":"poi_018","name":"Hồ Tuyền Lâm",         "lat":11.8668,"lon":108.4276,"category":"relaxation","tags":["lake","relaxation","nature"],         "rating":4.5,"province":"Đà Lạt","type":"Hồ"},
    {"id":"poi_019","name":"Nhà thờ Con Gà Đà Lạt","lat":11.9401,"lon":108.4394,"category":"culture", "tags":["heritage","culture","scenic"],          "rating":4.4,"province":"Đà Lạt","type":"Nhà thờ"},
    {"id":"poi_020","name":"Dinh Bảo Đại",         "lat":11.9200,"lon":108.4347,"category":"culture",  "tags":["heritage","culture","history"],         "rating":4.3,"province":"Đà Lạt","type":"Di tích"},
    {"id":"poi_021","name":"Thác Pongour",         "lat":11.6294,"lon":108.2100,"category":"nature",   "tags":["waterfall","nature","adventure"],       "rating":4.4,"province":"Lâm Đồng","type":"Thác"},
    {"id":"poi_022","name":"Bãi biển Nha Trang",   "lat":12.2451,"lon":109.1946,"category":"relaxation","tags":["beach","relaxation","resort"],        "rating":4.5,"province":"Khánh Hòa","type":"Bãi biển"},
    {"id":"poi_023","name":"Tháp Chàm Mỹ Sơn",    "lat":15.7630,"lon":108.1230,"category":"culture",  "tags":["heritage","culture","history"],         "rating":4.7,"province":"Quảng Nam","type":"Di sản"},
    {"id":"poi_024","name":"Hội quán Phúc Kiến",   "lat":15.8772,"lon":108.3274,"category":"culture",  "tags":["heritage","culture","food"],            "rating":4.6,"province":"Quảng Nam","type":"Di tích"},
    {"id":"poi_025","name":"Suối Tiên",            "lat":10.8677,"lon":106.8494,"category":"attraction","tags":["attraction","family","relaxation"],    "rating":4.2,"province":"TP.HCM","type":"Khu vui chơi"},
]

STYLE_TAGS = {
    "adventure":  ["trekking","mountain","waterfall","cave","boat","adventure"],
    "culture":    ["temple","museum","heritage","festival","culture","history"],
    "food":       ["restaurant","street_food","market","cafe","food"],
    "relaxation": ["beach","resort","spa","lake","relaxation"],
    "family":     ["park","zoo","amusement","beach","family","attraction"],
    "ecotourism": ["ecotourism","nature","boat","lake"],
    "scenic":     ["scenic","mountain","waterfall","boat"],
    "fuel":       ["fuel", "gas_station", "petrol"],
    "all":        [],   # không lọc
}


class POIEngine:
    TRAVEL_STYLES = STYLE_TAGS

    def __init__(self):
        self.cultural_data = load_json(CULTURAL_FILE) or {}
        self.pois = SAMPLE_POIS

    # ── Dọc tuyến đường ──────────────────────────────────────────────────────
    def get_pois_on_route(self, polyline: List, style: str = "all",
                          buffer_km: float = 8.0, max_results: int = 12) -> List[Dict]:
        """
        Tìm POI trong buffer_km km tính từ tuyến đường.
        polyline: list [[lon,lat], ...]
        """
        if not polyline:
            return []

        style_tags = STYLE_TAGS.get(style, [])
        results    = []
        # Sample polyline để tính nhanh
        sample = polyline[::max(1, len(polyline)//80)]

        for poi in self.pois:
            # Khoảng cách nhỏ nhất từ POI đến tuyến
            min_dist = min(
                haversine_distance(poi["lat"], poi["lon"], c[1], c[0])
                for c in sample
            )
            if min_dist > buffer_km:
                continue

            # Tính km từ đầu tuyến đến điểm gần nhất
            route_km = self._km_along_route(poi, sample)

            # Match score
            if style == "all" or not style_tags:
                match = 0.5
            else:
                overlap = len(set(poi.get("tags",[])) & set(style_tags))
                match   = overlap / len(style_tags) if style_tags else 0.5

            if match == 0 and style != "all":
                continue

            results.append({
                **poi,
                "dist_from_route_km": round(min_dist, 2),
                "route_km":           round(route_km, 1),
                "match_score":        round(match, 2),
                "final_score":        round(match * 0.55 + poi.get("rating", 3) / 5 * 0.45, 3),
            })

        results.sort(key=lambda x: x["final_score"], reverse=True)
        return results[:max_results]


    # ── Cây xăng dọc đúng tuyến ─────────────────────────────────────────────
    def get_fuel_stations_on_route(self, polyline: List, corridor_m: float = 300,
                                   max_results: int = 12,
                                   current_position: Optional[Tuple[float, float]] = None,
                                   only_upcoming: bool = True) -> List[Dict]:
        """
        Tìm cây xăng dọc tuyến theo cơ chế search-along-route.

        Bản nâng cấp:
        - Vẫn ưu tiên hành lang hẹp 300m để không lấy cây xăng lệch hẻm.
        - Nếu không có kết quả, tự nới dần 600m → 1000m → 1500m.
        - Không chặn cứng vì nhiều cây xăng OSM bị đặt lệch khỏi tim đường.
        - Luôn gắn route_km để panel JS tính "còn bao nhiêu km" theo GPS mỗi giây.
        """
        if not polyline or len(polyline) < 2:
            return []

        requested = max(100.0, float(corridor_m or 300.0))
        corridor_steps = []
        for c in [requested, 600.0, 1000.0, 1500.0]:
            if c not in corridor_steps:
                corridor_steps.append(c)

        # Fetch Overpass một lần theo bbox rộng, sau đó lọc nhiều mức corridor.
        route_key_base = self._route_cache_key(polyline, 1500)
        cache = getattr(self, "_fuel_route_cache", {})
        cached = cache.get(route_key_base)
        now = time.time()
        # Cache kết quả có dữ liệu 15 phút; cache rỗng chỉ 45 giây để không bị kẹt "không có cây xăng".
        if cached:
            age = now - cached.get("ts", 0)
            cached_raw = list(cached.get("raw", []))
            if cached_raw and age < 15 * 60:
                raw_stations = cached_raw
            elif (not cached_raw) and age < 45:
                raw_stations = cached_raw
            else:
                raw_stations = self._fetch_fuel_from_overpass(polyline)
                cache[route_key_base] = {"ts": now, "raw": raw_stations}
                self._fuel_route_cache = cache
        else:
            raw_stations = self._fetch_fuel_from_overpass(polyline)
            cache[route_key_base] = {"ts": now, "raw": raw_stations}
            self._fuel_route_cache = cache

        # Ghép thêm kho cây xăng cục bộ nếu OSM/Overpass thiếu dữ liệu.
        # File này giúp app không phụ thuộc 100% vào Google/OSM: bạn có thể tự thêm cây xăng thật.
        try:
            custom_stations = self._load_custom_fuel_stations()
            if custom_stations:
                raw_stations = self._merge_fuel_stations(raw_stations, custom_stations)
        except Exception:
            pass

        # Lọc bỏ cây xăng đóng cửa trước khi xét hành lang tuyến.
        raw_stations = [x for x in (raw_stations or []) if not self._is_closed_fuel_station(x)]

        best = []
        used_corridor = None
        for cm in corridor_steps:
            filtered = self._filter_pois_along_route(raw_stations, polyline, corridor_m=cm)
            # Gộp trùng sau khi đã có route_km/dist_from_route_km để chọn bản tốt nhất.
            filtered = self._dedupe_fuel_stations_by_distance(filtered, threshold_m=120.0)
            if filtered:
                best = filtered
                used_corridor = cm
                break

        if not best:
            return []

        if current_position and only_upcoming:
            cur_km = self._nearest_km_on_polyline(polyline, current_position[0], current_position[1])
            best = [x for x in best if float(x.get("route_km", 0)) >= cur_km - 0.3]

        # Gộp thêm lần cuối sau khi bỏ cây đã đi qua.
        best = self._dedupe_fuel_stations_by_distance(best, threshold_m=120.0)

        for x in best:
            x["fuel_corridor_m"] = int(used_corridor or requested)

        best.sort(key=lambda x: (float(x.get("route_km", 0)), float(x.get("dist_from_route_km", 99))))
        return best[:max_results]

    def get_next_fuel_stations(self, fuel_stations: List[Dict], polyline: List,
                               current_position: Optional[Tuple[float, float]] = None,
                               max_results: int = 2) -> List[Dict]:
        """
        Lấy các cây xăng tiếp theo trên tuyến.

        Cơ chế:
        - Dựa vào route_km của cây xăng trên polyline.
        - Nếu có GPS hiện tại thì tính current_route_km.
        - Cây xăng đã đi qua quá 300m sẽ bị loại.
        - Cây xăng 2 tự đẩy lên cây xăng 1 sau khi đi qua cây xăng 1.
        - Trả thêm dist_ahead_km để UI hiển thị: còn bao nhiêu km tới cây xăng.
        """
        items = [dict(x) for x in (fuel_stations or [])]
        cur_km = 0.0
        has_gps = False
        if current_position and polyline:
            try:
                cur_km = float(self._nearest_km_on_polyline(polyline, current_position[0], current_position[1]) or 0.0)
                has_gps = True
            except Exception:
                cur_km = 0.0
                has_gps = False

        out = []
        for x in items:
            try:
                rk = float(x.get("route_km", 0) or 0.0)
            except Exception:
                rk = 0.0
            ahead = rk - cur_km if has_gps else rk
            # Đã đi qua hơn 300m thì bỏ khỏi danh sách.
            if has_gps and ahead < -0.3:
                continue
            x["current_route_km"] = cur_km if has_gps else None
            x["dist_ahead_km"] = max(0.0, ahead)
            out.append(x)

        out.sort(key=lambda x: float(x.get("dist_ahead_km", x.get("route_km", 0)) or 0.0))
        return out[:max_results]

    def _normalize_text_for_match(self, text: str) -> str:
        """Chuẩn hoá chữ Việt để lọc trùng/lọc đóng cửa chắc hơn."""
        try:
            text = str(text or "").lower().strip()
            text = unicodedata.normalize("NFD", text)
            text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
            text = text.replace("đ", "d")
            return " ".join(text.split())
        except Exception:
            return ""

    def _fuel_station_tags(self, station: Dict) -> Dict:
        """Gộp OSM tags + các field đã chuẩn hoá để kiểm tra trạng thái trạm xăng."""
        tags = {}
        try:
            raw = station.get("osm_tags") or station.get("tags_raw") or {}
            if isinstance(raw, dict):
                tags.update({str(k): v for k, v in raw.items()})
        except Exception:
            pass
        # Copy thêm các field phổ biến nếu có ở cấp station.
        for k in [
            "amenity", "construction:amenity", "disused:amenity", "abandoned:amenity",
            "construction", "access", "motor_vehicle", "vehicle", "opening_hours",
            "status", "operational_status", "name", "operator", "brand", "address",
            "description", "note", "source"
        ]:
            if station.get(k) is not None and k not in tags:
                tags[k] = station.get(k)
        return tags

    def _opening_hours_confidently_closed_now(self, opening_hours: str) -> bool:
        """
        Parser nhẹ cho opening_hours.
        Chỉ kết luận đóng nếu chuỗi đơn giản đủ chắc, ví dụ:
        - 24/7 -> không đóng
        - 06:00-22:00, Mo-Su 06:00-22:00 -> ngoài giờ thì đóng
        Nếu cú pháp phức tạp quá thì trả False để không loại nhầm.
        """
        text = str(opening_hours or "").strip()
        if not text:
            return False
        norm = self._normalize_text_for_match(text)
        if "24/7" in norm or "24h" in norm or "always open" in norm:
            return False
        if norm in {"off", "closed"}:
            return True

        # Nếu có nhiều điều kiện phức tạp như PH, sunrise, open ended... thì không tự đoán.
        if any(x in norm for x in ["ph", "su[", "sunrise", "sunset", "unknown"]):
            return False

        # Lấy tất cả khoảng giờ trong chuỗi. Không xử lý lịch ngày phức tạp; chỉ dùng khi có pattern rõ.
        intervals = re.findall(r'(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})', text)
        if not intervals:
            return False

        now = datetime.now().time()
        def _to_minutes(t: str) -> int:
            h, m = t.split(":", 1)
            return int(h) * 60 + int(m)
        now_min = now.hour * 60 + now.minute

        open_now = False
        for a, b in intervals:
            try:
                start = _to_minutes(a)
                end = _to_minutes(b)
                if start == end:
                    open_now = True
                    break
                if start < end:
                    if start <= now_min <= end:
                        open_now = True
                        break
                else:
                    # Qua nửa đêm, ví dụ 22:00-05:00
                    if now_min >= start or now_min <= end:
                        open_now = True
                        break
            except Exception:
                return False
        return not open_now

    def _is_closed_fuel_station(self, station: Dict) -> bool:
        """
        Bỏ qua cây xăng không nên gợi ý chính.
        Rule mới:
        - construction:amenity=fuel -> loại
        - disused/abandoned/closed/under construction -> loại
        - access=no/private + không có dấu hiệu hoạt động rõ -> loại
        - opening_hours hiện tại đã hết giờ -> loại khỏi top gợi ý
        - chữ đóng cửa/đang sửa/under construction trong tên/ghi chú -> loại
        """
        if not isinstance(station, dict):
            return True
        if station.get("active") is False:
            return True

        # Blacklist thủ công nếu người dùng có dùng về sau.
        try:
            if self._is_closed_by_user_override(station):
                return True
        except Exception:
            pass

        tags = self._fuel_station_tags(station)
        def _norm_val(key: str) -> str:
            return self._normalize_text_for_match(tags.get(key, ""))

        amenity = _norm_val("amenity")
        construction_amenity = _norm_val("construction:amenity")
        disused_amenity = _norm_val("disused:amenity")
        abandoned_amenity = _norm_val("abandoned:amenity")
        construction = _norm_val("construction")
        access = _norm_val("access")

        # 1) OSM lifecycle/construction tags.
        if construction_amenity == "fuel" or construction == "fuel":
            station["fuel_status"] = "under_construction"
            return True
        if disused_amenity == "fuel" or abandoned_amenity == "fuel":
            station["fuel_status"] = "closed_or_disused"
            return True
        if amenity in {"construction", "disused", "abandoned"}:
            station["fuel_status"] = "not_active_amenity"
            return True

        # 2) access=no/private: nếu không có tín hiệu mở cửa rõ thì không đưa vào gợi ý chính.
        if access in {"no", "private", "customers"}:
            oh = str(tags.get("opening_hours") or "")
            # customers đôi khi vẫn là trạm nội bộ/khách hàng; loại khỏi gợi ý chính cho an toàn.
            if access in {"no", "private", "customers"}:
                station["fuel_status"] = "access_restricted"
                return True

        # 3) Từ khoá đóng cửa/đang sửa trong dữ liệu text.
        parts = []
        for key in [
            "name", "address", "operator", "brand", "opening_hours", "status",
            "operational_status", "description", "note", "source"
        ]:
            val = tags.get(key)
            if val is not None:
                parts.append(str(val))
        txt = self._normalize_text_for_match(" | ".join(parts))
        closed_keywords = [
            "dong cua", "tam thoi dong cua", "da dong cua", "ngung hoat dong",
            "khong con hoat dong", "dang sua", "dang sua chua", "dang thi cong",
            "tam ngung", "nghi ban", "closed", "temporarily closed", "permanently closed",
            "under construction", "construction", "disused", "abandoned", "not in service",
            "out of service", "inactive", "razed", "demolished"
        ]
        if any(k in txt for k in closed_keywords):
            station["fuel_status"] = "closed_text"
            return True

        # 4) opening_hours: nếu chắc chắn đang ngoài giờ thì ẩn khỏi top gợi ý.
        opening_hours = str(tags.get("opening_hours") or "")
        if opening_hours and self._opening_hours_confidently_closed_now(opening_hours):
            station["fuel_status"] = "closed_now"
            return True

        station["fuel_status"] = "open_or_unknown"
        return False

    def _closed_fuel_override_paths(self):
        """Các vị trí file blacklist cây xăng đóng cửa."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return [
            os.path.join(os.getcwd(), "data", "fuel_stations_closed.json"),
            os.path.join(root, "data", "fuel_stations_closed.json"),
            os.path.join(os.getcwd(), "fuel_stations_closed.json"),
        ]

    def _load_closed_fuel_overrides(self) -> List[Dict]:
        """
        Đọc data/fuel_stations_closed.json để bỏ qua cây xăng Google/nguồn ngoài báo đóng cửa
        nhưng OSM không có tag trạng thái.

        Format hỗ trợ:
        [
          {"name":"Cây Xăng Viet Oil", "lat":11.123, "lon":107.456, "radius_m":150, "active":true},
          {"name_contains":"viet oil", "active":true}
        ]
        """
        now = time.time()
        cache = getattr(self, "_closed_fuel_override_cache", None)
        if isinstance(cache, dict) and now - cache.get("ts", 0) < 30:
            return list(cache.get("items", []))
        path = next((p for p in self._closed_fuel_override_paths() if os.path.exists(p)), None)
        items = []
        if path:
            try:
                data = json.load(open(path, "r", encoding="utf-8"))
                if isinstance(data, dict):
                    data = data.get("closed_stations") or data.get("stations") or []
                if isinstance(data, list):
                    for x in data:
                        if not isinstance(x, dict):
                            continue
                        if x.get("active", True) is False:
                            continue
                        items.append(dict(x))
            except Exception as e:
                logger.warning(f"Không đọc được fuel_stations_closed.json: {e}")
        self._closed_fuel_override_cache = {"ts": now, "items": items}
        return items

    def _is_closed_by_user_override(self, station: Dict) -> bool:
        """Bỏ qua station nếu khớp blacklist theo tên hoặc tọa độ gần nhau."""
        if not isinstance(station, dict):
            return False
        overrides = self._load_closed_fuel_overrides()
        if not overrides:
            return False
        st_name = self._normalize_text_for_match(" | ".join(str(station.get(k) or "") for k in ["name", "operator", "brand", "address", "description", "note"]))
        try:
            st_lat = float(station.get("lat"))
            st_lon = float(station.get("lon"))
        except Exception:
            st_lat = st_lon = None

        for item in overrides:
            # 1) Khớp tên chứa chuỗi do người dùng khai báo.
            needle = self._normalize_text_for_match(item.get("name_contains") or item.get("name") or "")
            if needle and st_name and needle in st_name:
                # Nếu có tọa độ thì vẫn ưu tiên kiểm tra tọa độ để không chặn nhầm cả thương hiệu.
                if item.get("lat") is None or item.get("lon") is None or st_lat is None or st_lon is None:
                    return True

            # 2) Khớp theo tọa độ gần nhau. Đây là cách an toàn nhất cho cây xăng đóng cửa.
            if item.get("lat") is not None and item.get("lon") is not None and st_lat is not None and st_lon is not None:
                try:
                    radius_m = float(item.get("radius_m") or 150.0)
                    d_km = haversine_distance(st_lat, st_lon, float(item.get("lat")), float(item.get("lon")))
                    if d_km <= radius_m / 1000.0:
                        return True
                except Exception:
                    pass
        return False

    def _fuel_name_quality(self, station: Dict) -> int:
        """Điểm chất lượng tên để khi trùng thì giữ bản có tên rõ hơn."""
        name = str(station.get("name") or "").strip()
        operator = str(station.get("operator") or station.get("brand") or "").strip()
        address = str(station.get("address") or station.get("province") or "").strip()
        score = 0
        if name and self._normalize_text_for_match(name) not in ["cay xang", "tram xang", "fuel", "gas station"]:
            score += 5
        if operator:
            score += 2
        if address:
            score += 1
        if station.get("source") == "custom":
            score += 1
        return score

    def _dedupe_fuel_stations_by_distance(self, stations: List[Dict], threshold_m: float = 100.0) -> List[Dict]:
        """
        Gộp các cây xăng trùng nhau từ OSM/custom.
        Nếu 2 điểm cách nhau dưới threshold_m thì coi là cùng một cây xăng.
        Ưu tiên giữ điểm: không đóng cửa, gần tuyến hơn, tên rõ hơn, route_km nhỏ hơn.
        """
        groups = []
        threshold_km = float(threshold_m or 100.0) / 1000.0
        for st in stations or []:
            if self._is_closed_fuel_station(st):
                continue
            try:
                lat, lon = float(st.get("lat")), float(st.get("lon"))
            except Exception:
                continue
            placed = False
            for group in groups:
                glat, glon = group["center"]
                if haversine_distance(lat, lon, glat, glon) <= threshold_km:
                    group["items"].append(st)
                    # cập nhật tâm đơn giản theo trung bình để gom cụm ổn hơn
                    n = len(group["items"])
                    group["center"] = ((glat * (n - 1) + lat) / n, (glon * (n - 1) + lon) / n)
                    placed = True
                    break
            if not placed:
                groups.append({"center": (lat, lon), "items": [st]})

        result = []
        for group in groups:
            def _rank(x):
                try:
                    dist_route = float(x.get("dist_from_route_km", 99.0) or 99.0)
                except Exception:
                    dist_route = 99.0
                try:
                    route_km = float(x.get("route_km", 10**9) or 10**9)
                except Exception:
                    route_km = 10**9
                # sort tăng: gần tuyến hơn, tên tốt hơn (âm để ưu tiên cao), route_km nhỏ hơn
                return (dist_route, -self._fuel_name_quality(x), route_km)
            best = sorted(group["items"], key=_rank)[0]
            result.append(best)

        result.sort(key=lambda x: (float(x.get("route_km", 0) or 0), float(x.get("dist_from_route_km", 99) or 99)))
        return result

    def _load_custom_fuel_stations(self) -> List[Dict]:
        """
        Fallback cục bộ: data/fuel_stations_custom.json
        Dùng khi OSM/Overpass thiếu cây xăng khu vực đó.

        Format:
        [
          {"name":"Petrolimex Madagui", "lat":11.3865, "lon":107.5326, "operator":"Petrolimex"}
        ]
        """
        candidates = [
            os.path.join(os.getcwd(), "data", "fuel_stations_custom.json"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "fuel_stations_custom.json"),
            os.path.join(os.getcwd(), "fuel_stations_custom.json"),
        ]
        path = next((x for x in candidates if os.path.exists(x)), None)
        if not path:
            return []
        try:
            data = json.load(open(path, "r", encoding="utf-8"))
            if isinstance(data, dict):
                data = data.get("stations") or data.get("fuel_stations") or []
            out = []
            for i, x in enumerate(data or []):
                try:
                    lat = float(x.get("lat"))
                    lon = float(x.get("lon"))
                except Exception:
                    continue
                station = {
                    "id": str(x.get("id") or f"custom_fuel_{i}"),
                    "name": str(x.get("name") or "Cây xăng"),
                    "lat": lat,
                    "lon": lon,
                    "category": "fuel",
                    "tags": ["fuel", "gas_station", "custom"],
                    "rating": x.get("rating", "—"),
                    "province": x.get("province", ""),
                    "address": x.get("address", ""),
                    "type": "Cây xăng",
                    "operator": x.get("operator") or x.get("brand") or "",
                    "brand": x.get("brand", ""),
                    "opening_hours": x.get("opening_hours", ""),
                    "access": x.get("access", ""),
                    "construction:amenity": x.get("construction:amenity", ""),
                    "construction": x.get("construction", ""),
                    "disused:amenity": x.get("disused:amenity", ""),
                    "abandoned:amenity": x.get("abandoned:amenity", ""),
                    "status": x.get("status", ""),
                    "description": x.get("description") or x.get("note") or "",
                    "active": x.get("active", True),
                    "source": "custom",
                    "osm_tags": x.get("osm_tags", {}) if isinstance(x.get("osm_tags", {}), dict) else {},
                }
                if not self._is_closed_fuel_station(station):
                    out.append(station)
            return self._dedupe_fuel_stations_by_distance(out, threshold_m=120.0)
        except Exception as e:
            logger.warning(f"Không đọc được data/fuel_stations_custom.json: {e}")
            return []

    def _merge_fuel_stations(self, *lists) -> List[Dict]:
        """Gộp dữ liệu OSM + custom, bỏ cây đóng cửa và bỏ trùng theo khoảng cách gần nhau."""
        out = []
        for items in lists:
            for x in items or []:
                try:
                    float(x.get("lat")); float(x.get("lon"))
                except Exception:
                    continue
                if self._is_closed_fuel_station(x):
                    continue
                y = dict(x)
                y["category"] = "fuel"
                out.append(y)
        return self._dedupe_fuel_stations_by_distance(out, threshold_m=120.0)

    def _fetch_fuel_from_overpass(self, polyline: List) -> List[Dict]:
        """
        Lấy cây xăng từ OpenStreetMap.

        Bản sửa mạnh hơn:
        - Không chỉ dùng bbox lớn vì Overpass dễ timeout/rỗng với tuyến dài.
        - Ưu tiên truy vấn theo các điểm mẫu dọc tuyến: nwr[amenity=fuel](around:...,...).
        - Bắt thêm một số tag/tên thường gặp ở Việt Nam: Petrolimex, PVOIL, xăng dầu...
        - Không cache rỗng quá lâu ở hàm gọi phía trên.
        """
        try:
            pts = [[float(p[1]), float(p[0])] for p in (polyline or []) if len(p) >= 2]
            if len(pts) < 2:
                return []

            # Lấy tối đa 18 điểm mẫu dọc tuyến để tránh query quá nặng.
            step = max(1, len(pts) // 18)
            samples = pts[::step]
            if pts[-1] not in samples:
                samples.append(pts[-1])
            samples = samples[:22]

            def _around_clauses(radius_m: int) -> str:
                clauses = []
                for lat, lon in samples:
                    # amenity=fuel là chuẩn nhất. name/brand mở rộng để bắt dữ liệu gắn thiếu tag.
                    clauses.append(f'node["amenity"="fuel"](around:{radius_m},{lat},{lon});')
                    clauses.append(f'way["amenity"="fuel"](around:{radius_m},{lat},{lon});')
                    clauses.append(f'relation["amenity"="fuel"](around:{radius_m},{lat},{lon});')
                    clauses.append(f'node["name"~"xăng|xang|petrol|fuel|Petrolimex|PVOIL|PV Oil|Mipec",i](around:{radius_m},{lat},{lon});')
                    clauses.append(f'way["name"~"xăng|xang|petrol|fuel|Petrolimex|PVOIL|PV Oil|Mipec",i](around:{radius_m},{lat},{lon});')
                return "\n".join(clauses)

            queries = []
            for radius in [1200, 2500, 5000]:
                queries.append(f"""
                [out:json][timeout:25];
                (
                  {_around_clauses(radius)}
                );
                out center tags;
                """)

            # Fallback bbox vẫn giữ lại nếu around query rỗng.
            lats = [p[0] for p in pts]; lons = [p[1] for p in pts]
            pad = 0.12
            south, north = min(lats) - pad, max(lats) + pad
            west, east = min(lons) - pad, max(lons) + pad
            queries.append(f"""
            [out:json][timeout:25];
            (
              node["amenity"="fuel"]({south},{west},{north},{east});
              way["amenity"="fuel"]({south},{west},{north},{east});
              relation["amenity"="fuel"]({south},{west},{north},{east});
              node["name"~"xăng|xang|petrol|fuel|Petrolimex|PVOIL|PV Oil|Mipec",i]({south},{west},{north},{east});
              way["name"~"xăng|xang|petrol|fuel|Petrolimex|PVOIL|PV Oil|Mipec",i]({south},{west},{north},{east});
            );
            out center tags;
            """)

            endpoints = [
                "https://overpass-api.de/api/interpreter",
                "https://overpass.kumi.systems/api/interpreter",
                "https://overpass.openstreetmap.ru/api/interpreter",
            ]

            last_err = None
            for query in queries:
                data = None
                for endpoint in endpoints:
                    try:
                        resp = requests.post(endpoint, data={"data": query}, timeout=30, headers={"User-Agent": "TripSmartPro/1.0"})
                        resp.raise_for_status()
                        data = resp.json()
                        break
                    except Exception as e:
                        last_err = e
                        continue
                if not data:
                    continue
                out = self._parse_overpass_fuel_elements(data)
                if out:
                    return out

            if last_err:
                logger.warning(f"Overpass chưa trả cây xăng: {last_err}")
            return []
        except Exception as e:
            logger.warning(f"Không lấy được cây xăng từ Overpass: {e}")
            return []

    def _parse_overpass_fuel_elements(self, data: Dict) -> List[Dict]:
        """Parse kết quả Overpass thành danh sách cây xăng chuẩn hoá."""
        out = []
        seen = set()
        for el in (data or {}).get("elements", []):
            lat = el.get("lat") or (el.get("center") or {}).get("lat")
            lon = el.get("lon") or (el.get("center") or {}).get("lon")
            if lat is None or lon is None:
                continue
            tags = el.get("tags") or {}
            name = tags.get("name") or tags.get("brand") or tags.get("operator") or "Cây xăng"
            key = (round(float(lat), 6), round(float(lon), 6), str(name).lower())
            if key in seen:
                continue
            seen.add(key)
            station = {
                "id": f"fuel_{el.get('type','node')}_{el.get('id','')}",
                "name": name,
                "lat": float(lat),
                "lon": float(lon),
                "category": "fuel",
                "tags": ["fuel", "gas_station"],
                "osm_tags": dict(tags),
                "rating": "—",
                "province": tags.get("addr:province") or tags.get("addr:city") or tags.get("addr:district") or "",
                "type": "Cây xăng",
                "operator": tags.get("operator") or tags.get("brand") or "",
                "brand": tags.get("brand", ""),
                "opening_hours": tags.get("opening_hours", ""),
                "access": tags.get("access", ""),
                "construction:amenity": tags.get("construction:amenity", ""),
                "construction": tags.get("construction", ""),
                "disused:amenity": tags.get("disused:amenity", ""),
                "abandoned:amenity": tags.get("abandoned:amenity", ""),
                "status": tags.get("status") or tags.get("operational_status") or tags.get("disused") or tags.get("abandoned") or "",
                "description": tags.get("description") or tags.get("note") or "",
                "source": "osm",
            }
            if not self._is_closed_fuel_station(station):
                out.append(station)
        return self._dedupe_fuel_stations_by_distance(out, threshold_m=120.0)

    def _filter_pois_along_route(self, pois: List[Dict], polyline: List,
                                 corridor_m: float = 300) -> List[Dict]:
        """Chỉ giữ POI nằm gần polyline thật, rồi gắn route_km để sắp theo tuyến."""
        results = []
        corridor_km = float(corridor_m) / 1000.0
        for poi in pois or []:
            lat, lon = poi.get("lat"), poi.get("lon")
            if lat is None or lon is None:
                continue
            dist_km, route_km = self._distance_and_km_to_polyline(polyline, float(lat), float(lon))
            if dist_km <= corridor_km:
                results.append({
                    **poi,
                    "dist_from_route_km": round(dist_km, 3),
                    "dist_from_route_m": int(round(dist_km * 1000)),
                    "route_km": round(route_km, 2),
                    "final_score": max(0.0, 1.0 - dist_km / max(corridor_km, 1e-9)),
                })
        results.sort(key=lambda x: (float(x.get("route_km", 0)), float(x.get("dist_from_route_km", 99))))
        return results

    def _route_cache_key(self, polyline: List, corridor_m: float) -> str:
        if not polyline:
            return "empty"
        pts = polyline[::max(1, len(polyline)//25)]
        raw = ";".join(f"{round(float(p[0]),4)},{round(float(p[1]),4)}" for p in pts if len(p) >= 2)
        return f"fuel:{int(corridor_m)}:{len(polyline)}:{raw}"

    def _nearest_km_on_polyline(self, polyline: List, lat: float, lon: float) -> float:
        return self._distance_and_km_to_polyline(polyline, lat, lon)[1]

    def _distance_and_km_to_polyline(self, polyline: List, lat: float, lon: float) -> Tuple[float, float]:
        """Khoảng cách vuông góc gần nhất tới polyline + km dọc tuyến tại điểm gần nhất."""
        if not polyline:
            return float("inf"), 0.0
        best_dist = float("inf")
        best_route_km = 0.0
        acc_km = 0.0
        for a, b in zip(polyline[:-1], polyline[1:]):
            try:
                lon1, lat1 = float(a[0]), float(a[1])
                lon2, lat2 = float(b[0]), float(b[1])
                seg_km = haversine_distance(lat1, lon1, lat2, lon2)
                dist_km, t = self._point_to_segment_distance_km(lat, lon, lat1, lon1, lat2, lon2)
                if dist_km < best_dist:
                    best_dist = dist_km
                    best_route_km = acc_km + max(0.0, min(1.0, t)) * seg_km
                acc_km += seg_km
            except Exception:
                continue
        return best_dist, best_route_km

    def _point_to_segment_distance_km(self, lat: float, lon: float,
                                      lat1: float, lon1: float,
                                      lat2: float, lon2: float) -> Tuple[float, float]:
        """Xấp xỉ phẳng đủ tốt cho hành lang 100–300m quanh tuyến."""
        mean_lat = math.radians((lat + lat1 + lat2) / 3.0)
        kx = 111.320 * math.cos(mean_lat)
        ky = 110.574
        px, py = lon * kx, lat * ky
        ax, ay = lon1 * kx, lat1 * ky
        bx, by = lon2 * kx, lat2 * ky
        vx, vy = bx - ax, by - ay
        wx, wy = px - ax, py - ay
        denom = vx * vx + vy * vy
        t = 0.0 if denom <= 1e-12 else (wx * vx + wy * vy) / denom
        t = max(0.0, min(1.0, t))
        cx, cy = ax + t * vx, ay + t * vy
        return math.sqrt((px - cx) ** 2 + (py - cy) ** 2), t

    # ── Gần điểm cụ thể ──────────────────────────────────────────────────────
    def get_pois_near_point(self, lat: float, lon: float,
                             style: str = "all", radius_km: float = 50.0,
                             max_results: int = 10) -> List[Dict]:
        """Tìm POI gần 1 điểm (dùng cho trang Điểm tham quan)."""
        style_tags = STYLE_TAGS.get(style, [])
        results    = []
        for poi in self.pois:
            dist = haversine_distance(lat, lon, poi["lat"], poi["lon"])
            if dist > radius_km:
                continue
            if style != "all" and style_tags:
                overlap = len(set(poi.get("tags",[])) & set(style_tags))
                if overlap == 0:
                    continue
                match = overlap / len(style_tags)
            else:
                match = 0.5

            results.append({
                **poi,
                "dist_from_route_km": round(dist, 2),
                "route_km":           0,
                "match_score":        round(match, 2),
            })

        results.sort(key=lambda x: x["dist_from_route_km"])
        return results[:max_results]

    def get_poi_detail(self, poi_id: str) -> Optional[Dict]:
        for poi in self.pois:
            if poi["id"] == poi_id:
                return {
                    **poi,
                    "story":      self._get_cultural_story(poi_id),
                    "local_food": self._get_local_food(poi.get("province","")),
                    "best_time":  "Tháng 11 – tháng 3 (mùa khô)",
                    "travel_tip": "Nên đến vào buổi sáng sớm để tránh đông đúc",
                }
        return None

    # ── Internal ─────────────────────────────────────────────────────────────
    def _km_along_route(self, poi: Dict, sample: List) -> float:
        """Ước tính km từ đầu tuyến đến điểm gần nhất với POI."""
        if not sample:
            return 0.0
        best_i, min_d = 0, float("inf")
        for i, c in enumerate(sample):
            d = haversine_distance(poi["lat"], poi["lon"], c[1], c[0])
            if d < min_d:
                min_d, best_i = d, i
        # Tính km đến điểm best_i
        km = 0.0
        for i in range(1, best_i + 1):
            km += haversine_distance(sample[i-1][1], sample[i-1][0],
                                     sample[i][1],   sample[i][0])
        return km

    def _get_cultural_story(self, poi_id: str) -> str:
        return self.cultural_data.get("stories", {}).get(
            poi_id, "Khám phá câu chuyện và lịch sử địa phương...")

    def _get_local_food(self, province: str) -> List[str]:
        food_map = {
            "Đà Lạt":      ["Bánh mì xíu mại","Bơ sáp Đà Lạt","Cà phê chồn"],
            "Hội An":      ["Cao lầu","Mì Quảng","Bánh mì Phượng"],
            "Quảng Nam":   ["Cao lầu","Mì Quảng","Bánh đập"],
            "Huế":         ["Bún bò Huế","Bánh nậm","Cơm hến"],
            "Hà Nội":      ["Phở Hà Nội","Bún chả","Bánh cuốn"],
            "TP.HCM":      ["Hủ tiếu Nam Vang","Bánh mì Sài Gòn","Cơm tấm"],
            "Đà Nẵng":     ["Mì Quảng","Bánh tráng cuốn thịt heo","Bún mắm nêm"],
            "Khánh Hòa":   ["Bún cá","Nem Ninh Hoà","Bánh căn"],
            "Cần Thơ":     ["Bánh cống","Lẩu mắm","Bún nước lèo"],
            "Quảng Bình":  ["Bánh canh","Chả mực","Cháo canh"],
        }
        return food_map.get(province, ["Ẩm thực địa phương đặc sắc"])