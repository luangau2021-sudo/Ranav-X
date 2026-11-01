# ui/sos_view.py
# Giao diện SOS — màn hình khẩn cấp, đơn giản, dễ thấy

import time
from utils.logger import setup_logger

logger = setup_logger(__name__)


def show_sos_screen():
    """Hiển thị màn hình SOS với hướng dẫn rõ ràng."""
    print("\n" + "🆘" * 20)
    print("          TÌNH HUỐNG KHẨN CẤP — SOS")
    print("🆘" * 20)
    print("\n  Chọn loại khẩn cấp:")
    print("  1. 🚗 Tai nạn giao thông")
    print("  2. 🏥 Cấp cứu y tế")
    print("  3. 🔥 Cháy / hỏa hoạn")
    print("  4. 🏔️ Bị mắc kẹt / lạc đường")
    print("  5. 🚨 Khẩn cấp khác")
    print("  0. ← Quay lại")
    return input("\n  Chọn: ").strip()


def show_emergency_numbers():
    """Hiển thị bảng số khẩn cấp nổi bật."""
    print("\n" + "=" * 50)
    print("  📞 SỐ ĐIỆN THOẠI KHẨN CẤP VIỆT NAM")
    print("=" * 50)
    print("  🚓  Công an          :  113")
    print("  🚒  Cứu hỏa          :  114")
    print("  🚑  Cấp cứu y tế     :  115")
    print("  🏔️  Tìm kiếm cứu nạn : 1800 599 920")
    print("=" * 50)


def show_sos_active(sos_info: dict):
    """Màn hình sau khi SOS đã kích hoạt."""
    print("\n" + "🔴" * 25)
    print("       SOS ĐÃ GỬI — GIỮ BÌNH TĨNH")
    print("🔴" * 25)
    print(f"\n  ID khẩn cấp: {sos_info.get('sos_id','')}")
    print(f"\n  📍 Vị trí của bạn:")
    print(f"  {sos_info.get('location_url','')}")
    print("\n  📱 Sao chép tin nhắn này gửi người thân:")
    print(f"\n  {sos_info.get('message_template','')}")
    print("\n  ⚡ Hướng dẫn ngay:")
    for step in sos_info.get("instructions", [])[:3]:
        print(f"  {step}")
    print("\n" + "🔴" * 25)
