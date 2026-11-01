# core/microlearning.py
# Chọn fact/mẹo ngắn theo ngữ cảnh để hiển thị dạng nudge nhỏ, không gây xao nhãng.

import json
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

FACT_HISTORY_KEY = "micro_fact_recent_ids"
FACT_LAST_TS_KEY = "micro_fact_last_ts"
FACT_LAST_ID_KEY = "micro_fact_last_id"

DEFAULT_FACTS_PATHS = [
    Path("data/micro_facts.json"),
    Path("micro_facts.json"),
]

# Trigger mạnh: khi có các trigger này thì KHÔNG chọn fact default lan man nữa.
# Thứ tự thể hiện mức ưu tiên khi nhiều ngữ cảnh cùng xuất hiện.
STRONG_TRIGGER_PRIORITY = [
    "sos",
    "disaster",
    "flood",
    "landslide",
    "storm",
    "rain",
    "fog",
    "wind",
    "mountain",
    "slope",
    "night",
    "high_speed",
    "speed",
    "traffic",
    "fatigue",
    "risk",
]

WEATHER_RAIN_WORDS = [
    "rain", "mưa", "shower", "drizzle", "storm", "dông", "giông", "thunder",
    "bão", "áp thấp", "mưa nhẹ", "mưa vừa", "mưa lớn"
]
WEATHER_FOG_WORDS = ["fog", "sương", "sương mù", "mist", "mù"]
WEATHER_WIND_WORDS = ["wind", "gió", "gió mạnh"]
FLOOD_WORDS = ["flood", "ngập", "lụt", "lũ", "nước dâng", "ngập nước"]
LANDSLIDE_WORDS = ["landslide", "sạt", "sạt lở", "taluy", "đá rơi", "sụt lún"]
MOUNTAIN_WORDS = ["pass", "đèo", "dốc", "cua tay áo", "núi", "mountain", "slope"]
TRAFFIC_WORDS = ["kẹt xe", "ùn tắc", "traffic", "jam", "tắc đường"]
SOS_WORDS = ["sos", "khẩn cấp", "cấp cứu", "tai nạn"]


def _norm_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _has_any(text: str, words: List[str]) -> bool:
    text = _norm_text(text)
    return any(w in text for w in words)


def load_fact_bank(path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Đọc kho fact từ JSON.

    Ưu tiên:
    1) data/micro_facts.json
    2) micro_facts.json

    Nếu file không tồn tại, rỗng, sai format, hoặc facts=[] thì dùng fallback tối thiểu.
    """
    paths = [Path(path)] if path else DEFAULT_FACTS_PATHS
    for p in paths:
        try:
            if not p.exists():
                continue

            raw = p.read_text(encoding="utf-8").strip()
            if not raw:
                continue

            data = json.loads(raw)
            facts = data.get("facts", data) if isinstance(data, dict) else data
            if not isinstance(facts, list):
                continue

            cleaned = [
                f for f in facts
                if isinstance(f, dict)
                and f.get("active", True)
                and str(f.get("text", "")).strip()
            ]
            # Quan trọng: nếu file có facts=[] thì không trả về list rỗng.
            # Trả về rỗng sẽ làm app không còn dữ liệu để chọn.
            if cleaned:
                return cleaned
        except Exception:
            continue

    return [
        {
            "id": "fallback_distance_4s",
            "category": "distance",
            "trigger": ["default", "distance"],
            "text": "Giữ khoảng cách 4 giây để có thêm thời gian phản ứng.",
            "priority": 5,
            "active": True,
            "language": "vi",
        },
        {
            "id": "fallback_rain_brake",
            "category": "weather",
            "trigger": ["rain", "weather"],
            "text": "Mưa làm quãng phanh dài hơn, hãy giữ khoảng cách xa hơn.",
            "priority": 9,
            "active": True,
            "language": "vi",
        },
        {
            "id": "fallback_night_speed",
            "category": "night",
            "trigger": ["night"],
            "text": "Ban đêm tầm nhìn ngắn hơn, nên giảm tốc trước khúc cua.",
            "priority": 8,
            "active": True,
            "language": "vi",
        },
        {
            "id": "fallback_mountain_curve",
            "category": "mountain",
            "trigger": ["mountain", "slope"],
            "text": "Trên đường đèo, hãy giảm tốc trước khúc cua khuất tầm nhìn.",
            "priority": 8,
            "active": True,
            "language": "vi",
        },
        {
            "id": "fallback_flood_turnaround",
            "category": "flood",
            "trigger": ["flood", "rain"],
            "text": "Không đi vào vùng ngập nếu không biết độ sâu và tình trạng mặt đường.",
            "priority": 10,
            "active": True,
            "language": "vi",
        },
    ]


def build_micro_context(
    mode: Optional[str] = None,
    weather_text: Optional[str] = None,
    route_risk_forecast: Optional[Dict[str, Any]] = None,
    danger_markers: Optional[List[Dict[str, Any]]] = None,
    speed_kmh: Optional[float] = None,
    is_night: Optional[bool] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Gom ngữ cảnh thành trigger.

    Điểm sửa chính:
    - Có trigger ngày/đêm rõ ràng: night hoặc day.
    - Mưa/sương/gió/ngập/sạt/đèo được lấy từ cả weather_text, weather_alerts,
      hazard_label, hazard_type, danger_markers.
    - Có primary_triggers để bộ chọn fact ưu tiên đúng ngữ cảnh.
    """
    triggers: Set[str] = {"default"}

    mode_s = _norm_text(mode)
    if mode_s:
        triggers.add(mode_s)

    wx = _norm_text(weather_text)
    if _has_any(wx, WEATHER_RAIN_WORDS):
        triggers.update(["weather", "rain"])
        if _has_any(wx, ["storm", "dông", "giông", "thunder", "bão", "áp thấp"]):
            triggers.add("storm")
    if _has_any(wx, WEATHER_FOG_WORDS):
        triggers.update(["weather", "fog"])
    if _has_any(wx, WEATHER_WIND_WORDS):
        triggers.update(["weather", "wind"])
    if _has_any(wx, FLOOD_WORDS):
        triggers.update(["flood", "weather"])
    if _has_any(wx, LANDSLIDE_WORDS):
        triggers.update(["landslide", "mountain"])
    if _has_any(wx, TRAFFIC_WORDS):
        triggers.add("traffic")
    if _has_any(wx, SOS_WORDS):
        triggers.add("sos")

    if is_night is None:
        try:
            hour = time.localtime().tm_hour
            is_night = hour >= 18 or hour <= 5
        except Exception:
            is_night = False
    triggers.add("night" if is_night else "day")

    try:
        if speed_kmh is not None and float(speed_kmh) >= 60:
            triggers.update(["speed", "high_speed"])
    except Exception:
        pass

    if route_risk_forecast:
        level = _norm_text(route_risk_forecast.get("overall_level"))
        if level in {"medium", "high", "very_high"}:
            triggers.add("risk")

        # Đọc nhiều đoạn hơn để không bỏ sót đoạn ngữ cảnh đang ở gần phía trước.
        for seg in route_risk_forecast.get("attention_segments", [])[:10]:
            hz = _norm_text(
                " ".join(str(seg.get(k, "")) for k in [
                    "hazard_type", "hazard_label", "label", "desc", "name"
                ])
            )
            alerts = _norm_text(" ".join(seg.get("weather_alerts", []) or []))
            txt = f"{hz} {alerts}"

            if _has_any(txt, FLOOD_WORDS):
                triggers.update(["flood", "weather"])
            if _has_any(txt, LANDSLIDE_WORDS):
                triggers.update(["landslide", "mountain"])
            if _has_any(txt, MOUNTAIN_WORDS):
                triggers.update(["mountain", "slope"])
            if _has_any(txt, WEATHER_RAIN_WORDS):
                triggers.update(["weather", "rain"])
                if _has_any(txt, ["storm", "dông", "giông", "thunder", "bão", "áp thấp"]):
                    triggers.add("storm")
            if _has_any(txt, WEATHER_FOG_WORDS):
                triggers.update(["weather", "fog"])
            if _has_any(txt, WEATHER_WIND_WORDS):
                triggers.update(["weather", "wind"])
            if _has_any(txt, TRAFFIC_WORDS):
                triggers.add("traffic")

    for m in danger_markers or []:
        txt = _norm_text(" ".join(str(m.get(k, "")) for k in [
            "type", "label", "desc", "name", "hazard_type", "hazard_label"
        ]))
        if _has_any(txt, FLOOD_WORDS):
            triggers.update(["flood", "weather"])
        if _has_any(txt, LANDSLIDE_WORDS):
            triggers.update(["landslide", "mountain"])
        if _has_any(txt, MOUNTAIN_WORDS):
            triggers.update(["mountain", "slope"])
        if _has_any(txt, WEATHER_RAIN_WORDS):
            triggers.update(["weather", "rain"])
        if _has_any(txt, TRAFFIC_WORDS):
            triggers.add("traffic")

    if extra:
        for k, v in extra.items():
            if bool(v):
                triggers.add(_norm_text(k))

    primary = [t for t in STRONG_TRIGGER_PRIORITY if t in triggers]

    return {
        "triggers": sorted(t for t in triggers if t),
        "primary_triggers": primary,
        "is_night": bool(is_night),
    }


def _fact_triggers(fact: Dict[str, Any]) -> Set[str]:
    trg = fact.get("trigger", [])
    if isinstance(trg, str):
        trg = [trg]
    return {_norm_text(x) for x in trg if _norm_text(x)}


def _valid_fact_language(fact: Dict[str, Any], language: str) -> bool:
    lang = _norm_text(fact.get("language", language))
    return lang in {_norm_text(language), "", "vi"}


def _candidate_score(
    fact: Dict[str, Any],
    fact_triggers: Set[str],
    ctx_triggers: Set[str],
    primary_triggers: List[str],
    recent: Set[str],
) -> float:
    fid = str(fact.get("id", ""))
    category = _norm_text(fact.get("category", ""))
    base = float(fact.get("priority", 1) or 1)

    overlap = ctx_triggers & fact_triggers
    primary_overlap = set(primary_triggers) & fact_triggers

    score = base
    score += len(overlap) * 4
    score += len(primary_overlap) * 12

    # Nếu category trùng primary trigger thì tăng mạnh.
    if category in primary_triggers:
        score += 10

    # Nếu fact vừa đúng nhiều trigger cùng lúc, ví dụ night + rain, ưu tiên cao.
    if len(primary_overlap) >= 2:
        score += 12

    # Không cấm hẳn fact cũ nếu kho fact quá ít, nhưng giảm mạnh.
    if fid in recent:
        score *= 0.08

    return max(0.1, score)


def select_micro_fact(
    context: Optional[Dict[str, Any]] = None,
    recent_ids: Optional[List[str]] = None,
    facts: Optional[List[Dict[str, Any]]] = None,
    language: str = "vi",
) -> Optional[Dict[str, Any]]:
    """
    Chọn fact đúng ngữ cảnh.

    Khác bản cũ:
    - Nếu có ngữ cảnh mạnh như rain/night/flood/mountain thì chỉ chọn fact trùng
      các trigger đó trước, không cho default chen vào.
    - Chỉ fallback về default khi không có fact nào khớp ngữ cảnh.
    - Nếu có fact chưa xuất hiện gần đây thì loại fact cũ khỏi pool.
    """
    facts = facts or load_fact_bank()
    if not facts:
        return None

    recent = set(recent_ids or [])
    ctx = context or {}
    ctx_triggers = set(ctx.get("triggers", ["default"])) or {"default"}
    primary_triggers = list(ctx.get("primary_triggers", []))

    valid: List[Tuple[Dict[str, Any], Set[str]]] = []
    for fact in facts:
        if not fact.get("active", True):
            continue
        if not _valid_fact_language(fact, language):
            continue
        if not str(fact.get("text", "")).strip():
            continue
        valid.append((fact, _fact_triggers(fact) or {"default"}))

    if not valid:
        return None

    # 1) Có ngữ cảnh mạnh → bắt buộc ưu tiên fact khớp trigger mạnh.
    pool: List[Tuple[float, Dict[str, Any]]] = []
    if primary_triggers:
        primary_set = set(primary_triggers)
        for fact, ftrg in valid:
            if primary_set & ftrg:
                pool.append((
                    _candidate_score(fact, ftrg, ctx_triggers, primary_triggers, recent),
                    fact
                ))

    # 2) Nếu không có fact khớp trigger mạnh, dùng fact khớp trigger thường.
    if not pool:
        weak_triggers = ctx_triggers - {"default"}
        for fact, ftrg in valid:
            if weak_triggers & ftrg:
                pool.append((
                    _candidate_score(fact, ftrg, ctx_triggers, primary_triggers, recent),
                    fact
                ))

    # 3) Cuối cùng mới dùng default.
    if not pool:
        for fact, ftrg in valid:
            if "default" in ftrg:
                pool.append((
                    _candidate_score(fact, ftrg, ctx_triggers, primary_triggers, recent),
                    fact
                ))

    if not pool:
        pool = [
            (_candidate_score(fact, ftrg, ctx_triggers, primary_triggers, recent), fact)
            for fact, ftrg in valid
        ]

    # Nếu còn đủ lựa chọn mới, loại các fact vừa hiện gần đây.
    non_recent_pool = [(w, f) for w, f in pool if str(f.get("id", "")) not in recent]
    if len(non_recent_pool) >= 2:
        pool = non_recent_pool

    weights = [w for w, _ in pool]
    return random.choices([f for _, f in pool], weights=weights, k=1)[0]


def remember_fact(st_session_state: Any, fact_id: str, limit: int = 12) -> None:
    """Lưu vài fact gần nhất vào st.session_state để tránh lặp."""
    if not fact_id:
        return
    recent = list(st_session_state.get(FACT_HISTORY_KEY, []))
    recent = [x for x in recent if x != fact_id]
    recent.insert(0, fact_id)
    st_session_state[FACT_HISTORY_KEY] = recent[:limit]
    st_session_state[FACT_LAST_ID_KEY] = fact_id
    st_session_state[FACT_LAST_TS_KEY] = time.time()
