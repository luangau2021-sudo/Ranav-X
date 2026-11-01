from typing import Dict
from utils.config import HUMAN_PROFILES
from utils.logger import setup_logger
from utils.helpers import haversine_distance

logger = setup_logger(__name__)

class HumanAwareRouter:
    AVOID_TYPES = {
        "elderly":      ["mountain_pass", "sharp_curve", "long_stretch", "unpaved"],
        "night_driver": ["dark_road", "mountain_pass", "accident_prone", "isolated"],
        "motion_sick":  ["mountain_pass", "sharp_curve", "elevation_change"],
        "stressed":     ["heavy_traffic", "construction", "noise_zone"],
        "family":       ["toll_heavy", "unpaved", "no_rest_stop"],
    }
    PREFER_TYPES = {
        "elderly":      ["hospital_nearby", "rest_stop", "flat_road"],
        "night_driver": ["well_lit", "gas_station", "rest_area"],
        "motion_sick":  ["flat_road", "straight_road", "short_segment"],
        "stressed":     ["scenic", "nature", "low_traffic"],
        "family":       ["rest_stop", "restaurant", "gas_station"],
    }

    def __init__(self):
        logger.info("HumanAwareRouter khởi động")

    def build_profile(self, age, travel_hour, has_motion_sickness, stress_level, has_children):
        profile_type = self._classify_user(age, travel_hour, has_motion_sickness, stress_level, has_children)
        base   = HUMAN_PROFILES.get(profile_type, {})
        alerts = self._generate_alerts(profile_type, age, travel_hour, stress_level)
        return {
            "profile_type":     profile_type,
            "avoid":            self.AVOID_TYPES.get(profile_type, []),
            "prefer":           self.PREFER_TYPES.get(profile_type, []),
            "rest_interval_km": base.get("rest_interval_km", 100),
            "max_drive_hours":  base.get("max_drive_hours", 4),
            "alerts":           alerts,
            "summary":          self._profile_summary(profile_type),
        }

    def adjust_route_score(self, route, profile):
        score, notes = 1.0, []
        tags = route.get("tags", [])
        for t in profile["avoid"]:
            if t in tags: score -= 0.2; notes.append(f"⚠️ Tuyến này có {self._tag_label(t)}")
        for t in profile["prefer"]:
            if t in tags: score += 0.15; notes.append(f"✅ Phù hợp: có {self._tag_label(t)}")
        dist, interval = route.get("distance_km", 0), profile["rest_interval_km"]
        if dist > interval:
            notes.append(f"🛑 Nên dừng nghỉ {int(dist//interval)} lần (mỗi {interval} km)")
        route["human_score"] = round(max(0.0, min(1.0, score)), 2)
        route["human_notes"] = notes
        return route

    def suggest_rest_stops(self, polyline, rest_interval_km):
        if not polyline or len(polyline) < 2: return []
        stops, accumulated = [], 0.0
        for i in range(1, len(polyline)):
            prev, curr = polyline[i-1], polyline[i]
            accumulated += haversine_distance(prev[1], prev[0], curr[1], curr[0])
            if accumulated >= rest_interval_km:
                stops.append({"lat": curr[1], "lon": curr[0],
                    "km_from_start": round(accumulated, 1), "suggestion": "Dừng nghỉ đề xuất"})
                accumulated = 0
        return stops

    def _classify_user(self, age, travel_hour, has_motion_sickness, stress_level, has_children):
        if age >= 60: return "elderly"
        if travel_hour >= 22 or travel_hour <= 4: return "night_driver"
        if has_motion_sickness: return "motion_sick"
        if stress_level >= 4: return "stressed"
        if has_children: return "family"
        return "normal"

    def _generate_alerts(self, profile_type, age, travel_hour, stress_level):
        alerts = []
        if profile_type == "night_driver": alerts.append("🌙 Lái xe ban đêm: hệ thống sẽ tránh đèo, đường tối")
        if profile_type == "elderly":      alerts.append(f"👴 Người cao tuổi ({age} tuổi): ưu tiên đường bằng phẳng")
        if profile_type == "motion_sick":  alerts.append("🤢 Tránh đèo và đường quanh co")
        if profile_type == "stressed":     alerts.append("😰 Chế độ bình tâm: ưu tiên đường cảnh đẹp, ít xe")
        if stress_level >= 4:              alerts.append("💡 Gợi ý: nghe nhạc thư giãn trong hành trình")
        return alerts

    def _profile_summary(self, t):
        return {"elderly": "Người cao tuổi", "night_driver": "Lái xe ban đêm",
                "motion_sick": "Dễ say xe", "stressed": "Đang căng thẳng",
                "family": "Gia đình có trẻ nhỏ", "normal": "Bình thường"}.get(t, "Bình thường")

    def _tag_label(self, tag):
        return {"mountain_pass": "đèo núi", "sharp_curve": "cua gắt", "dark_road": "đường tối",
                "heavy_traffic": "kẹt xe", "rest_stop": "trạm nghỉ", "scenic": "cảnh đẹp",
                "hospital_nearby": "bệnh viện gần"}.get(tag, tag)

