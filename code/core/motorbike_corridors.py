# core/motorbike_corridors.py
# Hành lang tuyến an toàn cho xe máy.
# Mục tiêu: tránh waypoint ngẫu nhiên làm tuyến vòng méo; ưu tiên các điểm trung gian thật.

from __future__ import annotations
from typing import Dict, List, Tuple

Coord = Tuple[float, float]  # (lat, lon)

# Các corridor được thiết kế để OSRM bị ép đi qua vùng/đường có thật,
# sau đó legal_route_filter.py vẫn kiểm tra lại cao tốc/ĐCT.
MOTORBIKE_CORRIDORS: List[Dict] = [
    {
        "name": "Lâm Đồng: Đạ Huoai/Bảo Lộc/Di Linh ↔ Đà Lạt tránh Liên Khương - Prenn",
        "region": "lam_dong_west_to_dalat",
        "bounds": {
            "lat_min": 11.20,
            "lat_max": 12.15,
            "lon_min": 107.35,
            "lon_max": 108.75,
        },
        # waypoint theo hướng tây/southwest -> Đà Lạt
        # Lưu ý: đây là tọa độ vùng/thị trấn, không phải điểm ngẫu nhiên giữa núi.
        "west_to_dalat": [
            ("Bảo Lộc", 11.5480, 107.8070),
            ("Di Linh", 11.5810, 108.0720),
            ("Đức Trọng", 11.7350, 108.3730),
            ("Đơn Dương", 11.7760, 108.4980),
            ("Trại Mát", 11.9290, 108.5050),
        ],
        "dalat_to_west": [
            ("Trại Mát", 11.9290, 108.5050),
            ("Đơn Dương", 11.7760, 108.4980),
            ("Đức Trọng", 11.7350, 108.3730),
            ("Di Linh", 11.5810, 108.0720),
            ("Bảo Lộc", 11.5480, 107.8070),
        ],
    },
    {
        "name": "Đồng Nai - TP.HCM: Long Thành ↔ TP.HCM tránh cao tốc",
        "region": "dong_nai_hcm",
        "bounds": {
            "lat_min": 10.45,
            "lat_max": 11.05,
            "lon_min": 106.45,
            "lon_max": 107.25,
        },
        "east_to_hcm": [
            ("Long Thành", 10.7890, 106.9570),
            ("Nhơn Trạch", 10.7110, 106.8860),
            ("Phà Cát Lái", 10.7700, 106.7890),
        ],
        "hcm_to_east": [
            ("Phà Cát Lái", 10.7700, 106.7890),
            ("Nhơn Trạch", 10.7110, 106.8860),
            ("Long Thành", 10.7890, 106.9570),
        ],
    },
]


def _in_bounds(pt: Coord, bounds: Dict[str, float]) -> bool:
    lat, lon = float(pt[0]), float(pt[1])
    return (
        bounds["lat_min"] <= lat <= bounds["lat_max"] and
        bounds["lon_min"] <= lon <= bounds["lon_max"]
    )


def _near_dalat(pt: Coord) -> bool:
    lat, lon = float(pt[0]), float(pt[1])
    return 11.82 <= lat <= 12.08 and 108.30 <= lon <= 108.65


def _west_lam_dong(pt: Coord) -> bool:
    lat, lon = float(pt[0]), float(pt[1])
    return 11.25 <= lat <= 11.75 and 107.35 <= lon <= 108.25


def _near_hcm(pt: Coord) -> bool:
    lat, lon = float(pt[0]), float(pt[1])
    return 10.60 <= lat <= 10.95 and 106.55 <= lon <= 106.90


def _near_long_thanh_dong_nai(pt: Coord) -> bool:
    lat, lon = float(pt[0]), float(pt[1])
    return 10.60 <= lat <= 10.95 and 106.85 <= lon <= 107.20


def get_motorbike_corridor_candidates(origin: Coord, destination: Coord) -> List[Dict]:
    """Trả về danh sách corridor phù hợp với cặp điểm origin/destination.

    Không dựa vào text người dùng; chỉ dựa vào tọa độ đã geocode.
    Mỗi candidate có: name, waypoints [(lat, lon), ...]
    """
    out: List[Dict] = []
    o = (float(origin[0]), float(origin[1]))
    d = (float(destination[0]), float(destination[1]))

    # Lâm Đồng: nếu một đầu gần Đà Lạt/Đức Trọng và đầu kia ở Đạ Huoai/Bảo Lộc/Di Linh
    if (_west_lam_dong(o) and _near_dalat(d)) or (_near_dalat(o) and _west_lam_dong(d)):
        c = MOTORBIKE_CORRIDORS[0]
        if _west_lam_dong(o) and _near_dalat(d):
            wps = c["west_to_dalat"]
        else:
            wps = c["dalat_to_west"]
        out.append({
            "name": c["name"],
            "region": c["region"],
            "waypoints": [(float(lat), float(lon)) for _name, lat, lon in wps],
            "labels": [str(_name) for _name, _lat, _lon in wps],
        })

    # TP.HCM - Long Thành/Đồng Nai
    if (_near_hcm(o) and _near_long_thanh_dong_nai(d)) or (_near_long_thanh_dong_nai(o) and _near_hcm(d)):
        c = MOTORBIKE_CORRIDORS[1]
        if _near_hcm(o) and _near_long_thanh_dong_nai(d):
            wps = c["hcm_to_east"]
        else:
            wps = c["east_to_hcm"]
        out.append({
            "name": c["name"],
            "region": c["region"],
            "waypoints": [(float(lat), float(lon)) for _name, lat, lon in wps],
            "labels": [str(_name) for _name, _lat, _lon in wps],
        })

    return out
