# api/weather_api.py
# Kết nối OpenWeatherMap — lấy thời tiết thực tế và dự báo.
# Có fallback Open-Meteo để app không bị crash nếu thiếu API key.

import os
import requests
from typing import Dict, Optional, List
from utils.config import OPENWEATHER_API_KEY
from utils.logger import setup_logger

logger = setup_logger(__name__)


class WeatherAPI:
    """Lấy thông tin thời tiết hiện tại và dự báo 5 ngày."""

    BASE_URL      = "https://api.openweathermap.org/data/2.5"
    CURRENT_URL   = f"{BASE_URL}/weather"
    FORECAST_URL  = f"{BASE_URL}/forecast"
    OPENMETEO_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = (api_key or OPENWEATHER_API_KEY or os.getenv("OPENWEATHER_API_KEY", "")).strip()
        self.has_api_key = bool(self.api_key and not self.api_key.startswith("YOUR_"))
        logger.info(f"WeatherAPI khởi động · OpenWeather={'ON' if self.has_api_key else 'OFF, dùng fallback'}")

    # ----------------------------------------------------------
    # PUBLIC
    # ----------------------------------------------------------
    def get_current(self, lat: float, lon: float) -> Optional[Dict]:
        """Thời tiết hiện tại tại tọa độ."""
        if self.has_api_key:
            try:
                r = requests.get(
                    self.CURRENT_URL,
                    params={
                        "lat": lat,
                        "lon": lon,
                        "appid": self.api_key,
                        "units": "metric",
                        "lang": "vi",
                    },
                    timeout=8,
                )
                r.raise_for_status()
                return self._parse_current_openweather(r.json())
            except Exception as e:
                logger.warning(f"OpenWeather current lỗi, chuyển sang Open-Meteo: {e}")

        return self._get_current_open_meteo(lat, lon)

    def get_forecast(self, lat: float, lon: float, days: int = 3) -> List[Dict]:
        """Dự báo thời tiết. OpenWeather trả mỗi 3 giờ; Open-Meteo trả mỗi giờ."""
        days = max(1, min(int(days or 1), 5))

        if self.has_api_key:
            try:
                r = requests.get(
                    self.FORECAST_URL,
                    params={
                        "lat": lat,
                        "lon": lon,
                        "appid": self.api_key,
                        "units": "metric",
                        "lang": "vi",
                        "cnt": days * 8,
                    },
                    timeout=8,
                )
                r.raise_for_status()
                return self._parse_forecast_openweather(r.json())
            except Exception as e:
                logger.warning(f"OpenWeather forecast lỗi, chuyển sang Open-Meteo: {e}")

        return self._get_forecast_open_meteo(lat, lon, days)

    def get_rain_24h_forecast(self, lat: float, lon: float) -> float:
        """Tổng mưa dự báo 24h tới, đơn vị mm."""
        forecast = self.get_forecast(lat, lon, days=2)
        if not forecast:
            return 0.0

        total = 0.0
        used_hours = 0
        for item in forecast:
            hours = int(item.get("period_hours", 3) or 3)
            total += float(item.get("rain_mm", 0) or 0)
            used_hours += hours
            if used_hours >= 24:
                break
        return round(total, 2)

    def get_weather_risk(self, lat: float, lon: float) -> Dict:
        """Đánh giá rủi ro thời tiết cho việc di chuyển."""
        weather = self.get_current(lat, lon)
        if not weather:
            return {"risk_score": 0.1, "alerts": [], "weather": {}}

        alerts = []
        risk = 0.1
        condition = str(weather.get("condition_main", "")).lower()
        desc = str(weather.get("description", "")).lower()
        rain_mm = float(weather.get("rain_mm", 0) or 0)
        visibility_m = weather.get("visibility_m")

        if "thunderstorm" in condition or "dông" in desc:
            risk = 0.9
            alerts.append("⛈️ Dông bão — hạn chế di chuyển")
        elif "rain" in condition or "mưa" in desc or rain_mm > 0:
            if rain_mm >= 30:
                risk = 0.75
                alerts.append("🌧️ Mưa lớn — nguy cơ ngập, trơn trượt")
            elif rain_mm >= 10:
                risk = 0.60
                alerts.append("🌧️ Mưa vừa — giảm tốc độ")
            else:
                risk = 0.40
                alerts.append("🌦️ Có mưa — lái xe thận trọng")

        if condition in ("fog", "mist", "haze") or "sương" in desc:
            risk = max(risk, 0.55)
            alerts.append("🌫️ Sương mù — giảm tầm nhìn, bật đèn")

        if visibility_m is not None and visibility_m < 2000:
            risk = max(risk, 0.55)
            alerts.append(f"🌫️ Tầm nhìn thấp khoảng {visibility_m:.0f} m")

        wind = float(weather.get("wind_speed_ms", 0) or 0)
        if wind > 15:
            risk = max(risk, 0.60)
            alerts.append(f"💨 Gió mạnh {wind:.0f} m/s")

        return {"risk_score": round(risk, 2), "alerts": alerts, "weather": weather}

    # ----------------------------------------------------------
    # PARSE OPENWEATHER
    # ----------------------------------------------------------
    def _parse_current_openweather(self, data: Dict) -> Dict:
        main = data.get("main", {})
        weather = data.get("weather", [{}])[0]
        wind = data.get("wind", {})
        rain = data.get("rain", {}) or {}
        clouds = data.get("clouds", {}) or {}

        return {
            "temp_c": main.get("temp"),
            "feels_like_c": main.get("feels_like"),
            "humidity_pct": main.get("humidity"),
            "pressure_hpa": main.get("pressure"),
            "description": weather.get("description", ""),
            "condition_main": weather.get("main", ""),
            "icon": weather.get("icon", ""),
            "wind_speed_ms": wind.get("speed", 0),
            "wind_deg": wind.get("deg"),
            "cloud_pct": clouds.get("all", 0),
            "visibility_m": data.get("visibility"),
            "rain_mm": rain.get("1h", rain.get("3h", 0)) or 0,
            "rain_1h_mm": rain.get("1h", 0) or 0,
            "rain_3h_mm": rain.get("3h", 0) or 0,
            "city": data.get("name", ""),
            "source": "openweather",
        }

    def _parse_forecast_openweather(self, data: Dict) -> List[Dict]:
        result = []
        for item in data.get("list", []):
            main = item.get("main", {})
            weather = item.get("weather", [{}])[0]
            rain = item.get("rain", {}) or {}
            clouds = item.get("clouds", {}) or {}
            result.append({
                "datetime": item.get("dt_txt", ""),
                "temp_c": main.get("temp"),
                "humidity_pct": main.get("humidity"),
                "description": weather.get("description", ""),
                "condition_main": weather.get("main", ""),
                "rain_mm": rain.get("3h", 0) or 0,
                "cloud_pct": clouds.get("all", 0),
                "period_hours": 3,
                "source": "openweather",
            })
        return result

    # ----------------------------------------------------------
    # FALLBACK OPEN-METEO
    # ----------------------------------------------------------
    def _get_current_open_meteo(self, lat: float, lon: float) -> Dict:
        try:
            r = requests.get(
                self.OPENMETEO_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,cloud_cover",
                    "timezone": "auto",
                    "forecast_days": 1,
                },
                timeout=8,
            )
            r.raise_for_status()
            cur = r.json().get("current", {})
            desc, cond = self._map_weather_code(cur.get("weather_code"))
            return {
                "temp_c": cur.get("temperature_2m"),
                "feels_like_c": cur.get("apparent_temperature"),
                "humidity_pct": cur.get("relative_humidity_2m"),
                "pressure_hpa": None,
                "description": desc,
                "condition_main": cond,
                "icon": "",
                "wind_speed_ms": cur.get("wind_speed_10m", 0),
                "cloud_pct": cur.get("cloud_cover", 0),
                "visibility_m": None,
                "rain_mm": cur.get("precipitation", 0) or 0,
                "rain_1h_mm": cur.get("precipitation", 0) or 0,
                "rain_3h_mm": 0,
                "city": "",
                "source": "open-meteo",
            }
        except Exception as e:
            logger.error(f"Open-Meteo current lỗi: {e}")
            return self._fallback_weather()

    def _get_forecast_open_meteo(self, lat: float, lon: float, days: int) -> List[Dict]:
        try:
            r = requests.get(
                self.OPENMETEO_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "hourly": "temperature_2m,relative_humidity_2m,precipitation,weather_code,cloud_cover",
                    "timezone": "auto",
                    "forecast_days": max(days, 1),
                },
                timeout=8,
            )
            r.raise_for_status()
            hourly = r.json().get("hourly", {})
            result = []
            for dt, temp, hum, rain, code, cloud in zip(
                hourly.get("time", []),
                hourly.get("temperature_2m", []),
                hourly.get("relative_humidity_2m", []),
                hourly.get("precipitation", []),
                hourly.get("weather_code", []),
                hourly.get("cloud_cover", []),
            ):
                desc, cond = self._map_weather_code(code)
                result.append({
                    "datetime": dt,
                    "temp_c": temp,
                    "humidity_pct": hum,
                    "description": desc,
                    "condition_main": cond,
                    "rain_mm": rain or 0,
                    "cloud_pct": cloud or 0,
                    "period_hours": 1,
                    "source": "open-meteo",
                })
            return result
        except Exception as e:
            logger.error(f"Open-Meteo forecast lỗi: {e}")
            return []

    def _map_weather_code(self, code) -> tuple:
        mapping = {
            0: ("Trời quang", "clear"),
            1: ("Khá quang", "clear"),
            2: ("Có mây", "clouds"),
            3: ("Nhiều mây", "clouds"),
            45: ("Sương mù", "fog"),
            48: ("Sương mù đóng băng", "fog"),
            51: ("Mưa phùn nhẹ", "rain"),
            53: ("Mưa phùn", "rain"),
            55: ("Mưa phùn dày", "rain"),
            61: ("Mưa nhẹ", "rain"),
            63: ("Mưa vừa", "rain"),
            65: ("Mưa to", "rain"),
            80: ("Mưa rào nhẹ", "rain"),
            81: ("Mưa rào", "rain"),
            82: ("Mưa rào lớn", "rain"),
            95: ("Dông bão", "thunderstorm"),
            96: ("Dông kèm mưa đá", "thunderstorm"),
            99: ("Dông mạnh", "thunderstorm"),
        }
        return mapping.get(code, ("Không lấy được dữ liệu", "unknown"))

    def _fallback_weather(self) -> Dict:
        return {
            "temp_c": None,
            "feels_like_c": None,
            "humidity_pct": None,
            "description": "Không lấy được dữ liệu",
            "condition_main": "unknown",
            "wind_speed_ms": 0,
            "cloud_pct": 0,
            "visibility_m": None,
            "rain_mm": 0,
            "city": "",
            "source": "fallback",
        }
