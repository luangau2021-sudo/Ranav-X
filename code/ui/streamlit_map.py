# ui/streamlit_map.py
# Render bản đồ Folium dùng trong Streamlit.

import json
import html as _html
import folium

from core.route_calc import (
    RED_RISK_THRESHOLD, ORANGE_RISK_THRESHOLD, YELLOW_RISK_THRESHOLD,
    _risk_level_icon, _risk_score_float,
)

def _cluster_danger_markers(markers, max_gap_km=2.0, min_score=0.45, max_items=8):
    """
    Gom nhiều điểm nguy hiểm gần nhau thành vài đoạn trọng yếu để tránh spam UI.
    Không làm mất dữ liệu gốc; chỉ dùng cho hiển thị tab/metric/map marker.
    """
    if not markers:
        return []

    def _km(x):
        try:
            return float(x.get("route_km", 0) or 0)
        except Exception:
            return 0.0

    def _score(x):
        try:
            return float(x.get("score", 0) or 0)
        except Exception:
            return 0.0

    # Chỉ giữ các điểm có rủi ro đáng chú ý. Nếu tất cả thấp hơn ngưỡng,
    # lấy tối đa vài điểm cao nhất để người dùng vẫn có thông tin tham khảo.
    significant = [m for m in markers if _score(m) >= min_score]
    if not significant:
        return sorted(markers, key=_score, reverse=True)[:min(3, max_items)]

    # Gom theo loại/nhãn để không nhập chung lũ lụt với sạt lở nếu gần nhau.
    buckets = {}
    for m in significant:
        key = (m.get("type", "risk"), m.get("label", "Vùng rủi ro"))
        buckets.setdefault(key, []).append(m)

    clusters = []
    for _, items in buckets.items():
        items = sorted(items, key=_km)
        current = [items[0]]
        for m in items[1:]:
            if _km(m) - _km(current[-1]) <= max_gap_km:
                current.append(m)
            else:
                clusters.append(current)
                current = [m]
        clusters.append(current)

    summarized = []
    for cluster in clusters:
        cluster = sorted(cluster, key=_km)
        start_km = _km(cluster[0])
        end_km = _km(cluster[-1])
        best = max(cluster, key=_score)
        max_score = _score(best)
        avg_score = sum(_score(x) for x in cluster) / max(1, len(cluster))
        length_km = max(0.0, end_km - start_km)

        # Bỏ các cụm quá nhẹ và quá ngắn để tập trung vào điểm trọng yếu.
        if max_score < min_score and length_km < 1.0:
            continue

        if end_km - start_km >= 1:
            km_text = f"km {start_km:.0f}–{end_km:.0f}"
        else:
            km_text = f"km {start_km:.0f}"

        desc = best.get("desc", "")
        if len(cluster) > 1:
            desc = f"{desc} · Gom {len(cluster)} điểm gần nhau trong đoạn {km_text}."

        item = dict(best)
        item.update({
            "score": max_score,
            "avg_score": avg_score,
            "route_km": start_km,
            "km_start": start_km,
            "km_end": end_km,
            "km_text": km_text,
            "cluster_count": len(cluster),
            "cluster_length_km": round(length_km, 1),
            "desc": desc,
            "priority": max_score * 100 + length_km * 3 + len(cluster) * 0.5,
        })
        summarized.append(item)

    summarized.sort(key=lambda x: x.get("priority", 0), reverse=True)
    return summarized[:max_items]


def make_full_map(lat1, lon1, lat2, lon2,
                  colored_segments=None,
                  route_polyline=None,
                  alt_routes=None,
                  danger_markers=None,
                  rest_suggestions=None,
                  pois=None,
                  reports=None,
                  incident_marker=None,
                  forecast_segments=None,
                  gps_position=None,
                  enable_live_gps=False,
                  dest_lat=None,
                  dest_lon=None,
                  avg_speed_kmh=40.0,
                  speed_segments=None):

    mid_lat = (lat1 + lat2) / 2
    mid_lon = (lon1 + lon2) / 2
    m = folium.Map(location=[mid_lat, mid_lon], zoom_start=9,
                   tiles=None, prefer_canvas=True)

    folium.TileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
                     attr="© OpenStreetMap", name="🗺️ Đường phố", max_zoom=19).add_to(m)
    folium.TileLayer("https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
                     attr="© Google", name="🛰️ Vệ tinh", max_zoom=20).add_to(m)

    all_lats = [lat1, lat2]
    all_lons = [lon1, lon2]

    # ── Tuyến thay thế mờ ────────────────────────────────────────────────
    ALT_COLORS = ["#90caf9", "#a5d6a7", "#ef9a9a"]
    if alt_routes:
        for i, rt in enumerate(alt_routes):
            poly = rt.get("polyline", [])
            if not poly or len(poly) < 2: continue
            coords = [[p[1], p[0]] for p in poly]
            all_lats += [p[1] for p in poly]
            all_lons += [p[0] for p in poly]
            folium.PolyLine(coords, color=ALT_COLORS[i % len(ALT_COLORS)],
                weight=4, opacity=0.25,
                tooltip=f"{rt.get('label','Tuyến thay thế')} · {rt.get('distance_text','')} · {rt.get('duration_text','')}",
                smooth_factor=0, line_cap="round", line_join="round",
            ).add_to(m)

    # ── Tuyến chính gốc từ OSRM ───────────────────────────────────────────
    # FIX: Vẽ toàn bộ polyline gốc trước để đường luôn bám đúng mặt đường thật.
    # colored_segments chỉ là lớp phủ rủi ro; không dùng nó làm hình dạng chính
    # vì nếu risk_engine lấy mẫu thưa, đường sẽ nối thẳng và nhìn như đi xuyên rừng.
    if route_polyline:
        try:
            coords = [[p[1], p[0]] for p in route_polyline if len(p) >= 2]
            if len(coords) >= 2:
                all_lats += [p[1] for p in route_polyline if len(p) >= 2]
                all_lons += [p[0] for p in route_polyline if len(p) >= 2]
                folium.PolyLine(
                    coords,
                    color="#263238",
                    weight=8,
                    opacity=0.35,
                    tooltip="Tuyến OSRM gốc — bám đường thật",
                    smooth_factor=0,
                    line_cap="round",
                    line_join="round",
                ).add_to(m)
        except Exception:
            pass

    # ── Gradient polyline chính ───────────────────────────────────────────
    # Lớp này chỉ tô màu rủi ro trên đúng tuyến, không quyết định hình dạng tuyến.
    if colored_segments:
        for seg in colored_segments:
            all_lats += [seg["lat1"], seg["lat2"]]
            all_lons += [seg["lon1"], seg["lon2"]]
            score = seg["score"]
            w = 4 + int(score * 4)
            folium.PolyLine(
                [[seg["lat1"], seg["lon1"]], [seg["lat2"], seg["lon2"]]],
                color=seg["color"], weight=w, opacity=0.92,
                tooltip=f"Rủi ro: {score:.0%} | km {seg['route_km']:.1f}",
                smooth_factor=0, line_cap="round", line_join="round",
            ).add_to(m)

    # ── Marker xuất phát / đến ───────────────────────────────────────────
    folium.Marker([lat1, lon1],
        popup=folium.Popup("<b>🟢 Điểm xuất phát</b>", max_width=160),
        tooltip="Xuất phát",
        icon=folium.Icon(color="green", icon="play", prefix="glyphicon"),
    ).add_to(m)
    folium.Marker([lat2, lon2],
        popup=folium.Popup("<b>🏁 Điểm đến</b>", max_width=160),
        tooltip="Điểm đến",
        icon=folium.Icon(color="red", icon="flag", prefix="glyphicon"),
    ).add_to(m)

    # ── Marker nguy hiểm — TOP 5, vòng tròn nhỏ gọn ─────────────────────
    # FIX: Chỉ hiện 5 điểm nguy hiểm nhất + vòng tròn bán kính cố định nhỏ
    HAZARD_COLOR = {"landslide":"red","flood":"blue","geological":"darkred","bad_road":"orange"}
    HAZARD_ICON2 = {"landslide":"ban-circle","flood":"tint","geological":"warning-sign","bad_road":"road"}
    if danger_markers:
        top5 = sorted(danger_markers, key=lambda x: x.get("score", 0), reverse=True)[:5]
        for seg in top5:
            sc    = seg.get("score", 0)
            htype = seg.get("type", "bad_road")
            fc    = HAZARD_COLOR.get(htype, "red")
            fi    = HAZARD_ICON2.get(htype, "warning-sign")
            km_txt = f"km {seg.get('route_km', 0):.0f}"
            level  = "🔴 Nguy hiểm" if sc >= RED_RISK_THRESHOLD else "🟠 Cảnh báo" if sc >= ORANGE_RISK_THRESHOLD else "🟡 Chú ý"

            # Vòng tròn cố định nhỏ: 400–800m
            folium.Circle([seg["lat"], seg["lon"]], radius=int(400 + sc * 400),
                color=seg.get("color","#e53935"), fill=True,
                fill_opacity=0.15, weight=1.5).add_to(m)

            popup_html = (
                f"<div style='font-family:sans-serif;min-width:210px'>"
                f"<b>{seg.get('icon','⚠️')} {seg.get('label','')}</b><br>"
                f"<span style='background:{seg.get('color','#e53935')};color:white;"
                f"padding:2px 8px;border-radius:4px;font-size:.75rem'>"
                f"{level} · {sc:.0%}</span><br><br>"
                f"<span style='font-size:.83rem'>{seg.get('desc','')}</span><br>"
                f"<span style='color:#888;font-size:.75rem'>📍 {km_txt}</span></div>"
            )
            folium.Marker([seg["lat"], seg["lon"]],
                popup=folium.Popup(popup_html, max_width=260),
                tooltip=f"{seg.get('icon','⚠️')} {seg.get('label','')} ({km_txt})",
                icon=folium.Icon(color=fc, icon=fi, prefix="glyphicon"),
            ).add_to(m)

    # ── Điểm dừng nghỉ ───────────────────────────────────────────────────
    if rest_suggestions:
        for rs in rest_suggestions:
            km_txt = f"km {rs.get('route_km', 0):.0f}"
            folium.Marker([rs["lat"], rs["lon"]],
                popup=folium.Popup(
                    f"<div style='font-family:sans-serif'>"
                    f"<b style='color:#2e7d32'>{rs.get('icon','☕')} {rs.get('name','')}</b><br>"
                    f"<span style='font-size:.83rem'>{rs.get('desc','')}</span><br>"
                    f"<span style='color:#888;font-size:.75rem'>📍 {km_txt}</span></div>",
                    max_width=230),
                tooltip=f"☕ {rs.get('name','')} ({km_txt})",
                icon=folium.Icon(color="green", icon="time", prefix="glyphicon"),
            ).add_to(m)

    # ── POI dọc tuyến ────────────────────────────────────────────────────
    CSTYLE = {
        "fuel":("darkred","tint"),"food":("orange","cutlery"),"nature":("darkgreen","tree-conifer"),
        "scenic":("cadetblue","camera"),"culture":("purple","book"),
        "relaxation":("lightblue","tint"),"ecotourism":("darkgreen","leaf"),
        "attraction":("blue","star"),
    }
    CEMOJI = {"fuel":"⛽","food":"🍜","nature":"🌿","scenic":"📸","culture":"🏛️",
              "relaxation":"🏖️","ecotourism":"🌲","attraction":"⭐"}
    fuel_next = []
    fuel_order = {}
    if pois:
        try:
            fuel_next = sorted(
                [p for p in pois if str(p.get("category", "")).lower() == "fuel"],
                key=lambda x: float(x.get("route_km", 0) or 0),
            )[:2]
            for idx, fp in enumerate(fuel_next, start=1):
                key = fp.get("id") or (round(float(fp.get("lat", 0)), 6), round(float(fp.get("lon", 0)), 6))
                fuel_order[key] = idx
        except Exception:
            fuel_next = []
            fuel_order = {}

        for poi in pois:
            cat = poi.get("category","attraction")
            fc2, fi2 = CSTYLE.get(cat, ("blue","star"))
            emoji = CEMOJI.get(cat,"📍")
            km_txt = f"km {poi.get('route_km',0):.0f}"
            _poi_key = poi.get("id") or (round(float(poi.get("lat", 0)), 6), round(float(poi.get("lon", 0)), 6))
            _fuel_no = fuel_order.get(_poi_key)
            _display_name = f"Cây xăng {_fuel_no}" if _fuel_no else str(poi.get("name", ""))
            _sub_name = str(poi.get("name", ""))
            folium.Marker([poi["lat"], poi["lon"]],
                popup=folium.Popup(
                    f"<div style='font-family:sans-serif;min-width:190px'>"
                    f"<b>{emoji} {_display_name}</b><br>"
                    + (f"<span style='font-size:.82rem;color:#333'>{_html.escape(_sub_name)}</span><br>" if _fuel_no and _sub_name != _display_name else "")
                    + f"<span style='font-size:.8rem;color:#555'>{poi.get('type','')} · ⭐{poi.get('rating','?')} · {poi.get('province','')}</span><br>"
                    f"<span style='color:#888;font-size:.75rem'>📍 {km_txt} · ↔️{poi.get('dist_from_route_km',0)} km</span></div>",
                    max_width=240),
                tooltip=f"{emoji} {_display_name} ({km_txt})",
                icon=folium.Icon(color=fc2, icon=fi2, prefix="glyphicon"),
            ).add_to(m)

            # Nhãn nổi ngay cạnh marker cho 2 cây xăng tiếp theo.
            if _fuel_no:
                label_html = (
                    f"<div style=\"white-space:nowrap;background:#fff;border:2px solid #ff5252;"
                    f"border-radius:999px;padding:4px 9px;font-family:sans-serif;font-size:12px;"
                    f"font-weight:800;color:#d32f2f;box-shadow:0 3px 10px rgba(0,0,0,.22);\">"
                    f"⛽ Cây xăng {_fuel_no}"
                    + (f" · còn {float(poi.get('dist_ahead_km')):.1f} km" if poi.get('dist_ahead_km') is not None else "")
                    + "</div>"
                )
                folium.Marker(
                    [poi["lat"], poi["lon"]],
                    icon=folium.DivIcon(html=label_html, icon_size=(105, 26), icon_anchor=(-10, 12)),
                    z_index_offset=900,
                ).add_to(m)

    # ── Góc nhỏ chỉ hiển thị 2 cây xăng phía trước ───────────────────────────
    # JS cập nhật mỗi 1 giây từ localStorage tripsmart_gps, KHÔNG reload Streamlit.
    # Chỉ hiện: cây xăng 1/2 còn bao nhiêu km. Không hiện ETA/khoảng cách còn lại.
    panel_html = """
    <div id="ts-live-route-panel" style="
        position:absolute; top:12px; left:62px; z-index:9999;
        display:flex; align-items:center; gap:5px; flex-wrap:wrap;
        max-width:calc(100% - 120px);
        font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
        pointer-events:none;
    ">
      <div id="ts-live-fuel-1" title="Cây xăng tiếp theo" style="
          background:rgba(255,255,255,.95);
          border:1px solid rgba(239,68,68,.35);
          border-radius:999px;
          padding:4px 7px;
          font-size:11px;
          font-weight:900;
          color:#dc2626;
          line-height:1;
          box-shadow:0 3px 10px rgba(0,0,0,.18);
          white-space:nowrap;
      ">⛽ -- km</div>

      <div id="ts-live-fuel-2" title="Cây xăng kế tiếp" style="
          background:rgba(255,255,255,.95);
          border:1px solid rgba(239,68,68,.35);
          border-radius:999px;
          padding:4px 7px;
          font-size:11px;
          font-weight:900;
          color:#dc2626;
          line-height:1;
          box-shadow:0 3px 10px rgba(0,0,0,.18);
          white-space:nowrap;
      ">⛽ -- km</div>

      <div id="ts-live-speed-limit" title="Tốc độ tối đa đoạn hiện tại" style="
          background:rgba(255,255,255,.95);
          border:1px solid rgba(239,68,68,.35);
          border-radius:999px;
          padding:2px 7px 2px 3px;
          font-size:11px;
          font-weight:900;
          color:#111827;
          line-height:1;
          box-shadow:0 3px 10px rgba(0,0,0,.18);
          white-space:nowrap;
          display:flex;
          align-items:center;
          gap:4px;
      ">
        <span id="ts-speed-sign" style="
            width:22px;height:22px;
            border:3px solid #ef4444;
            border-radius:50%;
            display:inline-flex;
            align-items:center;
            justify-content:center;
            background:white;
            color:#111827;
            font-size:9px;
            font-weight:1000;
            line-height:1;
            box-sizing:border-box;
        ">?</span>
        <span id="ts-speed-text">--</span>
      </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(panel_html))

    # ── Báo cáo cộng đồng    # ── Báo cáo cộng đồng ────────────────────────────────────────────────
    RICON = {"accident":("red","exclamation-sign"),"flood":("blue","tint"),
             "traffic_jam":("orange","road"),"bad_road":("orange","warning-sign"),
             "landslide":("darkred","ban-circle")}
    if reports:
        for r in reports:
            c2, ic2 = RICON.get(r.get("type",""), ("gray","info-sign"))
            folium.Marker([r["lat"], r["lon"]],
                popup=folium.Popup(
                    f"<b>{r.get('icon','')} {r.get('label','')}</b><br>"
                    f"{r.get('description','')}<br>👍 {r.get('upvotes',0)}",
                    max_width=210),
                tooltip=f"{r.get('icon','')} {r.get('label','')}",
                icon=folium.Icon(color=c2, icon=ic2, prefix="glyphicon"),
            ).add_to(m)

    # ── Marker sự cố ─────────────────────────────────────────────────────
    if incident_marker:
        folium.Marker([incident_marker["lat"], incident_marker["lon"]],
            popup=folium.Popup(f"<b>🚧 Sự cố</b><br>{incident_marker.get('desc','')}", max_width=200),
            tooltip="🚧 Sự cố",
            icon=folium.Icon(color="black", icon="remove-sign", prefix="glyphicon"),
        ).add_to(m)

    # ── Dự báo rủi ro theo thời gian (AI) ─────────────────────────────────
    if forecast_segments:
        for seg in forecast_segments:
            _seg_score = _risk_score_float(seg.get("score", 0))
            # Theo ngưỡng mới: <40% bỏ qua; 40–64 vàng; 65–89 cam; >=90 đỏ.
            if _seg_score < YELLOW_RISK_THRESHOLD:
                continue  # bỏ qua các điểm an toàn để tránh spam bản đồ
            _seg_icon = _risk_level_icon(_seg_score)
            _seg_color = "#e53935" if _seg_score >= RED_RISK_THRESHOLD else "#fb8c00" if _seg_score >= ORANGE_RISK_THRESHOLD else "#fdd835"
            all_lats.append(seg["lat"])
            all_lons.append(seg["lon"])
            popup_html = (
                f"<div style='font-family:sans-serif;min-width:200px'>"
                f"<b>{_seg_icon} {seg.get('label','')}</b><br>"
                f"<span style='font-size:.85rem'>km {seg.get('route_km',0):.0f} · "
                f"ETA {seg.get('eta_text','')}</span><br>"
                f"<span style='font-size:.8rem'>Điểm rủi ro: {_seg_score:.0%}</span>"
                + ("<br><span style='font-size:.78rem;color:#555'>"
                   + "; ".join(seg.get("weather_alerts", [])) + "</span>" if seg.get("weather_alerts") else "")
                + "</div>"
            )
            folium.CircleMarker(
                [seg["lat"], seg["lon"]],
                radius=7,
                color=_seg_color,
                fill=True,
                fill_color=_seg_color,
                fill_opacity=0.85,
                weight=1,
                popup=folium.Popup(popup_html, max_width=240),
                tooltip=f"{_seg_icon} km {seg.get('route_km',0):.0f} · ETA {seg.get('eta_text','')} · {seg.get('label','')}",
            ).add_to(m)

    # ── GPS hiện tại — chấm/hình nhân nhấp nháy + tô đoạn đã đi/chưa đi ──────
    # gps_position: {"lat":.., "lon":.., "progress_idx":.., "off_route":bool,
    #                 "reroute_polyline":[[lon,lat],...] hoặc None}
    if gps_position:
        g_lat = gps_position.get("lat")
        g_lon = gps_position.get("lon")
        g_progress_idx = gps_position.get("progress_idx", 0)
        g_offroute = gps_position.get("off_route", False)
        g_reroute_pl = gps_position.get("reroute_polyline")

        if g_lat is not None and g_lon is not None:
            all_lats.append(g_lat)
            all_lons.append(g_lon)

            # Tô lại đoạn ĐÃ ĐI (xám mờ) chồng lên tuyến gốc, dựa trên progress_idx
            if route_polyline and g_progress_idx > 0:
                try:
                    coords_past = [[p[1], p[0]] for p in route_polyline[:g_progress_idx + 1] if len(p) >= 2]
                    if len(coords_past) >= 2:
                        folium.PolyLine(
                            coords_past,
                            color="#9e9e9e", weight=7, opacity=0.6,
                            tooltip="Đoạn đã đi qua",
                            smooth_factor=0, line_cap="round", line_join="round",
                        ).add_to(m)
                except Exception:
                    pass

            # Nếu lệch tuyến và có tuyến tính lại → vẽ tuyến mới màu cam
            if g_offroute and g_reroute_pl and len(g_reroute_pl) >= 2:
                try:
                    coords_new = [[p[1], p[0]] for p in g_reroute_pl if len(p) >= 2]
                    all_lats += [p[1] for p in g_reroute_pl if len(p) >= 2]
                    all_lons += [p[0] for p in g_reroute_pl if len(p) >= 2]
                    folium.PolyLine(
                        coords_new, color="#ff6f00", weight=6, opacity=0.9,
                        tooltip="Tuyến tính lại (an toàn nhất)",
                        smooth_factor=0, line_cap="round", line_join="round",
                    ).add_to(m)
                except Exception:
                    pass

            pulse_color = "#e53935" if g_offroute else "#1a73e8"

            # Vòng nhấp nháy ngoài
            pulse_html = f"""
            <div style="
                width:30px; height:30px;
                border-radius:50%;
                background:transparent;
                border: 3px solid {pulse_color};
                margin-top:-15px; margin-left:-15px;
                animation: gpsnavpulse 1.6s infinite;
            "></div>
            <style>
            @keyframes gpsnavpulse {{
                0%   {{ transform:scale(0.8); opacity:1; }}
                70%  {{ transform:scale(2.2); opacity:0; }}
                100% {{ transform:scale(0.8); opacity:0; }}
            }}
            </style>"""
            folium.Marker(
                [g_lat, g_lon],
                icon=folium.DivIcon(html=pulse_html),
                z_index_offset=1000,
            ).add_to(m)

            # Chấm GPS / hình nhân ở giữa
            folium.CircleMarker(
                location=[g_lat, g_lon],
                radius=10,
                color=pulse_color, fill=True,
                fill_color=pulse_color, fill_opacity=0.9,
                weight=2,
                tooltip="📍 Vị trí của bạn (GPS)",
            ).add_to(m)
            folium.Marker(
                [g_lat, g_lon],
                icon=folium.DivIcon(html='<div style="font-size:22px;margin-top:-34px;text-align:center">🧍</div>'),
                tooltip="📍 Vị trí của bạn (GPS)",
            ).add_to(m)

    folium.LayerControl(collapsed=True).add_to(m)
    pad = 0.05
    if all_lats and all_lons:
        m.fit_bounds([[min(all_lats)-pad, min(all_lons)-pad],
                      [max(all_lats)+pad, max(all_lons)+pad]])

    base_html = m._repr_html_()

    # ── Live GPS JS injection ─────────────────────────────────────────────────
    # Khi enable_live_gps=True, chèn JS watchPosition() vào HTML bản đồ.
    # Marker GPS được tạo và cập nhật HOÀN TOÀN phía client — không reload Streamlit,
    # không st_autorefresh, không mờ/chớp.
    if not enable_live_gps:
        return base_html

    _dest_lat = dest_lat if dest_lat is not None else lat2
    _dest_lon = dest_lon if dest_lon is not None else lon2

    # Serialize danger markers để JS có thể tính IoT state
    _dm_js = json.dumps([
        {
            "lat":   seg.get("lat", 0),
            "lon":   seg.get("lon", 0),
            "score": seg.get("score", 0),
            "label": seg.get("label", ""),
            "icon":  seg.get("icon", "⚠️"),
        }
        for seg in (danger_markers or [])
        if seg.get("lat") and seg.get("lon")
    ])

    # Serialize polyline để JS snap & tính progress
    _poly_js = json.dumps([
        [p[1], p[0]] for p in (route_polyline or []) if len(p) >= 2
    ])

    _fuel_js = json.dumps([
        {
            "name": str(p.get("name") or "Cây xăng"),
            "lat": float(p.get("lat")),
            "lon": float(p.get("lon")),
            "route_km": float(p.get("route_km", 0) or 0),
            "dist_from_route_m": p.get("dist_from_route_m"),
        }
        for p in (pois or [])
        if str(p.get("category", "")).lower() == "fuel" and p.get("lat") is not None and p.get("lon") is not None
    ], ensure_ascii=False)

    _speed_js = json.dumps([
        {
            "route_km": float(sg.get("route_km", 0) or 0),
            "maxspeed": sg.get("maxspeed"),
            "maxspeed_text": str(sg.get("maxspeed_text") or sg.get("maxspeed") or ""),
            "highway": str(sg.get("highway") or ""),
            "source": str(sg.get("source") or "osm"),
        }
        for sg in (speed_segments or [])
        if sg is not None
    ], ensure_ascii=False)

    try:
        _avg_speed_js = float(avg_speed_kmh or 40.0)
    except Exception:
        _avg_speed_js = 40.0

    live_gps_js = f"""
<script>
(function() {{
  // ── Haversine distance (km) ───────────────────────────────────────────────
  function hav(lat1, lon1, lat2, lon2) {{
    var R = 6371.0, r = Math.PI/180;
    var dlat = (lat2-lat1)*r, dlon = (lon2-lon1)*r;
    var a = Math.sin(dlat/2)*Math.sin(dlat/2) +
            Math.cos(lat1*r)*Math.cos(lat2*r)*Math.sin(dlon/2)*Math.sin(dlon/2);
    return R * 2 * Math.asin(Math.sqrt(Math.max(0,a)));
  }}

  // ── Data từ Python (serialize 1 lần khi render) ──────────────────────────
  var DANGER_MARKERS = {_dm_js};
  var ROUTE_POLY     = {_poly_js};   // [[lat,lon], ...]
  var FUEL_STATIONS  = {_fuel_js};   // cây xăng dọc tuyến, có route_km
  var SPEED_SEGMENTS = {_speed_js};   // maxspeed theo route_km, nếu không có thì panel ghi Không có thông tin
  var AVG_SPEED_KMH  = {_avg_speed_js};
  var DEST_LAT       = {_dest_lat};
  var DEST_LON       = {_dest_lon};
  var OFFROUTE_KM    = 0.025;  // 25 m

  // ── Giữ nguyên zoom/vị trí bản đồ khi Streamlit rerun nhẹ ───────────────────
  // Lưu view theo từng tuyến: tuyến mới vẫn fit_bounds bình thường,
  // tuyến hiện tại không nhảy về view ban đầu khi iframe Folium render lại.
  var MAP_VIEW_KEY_PREFIX = 'tripsmart_map_view_v1:';
  var MAP_VIEW_READY_TO_SAVE = false;
  var MAP_VIEW_RESTORE_UNTIL = 0;

  function routeViewKey() {{
    try {{
      if (!ROUTE_POLY || !ROUTE_POLY.length) return MAP_VIEW_KEY_PREFIX + 'no_route';
      var first = ROUTE_POLY[0];
      var last  = ROUTE_POLY[ROUTE_POLY.length - 1];
      return MAP_VIEW_KEY_PREFIX
        + Number(first[0]).toFixed(5) + ',' + Number(first[1]).toFixed(5)
        + '>'
        + Number(last[0]).toFixed(5) + ',' + Number(last[1]).toFixed(5)
        + ':'
        + ROUTE_POLY.length;
    }} catch(e) {{
      return MAP_VIEW_KEY_PREFIX + 'fallback';
    }}
  }}

  function saveMapView(map) {{
    try {{
      // Không lưu view mặc định ngay lúc iframe vừa dựng lại,
      // tránh ghi đè zoom/vị trí người dùng vừa chỉnh.
      if (!MAP_VIEW_READY_TO_SAVE || Date.now() < MAP_VIEW_RESTORE_UNTIL) return;
      if (!map || typeof map.getCenter !== 'function') return;
      var c = map.getCenter();
      var payload = {{
        lat: Number(c.lat),
        lon: Number(c.lng),
        zoom: Number(map.getZoom()),
        ts: Date.now()
      }};
      var raw = JSON.stringify(payload);
      var key = routeViewKey();
      try {{ localStorage.setItem(key, raw); }} catch(e) {{}}
      try {{ window.parent.localStorage.setItem(key, raw); }} catch(e) {{}}
    }} catch(e) {{}}
  }}

  function loadMapView() {{
    var raw = null;
    var key = routeViewKey();
    try {{ raw = localStorage.getItem(key); }} catch(e) {{}}
    if (!raw) {{
      try {{ raw = window.parent.localStorage.getItem(key); }} catch(e) {{}}
    }}
    if (!raw) return null;

    try {{
      var v = JSON.parse(raw);
      if (!v) return null;
      if (!Number.isFinite(Number(v.lat)) || !Number.isFinite(Number(v.lon)) || !Number.isFinite(Number(v.zoom))) return null;
      if (Date.now() - Number(v.ts || 0) > 45 * 60 * 1000) return null;
      return v;
    }} catch(e) {{
      return null;
    }}
  }}

  function restoreMapView(map) {{
    try {{
      if (!map || typeof map.setView !== 'function') return false;
      var v = loadMapView();
      if (!v) return false;
      map.setView([Number(v.lat), Number(v.lon)], Number(v.zoom), {{animate:false}});
      return true;
    }} catch(e) {{
      return false;
    }}
  }}

  function bindMapViewMemory(map) {{
    try {{
      if (!map || map.__tsViewMemoryBound) return;
      map.__tsViewMemoryBound = true;

      MAP_VIEW_READY_TO_SAVE = false;
      MAP_VIEW_RESTORE_UNTIL = Date.now() + 1800;

      function restoreOnly() {{
        restoreMapView(map);
      }}

      restoreOnly();
      setTimeout(restoreOnly, 60);
      setTimeout(restoreOnly, 220);
      setTimeout(restoreOnly, 650);
      setTimeout(restoreOnly, 1250);

      setTimeout(function() {{
        MAP_VIEW_READY_TO_SAVE = true;
        saveMapView(map);
      }}, 1850);

      map.on('moveend zoomend', function() {{
        saveMapView(map);
      }});
    }} catch(e) {{}}
  }}


  // ── Tìm Leaflet map object ────────────────────────────────────────────────
  function getLeafletMap() {{
    // Folium gắn map vào biến toàn cục có tên map_<uuid>
    for (var k in window) {{
      if (k.startsWith('map_') && window[k] && typeof window[k].addLayer === 'function') {{
        return window[k];
      }}
    }}
    return null;
  }}

  var gpsMarker    = null;
  var pulseCircle  = null;
  var watchId      = null;
  var gpsPollId    = null;
  var mapObj       = null;
  var statusEl     = null;
  var arrived      = false;

  // ── Tạo status badge trong bản đồ ────────────────────────────────────────
  function createStatusBadge(map) {{
    var badge = L.control({{position: 'topright'}});
    badge.onAdd = function() {{
      var div = L.DomUtil.create('div', '');
      div.id  = 'gps-live-badge';
      div.style.cssText = 'background:white;border-radius:20px;padding:6px 14px;' +
        'font-family:sans-serif;font-size:.82rem;font-weight:600;' +
        'border:1.5px solid #1976d2;color:#1565c0;cursor:pointer;' +
        'box-shadow:0 2px 8px rgba(0,0,0,.2);';
      div.innerHTML = '📡 Bật GPS';
      div.onclick = function() {{ startGPS(map); }};
      statusEl = div;
      return div;
    }};
    badge.addTo(map);
  }}

  function setStatus(text, color) {{
    if (statusEl) {{
      statusEl.innerHTML = text;
      statusEl.style.color       = color || '#1565c0';
      statusEl.style.borderColor = color || '#1976d2';
    }}
  }}

  // ── Snap GPS lên polyline, trả về khoảng cách lệch tuyến ─────────────────
  function snapToRoute(lat, lon) {{
    if (!ROUTE_POLY.length) return {{idx: 0, dist: 0}};
    var bestIdx = 0, bestDist = 9999;
    for (var i = 0; i < ROUTE_POLY.length; i++) {{
      var d = hav(lat, lon, ROUTE_POLY[i][0], ROUTE_POLY[i][1]);
      if (d < bestDist) {{ bestDist = d; bestIdx = i; }}
    }}
    return {{idx: bestIdx, dist: bestDist}};
  }}

  // ── Tính route_km hiện tại và cập nhật ETA/cây xăng mỗi giây ───────────────
  var ROUTE_CUM_KM = [];
  var ROUTE_TOTAL_KM = 0;
  function initRouteCumulative() {{
    ROUTE_CUM_KM = [];
    ROUTE_TOTAL_KM = 0;
    if (!ROUTE_POLY.length) return;
    ROUTE_CUM_KM.push(0);
    for (var i = 1; i < ROUTE_POLY.length; i++) {{
      ROUTE_TOTAL_KM += hav(ROUTE_POLY[i-1][0], ROUTE_POLY[i-1][1], ROUTE_POLY[i][0], ROUTE_POLY[i][1]);
      ROUTE_CUM_KM.push(ROUTE_TOTAL_KM);
    }}
  }}

  function currentRouteKm(lat, lon) {{
    if (!ROUTE_POLY.length) return 0;
    var snap = snapToRoute(lat, lon);
    var idx = Math.max(0, Math.min(snap.idx || 0, ROUTE_CUM_KM.length - 1));
    return ROUTE_CUM_KM[idx] || 0;
  }}

  function fmtKm(km) {{
    if (km == null || isNaN(km)) return '-- km';
    if (km < 1) return Math.max(0, km * 1000).toFixed(0) + ' m';
    return km.toFixed(1) + ' km';
  }}

  function fmtDuration(seconds) {{
    seconds = Math.max(0, Math.round(seconds || 0));
    var m = Math.round(seconds / 60);
    if (m < 60) return m + ' phút';
    var h = Math.floor(m / 60);
    var mm = m % 60;
    return h + ' giờ ' + (mm ? mm + ' phút' : '');
  }}

  function fmtArrival(seconds) {{
    var d = new Date(Date.now() + Math.max(0, seconds || 0) * 1000);
    var hh = String(d.getHours()).padStart(2, '0');
    var mm = String(d.getMinutes()).padStart(2, '0');
    return hh + ':' + mm;
  }}

  function setSpeedPillEmpty() {{
    var signEl = document.getElementById('ts-speed-sign');
    var textEl = document.getElementById('ts-speed-text');
    if (signEl) signEl.innerHTML = '?';
    if (textEl) textEl.innerHTML = '--';
  }}

  function speedNumberFromText(text, fallback) {{
    var n = Number(fallback);
    if (Number.isFinite(n) && n > 0) return String(Math.round(n));
    var m = String(text || '').match(/[0-9]+/);
    return m ? m[0] : null;
  }}

  function updateSpeedLimitPanel(curKm) {{
    var speedEl = document.getElementById('ts-live-speed-limit');
    var signEl = document.getElementById('ts-speed-sign');
    var textEl = document.getElementById('ts-speed-text');
    if (!speedEl || !signEl || !textEl) return;

    if (!SPEED_SEGMENTS || !SPEED_SEGMENTS.length) {{
      setSpeedPillEmpty();
      speedEl.title = 'Chưa có dữ liệu tốc độ tối đa';
      return;
    }}

    var best = null, bestDiff = 999999;
    for (var i = 0; i < SPEED_SEGMENTS.length; i++) {{
      var sg = SPEED_SEGMENTS[i] || {{}};
      var rk = Number(sg.route_km || 0);
      var diff = Math.abs(rk - curKm);
      if (diff < bestDiff) {{ bestDiff = diff; best = sg; }}
    }}

    // Nếu maxspeed gần nhất quá xa vị trí hiện tại, coi như đoạn này chưa có thông tin.
    if (!best || bestDiff > 1.2 || best.maxspeed == null) {{
      setSpeedPillEmpty();
      speedEl.title = 'Chưa có dữ liệu tốc độ tối đa tại đoạn này';
      return;
    }}

    var rawText = String(best.maxspeed_text || (best.maxspeed + ' km/h'));
    var speedNo = speedNumberFromText(rawText, best.maxspeed);
    if (!speedNo) {{
      setSpeedPillEmpty();
      speedEl.title = rawText;
      return;
    }}

    signEl.innerHTML = speedNo;
    textEl.innerHTML = 'km/h';
    speedEl.title = 'Tốc độ tối đa: ' + rawText + (best.highway ? ' · ' + best.highway : '');
  }}

  function updateLiveRoutePanel(lat, lon) {{
    var fuel1El = document.getElementById('ts-live-fuel-1');
    var fuel2El = document.getElementById('ts-live-fuel-2');

    var curKm = currentRouteKm(lat, lon);
    updateSpeedLimitPanel(curKm);

    var upcoming = (FUEL_STATIONS || [])
      .filter(function(f) {{ return (Number(f.route_km || 0) - curKm) > 0.03; }})
      .map(function(f) {{
        var ahead = Number(f.route_km || 0) - curKm;
        return Object.assign({{}}, f, {{ahead_km: ahead}});
      }})
      .sort(function(a, b) {{ return a.ahead_km - b.ahead_km; }})
      .slice(0, 2);

    function setFuelPill(el, fuel, idx) {{
      if (!el) return;
      if (!fuel) {{
        el.innerHTML = '⛽ -- km';
        el.title = idx === 1 ? 'Chưa có cây xăng tiếp theo' : 'Chưa có cây xăng kế tiếp';
        return;
      }}
      var name = String(fuel.name || ('Cây xăng ' + idx)).replace(/[&<>"']/g, function(c) {{
        return {{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c];
      }});
      el.innerHTML = '⛽ ' + fmtKm(fuel.ahead_km);
      el.title = name + ' · còn ' + fmtKm(fuel.ahead_km);
    }}

    setFuelPill(fuel1El, upcoming[0], 1);
    setFuelPill(fuel2El, upcoming[1], 2);
  }}

    // ── Tính IoT state từ GPS  // ── Tính IoT state từ GPS ─────────────────────────────────────────────────
  function calcIoTState(lat, lon) {{
    var nearestDist = 9999, nearestDanger = null;
    for (var i = 0; i < DANGER_MARKERS.length; i++) {{
      var d = hav(lat, lon, DANGER_MARKERS[i].lat, DANGER_MARKERS[i].lon);
      if (d < nearestDist) {{ nearestDist = d; nearestDanger = DANGER_MARKERS[i]; }}
    }}
    var score = (nearestDanger && nearestDist < 1.0) ? nearestDanger.score : 0;
    if (score >= 0.85) return 'danger';
    if (score >= 0.65 || nearestDist < 2.0) return 'warning';
    return 'safe';
  }}

  // ── Cập nhật marker GPS trên bản đồ ──────────────────────────────────────
  function updateGPSMarker(map, lat, lon) {{
    var snap     = snapToRoute(lat, lon);
    var offRoute = snap.dist > OFFROUTE_KM;
    var state    = calcIoTState(lat, lon);

    var color = offRoute ? '#e53935' : (state === 'danger' ? '#e53935' :
                                        state === 'warning' ? '#f9a825' : '#1a73e8');

    // Xóa marker cũ
    if (gpsMarker)   {{ map.removeLayer(gpsMarker);   gpsMarker   = null; }}
    if (pulseCircle) {{ map.removeLayer(pulseCircle); pulseCircle = null; }}

    // Vòng nhấp nháy (CSS animation trong DivIcon)
    var pulseIcon = L.divIcon({{
      className: '',
      html: '<div style="width:36px;height:36px;border-radius:50%;border:3px solid ' + color + ';' +
            'margin-top:-18px;margin-left:-18px;' +
            'animation:gpsnavpulse 1.6s infinite;"></div>' +
            '<style>@keyframes gpsnavpulse{{' +
            '0%{{transform:scale(.7);opacity:1}}' +
            '70%{{transform:scale(2.2);opacity:0}}' +
            '100%{{transform:scale(.7);opacity:0}}' +
            '}}</style>',
      iconSize:   [0, 0],
      iconAnchor: [0, 0],
    }});

    gpsMarker = L.marker([lat, lon], {{icon: pulseIcon, zIndexOffset: 1000}}).addTo(map);

    // Chấm chính + emoji người
    pulseCircle = L.circleMarker([lat, lon], {{
      radius:      10,
      color:       color,
      fillColor:   color,
      fillOpacity: 0.9,
      weight:      2,
    }}).addTo(map);
    pulseCircle.bindTooltip('📍 Vị trí của bạn (GPS live)');

    // Status badge
    var stateEmoji = state === 'danger' ? '🔴' : state === 'warning' ? '🟡' : '🟢';
    setStatus(stateEmoji + ' GPS ' + lat.toFixed(5) + ', ' + lon.toFixed(5), color);
    updateLiveRoutePanel(lat, lon);

    // NGUỒN GPS CHUNG CỦA TOÀN APP:
    // Chấm xanh trên bản đồ cập nhật tới đâu thì ghi ngay cùng tọa độ đó
    // vào localStorage + parent localStorage + postMessage để SOS đọc lại.
    var sharedGpsPayload = {{
      lat: lat, lon: lon, acc: 0, ts: Date.now(),
      offRoute: offRoute, iotState: state, source: 'map_live_blue_dot'
    }};
    try {{ localStorage.setItem('tripsmart_gps', JSON.stringify(sharedGpsPayload)); }} catch(e) {{}}
    try {{ window.parent.localStorage.setItem('tripsmart_gps', JSON.stringify(sharedGpsPayload)); }} catch(e) {{}}
    try {{
      window.parent.postMessage({{
        type: 'tripsmart_gps',
        payload: sharedGpsPayload,
      }}, '*');
    }} catch(e) {{}}

    // Kiểm tra đến nơi
    if (!arrived && hav(lat, lon, DEST_LAT, DEST_LON) < 0.05) {{
      arrived = true;
      setStatus('🎉 Đã đến điểm đến!', '#2e7d32');
      if (watchId !== null) navigator.geolocation.clearWatch(watchId);
    }}
  }}

  // ── Bắt đầu watchPosition ─────────────────────────────────────────────────
  function startGPS(map) {{
    if (!navigator.geolocation) {{
      setStatus('❌ Trình duyệt không hỗ trợ GPS', '#b71c1c');
      return;
    }}
    setStatus('⏳ Đang chờ GPS…', '#f57c00');

    // Lần đầu: lấy ngay
    navigator.geolocation.getCurrentPosition(
      function(pos) {{ updateGPSMarker(map, pos.coords.latitude, pos.coords.longitude); }},
      function(err) {{ setStatus('❌ ' + (err.code===1 ? 'Bị từ chối quyền GPS' : 'Lỗi GPS'), '#b71c1c'); }},
      {{enableHighAccuracy: true, timeout: 10000, maximumAge: 0}}
    );

    // Theo dõi liên tục — cập nhật marker KHÔNG reload Streamlit
    if (watchId !== null) navigator.geolocation.clearWatch(watchId);
    watchId = navigator.geolocation.watchPosition(
      function(pos) {{ updateGPSMarker(map, pos.coords.latitude, pos.coords.longitude); }},
      function(err) {{ setStatus('⚠️ Mất tín hiệu GPS', '#f57c00'); }},
      {{enableHighAccuracy: true, timeout: 10000, maximumAge: 0}}
    );

    // Cưỡng bức kiểm tra GPS mỗi 1 giây từ chính bản đồ.
    // Đây là nguồn GPS chung: chấm xanh cập nhật → localStorage tripsmart_gps → SOS đọc lại.
    if (gpsPollId !== null) clearInterval(gpsPollId);
    gpsPollId = setInterval(function() {{
      navigator.geolocation.getCurrentPosition(
        function(pos) {{ updateGPSMarker(map, pos.coords.latitude, pos.coords.longitude); }},
        function(err) {{ /* giữ tọa độ mới nhất đã có */ }},
        {{enableHighAccuracy: true, timeout: 8000, maximumAge: 0}}
      );
    }}, 1000);
  }}

  // ── Khởi động sau khi Leaflet map sẵn sàng ───────────────────────────────
  function init() {{
    mapObj = getLeafletMap();
    if (!mapObj) {{
      setTimeout(init, 200);
      return;
    }}
    initRouteCumulative();
    createStatusBadge(mapObj);
    bindMapViewMemory(mapObj);

    // Tự bật GPS nếu đã có quyền (saved localStorage < 30s)
    try {{
      var saved = localStorage.getItem('tripsmart_gps');
      if (saved) {{
        var p = JSON.parse(saved);
        if (Date.now() - p.ts < 30000) {{
          setTimeout(function() {{ startGPS(mapObj); }}, 500);
        }}
      }}
    }} catch(e) {{}}
  }}

  // Đợi DOM + Leaflet load xong
  if (document.readyState === 'complete') {{
    setTimeout(init, 300);
  }} else {{
    window.addEventListener('load', function() {{ setTimeout(init, 300); }});
  }}
}})();
</script>
"""

    # QUAN TRỌNG:
    # m._repr_html_() của Folium trả về một iframe. Nếu nối <script> vào base_html
    # thì script chạy ở trang cha của iframe, không nhìn thấy biến map_<uuid> của Leaflet.
    # Vì vậy phải nhúng script vào chính HTML gốc của Folium trước khi _repr_html_().
    try:
        from branca.element import Element
        m.get_root().html.add_child(Element(live_gps_js))
        return m._repr_html_()
    except Exception:
        # Fallback cũ: ít ổn định hơn, chỉ để tránh làm app crash nếu branca lỗi.
        if "</body>" in base_html:
            return base_html.replace("</body>", live_gps_js + "\n</body>")
        return base_html + live_gps_js
