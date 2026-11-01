# ui/map_view.py
# Giao diện bản đồ — render bản đồ Folium tương tác

import folium
import webbrowser
import os
from typing import List, Dict, Optional, Tuple
from utils.config import DEFAULT_MAP_CENTER, DEFAULT_ZOOM
from utils.logger import setup_logger

logger = setup_logger(__name__)

OUTPUT_MAP = "output_map.html"


class MapView:
    """
    Tạo và hiển thị bản đồ tương tác bằng Folium.
    Hiển thị: tuyến đường, vùng nguy hiểm, POI, điểm SOS, báo cáo cộng đồng.
    """

    COLORS = {
        "safe":     "green",
        "moderate": "orange",
        "danger":   "red",
        "sos":      "darkred",
        "poi":      "blue",
        "safe_zone": "purple",
    }

    def __init__(self):
        self.map = folium.Map(
            location=DEFAULT_MAP_CENTER,
            zoom_start=DEFAULT_ZOOM,
            tiles="OpenStreetMap",
        )
        logger.info("MapView khởi động")

    def render_route(
        self,
        polyline: List[List[float]],
        risk_score: float = 0.0,
        label: str = "Tuyến đường",
    ) -> None:
        """Vẽ tuyến đường lên bản đồ với màu sắc theo mức độ rủi ro."""
        if not polyline:
            return

        color = (
            self.COLORS["danger"]   if risk_score >= 0.7
            else self.COLORS["moderate"] if risk_score >= 0.4
            else self.COLORS["safe"]
        )

        # Folium dùng [lat, lon], ORS trả về [lon, lat]
        coords = [[p[1], p[0]] for p in polyline]

        folium.PolyLine(
            locations=coords,
            color=color,
            weight=5,
            opacity=0.8,
            tooltip=f"{label} — Rủi ro: {risk_score:.0%}",
        ).add_to(self.map)

    def add_marker(
        self,
        lat: float,
        lon: float,
        title: str,
        description: str = "",
        marker_type: str = "safe",
        icon_name: str = "info-sign",
    ) -> None:
        """Thêm marker lên bản đồ."""
        color = self.COLORS.get(marker_type, "blue")
        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(f"<b>{title}</b><br>{description}", max_width=300),
            tooltip=title,
            icon=folium.Icon(color=color, icon=icon_name, prefix="glyphicon"),
        ).add_to(self.map)

    def add_danger_circle(
        self,
        lat: float,
        lon: float,
        radius_m: float,
        label: str,
        risk_score: float,
    ) -> None:
        """Vẽ vùng nguy hiểm dạng hình tròn."""
        color = (
            self.COLORS["danger"]   if risk_score >= 0.7
            else self.COLORS["moderate"]
        )
        folium.Circle(
            location=[lat, lon],
            radius=radius_m,
            color=color,
            fill=True,
            fill_opacity=0.25,
            tooltip=f"⚠️ {label}",
        ).add_to(self.map)

    def add_crowdsource_reports(self, reports: List[Dict]) -> None:
        """Hiển thị báo cáo cộng đồng."""
        for r in reports:
            icon_map = {
                "accident":     ("red", "exclamation-sign"),
                "flood":        ("blue", "tint"),
                "traffic_jam":  ("orange", "road"),
                "bad_road":     ("orange", "warning-sign"),
                "landslide":    ("darkred", "ban-circle"),
            }
            color, icon = icon_map.get(r["type"], ("gray", "question-sign"))
            self.add_marker(
                r["lat"], r["lon"],
                title=f"{r['icon']} {r['label']}",
                description=f"{r.get('description','')} · {r.get('upvotes',0)} xác nhận",
                marker_type="moderate",
                icon_name=icon,
            )

    def add_poi_markers(self, pois: List[Dict]) -> None:
        """Hiển thị các điểm tham quan."""
        for poi in pois:
            self.add_marker(
                poi["lat"], poi["lon"],
                title=poi["name"],
                description=f"⭐ {poi.get('rating','N/A')} · Đường vòng: {poi.get('detour_km','?')}km",
                marker_type="poi",
                icon_name="star",
            )

    def add_safe_zones(self, zones: List[Dict]) -> None:
        """Hiển thị vùng an toàn khi thiên tai."""
        for z in zones:
            self.add_marker(
                z["lat"], z["lon"],
                title=f"🏠 {z['name']}",
                description=f"Sức chứa: {z.get('capacity','?')} người",
                marker_type="safe_zone",
                icon_name="home",
            )

    def center_map(self, lat: float, lon: float, zoom: int = 12) -> None:
        """Đặt vị trí trung tâm bản đồ."""
        self.map.location = [lat, lon]
        self.map.zoom_start = zoom

    def save_and_open(self, filepath: str = OUTPUT_MAP) -> str:
        """Lưu và mở bản đồ trong trình duyệt."""
        self.map.save(filepath)
        abs_path = os.path.abspath(filepath)
        webbrowser.open(f"file://{abs_path}")
        logger.info(f"Bản đồ đã lưu: {abs_path}")
        return abs_path

    def reset(self) -> None:
        """Tạo lại bản đồ trắng."""
        self.map = folium.Map(
            location=DEFAULT_MAP_CENTER,
            zoom_start=DEFAULT_ZOOM,
            tiles="OpenStreetMap",
        )
