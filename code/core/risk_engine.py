import os
import csv
from typing import List, Dict, Optional
from utils.config import (
    GEOLOGICAL_FILE,
    VIETNAM_ZONES_FILE,
    DANGER_THRESHOLD,
    GEOLOGICAL_RISK_HIGH,
    FLOOD_RISK_HIGH,
    LANDSLIDE_RISK_HIGH,
)
from utils.helpers import haversine_distance, load_json, format_risk_level
from utils.logger import setup_logger

try:
    from features.landslide_realtime import LandslideRealtimeEngine
except Exception:
    LandslideRealtimeEngine = None

logger = setup_logger(__name__)

# ── Đường dẫn CSV rủi ro tùy chỉnh ─────────────────────────────────────────
# Tự nhận biết: nếu file này nằm trong thư mục core/ thì lùi lên 1 cấp
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE) if os.path.basename(_HERE) == "core" else _HERE
CSV_RISK_FILE = os.path.join(_PROJECT_ROOT, "data", "risk_points_vietnam.csv")


def _score_to_color(score: float) -> str:
    """Trả về màu hex từ xanh an toàn đến đỏ nguy hiểm."""
    if score < 0.20:
        return "#1a73e8"
    if score < 0.40:
        return "#43a047"
    if score < 0.55:
        return "#fdd835"
    if score < 0.70:
        return "#fb8c00"
    return "#b71c1c"


BUILTIN_HAZARD_ZONES = [
    # SẠT LỞ / ĐỊA CHẤT
    {"lat": 22.33, "lon": 103.84, "radius_km": 25, "score": 0.85, "type": "landslide", "label": "Sạt lở Sapa", "icon": "⛰️", "desc": "Khu vực đèo núi cao, mưa lớn gây sạt lở thường xuyên tháng 7-9."},
    {"lat": 21.38, "lon": 103.02, "radius_km": 20, "score": 0.80, "type": "landslide", "label": "Sạt lở Điện Biên", "icon": "⛰️", "desc": "Địa hình dốc, nền đất yếu, nguy cơ sạt lở cao mùa mưa."},
    {"lat": 22.10, "lon": 104.87, "radius_km": 18, "score": 0.78, "type": "landslide", "label": "Sạt lở Hà Giang", "icon": "⛰️", "desc": "Cao nguyên đá, đèo Mã Pì Lèng — nguy cơ đá rơi, sạt lở."},
    {"lat": 15.12, "lon": 108.19, "radius_km": 15, "score": 0.72, "type": "geological", "label": "Địa chất yếu Quảng Nam", "icon": "🏔️", "desc": "Nền đất pha cát, dễ sụt lún sau mưa lớn."},
    {"lat": 14.35, "lon": 108.00, "radius_km": 20, "score": 0.70, "type": "landslide", "label": "Sạt lở Kon Tum", "icon": "⛰️", "desc": "Vùng Tây Nguyên giáp núi, đèo dốc nguy hiểm."},
    {"lat": 11.91, "lon": 108.43, "radius_km": 12, "score": 0.62, "type": "landslide", "label": "Đèo Prenn – Đà Lạt", "icon": "⛰️", "desc": "Đèo núi, đường hẹp, sương mù dày đặc buổi sáng."},
    {"lat": 11.50, "lon": 108.07, "radius_km": 15, "score": 0.65, "type": "landslide", "label": "Đèo Bảo Lộc", "icon": "⛰️", "desc": "Đèo dài, nhiều cua gấp, dễ sạt lở mùa mưa."},
    {"lat": 13.79, "lon": 109.22, "radius_km": 10, "score": 0.55, "type": "geological", "label": "Vùng ven biển Bình Định", "icon": "🌊", "desc": "Xói lở bờ biển, nguy cơ ngập khi bão."},

    # LŨ LỤT
    {"lat": 10.34, "lon": 105.32, "radius_km": 30, "score": 0.80, "type": "flood", "label": "Lũ đồng bằng Cần Thơ", "icon": "🌊", "desc": "Ngập lũ theo mùa tháng 8-11, mực nước có thể +1.5m."},
    {"lat": 10.82, "lon": 106.63, "radius_km": 25, "score": 0.68, "type": "flood", "label": "Ngập TP.HCM", "icon": "🌊", "desc": "Vùng thấp triều cường, ngập sau mưa lớn >80mm."},
    {"lat": 15.88, "lon": 108.34, "radius_km": 20, "score": 0.75, "type": "flood", "label": "Lũ Hội An – Quảng Nam", "icon": "🌊", "desc": "Lũ lịch sử thường xuyên tháng 10-12, phố cổ ngập sâu."},
    {"lat": 17.47, "lon": 106.60, "radius_km": 25, "score": 0.72, "type": "flood", "label": "Lũ Quảng Bình", "icon": "🌊", "desc": "Vùng trũng, lũ ống, lũ quét nguy hiểm mùa mưa bão."},
    {"lat": 20.86, "lon": 106.06, "radius_km": 20, "score": 0.65, "type": "flood", "label": "Ngập Hải Phòng", "icon": "🌊", "desc": "Vùng ven biển, nguy cơ ngập do triều cường và bão."},
    {"lat": 16.07, "lon": 108.22, "radius_km": 15, "score": 0.60, "type": "flood", "label": "Ngập Đà Nẵng", "icon": "🌊", "desc": "Các quận ven sông, ngập sâu khi mưa lớn kết hợp triều."},

    # ĐƯỜNG XẤU / NÚI
    {"lat": 21.83, "lon": 104.14, "radius_km": 15, "score": 0.70, "type": "bad_road", "label": "Đèo Pha Đin", "icon": "🛣️", "desc": "Một trong tứ đại đỉnh đèo VN, đường hẹp 3.5m, nhiều cua tay áo."},
    {"lat": 21.88, "lon": 104.67, "radius_km": 12, "score": 0.68, "type": "bad_road", "label": "Đèo Ô Quy Hồ", "icon": "🛣️", "desc": "Đèo dài 50km, sương mù dày, đường trơn mùa mưa."},
    {"lat": 16.20, "lon": 107.95, "radius_km": 18, "score": 0.73, "type": "bad_road", "label": "Đèo Hải Vân", "icon": "🛣️", "desc": "Đèo cao 496m, gió lớn, sương mù, nhiều tai nạn."},
    {"lat": 12.90, "lon": 108.44, "radius_km": 12, "score": 0.62, "type": "bad_road", "label": "Đèo Phượng Hoàng", "icon": "🛣️", "desc": "Đèo dốc, đường hẹp, trơn mùa mưa tháng 7-10."},
    {"lat": 14.24, "lon": 108.88, "radius_km": 10, "score": 0.60, "type": "bad_road", "label": "Đèo Mang Yang", "icon": "🛣️", "desc": "Quốc lộ 19, đèo núi, nhiều xe tải, cần thận trọng."},
]


def _load_csv_hazards(csv_path: str) -> List[Dict]:
    """
    Đọc file CSV điểm rủi ro tùy chỉnh và trả về list zone dict.

    Cột CSV cần có (không phân biệt hoa thường):
        lat, lon, radius_km, score, type, label, icon, desc

    In debug chi tiết ra terminal để dễ kiểm tra.
    """
    print(f"\n[RiskEngine CSV] Đường dẫn đang tìm : {csv_path}")
    print(f"[RiskEngine CSV] File tồn tại       : {os.path.exists(csv_path)}")

    if not os.path.exists(csv_path):
        print(f"[RiskEngine CSV] ⚠️  Không tìm thấy file — bỏ qua CSV.\n")
        return []

    zones = []
    try:
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            # Chuẩn hoá tên cột: strip khoảng trắng + lowercase
            reader.fieldnames = [h.strip().lower() for h in (reader.fieldnames or [])]
            for i, row in enumerate(reader, start=2):  # start=2 vì dòng 1 là header
                try:
                    zone = {
                        "lat":       float(row["lat"]),
                        "lon":       float(row["lon"]),
                        "radius_km": float(row.get("radius_km") or 15),
                        "score":     float(row.get("score") or 0.65),
                        "type":      str(row.get("type") or "geological").strip(),
                        "label":     str(row.get("label") or "Điểm rủi ro").strip(),
                        "icon":      str(row.get("icon") or "⚠️").strip(),
                        "desc":      str(row.get("desc") or "").strip(),
                    }
                    zones.append(zone)
                except (KeyError, ValueError) as e:
                    print(f"[RiskEngine CSV] ⚠️  Dòng {i} bị bỏ qua: {e} — {dict(row)}")
    except Exception as e:
        print(f"[RiskEngine CSV] ❌ Lỗi đọc file: {e}\n")
        return []

    print(f"[RiskEngine CSV] Đã đọc được        : {len(zones)} dòng hợp lệ\n")
    return zones


class RiskEngine:
    def __init__(self):
        self.geological_data = load_json(GEOLOGICAL_FILE) or {}
        self.danger_zones = load_json(VIETNAM_ZONES_FILE) or {"zones": []}

        # ── 1. Zone tích hợp sẵn ────────────────────────────────────────────
        self.hazard_zones = list(BUILTIN_HAZARD_ZONES)
        builtin_count = len(self.hazard_zones)

        # ── 2. Zone từ file JSON địa chất ───────────────────────────────────
        for z in self.geological_data.get("high_risk_zones", []):
            self.hazard_zones.append({
                "lat": z["lat"],
                "lon": z["lon"],
                "radius_km": z.get("radius_km", 15),
                "score": z.get("risk_score", 0.75),
                "type": "geological",
                "label": z.get("name", "Vùng nguy hiểm"),
                "icon": "⚠️",
                "desc": z.get("desc", ""),
            })
        json_count = len(self.hazard_zones) - builtin_count

        # ── 3. Zone từ CSV rủi ro tùy chỉnh ─────────────────────────────────
        csv_zones = _load_csv_hazards(CSV_RISK_FILE)
        self.hazard_zones.extend(csv_zones)

        # ── Debug tổng kết ───────────────────────────────────────────────────
        print(
            f"[RiskEngine] ✅ Tổng hazard zones: {len(self.hazard_zones)}"
            f"  (builtin={builtin_count}, json={json_count}, csv={len(csv_zones)})"
        )

        self.landslide_realtime = None
        if LandslideRealtimeEngine:
            try:
                self.landslide_realtime = LandslideRealtimeEngine()
            except Exception as e:
                logger.warning(f"Không bật được LandslideRealtimeEngine: {e}")

        logger.info(
            f"RiskEngine: {len(self.hazard_zones)} hazard zones"
            f" (builtin={builtin_count}, json={json_count}, csv={len(csv_zones)})"
            f" · landslide realtime={'ON' if self.landslide_realtime else 'OFF'}"
        )

    # ── PUBLIC ────────────────────────────────────────────────────────────────
    def analyze_point(self, lat: float, lon: float) -> Dict:
        geo_score = self._geological_risk(lat, lon)
        flood_score = self._flood_risk(lat, lon)
        land_score = self._landslide_risk(lat, lon)
        realtime_land = self._realtime_landslide_score(lat, lon)
        if realtime_land:
            land_score = max(land_score, realtime_land.get("score", 0))

        zone_info = self._nearest_danger_zone(lat, lon)
        overall = max(geo_score, flood_score, land_score)
        if zone_info and zone_info["distance_km"] < zone_info.get("radius_km", 5):
            overall = min(1.0, overall + 0.2)

        alerts = self._build_alerts(geo_score, flood_score, land_score, zone_info)
        if realtime_land and realtime_land.get("score", 0) >= 0.55:
            alerts.append(f"⛰️ {realtime_land.get('label')}: {realtime_land.get('reason')}")

        return {
            "overall_score": round(overall, 3),
            "level": format_risk_level(overall),
            "geological": round(geo_score, 3),
            "flood": round(flood_score, 3),
            "landslide": round(land_score, 3),
            "nearest_danger_zone": zone_info["name"] if zone_info else None,
            "alerts": alerts,
        }

    def analyze_route(self, polyline: List) -> Dict:
        """
        Phân tích toàn tuyến.
        Trả về danger_segments, rest_suggestions, avg_score, safe_to_proceed, summary.
        Có tích hợp cảnh báo sạt lở gần thời gian thực nhưng chỉ gọi API theo mẫu thưa để tránh chậm/quota.
        """
        if not polyline:
            return {
                "danger_segments": [],
                "rest_suggestions": [],
                "avg_score": 0,
                "safe_to_proceed": True,
                "summary": "Không có dữ liệu tuyến đường.",
            }

        sample = self._sample_route_by_distance(polyline, target_gap_km=8.0, max_points=45)
        scores = []
        danger_segments = []
        seen_zones = set()
        seen_realtime_cells = set()

        for item in sample:
            lat_c = item["lat"]
            lon_c = item["lon"]
            route_km = item["route_km"]

            base_score = self._point_score(lat_c, lon_c)
            score = base_score

            realtime_land = None
            if self.landslide_realtime:
                # Chỉ gọi realtime cho vùng có khả năng đồi núi hoặc đã có rủi ro nền.
                if base_score >= 0.32 or self._landslide_risk(lat_c, lon_c) >= 0.35:
                    realtime_land = self._realtime_landslide_score(lat_c, lon_c)
                    if realtime_land:
                        score = max(score, realtime_land.get("score", 0))

            scores.append(score)

            # 1) Cảnh báo realtime sạt lở ưu tiên riêng
            if realtime_land and realtime_land.get("score", 0) >= 0.55:
                cell = (round(lat_c, 1), round(lon_c, 1), realtime_land.get("level"))
                if cell not in seen_realtime_cells:
                    seen_realtime_cells.add(cell)
                    danger_segments.append({
                        "lat": lat_c,
                        "lon": lon_c,
                        "score": round(realtime_land["score"], 3),
                        "color": realtime_land.get("color", _score_to_color(realtime_land["score"])),
                        "type": "landslide",
                        "label": realtime_land.get("label", "Nguy cơ sạt lở"),
                        "icon": "⛰️",
                        "desc": realtime_land.get("reason", "Ước tính nguy cơ sạt lở theo thời tiết và địa hình."),
                        "route_km": round(route_km, 1),
                        "alerts": [f"⛰️ {realtime_land.get('label')}: {realtime_land.get('reason')}"]
                    })
                continue

            # 2) Cảnh báo nền hiện có
            if score >= 0.40:
                hz = self._nearest_hazard_zone(lat_c, lon_c)
                if hz:
                    key = hz["label"]
                    if key not in seen_zones:
                        seen_zones.add(key)
                        danger_segments.append({
                            "lat": lat_c,
                            "lon": lon_c,
                            "score": round(score, 3),
                            "color": _score_to_color(score),
                            "type": hz["type"],
                            "label": hz["label"],
                            "icon": hz["icon"],
                            "desc": hz["desc"],
                            "route_km": round(route_km, 1),
                            "alerts": [f"{hz['icon']} {hz['label']}: {hz['desc']}"],
                        })
                elif score >= 0.55:
                    # Chỉ giữ cảnh báo chung khi đủ đáng chú ý để tránh spam 78+ dòng.
                    danger_segments.append({
                        "lat": lat_c,
                        "lon": lon_c,
                        "score": round(score, 3),
                        "color": _score_to_color(score),
                        "type": "general",
                        "label": "Vùng rủi ro",
                        "icon": "⚠️",
                        "desc": f"Điểm rủi ro ({score:.0%}) trên tuyến đường.",
                        "route_km": round(route_km, 1),
                        "alerts": [f"⚠️ Rủi ro {score:.0%}"],
                    })

        danger_segments = self._dedupe_and_limit_dangers(danger_segments, max_items=18)
        avg = sum(scores) / len(scores) if scores else 0
        rest_suggestions = self._suggest_rest_stops(polyline)

        if avg < 0.30:
            summary = f"✅ Tuyến an toàn · {len(danger_segments)} vùng cần chú ý · Rủi ro TB {avg:.0%}"
        elif avg < 0.55:
            summary = f"🟡 Tuyến trung bình · {len(danger_segments)} vùng nguy hiểm · Rủi ro TB {avg:.0%} · Lái xe thận trọng"
        else:
            summary = f"🔴 Tuyến rủi ro cao · {len(danger_segments)} vùng nguy hiểm · Rủi ro TB {avg:.0%} · Cân nhắc tuyến khác"

        return {
            "danger_segments": danger_segments,
            "rest_suggestions": rest_suggestions,
            "avg_score": round(avg, 3),
            "safe_to_proceed": avg < DANGER_THRESHOLD,
            "summary": summary,
        }

    def score_polyline_segments(self, polyline: List) -> List[Dict]:
        """Tô màu gradient từng đoạn nhỏ. Không gọi realtime ở đây để tránh chậm và tốn quota."""
        if not polyline or len(polyline) < 2:
            return []

        result = []
        accumulated = 0.0
        # FIX: Không được downsample bằng polyline[::k].
        # Cách đó nối các điểm xa nhau thành đoạn thẳng, làm tuyến đèo nhìn như
        # cắt xuyên rừng dù OSRM có polyline đúng. Giữ toàn bộ điểm liền kề
        # để lớp màu rủi ro vẫn bám đúng hình dạng đường thật.
        pts = polyline

        for i in range(len(pts) - 1):
            p1, p2 = pts[i], pts[i + 1]
            lon1, lat1 = p1[0], p1[1]
            lon2, lat2 = p2[0], p2[1]
            mid_lat = (lat1 + lat2) / 2
            mid_lon = (lon1 + lon2) / 2
            score = self._point_score(mid_lat, mid_lon)
            seg_km = haversine_distance(lat1, lon1, lat2, lon2)
            accumulated += seg_km
            result.append({
                "lat1": lat1,
                "lon1": lon1,
                "lat2": lat2,
                "lon2": lon2,
                "score": round(score, 3),
                "color": _score_to_color(score),
                "route_km": round(accumulated, 1),
            })
        return result

    def get_danger_level(self, score: float) -> str:
        return format_risk_level(score)

    def extract_risk_features_for_point(self, lat: float, lon: float) -> Dict:
        """
        Tạo đặc trưng rủi ro địa lý cho một điểm trên tuyến.

        Trả về dict:
            dist_nearest_km    : khoảng cách tới hazard zone gần nhất (km)
            nearest_score      : điểm rủi ro của zone gần nhất
            nearest_type       : loại zone gần nhất (landslide/flood/...)
            nearest_label      : tên zone gần nhất
            zone_count_5km     : số zone trong bán kính 5km
            max_score_10km     : điểm rủi ro cao nhất trong bán kính 10km
            is_landslide_zone, is_flood_zone, is_bad_road_zone, is_geological_zone
            base_geo_score     : điểm rủi ro nền (geo/flood/landslide tổng hợp)
        """
        dist_nearest  = float("inf")
        nearest_score = 0.0
        nearest_type  = None
        nearest_label = None
        zone_count_5km = 0
        max_score_10km = 0.0
        is_landslide = is_flood = is_bad_road = is_geo = 0

        for hz in self.hazard_zones:
            d = haversine_distance(lat, lon, hz["lat"], hz["lon"])
            if d < dist_nearest:
                dist_nearest  = d
                nearest_score = hz["score"]
                nearest_type  = hz["type"]
                nearest_label = hz.get("label", "Vùng rủi ro")
            if d <= hz["radius_km"]:
                t = hz["type"]
                if t == "landslide":   is_landslide = 1
                if t == "flood":       is_flood     = 1
                if t == "bad_road":    is_bad_road  = 1
                if t == "geological":  is_geo       = 1
            if d <= 5.0:
                zone_count_5km += 1
            if d <= 10.0 and hz["score"] > max_score_10km:
                max_score_10km = hz["score"]

        if dist_nearest == float("inf"):
            dist_nearest = 999.0

        return {
            "dist_nearest_km": round(dist_nearest, 2),
            "nearest_score": round(nearest_score, 3),
            "nearest_type": nearest_type,
            "nearest_label": nearest_label,
            "zone_count_5km": zone_count_5km,
            "max_score_10km": round(max_score_10km, 3),
            "is_landslide_zone": is_landslide,
            "is_flood_zone": is_flood,
            "is_bad_road_zone": is_bad_road,
            "is_geological_zone": is_geo,
            "base_geo_score": round(self._point_score(lat, lon), 3),
        }

    # ── INTERNAL ─────────────────────────────────────────────────────────────
    def _point_score(self, lat: float, lon: float) -> float:
        return max(
            self._geological_risk(lat, lon),
            self._flood_risk(lat, lon),
            self._landslide_risk(lat, lon),
        )

    def _realtime_landslide_score(self, lat: float, lon: float) -> Optional[Dict]:
        if not self.landslide_realtime:
            return None
        try:
            return self.landslide_realtime.analyze_point(lat, lon)
        except Exception as e:
            logger.warning(f"Landslide realtime lỗi tại ({lat}, {lon}): {e}")
            return None

    def _geological_risk(self, lat, lon) -> float:
        for zone in self.hazard_zones:
            if zone["type"] in ("geological", "landslide", "bad_road"):
                d = haversine_distance(lat, lon, zone["lat"], zone["lon"])
                if d <= zone["radius_km"]:
                    factor = max(0.0, 1.0 - d / zone["radius_km"])
                    return min(1.0, zone["score"] * (0.5 + 0.5 * factor))
        if 14.0 <= lat <= 23.5 and 102.0 <= lon <= 106.5:
            return 0.30
        return 0.10

    def _flood_risk(self, lat, lon) -> float:
        for zone in self.hazard_zones:
            if zone["type"] == "flood":
                d = haversine_distance(lat, lon, zone["lat"], zone["lon"])
                if d <= zone["radius_km"]:
                    factor = max(0.0, 1.0 - d / zone["radius_km"])
                    return min(1.0, zone["score"] * (0.5 + 0.5 * factor))
        if 9.0 <= lat <= 11.5 and 104.5 <= lon <= 106.8:
            return 0.55
        if 20.0 <= lat <= 21.5 and 105.5 <= lon <= 107.0:
            return 0.45
        if 14.0 <= lat <= 18.0 and 107.5 <= lon <= 109.0:
            return 0.50
        return 0.12

    def _landslide_risk(self, lat, lon) -> float:
        for zone in self.hazard_zones:
            if zone["type"] == "landslide":
                d = haversine_distance(lat, lon, zone["lat"], zone["lon"])
                if d <= zone["radius_km"]:
                    factor = max(0.0, 1.0 - d / zone["radius_km"])
                    return min(1.0, zone["score"] * (0.5 + 0.5 * factor))
        if 11.5 <= lat <= 16.0 and 107.0 <= lon <= 109.0:
            return 0.45
        if 20.5 <= lat <= 23.5 and 102.0 <= lon <= 105.0:
            return 0.60
        return 0.10

    def _nearest_hazard_zone(self, lat, lon) -> Optional[Dict]:
        closest, min_dist = None, float("inf")
        for hz in self.hazard_zones:
            d = haversine_distance(lat, lon, hz["lat"], hz["lon"])
            if d < min_dist and d <= hz["radius_km"] * 1.2:
                min_dist = d
                closest = hz
        return closest

    def _nearest_danger_zone(self, lat, lon) -> Optional[Dict]:
        zones = self.danger_zones.get("zones", [])
        closest, min_dist = None, float("inf")
        for zone in zones:
            dist = haversine_distance(lat, lon, zone["lat"], zone["lon"])
            if dist < min_dist:
                min_dist = dist
                closest = {**zone, "distance_km": round(dist, 2)}
        return closest if closest and min_dist < 50 else None

    def _build_alerts(self, geo, flood, land, zone) -> List[str]:
        alerts = []
        if geo >= GEOLOGICAL_RISK_HIGH:
            alerts.append("⚠️ Khu vực có nguy cơ địa chất cao")
        if flood >= FLOOD_RISK_HIGH:
            alerts.append("🌊 Cảnh báo nguy cơ lũ lụt")
        if land >= LANDSLIDE_RISK_HIGH:
            alerts.append("⛰️ Cảnh báo nguy cơ sạt lở")
        if zone:
            alerts.append(f"📍 Gần vùng nguy hiểm: {zone['name']} ({zone['distance_km']} km)")
        return alerts

    def _suggest_rest_stops(self, polyline: List) -> List[Dict]:
        if not polyline or len(polyline) < 2:
            return []
        stops = []
        accumulated = 0.0
        interval_km = 80.0
        next_stop = interval_km
        rest_icons = ["☕", "🍜", "⛽", "🏪"]
        rest_desc = [
            "Dừng nghỉ, uống nước và kiểm tra xe.",
            "Điểm dừng ăn uống, tiếp sức.",
            "Trạm xăng / dịch vụ đường dài.",
            "Điểm nghỉ khuyến nghị trên hành trình.",
        ]
        idx = 0
        for i in range(1, len(polyline)):
            prev, curr = polyline[i - 1], polyline[i]
            accumulated += haversine_distance(prev[1], prev[0], curr[1], curr[0])
            if accumulated >= next_stop:
                stops.append({
                    "lat": curr[1],
                    "lon": curr[0],
                    "name": f"Điểm nghỉ {idx + 1}",
                    "icon": rest_icons[idx % len(rest_icons)],
                    "desc": rest_desc[idx % len(rest_desc)],
                    "route_km": round(accumulated, 1),
                })
                next_stop += interval_km
                idx += 1
        return stops

    def _sample_route_by_distance(self, polyline: List, target_gap_km: float = 8.0, max_points: int = 45) -> List[Dict]:
        if not polyline:
            return []

        result = []
        accumulated = 0.0
        next_take = 0.0
        prev = None

        for coord in polyline:
            lon, lat = coord[0], coord[1]
            if prev is not None:
                accumulated += haversine_distance(prev[1], prev[0], lat, lon)
            if accumulated >= next_take or not result:
                result.append({"lat": lat, "lon": lon, "route_km": accumulated})
                next_take += target_gap_km
            prev = coord

        if len(result) > max_points:
            step = max(1, len(result) // max_points)
            result = result[::step][:max_points]
        return result

    def _dedupe_and_limit_dangers(self, dangers: List[Dict], max_items: int = 18) -> List[Dict]:
        if not dangers:
            return []

        # Gom bớt các cảnh báo cùng loại quá gần nhau.
        dangers = sorted(dangers, key=lambda x: (x.get("type", ""), x.get("route_km", 0)))
        compact = []
        for d in dangers:
            if compact:
                last = compact[-1]
                same_type = last.get("type") == d.get("type")
                close_km = abs(float(d.get("route_km", 0)) - float(last.get("route_km", 0))) < 4
                same_label = last.get("label") == d.get("label")
                if same_type and close_km and same_label:
                    if d.get("score", 0) > last.get("score", 0):
                        compact[-1] = d
                    continue
            compact.append(d)

        # Ưu tiên cảnh báo mạnh hơn; sau đó sắp lại theo km để UI dễ đọc.
        compact = sorted(compact, key=lambda x: x.get("score", 0), reverse=True)[:max_items]
        compact = sorted(compact, key=lambda x: x.get("route_km", 0))
        return compact

    # ── SO SÁNH NHIỀU TUYẾN ───────────────────────────────────────────────────

    def compare_routes(self, routes: List[Dict]) -> List[Dict]:
        """
        So sánh danh sách tuyến đường theo các tiêu chí: tốc độ, an toàn, cân bằng.

        Mỗi route trong `routes` phải có:
            - polyline       : List[[lon, lat], ...]
            - distance_km    : float   (km)
            - duration_min   : float   (phút) — hoặc duration_text để parse
            - label          : str     (tên tuyến)

        Trả về list các dict enriched, được thêm:
            avg_risk_score   : float   rủi ro trung bình (0–1)
            danger_count     : int     số vùng nguy hiểm
            ai_label         : str     "Thấp" / "Trung bình" / "Cao"
            balance_score    : float   điểm cân bằng (thấp = tốt)
            tag              : str     "fastest" | "safest" | "balanced"
            tag_label        : str     nhãn hiển thị emoji
            rank_speed       : int     thứ hạng nhanh nhất (1 = tốt nhất)
            rank_safety      : int     thứ hạng an toàn nhất
            rank_balance     : int     thứ hạng cân bằng nhất
        """
        import re

        if not routes:
            return []

        # ── Hàm phụ: parse duration ──────────────────────────────────────────
        def _to_minutes(route: Dict) -> float:
            # Ưu tiên duration_min trực tiếp
            dm = route.get("duration_min")
            if isinstance(dm, (int, float)) and dm > 0:
                return float(dm)
            # duration_seconds
            ds = route.get("duration_seconds") or route.get("duration_s")
            if isinstance(ds, (int, float)) and ds > 0:
                return ds / 60.0
            # duration_text: "2h 30p", "1 giờ 5 phút", "45 phút", "3h"
            txt = str(route.get("duration_text") or "")
            if txt:
                h_m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:h|giờ|g)\b", txt, re.I)
                m_m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:m(?:in)?|phút|p)\b", txt, re.I)
                h = float(h_m.group(1).replace(",", ".")) if h_m else 0.0
                m = float(m_m.group(1).replace(",", ".")) if m_m else 0.0
                if h or m:
                    return h * 60.0 + m
            # Fallback: ước từ khoảng cách
            km = float(route.get("distance_km") or 0)
            if km > 0:
                return km / 60.0 * 60.0  # giả sử 60 km/h
            return 0.0

        # ── Phân tích rủi ro từng tuyến ──────────────────────────────────────
        enriched = []
        for idx, route in enumerate(routes):
            polyline = route.get("polyline") or []
            analysis = self.analyze_route(polyline) if polyline else {}

            avg_score   = analysis.get("avg_score", 0.0)
            danger_segs = analysis.get("danger_segments", [])
            danger_count = len(danger_segs)

            # Nhãn AI
            if avg_score < 0.35:
                ai_label = "Thấp"
            elif avg_score < 0.60:
                ai_label = "Trung bình"
            else:
                ai_label = "Cao"

            duration_min = _to_minutes(route)
            distance_km  = float(route.get("distance_km") or 0)

            enriched.append({
                **route,
                "route_index"    : idx,
                "duration_min"   : duration_min,
                "distance_km"    : distance_km,
                "avg_risk_score" : round(avg_score, 3),
                "danger_count"   : danger_count,
                "ai_label"       : ai_label,
                "danger_segments": danger_segs,
                "analysis_summary": analysis.get("summary", ""),
            })

        # ── Xếp hạng ─────────────────────────────────────────────────────────
        # Chuẩn hoá để tính điểm cân bằng: (thời gian, rủi ro) — cả hai thấp là tốt.
        times  = [r["duration_min"]   for r in enriched]
        risks  = [r["avg_risk_score"] for r in enriched]
        max_t  = max(times)  if max(times)  > 0 else 1.0
        max_r  = max(risks)  if max(risks)  > 0 else 1.0

        for r in enriched:
            norm_t = r["duration_min"]   / max_t  # 0–1, thấp=nhanh
            norm_r = r["avg_risk_score"] / max_r  # 0–1, thấp=an toàn
            # Điểm cân bằng: 40% thời gian + 60% rủi ro (ưu tiên an toàn hơn)
            r["balance_score"] = round(0.40 * norm_t + 0.60 * norm_r, 4)

        # Thứ hạng tốc độ (1 = nhanh nhất)
        by_speed = sorted(enriched, key=lambda x: x["duration_min"])
        for rank, r in enumerate(by_speed, 1):
            r["rank_speed"] = rank

        # Thứ hạng an toàn (1 = ít rủi ro nhất)
        by_safety = sorted(enriched, key=lambda x: (x["avg_risk_score"], x["danger_count"]))
        for rank, r in enumerate(by_safety, 1):
            r["rank_safety"] = rank

        # Thứ hạng cân bằng (1 = cân bằng nhất)
        by_balance = sorted(enriched, key=lambda x: x["balance_score"])
        for rank, r in enumerate(by_balance, 1):
            r["rank_balance"] = rank

        # ── Gán nhãn gợi ý ───────────────────────────────────────────────────
        # Có thể 1 tuyến giành nhiều danh hiệu — ưu tiên: fastest > safest > balanced.
        awarded = set()

        # Tuyến nhanh nhất: rank_speed == 1
        fastest_r = min(enriched, key=lambda x: x["duration_min"])
        fastest_r["tag"] = "fastest"
        fastest_r["tag_label"] = "🚀 Nhanh nhất"
        awarded.add(fastest_r["route_index"])

        # Tuyến an toàn nhất: rank_safety == 1, nếu khác tuyến nhanh nhất
        safest_r = min(enriched, key=lambda x: (x["avg_risk_score"], x["danger_count"]))
        if safest_r["route_index"] not in awarded:
            safest_r["tag"] = "safest"
            safest_r["tag_label"] = "🛡️ An toàn nhất"
            awarded.add(safest_r["route_index"])
        else:
            # Tuyến nhanh nhất cũng là an toàn nhất: đổi nhãn nếu rủi ro thực sự thấp
            if safest_r["avg_risk_score"] < 0.40:
                safest_r["tag_label"] = "🚀🛡️ Nhanh & An toàn"

        # Tuyến cân bằng: rank_balance == 1, nếu chưa được gán
        balanced_r = min(enriched, key=lambda x: x["balance_score"])
        if balanced_r["route_index"] not in awarded:
            balanced_r["tag"] = "balanced"
            balanced_r["tag_label"] = "⚖️ Cân bằng"
            awarded.add(balanced_r["route_index"])

        # Các tuyến còn lại (nếu có > 3 tuyến)
        for r in enriched:
            if "tag" not in r:
                r["tag"] = "other"
                r["tag_label"] = "🔵 Tuyến thay thế"

        return enriched