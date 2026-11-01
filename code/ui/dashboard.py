# ui/dashboard.py
# Màn hình chính — giao diện dòng lệnh (CLI) cho app

import os
from typing import Optional
from utils.helpers import format_distance, format_duration, format_risk_level
from utils.logger import setup_logger

logger = setup_logger(__name__)


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_header():
    print("=" * 60)
    print("   🗺️  TRIPSMART PRO — HUMAN-AWARE NAVIGATION VN")
    print("=" * 60)


def print_menu() -> str:
    print("\n📋 MENU CHÍNH")
    print("-" * 40)
    print("  1. 🗺️  Tìm đường")
    print("  2. ⚠️  Kiểm tra rủi ro khu vực")
    print("  3. 🆘  Kích hoạt SOS")
    print("  4. 📍  Xem báo cáo cộng đồng")
    print("  5. 🏛️  Gợi ý điểm tham quan")
    print("  6. 📔  Ký ức hành trình")
    print("  7. 🌪️  Thiên tai — tìm tuyến sơ tán")
    print("  8. 🌤️  Thời tiết hiện tại")
    print("  0. ❌  Thoát")
    print("-" * 40)
    return input("  Chọn (0-8): ").strip()


def print_route_result(route: dict):
    print("\n✅ KẾT QUẢ TÌM ĐƯỜNG")
    print("-" * 40)
    print(f"  📏 Khoảng cách : {route.get('distance_text', 'N/A')}")
    print(f"  ⏱️  Thời gian   : {route.get('duration_text', 'N/A')}")
    if route.get("fallback"):
        print(f"  ⚠️  {route.get('note','')}")
    steps = route.get("steps", [])
    if steps:
        print(f"\n  📝 Hướng dẫn ({len(steps)} bước):")
        for i, step in enumerate(steps[:5], 1):
            print(f"    {i}. {step['instruction']} ({step['distance_text'] if 'distance_text' in step else step['distance_km']}km)")
        if len(steps) > 5:
            print(f"    ... và {len(steps)-5} bước nữa")


def print_risk_result(risk: dict):
    print("\n⚠️  PHÂN TÍCH RỦI RO")
    print("-" * 40)
    print(f"  Tổng thể  : {risk.get('level','')}")
    print(f"  Địa chất  : {format_risk_level(risk.get('geological',0))}")
    print(f"  Lũ lụt    : {format_risk_level(risk.get('flood',0))}")
    print(f"  Sạt lở    : {format_risk_level(risk.get('landslide',0))}")
    alerts = risk.get("alerts", [])
    if alerts:
        print("\n  🚨 Cảnh báo:")
        for a in alerts:
            print(f"    {a}")


def print_sos_result(sos: dict):
    print("\n🆘 SOS ĐÃ KÍCH HOẠT")
    print("=" * 40)
    print(f"  ID: {sos.get('sos_id')}")
    print(f"\n  📞 Số khẩn cấp:")
    for c in sos.get("contacts", []):
        print(f"    {c['name']}: {c['number']}")
    print(f"\n  📍 Vị trí: {sos.get('location_url')}")
    print(f"\n  📋 Hướng dẫn:")
    for inst in sos.get("instructions", []):
        print(f"    {inst}")
    print("\n  📱 Tin nhắn mẫu:")
    print(f"  {sos.get('message_template','')}")
    print("=" * 40)


def print_weather(weather: dict):
    w = weather.get("weather", weather)
    print("\n🌤️  THỜI TIẾT")
    print("-" * 40)
    print(f"  Nhiệt độ  : {w.get('temp_c','?')}°C (cảm giác {w.get('feels_like_c','?')}°C)")
    print(f"  Mô tả     : {w.get('description','')}")
    print(f"  Gió       : {w.get('wind_speed_ms','?')} m/s")
    print(f"  Độ ẩm     : {w.get('humidity_pct','?')}%")
    alerts = weather.get("alerts", [])
    if alerts:
        for a in alerts:
            print(f"  ⚠️  {a}")


def get_coordinates(prompt: str):
    """Nhập tọa độ hoặc tên địa điểm từ người dùng."""
    print(f"\n  {prompt}")
    print("  (Nhập tọa độ 'lat,lon' hoặc tên địa điểm)")
    raw = input("  > ").strip()
    if "," in raw:
        try:
            parts = raw.split(",")
            return float(parts[0]), float(parts[1]), raw
        except ValueError:
            pass
    return None, None, raw


def ask_travel_mode() -> str:
    print("\n  Phương tiện:")
    print("  1. Ô tô  2. Xe máy  3. Xe đạp  4. Đi bộ")
    c = input("  Chọn [1]: ").strip() or "1"
    return {"1": "car", "2": "motorbike", "3": "bike", "4": "walk"}.get(c, "car")


def ask_human_profile() -> dict:
    print("\n  👤 THÔNG TIN NGƯỜI ĐI")
    print("-" * 30)
    try:
        age = int(input("  Tuổi: ").strip() or "30")
    except ValueError:
        age = 30
    try:
        hour = int(input("  Giờ xuất phát (0-23): ").strip() or "8")
    except ValueError:
        hour = 8
    motion = input("  Dễ say xe? (y/n) [n]: ").strip().lower() == "y"
    try:
        stress = int(input("  Mức stress 1-5 [2]: ").strip() or "2")
    except ValueError:
        stress = 2
    children = input("  Có trẻ nhỏ đi cùng? (y/n) [n]: ").strip().lower() == "y"
    return {
        "age": age,
        "travel_hour": hour,
        "has_motion_sickness": motion,
        "stress_level": stress,
        "has_children": children,
    }
