
# features/sos.py
# Module SOS — khẩn cấp, kết nối cứu hộ, gửi vị trí

import time
from typing import Dict, Optional
from utils.config import SOS_POLICE, SOS_FIRE, SOS_AMBULANCE, SOS_RESCUE
from utils.logger import setup_logger

logger = setup_logger(__name__)


class SOSHandler:
    """
    Xử lý tình huống khẩn cấp:
    - Gửi vị trí tức thời
    - Hiển thị số điện thoại cứu hộ
    - Ghi log sự cố
    - Cảnh báo crowdsource
    """

    EMERGENCY_CONTACTS = {
        "police":    {"name": "Công an",      "number": SOS_POLICE},
        "fire":      {"name": "Cứu hỏa",      "number": SOS_FIRE},
        "ambulance": {"name": "Cấp cứu y tế", "number": SOS_AMBULANCE},
        "rescue":    {"name": "Tìm kiếm cứu nạn", "number": SOS_RESCUE},
    }

    def __init__(self):
        self.active_sos: Optional[Dict] = None
        logger.info("SOSHandler khởi động")

    # ----------------------------------------------------------
    # PUBLIC
    # ----------------------------------------------------------
    def trigger_sos(
        self,
        lat: float,
        lon: float,
        user_id: str,
        emergency_type: str = "general",
        message: str = "",
    ) -> Dict:
        """
        Kích hoạt SOS.

        Args:
            lat, lon:       vị trí hiện tại
            user_id:        ID người dùng
            emergency_type: 'accident' | 'medical' | 'stranded' | 'general'
            message:        mô tả thêm

        Returns:
            {
                sos_id: str,
                contacts: [Dict],
                location_url: str,
                instructions: [str],
                timestamp: float,
            }
        """
        sos_id = f"SOS_{user_id}_{int(time.time())}"

        self.active_sos = {
            "sos_id":         sos_id,
            "lat":            lat,
            "lon":            lon,
            "user_id":        user_id,
            "emergency_type": emergency_type,
            "message":        message,
            "timestamp":      time.time(),
            "status":         "active",
        }

        logger.warning(f"SOS KÍCH HOẠT: {sos_id} tại ({lat}, {lon}) — {emergency_type}")

        contacts     = self._get_relevant_contacts(emergency_type)
        location_url = self._build_google_maps_url(lat, lon)
        instructions = self._get_instructions(emergency_type)

        return {
            "sos_id":       sos_id,
            "contacts":     contacts,
            "location_url": location_url,
            "instructions": instructions,
            "timestamp":    self.active_sos["timestamp"],
            "message_template": self._build_message(lat, lon, emergency_type, location_url),
        }

    def cancel_sos(self, sos_id: str) -> bool:
        """Hủy SOS khi tình huống đã được giải quyết."""
        if self.active_sos and self.active_sos["sos_id"] == sos_id:
            self.active_sos["status"] = "cancelled"
            logger.info(f"SOS đã hủy: {sos_id}")
            return True
        return False

    def get_all_contacts(self) -> Dict:
        """Trả về toàn bộ danh bạ khẩn cấp."""
        return self.EMERGENCY_CONTACTS

    def report_incident(
        self,
        lat: float,
        lon: float,
        incident_type: str,
        description: str = "",
    ) -> Dict:
        """Báo cáo sự cố (không phải SOS khẩn cấp)."""
        incident = {
            "lat":           lat,
            "lon":           lon,
            "type":          incident_type,
            "description":   description,
            "timestamp":     time.time(),
            "verified":      False,
        }
        logger.info(f"Báo cáo sự cố: {incident_type} tại ({lat}, {lon})")
        return incident

    # ----------------------------------------------------------
    # PRIVATE
    # ----------------------------------------------------------
    def _get_relevant_contacts(self, emergency_type: str) -> list:
        priority = {
            "accident": ["ambulance", "police"],
            "medical":  ["ambulance"],
            "fire":     ["fire", "ambulance"],
            "stranded": ["rescue", "police"],
            "general":  ["police", "rescue"],
        }
        keys = priority.get(emergency_type, ["police"])
        return [
            {**self.EMERGENCY_CONTACTS[k], "type": k}
            for k in keys if k in self.EMERGENCY_CONTACTS
        ]

    def _build_google_maps_url(self, lat: float, lon: float) -> str:
        return f"https://maps.google.com/?q={lat},{lon}"

    def _build_message(
        self, lat: float, lon: float, emergency_type: str, url: str
    ) -> str:
        labels = {
            "accident": "tai nạn giao thông",
            "medical":  "cấp cứu y tế",
            "fire":     "cháy",
            "stranded": "bị mắc kẹt",
            "general":  "tình huống khẩn cấp",
        }
        label = labels.get(emergency_type, "tình huống khẩn cấp")
        return (
            f"🆘 Tôi đang gặp {label}!\n"
            f"📍 Vị trí: {url}\n"
            f"Tọa độ: {lat:.5f}, {lon:.5f}\n"
            f"Vui lòng hỗ trợ ngay!"
        )

    def _get_instructions(self, emergency_type: str) -> list:
        base = [
            "1. Giữ bình tĩnh",
            "2. Đứng ở nơi an toàn, thoáng",
            "3. Chia sẻ link vị trí cho người thân",
        ]
        specific = {
            "accident": ["4. Không di chuyển nếu bị thương", "5. Bật đèn cảnh báo xe"],
            "medical":  ["4. Nằm xuống, không ăn uống gì", "5. Theo dõi hơi thở"],
            "stranded": ["4. Tiết kiệm pin điện thoại", "5. Ở gần phương tiện"],
            "fire":     ["4. Rời xa ngọn lửa ngay", "5. Không quay lại lấy đồ"],
        }
        return base + specific.get(emergency_type, [])
