# ui/route_panels.py
# Các khối hiển thị phụ: dự báo rủi ro, môi trường/xã hội, micro fact an toàn.

import random
import time
import json
import hashlib
import streamlit as st
import streamlit.components.v1 as components

from core.microlearning import (
    FACT_HISTORY_KEY, build_micro_context, load_fact_bank,
    remember_fact, select_micro_fact,
)

from core.route_calc import (
    _risk_level_icon, _risk_score_float, _get_route_distance_km,
)

# Hệ số CO₂e ước tính theo phương tiện (g/km)
# Tách từ app.py cũ sang module ui/route_panels.py để tránh NameError sau khi split app.
CO2_G_PER_KM_BY_MODE = {
    "car": 180.0,
    "motorbike": 75.0,
    "bike": 0.0,
    "walk": 0.0,
}

def _render_route_forecast(route_risk_forecast, departure_dt, title="Dự báo rủi ro theo hành trình"):
    """Hiển thị 1 block dự báo rủi ro theo thời gian (dùng chung cho tuyến gốc và tuyến cập nhật ETA)."""
    ov_level = route_risk_forecast["overall_level"]
    ov_color = {"low":"alert-success","medium":"alert-warning",
                "high":"alert-danger","very_high":"alert-danger",
                "unknown":"alert-info"}.get(ov_level, "alert-info")
    st.markdown(
        f'<div class="{ov_color}">🤖 <b>{title}:</b> '
        f'{route_risk_forecast["overall_label"]} '
        f'(điểm TB {route_risk_forecast["overall_score"]:.0%}) · '
        f'Tham chiếu giờ {departure_dt.strftime("%H:%M")}</div>',
        unsafe_allow_html=True,
    )

    attn = route_risk_forecast.get("attention_segments", [])
    if attn:
        with st.expander(f"⏱️ Đoạn cần chú ý theo thời gian ({len(attn)})", expanded=True):
            for seg in attn[:8]:
                hz_txt = f" · gần {seg['hazard_label']}" if seg.get("hazard_label") else ""
                wx_txt = " · " + "; ".join(seg["weather_alerts"]) if seg.get("weather_alerts") else ""
                _seg_score = _risk_score_float(seg.get("score", 0))
                _seg_icon = _risk_level_icon(_seg_score)
                st.markdown(
                    f'<div class="step-box">{_seg_icon} '
                    f'<b>km {seg["route_km"]:.0f}</b> · ETA {seg["eta_text"]} · '
                    f'{seg["label"]} ({_seg_score:.0%}){hz_txt}{wx_txt}</div>',
                    unsafe_allow_html=True,
                )

    for rec in route_risk_forecast.get("recommendations", []):
        st.markdown(f'<div class="alert-info">💡 {rec}</div>', unsafe_allow_html=True)


def _co2_factor_g_per_km(mode: str) -> float:
    return float(CO2_G_PER_KM_BY_MODE.get(str(mode or "car"), 180.0))


def _estimate_hazard_penalty_equiv_km(danger_markers) -> float:
    """
    Ước tính quãng đường tương đương bị lãng phí nhiên liệu nếu đi vào vùng ngập/sạt lở/đường xấu:
    phải chạy chậm, dừng chờ, quay đầu, hoặc giữ ga trong điều kiện xấu. Đây là mô hình minh bạch
    phục vụ giáo dục Net Zero, không phải đo khí thải tuyệt đối.
    """
    penalty = 0.0
    for seg in danger_markers or []:
        try:
            score = float(seg.get("score", 0) or 0)
        except Exception:
            score = 0.0
        typ = str(seg.get("type", "") or "").lower()
        txt = (str(seg.get("label", "") or "") + " " + str(seg.get("desc", "") or "")).lower()
        if any(k in typ + " " + txt for k in ["flood", "ngập", "lụt", "lũ"]):
            penalty += 2.8 * max(score, 0.35)
        elif any(k in typ + " " + txt for k in ["landslide", "sạt", "đèo", "bad_road", "đường xấu"]):
            penalty += 1.4 * max(score, 0.30)
        elif score >= 0.55:
            penalty += 0.8 * score
    return min(18.0, max(0.0, penalty))


def _render_env_social_impact(route, danger_markers, mode: str, reroute_route=None):
    """Hiển thị tác động Môi trường & Xã hội cho tuyến hiện tại và tuyến vòng nếu có."""
    mode_label = {"car":"ô tô", "motorbike":"xe máy", "bike":"xe đạp", "walk":"đi bộ"}.get(mode, mode)
    base_km = _get_route_distance_km(route or {})
    reroute_km = _get_route_distance_km(reroute_route or {}) if reroute_route else 0.0
    co2_gpkm = _co2_factor_g_per_km(mode)
    base_co2_kg = base_km * co2_gpkm / 1000.0
    penalty_km = _estimate_hazard_penalty_equiv_km(danger_markers)
    penalty_co2_kg = penalty_km * co2_gpkm / 1000.0

    if reroute_route and reroute_km > 0:
        reroute_co2_kg = reroute_km * co2_gpkm / 1000.0
        risky_total_kg = base_co2_kg + penalty_co2_kg
        net_saved_kg = risky_total_kg - reroute_co2_kg
        comparison_text = (
            f"So với tuyến gốc có rủi ro, tuyến vòng ước tính {'giảm' if net_saved_kg >= 0 else 'tăng'} "
            f"{abs(net_saved_kg):.2f} kg CO₂e."
        )
    else:
        reroute_co2_kg = None
        net_saved_kg = penalty_co2_kg
        comparison_text = (
            f"Nếu người dùng chủ động tránh vùng ngập/đường xấu, app ước tính có thể tránh lãng phí "
            f"khoảng {penalty_co2_kg:.2f} kg CO₂e do dừng chờ, quay đầu hoặc chạy chậm trong vùng rủi ro."
        )

    flood_count = 0
    high_count = 0
    for seg in danger_markers or []:
        txt = (str(seg.get("type", "") or "") + " " + str(seg.get("label", "") or "") + " " + str(seg.get("desc", "") or "")).lower()
        if any(k in txt for k in ["flood", "ngập", "lụt", "lũ"]):
            flood_count += 1
        try:
            if float(seg.get("score", 0) or 0) >= 0.6:
                high_count += 1
        except Exception:
            pass

    st.subheader("🌱 Tác động Môi trường & Xã hội")
    st.caption(
        "Mục này giúp gắn sản phẩm với Net Zero, an sinh xã hội và giáo dục an toàn. "
        "Các con số là ước tính minh bạch để so sánh phương án, không thay thế kiểm kê phát thải chính thức."
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Phương tiện", mode_label)
    c2.metric("Hệ số CO₂e", f"{co2_gpkm:.0f} g/km")
    c3.metric("CO₂e tuyến gốc", f"{base_co2_kg:.2f} kg")
    c4.metric("Tiềm năng giảm", f"{max(0.0, net_saved_kg):.2f} kg")

    if reroute_co2_kg is not None:
        c5, c6, c7 = st.columns(3)
        c5.metric("Tuyến gốc", f"{base_km:.1f} km")
        c6.metric("Tuyến vòng", f"{reroute_km:.1f} km")
        c7.metric("CO₂e tuyến vòng", f"{reroute_co2_kg:.2f} kg")

    css = "alert-success" if net_saved_kg >= 0 else "alert-warning"
    st.markdown(f'<div class="{css}">🌍 <b>Net Zero:</b> {comparison_text}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="alert-info">🤝 <b>An sinh xã hội:</b> Tuyến hiện tại phát hiện {len(danger_markers or [])} vùng cần chú ý, '
        f'trong đó có {high_count} vùng rủi ro cao và {flood_count} vùng liên quan ngập/lũ. '
        'Cảnh báo sớm giúp học sinh, gia đình, người đi làm và lực lượng hỗ trợ địa phương ra quyết định an toàn hơn.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="alert-success">📚 <b>Giáo dục:</b> Dữ liệu rủi ro, thời tiết, ETA và mẹo ngắn theo ngữ cảnh biến app thành công cụ học tập '
        'về giao thông, môi trường, tư duy phản biện và trách nhiệm cộng đồng.</div>',
        unsafe_allow_html=True,
    )



_FACT_ROTATE_SEC = 300  # 5 phút

def _render_safety_quiz(key_prefix: str = "safety_quiz"):
    """
    Microlearning/Nudge an toàn dạng client-side.

    Mục tiêu:
    - Chỉ hiện 1 dòng: 💡 + fact.
    - Tự đổi sau 5 phút bằng JavaScript trong trình duyệt.
    - KHÔNG dùng st_autorefresh, nên không rerun toàn app và không reset/phân tích lại tuyến.
    - Fact vẫn được lọc theo ngữ cảnh hiện tại khi Streamlit render: mưa, đêm, đèo, ngập, sạt lở, tốc độ...
    """
    route_risk_forecast = st.session_state.get("last_route_risk_forecast") or st.session_state.get("route_risk_forecast")
    danger_markers = st.session_state.get("last_danger_markers") or st.session_state.get("danger_markers") or []
    mode = st.session_state.get("last_mode") or st.session_state.get("mode") or "car"
    weather_text = st.session_state.get("last_weather_text") or st.session_state.get("weather_desc") or ""
    speed_kmh = st.session_state.get("gps_speed_kmh") or st.session_state.get("current_speed_kmh")

    context = build_micro_context(
        mode=mode,
        weather_text=weather_text,
        route_risk_forecast=route_risk_forecast,
        danger_markers=danger_markers,
        speed_kmh=speed_kmh,
    )

    facts = load_fact_bank()
    if not facts:
        return

    ctx_triggers = set((context or {}).get("triggers", ["default"])) or {"default"}
    primary_triggers = set((context or {}).get("primary_triggers", []))

    def _norm(v):
        return str(v or "").strip().lower()

    def _triggers_of_fact(fact):
        trg = fact.get("trigger", [])
        if isinstance(trg, str):
            trg = [trg]
        return {_norm(x) for x in trg if _norm(x)}

    def _fact_ok(fact):
        if not fact.get("active", True):
            return False
        if not str(fact.get("text", "")).strip():
            return False
        lang = _norm(fact.get("language", "vi"))
        return lang in {"", "vi"}

    valid_facts = [f for f in facts if _fact_ok(f)]
    if not valid_facts:
        return

    # Ưu tiên fact đúng ngữ cảnh mạnh trước.
    pool = []
    if primary_triggers:
        for f in valid_facts:
            if primary_triggers & _triggers_of_fact(f):
                pool.append(f)

    # Nếu không có primary_triggers hoặc không có fact khớp, dùng trigger thường.
    if not pool:
        weak_triggers = ctx_triggers - {"default"}
        for f in valid_facts:
            if weak_triggers & _triggers_of_fact(f):
                pool.append(f)

    # Cuối cùng mới fallback default.
    if not pool:
        for f in valid_facts:
            if "default" in _triggers_of_fact(f):
                pool.append(f)

    if not pool:
        pool = valid_facts

    # Sắp xếp nhẹ theo priority để fact quan trọng lên trước, nhưng vẫn giữ đủ pool để JS xoay vòng.
    try:
        pool = sorted(pool, key=lambda f: float(f.get("priority", 1) or 1), reverse=True)
    except Exception:
        pass

    # Giới hạn pool để payload HTML gọn, nhưng vẫn đủ đa dạng.
    pool = pool[:24]

    # Chọn fact đầu tiên theo logic server để lần render đầu vẫn hợp lý.
    recent_ids = st.session_state.get(FACT_HISTORY_KEY, [])
    first_fact = select_micro_fact(context=context, recent_ids=recent_ids, facts=pool, language="vi")
    if first_fact:
        remember_fact(st.session_state, str(first_fact.get("id", "")))
    else:
        first_fact = pool[0]

    # Đưa first_fact lên đầu pool, bỏ trùng id/text.
    ordered = []
    seen = set()
    for f in [first_fact] + pool:
        fid = str(f.get("id", "") or f.get("text", ""))
        txt = str(f.get("text", "")).strip()
        key = fid + "|" + txt
        if txt and key not in seen:
            seen.add(key)
            ordered.append({"id": fid, "text": txt})

    if not ordered:
        return

    facts_json = json.dumps(ordered, ensure_ascii=False)
    sig_src = "|".join(item["id"] + ":" + item["text"] for item in ordered)
    pool_sig = hashlib.md5(sig_src.encode("utf-8")).hexdigest()[:12]
    safe_prefix = "".join(ch if ch.isalnum() else "_" for ch in str(key_prefix))
    storage_key = f"tripsmart_microfact_idx_{safe_prefix}"
    sig_key = f"tripsmart_microfact_sig_{safe_prefix}"

    # Dùng components.html để JS chạy trong browser.
    # JS tạo/ cập nhật card ở parent.document nên không bị giới hạn bởi iframe height.
    components.html(
        f"""
        <script>
        (function() {{
            const FACTS = {facts_json};
            const ROTATE_MS = 300000;
            const STORAGE_KEY = {json.dumps(storage_key)};
            const SIG_KEY = {json.dumps(sig_key)};
            const POOL_SIG = {json.dumps(pool_sig)};
            const CARD_ID = "tripsmart-microfact-client-card";
            const STYLE_ID = "tripsmart-microfact-client-style";

            const doc = window.parent && window.parent.document ? window.parent.document : document;
            if (!FACTS || !FACTS.length) return;

            let oldSig = window.sessionStorage.getItem(SIG_KEY);
            if (oldSig !== POOL_SIG) {{
                window.sessionStorage.setItem(SIG_KEY, POOL_SIG);
                window.sessionStorage.setItem(STORAGE_KEY, "0");
            }}

            let idx = parseInt(window.sessionStorage.getItem(STORAGE_KEY) || "0", 10);
            if (!Number.isFinite(idx) || idx < 0 || idx >= FACTS.length) idx = 0;

            let style = doc.getElementById(STYLE_ID);
            if (!style) {{
                style = doc.createElement("style");
                style.id = STYLE_ID;
                style.textContent = `
                    #tripsmart-microfact-client-card {{
                        position: fixed;
                        left: 18px;
                        bottom: 18px;
                        z-index: 2147483000;
                        width: min(360px, calc(100vw - 36px));
                        background: rgba(255, 255, 255, 0.96);
                        color: #1f2937;
                        border: 1px solid rgba(255, 71, 87, 0.18);
                        border-left: 5px solid #ff4757;
                        border-radius: 16px;
                        box-shadow: 0 14px 36px rgba(15, 23, 42, 0.16);
                        padding: 12px 14px;
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                        pointer-events: none;
                    }}
                    #tripsmart-microfact-client-card .ts-mf-line {{
                        margin: 0;
                        display: flex;
                        align-items: center;
                        gap: 8px;
                        font-size: 15px;
                        font-weight: 800;
                        line-height: 1.35;
                    }}
                    #tripsmart-microfact-client-card .ts-mf-bulb {{
                        flex: 0 0 auto;
                    }}
                    #tripsmart-microfact-client-card .ts-mf-text {{
                        overflow-wrap: anywhere;
                    }}
                    @media (max-width: 760px) {{
                        #tripsmart-microfact-client-card {{
                            left: 10px;
                            right: 10px;
                            bottom: 10px;
                            width: auto;
                            padding: 10px 12px;
                            border-radius: 14px;
                        }}
                        #tripsmart-microfact-client-card .ts-mf-line {{
                            font-size: 14px;
                        }}
                    }}
                `;
                doc.head.appendChild(style);
            }}

            let card = doc.getElementById(CARD_ID);
            if (!card) {{
                card = doc.createElement("div");
                card.id = CARD_ID;
                card.innerHTML = `
                    <p class="ts-mf-line">
                        <span class="ts-mf-bulb">💡</span>
                        <span class="ts-mf-text"></span>
                    </p>
                `;
                doc.body.appendChild(card);
            }}

            const textEl = card.querySelector(".ts-mf-text");

            function showFact(i) {{
                const fact = FACTS[i % FACTS.length];
                if (textEl) textEl.textContent = fact.text || "";
                window.sessionStorage.setItem(STORAGE_KEY, String(i % FACTS.length));
            }}

            showFact(idx);

            if (window.__tripsmartMicroFactTimer) {{
                clearInterval(window.__tripsmartMicroFactTimer);
            }}

            window.__tripsmartMicroFactTimer = setInterval(function() {{
                idx = (idx + 1) % FACTS.length;
                showFact(idx);
            }}, ROTATE_MS);
        }})();
        </script>
        """,
        height=0,
        width=0,
    )
