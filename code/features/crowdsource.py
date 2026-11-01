import time
import json
from typing import List, Dict, Optional
from utils.helpers import haversine_distance, load_json, save_json
from utils.config import VIETNAM_ZONES_FILE
from utils.logger import setup_logger

logger = setup_logger(__name__)

REPORTS_FILE = "data/crowdsource_reports.json"


class CrowdsourceEngine:
    """
    Quản lý báo cáo từ cộng đồng:
    - Tắc đường, tai nạn, ngập nước, đường xấu
    - Xác minh báo cáo (upvote/downvote)
    - Chia sẻ lên map realtime
    """

    MANUAL_DELETE_WINDOW_MIN = 15

    REPORT_TYPES = {
        "accident":     {"label": "Tai nạn",       "icon": "🚨", "expire_hours": 4},
        "flood":        {"label": "Ngập nước",      "icon": "🌊", "expire_hours": 6},
        "traffic_jam":  {"label": "Tắc đường",      "icon": "🚗", "expire_hours": 2},
        "bad_road":     {"label": "Đường xấu",      "icon": "⚠️", "expire_hours": 48},
        "landslide":    {"label": "Sạt lở",         "icon": "⛰️", "expire_hours": 24},
        "construction": {"label": "Thi công",       "icon": "🚧", "expire_hours": 72},
        "gas_station":  {"label": "Trạm xăng",      "icon": "⛽", "expire_hours": 168},
        "rest_stop":    {"label": "Điểm nghỉ tốt",  "icon": "☕", "expire_hours": 168},
    }

    def __init__(self):
        data = load_json(REPORTS_FILE) or {"reports": []}
        self.reports: List[Dict] = data.get("reports", [])
        self._cleanup_expired()
        logger.info(f"CrowdsourceEngine: {len(self.reports)} báo cáo đang hoạt động")

    # ----------------------------------------------------------
    # PUBLIC
    # ----------------------------------------------------------
    def submit_report(
        self,
        lat: float,
        lon: float,
        report_type: str,
        user_id: str,
        description: str = "",
        severity: int = 3,        # 1 (nhẹ) – 5 (nghiêm trọng)
    ) -> Dict:
        """Người dùng gửi báo cáo mới."""
        if report_type not in self.REPORT_TYPES:
            return {"success": False, "error": "Loại báo cáo không hợp lệ"}

        report_info = self.REPORT_TYPES[report_type]
        report = {
            "id":          f"RPT_{int(time.time())}_{user_id[:4]}",
            "lat":         lat,
            "lon":         lon,
            "type":        report_type,
            "label":       report_info["label"],
            "icon":        report_info["icon"],
            "description": description,
            "severity":    severity,
            "user_id":     user_id,
            "timestamp":   time.time(),
            "expire_at":   time.time() + report_info["expire_hours"] * 3600,
            "upvotes":     0,
            "downvotes":   0,
            "verified":    False,
        }

        self.reports.append(report)
        self._save()
        logger.info(f"Báo cáo mới: {report_type} tại ({lat}, {lon}) — severity {severity}")

        return {"success": True, "report_id": report["id"], "report": report}

    def get_nearby_reports(
        self,
        lat: float,
        lon: float,
        radius_km: float = 20.0,
        types: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Lấy báo cáo gần một vị trí."""
        result = []
        for r in self.reports:
            dist = haversine_distance(lat, lon, r["lat"], r["lon"])
            if dist <= radius_km:
                if types is None or r["type"] in types:
                    result.append({**r, "distance_km": round(dist, 2)})
        return sorted(result, key=lambda x: x["distance_km"])

    def vote_report(self, report_id: str, user_id: str, is_upvote: bool) -> bool:
        """Xác nhận hoặc phủ nhận báo cáo."""
        for r in self.reports:
            if r["id"] == report_id:
                if is_upvote:
                    r["upvotes"] += 1
                    if r["upvotes"] >= 3:
                        r["verified"] = True
                else:
                    r["downvotes"] += 1
                self._save()
                return True
        return False

    def can_delete_report(self, report: Dict, user_id: str) -> tuple[bool, str]:
        """Chỉ cho người tạo tự xóa trong thời gian ngắn, và không xóa nếu đã verified."""
        if report.get("user_id") != user_id:
            return False, "Bạn chỉ có thể xóa báo cáo do mình tạo"
        if report.get("verified"):
            return False, "Báo cáo đã được cộng đồng xác minh, không thể tự xóa"
        age_minutes = (time.time() - report.get("timestamp", time.time())) / 60
        if age_minutes > self.MANUAL_DELETE_WINDOW_MIN:
            return False, f"Chỉ được tự xóa trong {self.MANUAL_DELETE_WINDOW_MIN} phút đầu"
        return True, "OK"

    def delete_report(self, report_id: str, user_id: str) -> Dict:
        """Xóa báo cáo nếu người dùng có quyền."""
        for idx, report in enumerate(self.reports):
            if report["id"] == report_id:
                allowed, message = self.can_delete_report(report, user_id)
                if not allowed:
                    return {"success": False, "error": message}
                removed = self.reports.pop(idx)
                self._save()
                logger.info(f"Đã xóa báo cáo {report_id} bởi {user_id}")
                return {"success": True, "report": removed}
        return {"success": False, "error": "Không tìm thấy báo cáo"}

    def get_reports_on_route(
        self,
        polyline: List[List[float]],
        corridor_km: float = 2.0,
    ) -> List[Dict]:
        """Lấy tất cả báo cáo trong hành lang dọc tuyến đường."""
        result = []
        for r in self.reports:
            for coord in polyline[::5]:  # Lấy mẫu
                dist = haversine_distance(r["lat"], r["lon"], coord[1], coord[0])
                if dist <= corridor_km:
                    result.append(r)
                    break
        return result

    # ----------------------------------------------------------
    # PRIVATE
    # ----------------------------------------------------------
    def _cleanup_expired(self):
        now = time.time()
        before = len(self.reports)
        self.reports = [r for r in self.reports if r.get("expire_at", now + 1) > now]
        removed = before - len(self.reports)
        if removed:
            logger.info(f"Đã xóa {removed} báo cáo hết hạn")
            self._save()

    def _save(self):
        save_json(REPORTS_FILE, {"reports": self.reports})