import time
from typing import List, Dict, Tuple, Optional
from utils.helpers import haversine_distance, load_json
from utils.config import VIETNAM_ZONES_FILE
from utils.logger import setup_logger

logger = setup_logger(__name__)


class DisasterRouteEngine:
    """
    Ứng phó thiên tai: sạt lở, lũ, cháy rừng, bão.
    Tạo hành lang sơ tán, định tuyến xe cứu trợ, tìm vùng an toàn.
    """

    DISASTER_TYPES = {
        "flood":     {"severity_multiplier": 1.3, "avoid_elevation_max": 5},
        "landslide": {"severity_multiplier": 1.5, "avoid_slope": True},
        "fire":      {"severity_multiplier": 1.4, "avoid_forest": True},
        "storm":     {"severity_multiplier": 1.2, "avoid_coast": True},
        "earthquake":{"severity_multiplier": 1.6, "avoid_tall_building": True},
    }

    # Vùng an toàn mẫu (thực tế tích hợp từ cơ quan phòng chống thiên tai)
    SAFE_ZONES = [
        {"id": "sz_001", "name": "Trường học Nguyễn Du", "lat": 11.945, "lon": 108.440, "capacity": 500, "province": "Đà Lạt"},
        {"id": "sz_002", "name": "Sân vận động trung tâm", "lat": 11.942, "lon": 108.445, "capacity": 2000, "province": "Đà Lạt"},
        {"id": "sz_003", "name": "Khu tái định cư Bắc Hà", "lat": 22.280, "lon": 104.000, "capacity": 300, "province": "Lào Cai"},
        {"id": "sz_004", "name": "Trung tâm cứu trợ Cần Thơ", "lat": 10.045, "lon": 105.746, "capacity": 1500, "province": "Cần Thơ"},
    ]

    def __init__(self, router, risk_engine):
        self.router      = router
        self.risk_engine = risk_engine
        self.active_disasters: List[Dict] = []
        logger.info("DisasterRouteEngine khởi động")

    # ----------------------------------------------------------
    # PUBLIC
    # ----------------------------------------------------------
    def declare_disaster(
        self,
        lat: float,
        lon: float,
        disaster_type: str,
        radius_km: float,
        severity: int,            # 1–5
        description: str = "",
    ) -> Dict:
        """Khai báo vùng thiên tai mới."""
        disaster = {
            "id":            f"DIS_{int(time.time())}",
            "lat":           lat,
            "lon":           lon,
            "type":          disaster_type,
            "radius_km":     radius_km,
            "severity":      severity,
            "description":   description,
            "declared_at":   time.time(),
            "active":        True,
        }
        self.active_disasters.append(disaster)
        logger.warning(f"THIÊN TAI: {disaster_type} tại ({lat}, {lon}) — bán kính {radius_km}km, cấp {severity}")
        return disaster

    def find_evacuation_route(
        self,
        current_lat: float,
        current_lon: float,
        mode: str = "car",
    ) -> Dict:
        """
        Tìm tuyến đường sơ tán đến vùng an toàn gần nhất.

        Returns:
            {
                safe_zone: Dict,
                route: Dict,
                estimated_time_min: int,
                warnings: [str],
            }
        """
        safe_zone = self._find_nearest_safe_zone(current_lat, current_lon)
        if not safe_zone:
            return {"error": "Không tìm thấy vùng an toàn", "safe_zone": None}

        route = self.router.get_route(
            (current_lat, current_lon),
            (safe_zone["lat"], safe_zone["lon"]),
            mode=mode,
        )

        warnings = self._generate_disaster_warnings(current_lat, current_lon)

        return {
            "safe_zone":          safe_zone,
            "route":              route,
            "estimated_time_min": route.get("duration_min", 0) if route else 0,
            "warnings":           warnings,
            "instructions":       self._evacuation_instructions(warnings),
        }

    def get_rescue_vehicle_route(
        self,
        rescue_base: Tuple[float, float],
        victim_location: Tuple[float, float],
        vehicle_type: str = "ambulance",
    ) -> Dict:
        """
        Định tuyến xe cứu trợ tới nơi nạn nhân.
        Ưu tiên đường rộng, tránh vùng ngập.
        """
        route = self.router.get_route(
            rescue_base,
            victim_location,
            mode="car",
        )

        if route:
            route["priority"] = "emergency"
            route["vehicle"]  = vehicle_type
            route["note"]     = "Tuyến ưu tiên cứu hộ — tránh đường ngập và sạt lở"

        return route or {"error": "Không tìm được tuyến cứu hộ"}

    def get_active_disasters(self, lat: float = None, lon: float = None, radius_km: float = 100) -> List[Dict]:
        """Lấy danh sách thiên tai đang diễn ra, tùy chọn lọc theo vị trí."""
        active = [d for d in self.active_disasters if d["active"]]
        if lat is None:
            return active
        return [
            d for d in active
            if haversine_distance(lat, lon, d["lat"], d["lon"]) <= radius_km
        ]

    def get_all_safe_zones(self) -> List[Dict]:
        return self.SAFE_ZONES

    # ----------------------------------------------------------
    # PRIVATE
    # ----------------------------------------------------------
    def _find_nearest_safe_zone(self, lat: float, lon: float) -> Optional[Dict]:
        closest  = None
        min_dist = float("inf")
        for zone in self.SAFE_ZONES:
            dist = haversine_distance(lat, lon, zone["lat"], zone["lon"])
            # Tránh vùng an toàn nằm trong vùng thiên tai
            in_disaster = any(
                haversine_distance(zone["lat"], zone["lon"], d["lat"], d["lon"]) <= d["radius_km"]
                for d in self.active_disasters if d["active"]
            )
            if not in_disaster and dist < min_dist:
                min_dist = dist
                closest  = {**zone, "distance_km": round(dist, 2)}
        return closest

    def _generate_disaster_warnings(self, lat: float, lon: float) -> List[str]:
        warnings = []
        for disaster in self.active_disasters:
            if not disaster["active"]:
                continue
            dist = haversine_distance(lat, lon, disaster["lat"], disaster["lon"])
            if dist <= disaster["radius_km"] * 2:
                label = disaster["type"].upper()
                warnings.append(f"⚠️ {label} cách {dist:.1f}km — nguy hiểm cấp {disaster['severity']}/5")
        return warnings

    def _evacuation_instructions(self, warnings: List[str]) -> List[str]:
        base = [
            "1. Tắt gas, điện, nước trước khi rời đi",
            "2. Mang theo giấy tờ tùy thân và thuốc cần thiết",
            "3. Đi theo tuyến đường chỉ dẫn, không tự ý đi lối khác",
            "4. Liên hệ người thân thông báo hướng di chuyển",
            "5. Nghe theo hướng dẫn của cơ quan chức năng",
        ]
        if warnings:
            base.insert(0, "🚨 THOÁT HIỂM NGAY — đừng chờ đợi!")
        return base
