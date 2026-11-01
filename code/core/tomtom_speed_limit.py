import os
import requests

try:
    import streamlit as st
except Exception:
    st = None


def get_tomtom_key():
    """Ưu tiên Streamlit Secrets, sau đó mới đến biến môi trường."""
    if st is not None:
        try:
            key = st.secrets.get("TOMTOM_API_KEY", "")
            if key:
                return key
        except Exception:
            pass
    return os.getenv("TOMTOM_API_KEY", "")


def get_speed_limit_from_tomtom(lat, lon, heading=None, vehicle_type="PassengerCar"):
    """
    Lấy tốc độ tối đa hợp pháp tại GPS hiện tại bằng TomTom Snap to Roads.

    Lưu ý:
    - TomTom dùng tọa độ dạng longitude,latitude.
    - Kết quả có thể None nếu điểm không match được đường hoặc TomTom không có dữ liệu speed limit.
    """
    api_key = get_tomtom_key()
    if not api_key:
        return {
            "ok": False,
            "speed_limit": None,
            "message": "Thiếu TOMTOM_API_KEY",
            "raw": None,
        }

    url = "https://api.tomtom.com/snapToRoads/1"

    fields = "{projectedPoints{type,geometry{type,coordinates},properties{routeIndex,snapResult}},route{type,geometry{type,coordinates},properties{id,speedLimits{value,unit,type}}}}"

    params = {
        "key": api_key,
        "points": f"{float(lon)},{float(lat)}",
        "fields": fields,
        "vehicleType": vehicle_type,
        "measurementSystem": "metric",
    }

    if heading is not None:
        params["headings"] = str(float(heading))

    try:
        res = requests.get(url, params=params, timeout=8)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        return {
            "ok": False,
            "speed_limit": None,
            "message": f"Lỗi gọi TomTom: {e}",
            "raw": None,
        }

    # Kiểm tra điểm có match vào đường không
    projected = data.get("projectedPoints") or []
    if projected:
        snap_result = (
            projected[0]
            .get("properties", {})
            .get("snapResult")
        )
        if snap_result and snap_result != "Matched":
            return {
                "ok": False,
                "speed_limit": None,
                "message": f"GPS chưa khớp đường: {snap_result}",
                "raw": data,
            }

    # Lấy speed limit từ route road elements
    route = data.get("route") or []
    for element in route:
        props = element.get("properties", {}) or {}
        speed_limits = props.get("speedLimits")

        if isinstance(speed_limits, dict):
            speed_limits = [speed_limits]

        for item in speed_limits or []:
            if str(item.get("type", "")).lower() == "maximum":
                return {
                    "ok": True,
                    "speed_limit": item.get("value"),
                    "unit": item.get("unit", "km/h"),
                    "type": item.get("type"),
                    "message": "OK",
                    "raw": data,
                }

        # fallback nếu TomTom trả speed limit nhưng không ghi type Maximum
        if speed_limits:
            item = speed_limits[0]
            return {
                "ok": True,
                "speed_limit": item.get("value"),
                "unit": item.get("unit", "km/h"),
                "type": item.get("type"),
                "message": "OK",
                "raw": data,
            }

    return {
        "ok": False,
        "speed_limit": None,
        "message": "TomTom không có dữ liệu tốc độ tối đa tại điểm này",
        "raw": data,
    }