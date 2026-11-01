# core/copilot.py
# AI Mobility Copilot: phân tích trạng thái, lý do, hành động gợi ý.

from datetime import datetime, timedelta
import time as _time
import streamlit as st

from features.gps_live import GPS_MAX_AGE_SEC
from core.route_calc import (
    RED_RISK_THRESHOLD, YELLOW_RISK_THRESHOLD,
    _get_route_distance_km, _risk_level_icon,
)

def _safe_parse_dt(x):
    if isinstance(x, datetime):
        return x
    try:
        return datetime.fromisoformat(str(x))
    except Exception:
        return None


def _minutes_until_eta(seg, now_dt=None):
    """Số phút từ hiện tại đến ETA của segment AI forecast."""
    now_dt = now_dt or datetime.now()
    eta = _safe_parse_dt((seg or {}).get("eta"))
    if eta is None:
        try:
            txt = str((seg or {}).get("eta_text") or "")
            if ":" in txt:
                hh, mm = [int(v) for v in txt.split(":")[:2]]
                eta = now_dt.replace(hour=hh, minute=mm, second=0, microsecond=0)
                if eta < now_dt - timedelta(minutes=5):
                    eta += timedelta(days=1)
        except Exception:
            eta = None
    if eta is None:
        return None
    return (eta - now_dt).total_seconds() / 60.0


def _copilot_segment_score(seg):
    try:
        return float((seg or {}).get("score") or 0.0)
    except Exception:
        return 0.0


def _copilot_is_high(seg):
    # Chỉ coi là điểm đỏ/cực nguy hiểm khi >= 90%.
    # Các mức 65–89% vẫn là cảnh báo cam/vàng, chưa phải chấm đỏ.
    return _copilot_segment_score(seg) >= RED_RISK_THRESHOLD


def _build_mobility_copilot_state(forecast, route, danger_markers, rest_stops, mode, nav_active=False):
    """
    Tổng hợp dữ liệu thành trạng thái ra quyết định:
    - Safety Score 0–100, chỉ đo an toàn, không trộn Net Zero.
    - Risk trajectory đúng theo đoạn tuyến sẽ đi qua trong 0–15, 15–30, 30–60 phút tới.
    - Khuyến nghị hành động, nhưng không tự đổi tuyến.
    """
    now_dt = datetime.now()
    forecast = forecast or {}
    segments = list(forecast.get("segments") or [])
    danger_markers = list(danger_markers or [])
    rest_stops = list(rest_stops or [])
    dist_km = _get_route_distance_km(route or {})

    if segments:
        scores = [_copilot_segment_score(s) for s in segments]
        avg_score = sum(scores) / max(1, len(scores))
        max_score = max(scores) if scores else 0.0
        high_count = sum(1 for s in segments if _copilot_is_high(s))
        unknown_count = sum(1 for s in segments if str(s.get("level")) == "unknown")
    else:
        scores = []
        for d in danger_markers:
            try:
                scores.append(float(d.get("score") or 0.0))
            except Exception:
                pass
        avg_score = sum(scores) / max(1, len(scores)) if scores else 0.0
        max_score = max(scores) if scores else 0.0
        high_count = sum(1 for d in danger_markers if float(d.get("score") or 0) >= RED_RISK_THRESHOLD)
        unknown_count = 0

    score = 100.0
    score -= avg_score * 45.0
    score -= max_score * 25.0
    score -= min(high_count, 6) * 4.0
    if dist_km >= 80 and not rest_stops:
        score -= 6.0
    if unknown_count:
        score -= min(unknown_count, 5) * 2.0
    if nav_active:
        score += 3.0
    safety_score = int(max(0, min(100, round(score))))

    if safety_score >= 80:
        safety_label, safety_icon, safety_css = "An toàn tương đối", "🟢", "alert-success"
    elif safety_score >= 60:
        safety_label, safety_icon, safety_css = "Cần chú ý", "🟡", "alert-warning"
    else:
        safety_label, safety_icon, safety_css = "Rủi ro cao", "🔴", "alert-danger"

    # Không dùng kiểu cộng dồn 0–30/0–60. Mỗi ô tương ứng với đoạn tuyến sẽ đi qua
    # trong khoảng thời gian đó: 0–15, 15–30, 30–60 phút tới.
    windows = [
        (0, 15, "15 phút tới"),
        (15, 30, "30 phút tới"),
        (30, 60, "60 phút tới"),
    ]
    trajectory = []
    for start_min, end_min, label in windows:
        segs_in = []
        for seg in segments:
            mins = _minutes_until_eta(seg, now_dt)
            if mins is not None and start_min <= mins <= end_min:
                segs_in.append(seg)
        if segs_in:
            top = max(segs_in, key=_copilot_segment_score)
            trajectory.append({
                "window": label,
                "range_text": f"{start_min}–{end_min} phút",
                "level": top.get("level", "unknown"),
                "score": _copilot_segment_score(top),
                "desc": top.get("hazard_label") or top.get("label") or "Đoạn cần chú ý",
                "eta_text": top.get("eta_text", ""),
                "route_km": top.get("route_km", None),
                "segment": top,
            })
        elif segments:
            trajectory.append({
                "window": label,
                "range_text": f"{start_min}–{end_min} phút",
                "level": "low",
                "score": 0.0,
                "desc": "Chưa phát hiện điểm rủi ro cao trên phần tuyến sẽ đi qua trong khung này",
                "segment": None,
            })
        else:
            level = "unknown" if not danger_markers else ("high" if max_score >= RED_RISK_THRESHOLD else "medium" if max_score >= YELLOW_RISK_THRESHOLD else "low")
            top = danger_markers[0] if danger_markers else None
            trajectory.append({
                "window": label,
                "range_text": f"{start_min}–{end_min} phút",
                "level": level,
                "score": max_score,
                "desc": top.get("label", "Chưa có đủ dữ liệu AI theo ETA") if top else "Chưa có đủ dữ liệu AI theo ETA",
                "segment": top,
            })

    # Chỉ chấm đỏ (>= 90%) mới tạo quyết định.
    # Ưu tiên điểm đỏ gần nhất theo hành trình phía trước/ETA, không lấy theo khoảng cách chim bay.
    upcoming = []
    for seg in segments:
        if not _copilot_is_high(seg):
            continue
        mins = _minutes_until_eta(seg, now_dt)
        rkm = seg.get("route_km")
        if mins is not None and mins >= 0:
            upcoming.append((0, mins, float(rkm or 0), -_copilot_segment_score(seg), seg))
        elif rkm is not None:
            upcoming.append((1, 999999.0, float(rkm or 0), -_copilot_segment_score(seg), seg))
    # Nếu chưa có AI forecast segments, fallback về danger_markers đỏ có route_km.
    if not upcoming and danger_markers:
        for d in danger_markers:
            try:
                if float(d.get("score") or 0) >= RED_RISK_THRESHOLD:
                    upcoming.append((1, 999999.0, float(d.get("route_km") or 0), -float(d.get("score") or 0), d))
            except Exception:
                pass
    upcoming.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
    critical_seg = upcoming[0][4] if upcoming else None

    offroute = bool(st.session_state.get("nav_offroute", False))
    gps_age = None
    try:
        import time as _time
        gts = float(st.session_state.get("nav_gps_ts") or 0)
        gps_age = (_time.time() - gts) if gts else None
    except Exception:
        pass

    reasons = []
    if critical_seg:
        km_txt = f"km {critical_seg.get('route_km', 0):.0f}" if critical_seg.get("route_km") is not None else "đoạn phía trước"
        reasons.append(f"{_risk_level_icon(_copilot_segment_score(critical_seg))} {critical_seg.get('label','Rủi ro cao')} tại {km_txt}, ETA {critical_seg.get('eta_text','?')}.")
        if critical_seg.get("weather_alerts"):
            reasons.append("Thời tiết: " + "; ".join(critical_seg.get("weather_alerts", [])[:2]) + ".")
        if critical_seg.get("hazard_label"):
            reasons.append(f"Gần {critical_seg.get('hazard_label')}.")
    if offroute:
        reasons.append("GPS cho thấy bạn đang lệch khỏi tuyến hiện tại.")
    if max_score >= RED_RISK_THRESHOLD and not critical_seg:
        reasons.append("Tuyến có vùng rủi ro nền cao cần theo dõi.")
    if gps_age is not None and gps_age > GPS_MAX_AGE_SEC:
        reasons.append("GPS đã cũ hơn 5 phút nên độ tin cậy giảm.")
    if dist_km >= 80 and not rest_stops:
        reasons.append("Tuyến dài nhưng chưa có điểm nghỉ phù hợp được gợi ý.")

    if offroute:
        recommendation = "Nên tính lại tuyến từ GPS hiện tại."
        action = "reroute"
        rec_css = "alert-warning"
    elif critical_seg and _copilot_segment_score(critical_seg) >= RED_RISK_THRESHOLD:
        recommendation = "Nên đổi sang tuyến an toàn hơn hoặc nghỉ 15–30 phút rồi cập nhật lại dự báo."
        action = "reroute_or_rest"
        rec_css = "alert-danger"
    elif critical_seg:
        recommendation = "Nên giảm tốc, quan sát kỹ và cân nhắc tuyến an toàn hơn nếu thời tiết xấu."
        action = "caution"
        rec_css = "alert-warning"
    elif safety_score < 60:
        recommendation = "Nên xem xét tuyến an toàn hơn trước khi tiếp tục."
        action = "review"
        rec_css = "alert-warning"
    else:
        recommendation = "Có thể tiếp tục di chuyển, app sẽ tiếp tục theo dõi rủi ro phía trước."
        action = "continue"
        rec_css = "alert-success"

    confidence = 50
    if segments:
        confidence += 25
    if nav_active and gps_age is not None and gps_age <= GPS_MAX_AGE_SEC:
        confidence += 20
    if forecast.get("overall_level") and forecast.get("overall_level") != "unknown":
        confidence += 10
    if unknown_count:
        confidence -= min(20, unknown_count * 3)
    confidence = int(max(0, min(100, confidence)))

    return {
        "safety_score": safety_score,
        "safety_label": safety_label,
        "safety_icon": safety_icon,
        "safety_css": safety_css,
        "trajectory": trajectory,
        "critical_segment": critical_seg,
        "has_red_decision": bool(critical_seg),
        "recommendation": recommendation,
        "action": action,
        "rec_css": rec_css,
        "reasons": reasons,
        "confidence": confidence,
        "avg_score": avg_score,
        "max_score": max_score,
        "high_count": high_count,
    }


def _render_mobility_copilot_state(copilot_state):
    """Render phần đọc hiểu của AI Mobility Copilot theo kiểu gọn, dễ hiểu."""
    cs = copilot_state or {}
    has_red = bool(cs.get("has_red_decision") or cs.get("critical_segment"))
    title = "🧠 Trợ lý an toàn hành trình"
    st.subheader(title)

    if has_red:
        lead = "🔴 Phát hiện điểm rất nguy hiểm phía trước"
        detail = "Nên cân nhắc đổi tuyến, nghỉ hoặc tiếp tục có kiểm soát."
        css = "alert-danger"
    else:
        lead = "🟢 Chưa có điểm đỏ cần quyết định ngay"
        detail = "Có thể tiếp tục, hãy theo dõi tuyến đường và thời tiết."
        css = "alert-success" if cs.get("safety_score", 0) >= 60 else "alert-warning"

    st.markdown(
        f'<div class="{css}" style="font-size:1rem">'
        f'<b>{lead}</b><br>'
        f'🛡️ Mức an toàn: <b>{cs.get("safety_score",0)}/100</b> · '
        f'📈 Độ tin cậy: <b>{cs.get("confidence",0)}%</b><br>'
        f'<b>Khuyến nghị:</b> {cs.get("recommendation", detail)}'
        f'</div>',
        unsafe_allow_html=True,
    )

    m1, m2, m3 = st.columns(3)
    m1.metric("🛡️ An toàn", f"{cs.get('safety_score', 0)}/100")
    m2.metric("🔴 Điểm đỏ", cs.get("high_count", 0))
    m3.metric("📈 Tin cậy", f"{cs.get('confidence', 0)}%")

    if cs.get("reasons"):
        with st.expander("🔎 Vì sao app khuyến nghị như vậy?", expanded=has_red):
            for r in cs.get("reasons", []):
                st.markdown(f"- {r}")

    with st.expander("⏱️ Xem dự báo nguy hiểm phía trước 15 / 30 / 60 phút", expanded=False):
        for item in cs.get("trajectory", []):
            level = item.get("level", "unknown")
            score = float(item.get("score") or 0.0)
            icon = _risk_level_icon(score) if level != "unknown" else "⚪"
            eta_txt = f" · ETA {item.get('eta_text')}" if item.get("eta_text") else ""
            km_txt = f" · km {item.get('route_km'):.0f}" if isinstance(item.get("route_km"), (int, float)) else ""
            st.markdown(
                f'<div class="step-box">{icon} <b>{item.get("window")}</b> '
                f'<span style="color:#777">({item.get("range_text","")})</span>{km_txt}{eta_txt} · '
                f'{item.get("desc", "")} <span style="float:right">{score:.0%}</span></div>',
                unsafe_allow_html=True,
            )


def _route_avg_risk_for_copilot(route_obj, risk_engine):
    try:
        analysis = risk_engine.analyze_route((route_obj or {}).get("polyline", []))
        return float(analysis.get("avg_score") or 0.0), analysis
    except Exception:
        return 9.0, {}
