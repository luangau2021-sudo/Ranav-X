# utils/helpers.py
# Các hàm dùng chung toàn app

import math
import json
import os
from typing import Tuple, List, Dict, Optional
from utils.config import VIETNAM_BOUNDS

# ============================================================
# KIỂM TRA TỌA ĐỘ
# ============================================================
def is_in_vietnam(lat: float, lon: float) -> bool:
    """Kiểm tra tọa độ có nằm trong lãnh thổ Việt Nam không."""
    return (
        VIETNAM_BOUNDS["min_lat"] <= lat <= VIETNAM_BOUNDS["max_lat"] and
        VIETNAM_BOUNDS["min_lon"] <= lon <= VIETNAM_BOUNDS["max_lon"]
    )

# ============================================================
# TÍNH KHOẢNG CÁCH
# ============================================================
def haversine_distance(
    lat1: float, lon1: float,
    lat2: float, lon2: float
) -> float:
    """
    Tính khoảng cách thực tế giữa 2 tọa độ (km).
    Công thức Haversine.
    """
    R = 6371  # Bán kính Trái Đất (km)

    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)

    a = (math.sin(d_lat / 2) ** 2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(d_lon / 2) ** 2)

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# ============================================================
# ĐỌC FILE JSON
# ============================================================
def load_json(filepath: str) -> Optional[Dict]:
    """Đọc file JSON an toàn."""
    if not os.path.exists(filepath):
        print(f"[helpers] Không tìm thấy file: {filepath}")
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"[helpers] Lỗi đọc JSON {filepath}: {e}")
        return None

def save_json(filepath: str, data: Dict) -> bool:
    """Ghi dữ liệu ra file JSON."""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[helpers] Lỗi ghi JSON {filepath}: {e}")
        return False

# ============================================================
# ĐỊNH DẠNG
# ============================================================
def format_distance(km: float) -> str:
    """Hiển thị khoảng cách đẹp."""
    if km < 1:
        return f"{int(km * 1000)} m"
    return f"{km:.1f} km"

def format_duration(minutes: int) -> str:
    """Hiển thị thời gian đẹp."""
    if minutes < 60:
        return f"{minutes} phút"
    h = minutes // 60
    m = minutes % 60
    return f"{h} giờ {m} phút" if m > 0 else f"{h} giờ"

def format_risk_level(score: float) -> str:
    """Chuyển điểm rủi ro thành nhãn."""
    if score >= 0.7:
        return "🔴 Nguy hiểm cao"
    elif score >= 0.4:
        return "🟡 Trung bình"
    else:
        return "🟢 An toàn"

# ============================================================
# XỬ LÝ TỌA ĐỘ
# ============================================================
def midpoint(
    lat1: float, lon1: float,
    lat2: float, lon2: float
) -> Tuple[float, float]:
    """Tính điểm giữa 2 tọa độ."""
    return ((lat1 + lat2) / 2, (lon1 + lon2) / 2)
