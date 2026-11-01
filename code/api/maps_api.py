# api/maps_api.py
# TripSmart Pro - Maps API
# Fix tổng quát: ưu tiên địa danh hành chính Việt Nam trước POI fuzzy.
# Nguồn tìm kiếm: tọa độ thô -> user alias -> city/admin alias -> Goong -> Geoapify -> Google -> Nominatim.

import os
import json
import time
import unicodedata
import re
import requests
from typing import Dict, List, Tuple, Optional, Any

try:
    from utils.config import GOOGLE_MAPS_API_KEY, USER_ALIASES_FILE
except Exception:
    GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
    USER_ALIASES_FILE = os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data")),
        "user_aliases.json",
    )

try:
    from utils.logger import setup_logger
    logger = setup_logger(__name__)
except Exception:
    import logging
    logger = logging.getLogger(__name__)

_TIMEOUT = 8
_RETRY = 2
_SLEEP = 0.15


def _strip_accents(text: str) -> str:
    """Bỏ dấu tiếng Việt để so khớp alias ổn định hơn."""
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D")
    return text


def _compact(text: str) -> str:
    text = (text or "").lower().strip()
    for ch in [".", ",", ";", ":", "-", "_", "(", ")", "[", "]", "'", '"']:
        text = text.replace(ch, " ")
    text = " ".join(text.split())
    return text


class MapsAPI:
    """
    Geocoding, tìm địa điểm, reverse geocode.

    Sửa lỗi quan trọng:
    - Nếu người dùng nhập tên thành phố/tỉnh như "vũng tàu", "nha trang",
      không được lấy POI có chữ gần giống ở nơi khác như "Quán ... Vũng Tàu".
    - Các địa danh hành chính Việt Nam được ưu tiên tuyệt đối trước API fuzzy.
    - API vẫn dùng cho địa chỉ chi tiết, POI, nhà riêng, quán ăn, trường học...
    """

    # Goong REST API
    GOONG_GEOCODE_URL = "https://rsapi.goong.io/Geocode"
    GOONG_AUTOCOMPLETE_URL = "https://rsapi.goong.io/Place/AutoComplete"
    GOONG_DETAIL_URL = "https://rsapi.goong.io/Place/Detail"

    # Geoapify
    GEOAPIFY_GEOCODE_URL = "https://api.geoapify.com/v1/geocode/search"
    GEOAPIFY_AUTOCOMPLETE_URL = "https://api.geoapify.com/v1/geocode/autocomplete"
    GEOAPIFY_PLACES_URL = "https://api.geoapify.com/v2/places"
    GEOAPIFY_REVERSE_URL = "https://api.geoapify.com/v1/geocode/reverse"

    # Google optional
    GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
    PLACES_TEXT_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    PLACES_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    STATIC_MAP_URL = "https://maps.googleapis.com/maps/api/staticmap"

    # OSM fallback
    NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
    NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"

    USER_AGENT = "TripSmartPro/1.0 (Vietnam navigation app; contact: demo@tripsmart.local)"
    VN_BBOX = (102.14, 8.18, 109.47, 23.39)  # lon_min, lat_min, lon_max, lat_max

    # Địa danh hành chính/địa điểm lớn: ưu tiên tuyệt đối khi query khớp chính xác.
    # Tọa độ là tâm tương đối của thành phố/khu vực, đủ tốt để routing OSRM.
    ADMIN_ALIASES: Dict[str, Tuple[float, float, str, str]] = {
        # Trung ương / thành phố lớn
        "ha noi": (21.0278, 105.8342, "Hà Nội", "Thành phố Hà Nội"),
        "hanoi": (21.0278, 105.8342, "Hà Nội", "Thành phố Hà Nội"),
        "tp ha noi": (21.0278, 105.8342, "Hà Nội", "Thành phố Hà Nội"),
        "ho chi minh": (10.7769, 106.7009, "TP.HCM", "Thành phố Hồ Chí Minh"),
        "ho chi minh city": (10.7769, 106.7009, "TP.HCM", "Thành phố Hồ Chí Minh"),
        "hcm": (10.7769, 106.7009, "TP.HCM", "Thành phố Hồ Chí Minh"),
        "tphcm": (10.7769, 106.7009, "TP.HCM", "Thành phố Hồ Chí Minh"),
        "tp hcm": (10.7769, 106.7009, "TP.HCM", "Thành phố Hồ Chí Minh"),
        "sai gon": (10.7769, 106.7009, "TP.HCM", "Thành phố Hồ Chí Minh"),
        "da nang": (16.0544, 108.2022, "Đà Nẵng", "Thành phố Đà Nẵng"),
        "hai phong": (20.8449, 106.6881, "Hải Phòng", "Thành phố Hải Phòng"),
        "can tho": (10.0452, 105.7469, "Cần Thơ", "Thành phố Cần Thơ"),

        # Nam Trung Bộ / Tây Nguyên / Đông Nam Bộ
        "nha trang": (12.2388, 109.1967, "Nha Trang", "Khánh Hòa"),
        "tp nha trang": (12.2388, 109.1967, "Nha Trang", "Khánh Hòa"),
        "khanh hoa": (12.2585, 109.0526, "Khánh Hòa", "Tỉnh Khánh Hòa"),
        "vung tau": (10.4114, 107.1362, "Vũng Tàu", "Bà Rịa - Vũng Tàu"),
        "tp vung tau": (10.4114, 107.1362, "Vũng Tàu", "Bà Rịa - Vũng Tàu"),
        "ba ria": (10.4963, 107.1684, "Bà Rịa", "Bà Rịa - Vũng Tàu"),
        "ba ria vung tau": (10.5417, 107.2430, "Bà Rịa - Vũng Tàu", "Tỉnh Bà Rịa - Vũng Tàu"),
        "da lat": (11.9404, 108.4583, "Đà Lạt", "Lâm Đồng"),
        "tp da lat": (11.9404, 108.4583, "Đà Lạt", "Lâm Đồng"),
        "bao loc": (11.5489, 107.8077, "Bảo Lộc", "Lâm Đồng"),
        "da huoai": (11.4240, 107.6460, "Đạ Huoai", "Lâm Đồng"),
        "madagui": (11.3890, 107.5320, "Madagui", "Lâm Đồng"),
        "madaguoi": (11.3890, 107.5320, "Madaguoi", "Lâm Đồng"),
        "lam dong": (11.5753, 108.1429, "Lâm Đồng", "Tỉnh Lâm Đồng"),
        "phan thiet": (10.9333, 108.1000, "Phan Thiết", "Bình Thuận"),
        "binh thuan": (11.0904, 108.0721, "Bình Thuận", "Tỉnh Bình Thuận"),
        "phan rang": (11.5639, 108.9880, "Phan Rang - Tháp Chàm", "Ninh Thuận"),
        "ninh thuan": (11.6739, 108.8629, "Ninh Thuận", "Tỉnh Ninh Thuận"),
        "quy nhon": (13.7765, 109.2237, "Quy Nhơn", "Bình Định"),
        "binh dinh": (13.7820, 109.2190, "Bình Định", "Tỉnh Bình Định"),
        "tuy hoa": (13.0955, 109.3209, "Tuy Hòa", "Phú Yên"),
        "phu yen": (13.0882, 109.0929, "Phú Yên", "Tỉnh Phú Yên"),
        "buon ma thuot": (12.6667, 108.0500, "Buôn Ma Thuột", "Đắk Lắk"),
        "dak lak": (12.7100, 108.2378, "Đắk Lắk", "Tỉnh Đắk Lắk"),
        "dak nong": (12.2646, 107.6098, "Đắk Nông", "Tỉnh Đắk Nông"),
        "pleiku": (13.9718, 108.0151, "Pleiku", "Gia Lai"),
        "gia lai": (13.8079, 108.1094, "Gia Lai", "Tỉnh Gia Lai"),
        "kon tum": (14.3497, 108.0005, "Kon Tum", "Tỉnh Kon Tum"),
        "bien hoa": (10.9574, 106.8427, "Biên Hòa", "Đồng Nai"),
        "dong nai": (11.0686, 107.1676, "Đồng Nai", "Tỉnh Đồng Nai"),
        "thu dau mot": (10.9804, 106.6519, "Thủ Dầu Một", "Bình Dương"),
        "binh duong": (11.3254, 106.4770, "Bình Dương", "Tỉnh Bình Dương"),
        "tay ninh": (11.3100, 106.0983, "Tây Ninh", "Tỉnh Tây Ninh"),
        "binh phuoc": (11.7512, 106.7235, "Bình Phước", "Tỉnh Bình Phước"),

        # Miền Tây
        "my tho": (10.3600, 106.3600, "Mỹ Tho", "Tiền Giang"),
        "tien giang": (10.4493, 106.3421, "Tiền Giang", "Tỉnh Tiền Giang"),
        "ben tre": (10.2415, 106.3759, "Bến Tre", "Tỉnh Bến Tre"),
        "tra vinh": (9.9347, 106.3453, "Trà Vinh", "Tỉnh Trà Vinh"),
        "vinh long": (10.2397, 105.9572, "Vĩnh Long", "Tỉnh Vĩnh Long"),
        "long xuyen": (10.3864, 105.4352, "Long Xuyên", "An Giang"),
        "an giang": (10.5216, 105.1259, "An Giang", "Tỉnh An Giang"),
        "rach gia": (10.0125, 105.0809, "Rạch Giá", "Kiên Giang"),
        "kien giang": (9.8249, 105.1259, "Kiên Giang", "Tỉnh Kiên Giang"),
        "soc trang": (9.6035, 105.9739, "Sóc Trăng", "Tỉnh Sóc Trăng"),
        "bac lieu": (9.2940, 105.7216, "Bạc Liêu", "Tỉnh Bạc Liêu"),
        "ca mau": (9.1768, 105.1524, "Cà Mau", "Tỉnh Cà Mau"),
        "hau giang": (9.7845, 105.4701, "Hậu Giang", "Tỉnh Hậu Giang"),
        "dong thap": (10.4938, 105.6882, "Đồng Tháp", "Tỉnh Đồng Tháp"),
        "sa dec": (10.2908, 105.7563, "Sa Đéc", "Đồng Tháp"),

        # Miền Trung / Bắc Trung Bộ
        "hoi an": (15.8801, 108.3380, "Hội An", "Quảng Nam"),
        "tam ky": (15.5736, 108.4740, "Tam Kỳ", "Quảng Nam"),
        "quang nam": (15.5394, 108.0191, "Quảng Nam", "Tỉnh Quảng Nam"),
        "quang ngai": (15.1214, 108.8044, "Quảng Ngãi", "Tỉnh Quảng Ngãi"),
        "hue": (16.4637, 107.5909, "Huế", "Thừa Thiên Huế"),
        "thua thien hue": (16.4637, 107.5909, "Thừa Thiên Huế", "Tỉnh Thừa Thiên Huế"),
        "dong hoi": (17.4689, 106.6223, "Đồng Hới", "Quảng Bình"),
        "quang binh": (17.6103, 106.3487, "Quảng Bình", "Tỉnh Quảng Bình"),
        "dong ha": (16.8163, 107.1003, "Đông Hà", "Quảng Trị"),
        "quang tri": (16.7403, 107.1855, "Quảng Trị", "Tỉnh Quảng Trị"),
        "vinh": (18.6796, 105.6813, "Vinh", "Nghệ An"),
        "nghe an": (19.2342, 104.9200, "Nghệ An", "Tỉnh Nghệ An"),
        "ha tinh": (18.3559, 105.8877, "Hà Tĩnh", "Tỉnh Hà Tĩnh"),
        "thanh hoa": (19.8075, 105.7764, "Thanh Hóa", "Tỉnh Thanh Hóa"),
        "ninh binh": (20.2506, 105.9745, "Ninh Bình", "Tỉnh Ninh Bình"),
        "nam dinh": (20.4388, 106.1621, "Nam Định", "Tỉnh Nam Định"),

        # Miền Bắc
        "ha long": (20.9712, 107.0448, "Hạ Long", "Quảng Ninh"),
        "quang ninh": (21.0064, 107.2925, "Quảng Ninh", "Tỉnh Quảng Ninh"),
        "thai nguyen": (21.5928, 105.8442, "Thái Nguyên", "Tỉnh Thái Nguyên"),
        "bac giang": (21.2731, 106.1946, "Bắc Giang", "Tỉnh Bắc Giang"),
        "bac ninh": (21.1861, 106.0763, "Bắc Ninh", "Tỉnh Bắc Ninh"),
        "hai duong": (20.9373, 106.3145, "Hải Dương", "Tỉnh Hải Dương"),
        "hung yen": (20.6464, 106.0511, "Hưng Yên", "Tỉnh Hưng Yên"),
        "hoa binh": (20.8172, 105.3376, "Hòa Bình", "Tỉnh Hòa Bình"),
        "son la": (21.3270, 103.9141, "Sơn La", "Tỉnh Sơn La"),
        "dien bien phu": (21.3860, 103.0230, "Điện Biên Phủ", "Điện Biên"),
        "dien bien": (21.8042, 103.1077, "Điện Biên", "Tỉnh Điện Biên"),
        "lao cai": (22.4856, 103.9707, "Lào Cai", "Tỉnh Lào Cai"),
        "sapa": (22.3364, 103.8438, "Sa Pa", "Lào Cai"),
        "sa pa": (22.3364, 103.8438, "Sa Pa", "Lào Cai"),
        "ha giang": (22.8233, 104.9836, "Hà Giang", "Tỉnh Hà Giang"),
        "cao bang": (22.6657, 106.2570, "Cao Bằng", "Tỉnh Cao Bằng"),
        "lang son": (21.8526, 106.7615, "Lạng Sơn", "Tỉnh Lạng Sơn"),
        "tuyen quang": (21.8236, 105.2142, "Tuyên Quang", "Tỉnh Tuyên Quang"),
        "yen bai": (21.7168, 104.8986, "Yên Bái", "Tỉnh Yên Bái"),
        "phu tho": (21.3227, 105.4020, "Phú Thọ", "Tỉnh Phú Thọ"),
        "viet tri": (21.3227, 105.4020, "Việt Trì", "Phú Thọ"),
        "vinh phuc": (21.3609, 105.5474, "Vĩnh Phúc", "Tỉnh Vĩnh Phúc"),
    }

    # Alias cục bộ/POI chắc chắn. Không nên thêm quá nhiều để tránh bảo trì khó.
    LOCAL_ALIASES: Dict[str, Tuple[float, float, str, str]] = {
        "nam cat tien": (11.4209, 107.4287, "Nam Cát Tiên", "Đồng Nai / Lâm Đồng"),
        "chua khanh hy": (11.4240, 107.6460, "Chùa Khánh Hỷ", "Đạ Huoai, Lâm Đồng"),
        "chua khanh hy da huoai": (11.4240, 107.6460, "Chùa Khánh Hỷ", "Đạ Huoai, Lâm Đồng"),
        "chua khanh hy lam dong": (11.4240, 107.6460, "Chùa Khánh Hỷ", "Đạ Huoai, Lâm Đồng"),
        "vincom bao loc": (11.5489, 107.8077, "Vincom Bảo Lộc", "Bảo Lộc, Lâm Đồng"),
        "vincom plaza bao loc": (11.5489, 107.8077, "Vincom Plaza Bảo Lộc", "Bảo Lộc, Lâm Đồng"),
    }

    _cache: Dict[str, Tuple[float, float]] = {}

    def __init__(self):
        self.goong_key = os.getenv("GOONG_API_KEY", "").strip()
        self.has_goong = bool(self.goong_key and len(self.goong_key) > 10)

        self.geoapify_key = os.getenv("GEOAPIFY_API_KEY", "").strip()
        self.has_geoapify = bool(self.geoapify_key and len(self.geoapify_key) > 10)

        env_google = os.getenv("GOOGLE_MAPS_API_KEY", "")
        self.api_key = env_google or GOOGLE_MAPS_API_KEY or ""
        self.has_google_key = bool(self.api_key and "YOUR_" not in self.api_key and len(self.api_key.strip()) > 10)

        self._user_aliases: Dict[str, Tuple[float, float, str, str]] = {}
        self._load_user_aliases()

        logger.info(
            f"MapsAPI khởi động: Goong={'ON' if self.has_goong else 'OFF'}, "
            f"Geoapify={'ON' if self.has_geoapify else 'OFF'}, "
            f"Google={'ON' if self.has_google_key else 'OFF'}, "
            f"user_alias={len(self._user_aliases)}"
        )

    # =========================================================================
    # PUBLIC API
    # =========================================================================
    def geocode(self, address: str) -> Optional[Tuple[float, float]]:
        raw = (address or "").strip()
        if not raw:
            return None

        coord = self._parse_latlon(raw)
        if coord:
            return coord

        key = self._norm(raw)
        if key in self._cache:
            return self._cache[key]

        exact = self._lookup_exact_alias(raw)
        if exact:
            lat, lon, _, _ = exact
            self._cache[key] = (lat, lon)
            return lat, lon

        # API sources for POI/address.
        # Nếu query có số nhà cụ thể mà API chỉ trả số nhà khác, KHÔNG tự lấy kết quả gần đúng.
        candidates = self.geocode_candidates(raw, limit=1)
        if candidates:
            best = candidates[0]
            if best.get("match_status") == "near_address_mismatch":
                logger.warning(
                    f"Không geocode chính xác số nhà cho {raw!r}; "
                    f"bỏ qua kết quả gần đúng: {best.get('name')} / {best.get('address')}"
                )
                return None
            lat, lon = best["lat"], best["lon"]
            self._cache[key] = (lat, lon)
            return lat, lon

        logger.warning(f"Không geocode được: {raw!r}")
        return None

    def geocode_candidates(self, query: str, limit: int = 6) -> List[Dict]:
        raw = (query or "").strip()
        if not raw:
            return []

        coord = self._parse_latlon(raw)
        if coord:
            lat, lon = coord
            return [{"name": raw, "address": raw, "lat": lat, "lon": lon, "source": "coord"}]

        # FIX CHÍNH: Nếu query là tên thành phố/tỉnh/huyện đã biết thì trả ngay,
        # không cho Autocomplete lấy POI trùng chữ ở nơi khác.
        exact = self._lookup_exact_alias(raw)
        if exact:
            lat, lon, name, addr = exact
            return [{"name": name, "address": addr, "lat": lat, "lon": lon, "source": "admin_alias"}]

        results: List[Dict] = []
        seen = set()

        def merge(items: List[Dict]):
            for item in items or []:
                try:
                    lat = float(item.get("lat"))
                    lon = float(item.get("lon"))
                except Exception:
                    continue
                if not self._inside_vn_bbox(lat, lon):
                    continue
                k = (round(lat, 4), round(lon, 4), self._norm(item.get("name", ""))[:30])
                if k in seen:
                    continue
                seen.add(k)
                item["lat"] = lat
                item["lon"] = lon
                results.append(item)

        # 1. Goong: phù hợp địa chỉ/POI Việt Nam.
        if self.has_goong:
            merge(self._goong_geocode_candidates(raw, limit))
            if len(results) < 2:
                merge(self._goong_autocomplete_candidates(raw, limit))

        # 2. Geoapify: bổ sung khi Goong không đủ.
        if self.has_geoapify and len(results) < max(2, min(limit, 4)):
            merge(self._geoapify_autocomplete(raw, limit))
            if len(results) < 2:
                merge(self._geoapify_search_candidates(raw, limit))

        # 3. Google optional.
        if self.has_google_key and len(results) < 2:
            merge(self._google_candidates(raw, limit))

        # 4. Nominatim fallback.
        if len(results) < 2:
            merge(self._nominatim_candidates(raw, limit))

        ranked = self._rank_candidates(raw, results)

        # STRICT ADDRESS MODE:
        # Nếu người dùng nhập địa chỉ có số nhà ở đầu chuỗi, ví dụ "06 Nguyễn Viết Xuân",
        # app KHÔNG được tự đổi sang số nhà khác như 18/16/14 chỉ vì API trả về trước.
        # Ưu tiên exact house-number match; nếu không có, vẫn trả near candidates nhưng gắn cờ
        # để UI bắt người dùng chọn thủ công và cảnh báo rõ ràng.
        house = self._extract_house_number(raw)
        if house:
            exact_house = [it for it in ranked if self._candidate_has_house_number(it, house)]
            if exact_house:
                for it in exact_house:
                    it["match_status"] = "exact_house_number"
                    it["requested_house_number"] = house
                return exact_house[:limit]

            near = ranked[:limit]
            for it in near:
                it["match_status"] = "near_address_mismatch"
                it["requested_house_number"] = house
                it["warning"] = (
                    f"Không tìm thấy chính xác số nhà {house}; "
                    "đây chỉ là kết quả gần đúng, hãy chọn thủ công hoặc nhập tọa độ/ghim pin."
                )
            return near

        return ranked[:limit]

    def reverse_geocode(self, lat: float, lon: float) -> str:
        if self.has_geoapify:
            try:
                data = self._get(self.GEOAPIFY_REVERSE_URL, {
                    "lat": lat, "lon": lon, "apiKey": self.geoapify_key,
                    "lang": "vi", "format": "json",
                })
                results = data.get("results", [])
                if results:
                    return results[0].get("formatted", f"{lat:.4f}, {lon:.4f}")
            except Exception as e:
                logger.warning(f"Geoapify reverse lỗi: {e}")

        if self.has_google_key:
            try:
                data = self._get(self.GEOCODE_URL, {
                    "latlng": f"{lat},{lon}", "key": self.api_key,
                    "language": "vi", "region": "vn",
                })
                if data.get("status") == "OK" and data.get("results"):
                    return data["results"][0].get("formatted_address", f"{lat:.4f}, {lon:.4f}")
            except Exception as e:
                logger.warning(f"Google reverse lỗi: {e}")

        try:
            data = self._get(self.NOMINATIM_REVERSE_URL, {
                "lat": lat, "lon": lon, "format": "json", "addressdetails": 1,
            }, headers={"User-Agent": self.USER_AGENT})
            return data.get("display_name", f"{lat:.4f}, {lon:.4f}")
        except Exception as e:
            logger.error(f"Nominatim reverse lỗi: {e}")
            return f"{lat:.4f}, {lon:.4f}"

    def search_nearby_places(self, lat: float, lon: float, place_type: str = "restaurant", radius_m: int = 5000) -> List[Dict]:
        if self.has_geoapify:
            try:
                cat_map = {
                    "restaurant": "catering.restaurant",
                    "cafe": "catering.cafe",
                    "hospital": "healthcare.hospital",
                    "gas_station": "service.vehicle.fuel",
                    "hotel": "accommodation.hotel",
                    "atm": "service.financial.atm",
                    "pharmacy": "healthcare.pharmacy",
                }
                category = cat_map.get(place_type, f"commercial.{place_type}")
                data = self._get(self.GEOAPIFY_PLACES_URL, {
                    "categories": category,
                    "filter": f"circle:{lon},{lat},{radius_m}",
                    "bias": f"proximity:{lon},{lat}",
                    "limit": 10,
                    "apiKey": self.geoapify_key,
                    "lang": "vi",
                })
                return [self._parse_geoapify_place(f) for f in data.get("features", [])]
            except Exception as e:
                logger.warning(f"Geoapify Places lỗi: {e}")

        if self.has_google_key:
            try:
                data = self._get(self.PLACES_NEARBY_URL, {
                    "location": f"{lat},{lon}", "radius": radius_m,
                    "type": place_type, "key": self.api_key, "language": "vi",
                })
                if data.get("status") in ("OK", "ZERO_RESULTS"):
                    return [self._parse_google_place(p) for p in data.get("results", [])[:10]]
            except Exception as e:
                logger.warning(f"Google Nearby lỗi: {e}")
        return []

    def get_static_map_url(self, lat: float, lon: float, zoom: int = 13, width: int = 600, height: int = 400) -> str:
        if not self.has_google_key:
            return ""
        return (
            f"{self.STATIC_MAP_URL}?center={lat},{lon}&zoom={zoom}"
            f"&size={width}x{height}&markers=color:red%7C{lat},{lon}"
            f"&key={self.api_key}"
        )

    def save_user_alias(self, name: str, lat: float, lon: float) -> bool:
        key = self._norm(name)
        self._user_aliases[key] = (lat, lon, name, "Địa danh đã lưu")
        self._cache[key] = (lat, lon)
        try:
            os.makedirs(os.path.dirname(USER_ALIASES_FILE), exist_ok=True)
            data = {}
            if os.path.exists(USER_ALIASES_FILE):
                with open(USER_ALIASES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data[key] = {"name": name, "lat": lat, "lon": lon}
            with open(USER_ALIASES_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Không lưu được alias {name!r}: {e}")
            return False

    def delete_user_alias(self, name: str) -> bool:
        key = self._norm(name)
        self._user_aliases.pop(key, None)
        self._cache.pop(key, None)
        try:
            if not os.path.exists(USER_ALIASES_FILE):
                return True
            with open(USER_ALIASES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            data.pop(key, None)
            with open(USER_ALIASES_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Không xoá được alias {name!r}: {e}")
            return False

    def list_user_aliases(self) -> List[Dict]:
        try:
            if not os.path.exists(USER_ALIASES_FILE):
                return []
            with open(USER_ALIASES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [{"name": v.get("name", k), "lat": float(v["lat"]), "lon": float(v["lon"])} for k, v in data.items()]
        except Exception:
            return []

    # =========================================================================
    # GOONG
    # =========================================================================
    def _goong_geocode_candidates(self, query: str, limit: int = 6) -> List[Dict]:
        out: List[Dict] = []
        for q in self._query_variants(query)[:3]:
            try:
                data = self._get(self.GOONG_GEOCODE_URL, {"address": q, "api_key": self.goong_key})
                for r in data.get("results", [])[:limit]:
                    loc = r.get("geometry", {}).get("location", {})
                    if loc.get("lat") is None or loc.get("lng") is None:
                        continue
                    out.append({
                        "name": r.get("name") or r.get("formatted_address") or query,
                        "address": r.get("formatted_address") or "",
                        "lat": float(loc["lat"]),
                        "lon": float(loc["lng"]),
                        "source": "goong_geocode",
                    })
                if out:
                    break
            except Exception as e:
                logger.warning(f"Goong Geocode lỗi `{q}`: {e}")
        return out

    def _goong_autocomplete_candidates(self, query: str, limit: int = 6) -> List[Dict]:
        try:
            data = self._get(self.GOONG_AUTOCOMPLETE_URL, {
                "input": query,
                "api_key": self.goong_key,
                "limit": limit,
            })
            preds = data.get("predictions", [])[:limit]
        except Exception as e:
            logger.warning(f"Goong AutoComplete lỗi: {e}")
            return []

        out: List[Dict] = []
        for p in preds:
            place_id = p.get("place_id")
            desc = p.get("description") or p.get("structured_formatting", {}).get("main_text") or query
            if not place_id:
                continue
            try:
                detail = self._get(self.GOONG_DETAIL_URL, {"place_id": place_id, "api_key": self.goong_key})
                r = detail.get("result", {})
                loc = r.get("geometry", {}).get("location", {})
                if loc.get("lat") is None or loc.get("lng") is None:
                    continue
                name = r.get("name") or p.get("structured_formatting", {}).get("main_text") or desc
                out.append({
                    "name": name,
                    "address": r.get("formatted_address") or desc,
                    "lat": float(loc["lat"]),
                    "lon": float(loc["lng"]),
                    "source": "goong_place",
                    "place_id": place_id,
                })
            except Exception as e:
                logger.warning(f"Goong Place Detail lỗi `{desc}`: {e}")
        return out

    # =========================================================================
    # GEOAPIFY
    # =========================================================================
    def _geoapify_autocomplete(self, query: str, limit: int = 6) -> List[Dict]:
        lon_min, lat_min, lon_max, lat_max = self.VN_BBOX
        try:
            data = self._get(self.GEOAPIFY_AUTOCOMPLETE_URL, {
                "text": query,
                "apiKey": self.geoapify_key,
                "lang": "vi",
                "limit": limit,
                "filter": f"rect:{lon_min},{lat_min},{lon_max},{lat_max}",
                "bias": "countrycode:vn",
                "format": "json",
            })
            return [self._parse_geoapify_result(r, "geoapify_autocomplete") for r in data.get("results", []) if r.get("lat") and r.get("lon")]
        except Exception as e:
            logger.warning(f"Geoapify autocomplete lỗi: {e}")
            return []

    def _geoapify_search_candidates(self, query: str, limit: int = 6) -> List[Dict]:
        out: List[Dict] = []
        lon_min, lat_min, lon_max, lat_max = self.VN_BBOX
        for q in self._query_variants(query)[:3]:
            try:
                data = self._get(self.GEOAPIFY_GEOCODE_URL, {
                    "text": q,
                    "apiKey": self.geoapify_key,
                    "lang": "vi",
                    "limit": limit,
                    "filter": f"rect:{lon_min},{lat_min},{lon_max},{lat_max}",
                    "bias": "countrycode:vn",
                    "format": "json",
                })
                out.extend([self._parse_geoapify_result(r, "geoapify_search") for r in data.get("results", []) if r.get("lat") and r.get("lon")])
                if out:
                    break
            except Exception as e:
                logger.warning(f"Geoapify search lỗi `{q}`: {e}")
        return out

    def _parse_geoapify_result(self, r: Dict, source: str) -> Dict:
        name = r.get("name") or r.get("address_line1") or r.get("formatted", "")
        parts = []
        for key in ("suburb", "district", "county", "city", "state"):
            if r.get(key):
                parts.append(r[key])
        return {
            "name": name,
            "address": ", ".join(dict.fromkeys(parts)) or r.get("formatted", ""),
            "lat": float(r["lat"]),
            "lon": float(r["lon"]),
            "source": source,
            "result_type": r.get("result_type") or r.get("type") or "",
        }

    def _parse_geoapify_place(self, feature: Dict) -> Dict:
        props = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [0, 0])
        return {
            "name": props.get("name", ""),
            "lat": coords[1],
            "lon": coords[0],
            "rating": props.get("datasource", {}).get("raw", {}).get("stars", 0),
            "address": props.get("formatted", ""),
            "open": None,
            "place_id": props.get("place_id", ""),
        }

    # =========================================================================
    # GOOGLE + NOMINATIM
    # =========================================================================
    def _google_candidates(self, query: str, limit: int = 6) -> List[Dict]:
        try:
            data = self._get(self.PLACES_TEXT_URL, {
                "query": query,
                "key": self.api_key,
                "language": "vi",
                "region": "vn",
            })
            if data.get("status") != "OK":
                return []
            out = []
            for p in data.get("results", [])[:limit]:
                loc = p.get("geometry", {}).get("location", {})
                if loc.get("lat") is None or loc.get("lng") is None:
                    continue
                out.append({
                    "name": p.get("name", query),
                    "address": p.get("formatted_address") or p.get("vicinity", ""),
                    "lat": float(loc["lat"]),
                    "lon": float(loc["lng"]),
                    "source": "google_places",
                })
            return out
        except Exception as e:
            logger.warning(f"Google candidates lỗi: {e}")
            return []

    def _parse_google_place(self, p: Dict) -> Dict:
        loc = p["geometry"]["location"]
        return {
            "name": p.get("name", ""),
            "lat": loc["lat"],
            "lon": loc["lng"],
            "rating": p.get("rating", 0),
            "address": p.get("formatted_address") or p.get("vicinity", ""),
            "open": p.get("opening_hours", {}).get("open_now"),
            "place_id": p.get("place_id", ""),
        }

    def _nominatim_candidates(self, query: str, limit: int = 6) -> List[Dict]:
        out: List[Dict] = []
        for q in self._query_variants(query)[:4]:
            try:
                items = self._get(self.NOMINATIM_URL, {
                    "q": q,
                    "format": "jsonv2",
                    "limit": limit,
                    "addressdetails": 1,
                    "countrycodes": "vn",
                    "accept-language": "vi,en",
                }, headers={"User-Agent": self.USER_AGENT})
                for item in items:
                    addr = item.get("address", {}) or {}
                    parts = []
                    for key in ("suburb", "village", "town", "city", "county", "state"):
                        if addr.get(key):
                            parts.append(addr[key])
                    out.append({
                        "name": item.get("name") or item.get("display_name", query).split(",")[0],
                        "address": ", ".join(dict.fromkeys(parts)) or item.get("display_name", ""),
                        "lat": float(item["lat"]),
                        "lon": float(item["lon"]),
                        "source": "nominatim",
                        "result_type": item.get("type", ""),
                        "class": item.get("class", ""),
                        "importance": float(item.get("importance", 0) or 0),
                    })
                if out:
                    break
                time.sleep(_SLEEP)
            except Exception as e:
                logger.warning(f"Nominatim lỗi `{q}`: {e}")
        return out

    # =========================================================================
    # STRICT ADDRESS MATCH HELPERS
    # =========================================================================
    def _extract_house_number(self, query: str) -> Optional[str]:
        """
        Tách số nhà khi query bắt đầu bằng số nhà.
        Ví dụ: "06 Nguyễn Viết Xuân" -> "06"; "5/12 Lê Lợi" -> "5/12".
        Không áp dụng cho query không có số nhà rõ ràng.
        """
        q = (query or "").strip()
        if not q or "," in q and self._parse_latlon(q):
            return None
        m = re.match(r"^\s*(?:s[oố]\s*)?([0-9]+(?:/[0-9]+)?[a-zA-Z]?)\b", q, flags=re.IGNORECASE)
        if not m:
            return None
        return m.group(1).strip()

    def _house_number_variants(self, house: str) -> set:
        raw = (house or "").strip().lower()
        variants = {raw}
        m = re.match(r"^0*([0-9]+)(.*)$", raw)
        if m:
            variants.add((m.group(1) + m.group(2)).strip())
        return {v for v in variants if v}

    def _candidate_has_house_number(self, item: Dict, house: str) -> bool:
        """True nếu candidate chứa đúng số nhà người dùng nhập, chấp nhận 06 == 6."""
        text = f"{item.get('name','')} {item.get('address','')}"
        norm = self._norm(text)
        variants = self._house_number_variants(house)
        for v in variants:
            # Match theo token số nhà, tránh 6 khớp vào 16/60/106.
            if re.search(rf"(?<![0-9a-z]){re.escape(v)}(?![0-9a-z])", norm):
                return True
        return False

    # =========================================================================
    # HELPERS
    # =========================================================================
    def _get(self, url: str, params: Dict, headers: Dict = None) -> Any:
        req_headers = {"User-Agent": self.USER_AGENT}
        if headers:
            req_headers.update(headers)
        last_exc = None
        for attempt in range(_RETRY):
            try:
                r = requests.get(url, params=params, headers=req_headers, timeout=_TIMEOUT)
                r.raise_for_status()
                return r.json()
            except requests.exceptions.Timeout as e:
                last_exc = e
                time.sleep(_SLEEP * (attempt + 1))
            except requests.exceptions.RequestException as e:
                last_exc = e
                break
        raise last_exc or RuntimeError(f"GET thất bại: {url}")

    def _query_variants(self, query: str) -> List[str]:
        q = " ".join((query or "").strip().split())
        variants: List[str] = []

        def add(x: str):
            x = " ".join((x or "").strip().split())
            if x and x not in variants:
                variants.append(x)

        add(q)
        low = self._norm(q)
        # Với query ngắn như tên thành phố, không ép thêm địa phương xuất phát.
        # Chỉ thêm Việt Nam để API hiểu phạm vi quốc gia.
        if "viet nam" not in low:
            add(f"{q}, Việt Nam")

        # Context nhẹ cho POI phổ biến ở Lâm Đồng, nhưng không áp dụng cho city alias
        # vì city alias đã return trước.
        if "chua" in low:
            add(f"{q}, Lâm Đồng, Việt Nam")
            add(f"{q}, Đạ Huoai, Lâm Đồng, Việt Nam")
        elif "vincom" in low:
            add(f"{q}, Bảo Lộc, Lâm Đồng, Việt Nam")

        return variants

    def _rank_candidates(self, query: str, items: List[Dict]) -> List[Dict]:
        qn = self._norm(query)
        q_tokens = set(qn.split())

        def score(item: Dict) -> float:
            name = self._norm(item.get("name", ""))
            addr = self._norm(item.get("address", ""))
            src = item.get("source", "")
            result_type = self._norm(item.get("result_type", ""))
            cls = self._norm(item.get("class", ""))

            s = 0.0
            if name == qn or addr == qn:
                s += 120
            if qn and qn in name:
                s += 45
            if qn and qn in addr:
                s += 25
            if q_tokens and q_tokens.issubset(set(name.split())):
                s += 20

            # Ưu tiên kết quả hành chính / địa danh lớn hơn POI fuzzy.
            if result_type in ("city", "town", "village", "county", "state", "municipality", "administrative"):
                s += 55
            if cls in ("boundary", "place"):
                s += 35

            # Nguồn
            if src == "goong_geocode":
                s += 18
            elif src == "goong_place":
                s += 12
            elif src.startswith("geoapify"):
                s += 8
            elif src == "nominatim":
                s += float(item.get("importance", 0) or 0) * 10

            # Phạt các POI có tên chứa query nhưng địa chỉ ở tỉnh/thành khác khi query là cụm ngắn.
            # Ví dụ "vũng tàu" không nên trả "Quán Cô Năm Vũng Tàu" ở Đà Lạt.
            if len(q_tokens) <= 3 and qn in name and not (qn in addr):
                poi_words = ("quan", "cafe", "hotel", "nha hang", "bat dong san", "tiem", "shop", "bia", "karaoke")
                if any(w in name for w in poi_words):
                    s -= 60
            return s

        return sorted(items, key=score, reverse=True)

    def _lookup_exact_alias(self, query: str) -> Optional[Tuple[float, float, str, str]]:
        key = self._norm(query)
        # User alias ưu tiên cao nhất.
        if key in self._user_aliases:
            return self._user_aliases[key]
        if key in self.ADMIN_ALIASES:
            return self.ADMIN_ALIASES[key]
        if key in self.LOCAL_ALIASES:
            return self.LOCAL_ALIASES[key]
        return None

    def _load_user_aliases(self):
        try:
            if not os.path.exists(USER_ALIASES_FILE):
                return
            with open(USER_ALIASES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key, val in data.items():
                lat = float(val["lat"])
                lon = float(val["lon"])
                name = val.get("name", key)
                self._user_aliases[self._norm(key)] = (lat, lon, name, "Địa danh đã lưu")
                self._user_aliases[self._norm(name)] = (lat, lon, name, "Địa danh đã lưu")
        except Exception as e:
            logger.warning(f"Không nạp được user_aliases: {e}")

    def _parse_latlon(self, text: str) -> Optional[Tuple[float, float]]:
        try:
            cleaned = (text or "").strip().replace(";", ",")
            if "," not in cleaned:
                return None
            a, b = cleaned.split(",", 1)
            lat, lon = float(a.strip()), float(b.strip())
            if 8.0 <= lat <= 24.0 and 102.0 <= lon <= 110.0:
                return lat, lon
        except Exception:
            pass
        return None

    def _inside_vn_bbox(self, lat: float, lon: float) -> bool:
        lon_min, lat_min, lon_max, lat_max = self.VN_BBOX
        return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max

    def _norm(self, text: str) -> str:
        return _compact(_strip_accents(text))
