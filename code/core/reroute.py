from typing import List, Dict, Tuple, Optional
from utils.logger import setup_logger
from utils.helpers import haversine_distance

logger = setup_logger(__name__)


class RerouteEngine:
    """
    Tự động phát hiện nguy hiểm trên tuyến và đề xuất tuyến thay thế.
    Phối hợp với RiskEngine và Router.
    """

    REROUTE_RADIUS_KM = 15  # Bán kính tránh quanh vùng nguy hiểm

    def __init__(self, router, risk_engine):
        self.router      = router
        self.risk_engine = risk_engine
        logger.info("RerouteEngine khởi động")

    def check_and_reroute(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        current_route: Dict,
        mode: str = "car",
    ) -> Dict:
        """
        Kiểm tra tuyến hiện tại và tính lại nếu cần.

        Returns:
            {
                needs_reroute: bool,
                reason: str,
                new_route: Dict | None,
                danger_points: [Dict],
            }
        """
        polyline = current_route.get("polyline", [])
        if not polyline:
            return {"needs_reroute": False, "reason": "", "new_route": None, "danger_points": []}

        analysis = self.risk_engine.analyze_route(polyline)

        if not analysis["safe_to_proceed"]:
            danger_points = analysis["danger_segments"]
            logger.warning(f"Phát hiện {len(danger_points)} điểm nguy hiểm — tính lại tuyến")

            # Tạo waypoint tránh vùng nguy hiểm
            avoidance_waypoints = self._build_avoidance_waypoints(danger_points, polyline)

            new_route = self.router.get_route(
                origin, destination, mode, waypoints=avoidance_waypoints
            )

            return {
                "needs_reroute": True,
                "reason":        f"Phát hiện {len(danger_points)} điểm nguy hiểm trên tuyến",
                "new_route":     new_route,
                "danger_points": danger_points,
                "original_risk": analysis,
            }

        return {
            "needs_reroute": False,
            "reason":        "Tuyến đường an toàn",
            "new_route":     None,
            "danger_points": [],
        }

    def add_blocked_zone(
        self,
        blocked_zones: List[Dict],
        lat: float,
        lon: float,
        reason: str,
        radius_km: float = 5.0,
    ) -> List[Dict]:
        """Thêm vùng cấm mới (ví dụ: tai nạn, ngập lụt, cháy rừng)."""
        blocked_zones.append({
            "lat":       lat,
            "lon":       lon,
            "radius_km": radius_km,
            "reason":    reason,
        })
        logger.info(f"Đã thêm vùng cấm: {reason} tại ({lat}, {lon})")
        return blocked_zones

    def is_point_blocked(
        self,
        lat: float,
        lon: float,
        blocked_zones: List[Dict],
    ) -> Tuple[bool, Optional[str]]:
        """Kiểm tra điểm có nằm trong vùng bị chặn không."""
        for zone in blocked_zones:
            dist = haversine_distance(lat, lon, zone["lat"], zone["lon"])
            if dist <= zone["radius_km"]:
                return True, zone["reason"]
        return False, None

    # ----------------------------------------------------------
    # PRIVATE
    # ----------------------------------------------------------
    def _build_avoidance_waypoints(
        self,
        danger_points: List[Dict],
        polyline: List[List[float]],
    ) -> List[Tuple[float, float]]:
        """
        Tạo waypoint lệch sang bên để tránh điểm nguy hiểm.
        Lệch 0.1 độ (≈ 11 km) so với điểm nguy hiểm.
        """
        waypoints = []
        for point in danger_points[:3]:  # Tránh quá nhiều waypoint
            # Dịch sang Đông để tránh
            waypoints.append((
                point["lat"],
                point["lon"] + 0.1,
            ))
        return waypoints
