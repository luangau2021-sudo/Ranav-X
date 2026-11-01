# features/landslide_realtime.py
# Ước tính nguy cơ sạt lở gần thời gian thực cho TripSmart Pro.
# Nguồn động: OpenWeather Current Weather + 5 day / 3 hour Forecast.
# Lưu ý: đây là ước tính rủi ro, không phải cảnh báo chính thức của cơ quan nhà nước.

import os
import time
import math
import requests
from typing import Dict, List, Optional, Tuple

try:
    from utils.helpers import haversine_distance
except Exception:
    def haversine_distance(lat1, lon1, lat2, lon2):
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2
             + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
             * math.sin(dlon / 2) ** 2)
        return R * 2 * math.asin(math.sqrt(max(0, a)))


class LandslideRealtimeEngine:
    """
    Tính nguy cơ sạt lở động theo tuyến đường.

    Dữ liệu dùng:
    - OpenWeather Current Weather: mưa hiện tại, độ ẩm, tầm nhìn, điều kiện thời tiết.
    - OpenWeather 5 day / 3 hour Forecast: tổng mưa dự báo 24h tới.
    - Heuristic địa hình Việt Nam: nhận diện tương đối vùng núi/đèo theo tọa độ.

    API key:
    - Đặt biến môi trường OPENWEATHER_API_KEY
    - Hoặc truyền api_key khi khởi tạo.
    """

    CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
    FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"

    def __init__(self, api_key: Optional[str] = None, ttl_seconds: int = 20 * 60):
        self.api_key = api_key or os.getenv("OPENWEATHER_API_KEY", "").strip()
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[Tuple[float, float], Tuple[float, Dict]] = {}

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    # ------------------------------------------------------------------
    # PUBLIC
    # ------------------------------------------------------------------
    def analyze_route(
        self,
        polyline: List[List[float]],
        min_score: float = 0.55,
        max_api_points: int = 18,
    ) -> Dict:
        """
        Phân tích nguy cơ sạt lở trên tuyến.
        polyline format: [[lon, lat], ...]
        """
        if not self.enabled:
            return {
                "enabled": False,
                "danger_segments": [],
                "message": "Chưa có OPENWEATHER_API_KEY nên chưa bật sạt lở realtime.",
            }

        if not polyline or len(polyline) < 2:
            return {"enabled": True, "danger_segments": [], "message": "Không có polyline để phân tích."}

        sampled = self._sample_route(polyline, max_api_points=max_api_points)
        danger_segments = []
        checked = 0

        for item in sampled:
            lat = item["lat"]
            lon = item["lon"]
            route_km = item["route_km"]
            checked += 1

            result = self.analyze_point(lat, lon, route_km=route_km)
            if result.get("score", 0) >= min_score:
                score = result["score"]
                danger_segments.append({
                    "lat": lat,
                    "lon": lon,
                    "route_km": route_km,
                    "score": score,
                    "type": "landslide_realtime",
                    "label": result.get("label", "Nguy cơ sạt lở"),
                    "desc": result.get("reason", "Mưa lớn + địa hình dốc"),
                    "icon": "⛰️",
                    "color": "#b71c1c" if score >= 0.75 else "#fb8c00",
                    "source": "openweather_estimate",
                    "weather": result.get("weather", {}),
                })

        return {
            "enabled": True,
            "checked_points": checked,
            "danger_segments": danger_segments,
            "message": f"Đã kiểm tra sạt lở realtime tại {checked} điểm theo tuyến.",
        }

    def analyze_point(self, lat: float, lon: float, route_km: float = 0.0) -> Dict:
        """Tính nguy cơ sạt lở tại một điểm."""
        weather = self._get_weather_bundle(lat, lon)
        if weather.get("error"):
            return {
                "score": 0.0,
                "level": "unknown",
                "label": "Không có dữ liệu sạt lở realtime",
                "reason": weather.get("error", "Không lấy được dữ liệu thời tiết"),
                "weather": weather,
            }

        terrain_score = self._terrain_landslide_score(lat, lon)
        rain_now_score = self._score_rain_now(weather.get("rain_now_mm", 0.0))
        rain_24h_score = self._score_rain_24h(weather.get("rain_24h_forecast_mm", 0.0))
        humidity_score = self._score_humidity(weather.get("humidity", 0))
        condition_score = self._score_condition(weather.get("condition", ""), weather.get("description", ""))

        # Trọng số ưu tiên địa hình và mưa tích lũy.
        score = (
            terrain_score * 0.32 +
            rain_24h_score * 0.30 +
            rain_now_score * 0.18 +
            humidity_score * 0.10 +
            condition_score * 0.10
        )

        # Nếu địa hình rất thấp thì không đẩy điểm quá cao chỉ vì mưa.
        if terrain_score < 0.25:
            score = min(score, 0.54)

        score = round(max(0.0, min(1.0, score)), 2)
        level, label = self._level_label(score)
        reason = self._build_reason(score, terrain_score, weather)

        return {
            "score": score,
            "level": level,
            "label": label,
            "reason": reason,
            "weather": weather,
            "route_km": route_km,
        }

    # ------------------------------------------------------------------
    # WEATHER
    # ------------------------------------------------------------------
    def _get_weather_bundle(self, lat: float, lon: float) -> Dict:
        key = (round(lat, 2), round(lon, 2))
        now = time.time()
        cached = self._cache.get(key)
        if cached and now - cached[0] <= self.ttl_seconds:
            return cached[1]

        try:
            current = self._request_json(self.CURRENT_URL, {
                "lat": lat,
                "lon": lon,
                "appid": self.api_key,
                "units": "metric",
                "lang": "vi",
            })
            forecast = self._request_json(self.FORECAST_URL, {
                "lat": lat,
                "lon": lon,
                "appid": self.api_key,
                "units": "metric",
                "lang": "vi",
            })

            w0 = (current.get("weather") or [{}])[0]
            rain = current.get("rain") or {}
            rain_now = float(rain.get("1h", 0.0) or 0.0)
            # Nếu chỉ có rain.3h thì quy đổi trung bình mỗi giờ.
            if rain_now <= 0 and rain.get("3h") is not None:
                rain_now = float(rain.get("3h", 0.0) or 0.0) / 3.0

            rain_24h = 0.0
            for item in (forecast.get("list") or [])[:8]:  # 8 mốc x 3h = 24h
                rain_24h += float((item.get("rain") or {}).get("3h", 0.0) or 0.0)

            main = current.get("main") or {}
            bundle = {
                "condition": str(w0.get("main", "")),
                "description": str(w0.get("description", "")),
                "rain_now_mm": round(rain_now, 2),
                "rain_24h_forecast_mm": round(rain_24h, 2),
                "humidity": int(main.get("humidity", 0) or 0),
                "visibility_m": int(current.get("visibility", 10000) or 10000),
                "wind_speed_ms": float((current.get("wind") or {}).get("speed", 0.0) or 0.0),
                "temp_c": float(main.get("temp", 0.0) or 0.0),
            }
            self._cache[key] = (now, bundle)
            return bundle
        except Exception as e:
            return {"error": f"OpenWeather lỗi: {e}"}

    def _request_json(self, url: str, params: Dict) -> Dict:
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        data = r.json()
        if str(data.get("cod", "200")) not in ("200", "OK"):
            raise RuntimeError(data.get("message", "API trả lỗi"))
        return data

    # ------------------------------------------------------------------
    # SCORING
    # ------------------------------------------------------------------
    def _terrain_landslide_score(self, lat: float, lon: float) -> float:
        """
        Ước tính rủi ro nền theo vùng địa hình Việt Nam.
        Muốn chính xác hơn nữa cần thay hàm này bằng DEM/slope raster.
        """
        # Tây Bắc / Đông Bắc núi cao
        if 20.0 <= lat <= 23.6 and 102.0 <= lon <= 106.8:
            return 0.95
        # Bắc Trung Bộ và dãy Trường Sơn
        if 16.0 <= lat <= 20.0 and 104.5 <= lon <= 108.5:
            return 0.85
        # Nam Trung Bộ: đèo, taluy, ven núi
        if 11.0 <= lat <= 16.0 and 107.0 <= lon <= 109.5:
            return 0.80
        # Tây Nguyên / Lâm Đồng / Bình Phước phía bắc
        if 10.5 <= lat <= 15.0 and 106.5 <= lon <= 108.8:
            return 0.75
        # Ven đồng bằng có đồi thấp
        if 10.0 <= lat <= 21.5 and 105.5 <= lon <= 109.5:
            return 0.35
        # Đồng bằng thấp
        return 0.15

    def _score_rain_now(self, mm_h: float) -> float:
        if mm_h >= 30: return 1.0
        if mm_h >= 15: return 0.85
        if mm_h >= 7:  return 0.65
        if mm_h >= 2:  return 0.40
        if mm_h > 0:   return 0.20
        return 0.0

    def _score_rain_24h(self, mm: float) -> float:
        if mm >= 120: return 1.0
        if mm >= 80:  return 0.85
        if mm >= 50:  return 0.70
        if mm >= 25:  return 0.45
        if mm >= 10:  return 0.25
        return 0.0

    def _score_humidity(self, humidity: int) -> float:
        if humidity >= 95: return 0.8
        if humidity >= 90: return 0.6
        if humidity >= 80: return 0.35
        return 0.1

    def _score_condition(self, condition: str, description: str) -> float:
        text = f"{condition} {description}".lower()
        if "thunderstorm" in text or "dông" in text:
            return 1.0
        if "heavy" in text or "mưa lớn" in text or "rain" in text or "mưa" in text:
            return 0.65
        if "drizzle" in text or "mưa phùn" in text:
            return 0.25
        return 0.0

    def _level_label(self, score: float) -> Tuple[str, str]:
        if score >= 0.75:
            return "high", "Nguy cơ sạt lở cao"
        if score >= 0.55:
            return "medium", "Cần chú ý sạt lở"
        if score >= 0.35:
            return "low", "Rủi ro sạt lở nhẹ"
        return "safe", "Nguy cơ sạt lở thấp"

    def _build_reason(self, score: float, terrain_score: float, weather: Dict) -> str:
        parts = []
        if terrain_score >= 0.75:
            parts.append("địa hình đèo/núi có nền rủi ro cao")
        elif terrain_score >= 0.35:
            parts.append("khu vực có đồi núi hoặc taluy")
        else:
            parts.append("địa hình nền thấp")

        rain24 = weather.get("rain_24h_forecast_mm", 0)
        rain_now = weather.get("rain_now_mm", 0)
        if rain24 >= 50:
            parts.append(f"mưa dự báo 24h khoảng {rain24} mm")
        elif rain24 >= 10:
            parts.append(f"có mưa dự báo 24h khoảng {rain24} mm")

        if rain_now >= 7:
            parts.append(f"mưa hiện tại mạnh khoảng {rain_now} mm/h")
        elif rain_now > 0:
            parts.append(f"đang có mưa khoảng {rain_now} mm/h")

        if weather.get("humidity", 0) >= 90:
            parts.append(f"độ ẩm cao {weather.get('humidity')}%")

        desc = weather.get("description", "")
        if desc:
            parts.append(f"thời tiết: {desc}")

        return "Ước tính theo OpenWeather: " + "; ".join(parts) + "."

    # ------------------------------------------------------------------
    # ROUTE SAMPLING
    # ------------------------------------------------------------------
    def _sample_route(self, polyline: List[List[float]], max_api_points: int = 18) -> List[Dict]:
        """Lấy mẫu điểm theo tuyến, tránh gọi API quá nhiều."""
        cumulative = [0.0]
        total = 0.0
        for i in range(1, len(polyline)):
            lon1, lat1 = polyline[i - 1]
            lon2, lat2 = polyline[i]
            total += haversine_distance(lat1, lon1, lat2, lon2)
            cumulative.append(total)

        if total <= 0:
            lon, lat = polyline[0]
            return [{"lat": lat, "lon": lon, "route_km": 0.0}]

        # Tuyến dài thì lấy thưa hơn.
        if total < 100:
            interval = 8.0
        elif total < 500:
            interval = 15.0
        else:
            interval = 25.0

        targets = []
        km = interval
        while km < total and len(targets) < max_api_points:
            targets.append(km)
            km += interval

        # Luôn thêm gần đầu/cuối nếu tuyến đủ dài.
        if total >= 30:
            targets = [min(10.0, total * 0.15)] + targets + [max(total - 10.0, total * 0.85)]

        targets = sorted(set(round(t, 1) for t in targets if 0 <= t <= total))[:max_api_points]
        samples = []
        idx = 0
        for target in targets:
            while idx < len(cumulative) - 1 and cumulative[idx] < target:
                idx += 1
            lon, lat = polyline[idx]
            samples.append({"lat": lat, "lon": lon, "route_km": round(cumulative[idx], 1)})
        return samples
