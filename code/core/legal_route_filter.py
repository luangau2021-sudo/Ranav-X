# core/legal_route_filter.py
# Bộ lọc luật giao thông cơ bản cho TripSmart Pro.
# Mục tiêu giai đoạn 1: tập trung Ô tô + Xe máy, chặn lỗi lớn nhất là xe máy bị dẫn lên cao tốc.
# Không thay OSRM; chỉ kiểm tra tuyến sau khi OSRM trả về.

# Bản v4 theo yêu cầu: không giới hạn độ dài tuyến fallback.
# Sau khi loại tuyến sai luật, app chọn tuyến hợp lệ ngắn nhất trong các tuyến tìm được.

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Tuple

try:
    from core.motorbike_corridors import get_motorbike_corridor_candidates
except Exception:
    get_motorbike_corridor_candidates = None

# Các từ khóa thường xuất hiện trong step/instruction/tên đường khi route có cao tốc.
# OSRM public server không phải lúc nào trả full OSM tags nên ta kiểm tra cả instruction/name/ref.
EXPRESSWAY_KEYWORDS = (
    "cao tốc",
    "duong cao toc",
    "đường cao tốc",
    "duong cao tốc",
    "expressway",
    "motorway",
    "motorway_link",
    "freeway",
    "highway",
    "đct",
    "dct",
    "ct.",
    "ct ",
)

PRIVATE_OR_CONSTRUCTION_KEYWORDS = (
    "private",
    "access=no",
    "construction",
    "đang thi công",
    "dang thi cong",
    "công trường",
    "cong truong",
)

MODE_LABELS = {
    "car": "ô tô",
    "motorbike": "xe máy",
}


def normalize_mode(mode: str | None) -> str:
    """App mới chỉ dùng car/motorbike. Các mode cũ được ép về motorbike để không lỗi."""
    m = str(mode or "car").strip().lower()
    if m in {"car", "auto", "automobile", "driving"}:
        return "car"
    if m in {"motorbike", "motorcycle", "moto", "bike", "scooter"}:
        return "motorbike"
    return "car"


def _strip_accents_basic(text: str) -> str:
    """Chuẩn hóa nhẹ để bắt được ĐCT / DCT / cao tốc."""
    repl = {
        "đ": "d", "Đ": "D",
        "á": "a", "à": "a", "ả": "a", "ã": "a", "ạ": "a",
        "ă": "a", "ắ": "a", "ằ": "a", "ẳ": "a", "ẵ": "a", "ặ": "a",
        "â": "a", "ấ": "a", "ầ": "a", "ẩ": "a", "ẫ": "a", "ậ": "a",
        "é": "e", "è": "e", "ẻ": "e", "ẽ": "e", "ẹ": "e",
        "ê": "e", "ế": "e", "ề": "e", "ể": "e", "ễ": "e", "ệ": "e",
        "í": "i", "ì": "i", "ỉ": "i", "ĩ": "i", "ị": "i",
        "ó": "o", "ò": "o", "ỏ": "o", "õ": "o", "ọ": "o",
        "ô": "o", "ố": "o", "ồ": "o", "ổ": "o", "ỗ": "o", "ộ": "o",
        "ơ": "o", "ớ": "o", "ờ": "o", "ở": "o", "ỡ": "o", "ợ": "o",
        "ú": "u", "ù": "u", "ủ": "u", "ũ": "u", "ụ": "u",
        "ư": "u", "ứ": "u", "ừ": "u", "ử": "u", "ữ": "u", "ự": "u",
        "ý": "y", "ỳ": "y", "ỷ": "y", "ỹ": "y", "ỵ": "y",
    }
    return "".join(repl.get(ch, ch) for ch in text)


def _step_text(step: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ("instruction", "name", "ref", "highway", "road", "road_name", "mode"):
        val = step.get(key)
        if val:
            parts.append(str(val))
    # Một số route có raw step lồng trong key khác
    for key in ("raw", "osrm_step", "metadata", "tags"):
        val = step.get(key)
        if isinstance(val, dict):
            parts.extend(str(v) for v in val.values() if v is not None)
    text = " ".join(parts)
    text = text.lower()
    text_no_acc = _strip_accents_basic(text).lower()
    return text + " " + text_no_acc


def iter_route_steps(route: Dict[str, Any] | None) -> Iterable[Dict[str, Any]]:
    if not isinstance(route, dict):
        return []
    steps = route.get("steps") or []
    if isinstance(steps, list):
        return [s for s in steps if isinstance(s, dict)]
    return []


def route_has_expressway(route: Dict[str, Any] | None) -> Tuple[bool, str]:
    """Phát hiện tuyến có dấu hiệu cao tốc từ steps/instructions."""
    for step in iter_route_steps(route):
        txt = _step_text(step)
        # ĐCT thường xuất hiện dạng ĐCT01 / CT.01 / Cao tốc ...
        if re.search(r"\b(dct|đct)\s*\d*\b", txt) or re.search(r"\bct[ .-]?\d+\b", txt):
            return True, step.get("instruction") or step.get("name") or "cao tốc/ĐCT"
        for kw in EXPRESSWAY_KEYWORDS:
            if kw in txt:
                return True, step.get("instruction") or step.get("name") or kw
    return False, ""


def route_has_private_or_construction(route: Dict[str, Any] | None) -> Tuple[bool, str]:
    for step in iter_route_steps(route):
        txt = _step_text(step)
        for kw in PRIVATE_OR_CONSTRUCTION_KEYWORDS:
            if kw in txt:
                return True, step.get("instruction") or step.get("name") or kw
    return False, ""


def validate_route_for_mode(route: Dict[str, Any] | None, mode: str | None) -> Tuple[bool, List[str]]:
    """
    Kiểm tra tuyến có phù hợp với phương tiện không.
    Trả về (ok, issues). Giai đoạn 1 chỉ chắc nhất ở việc chặn xe máy lên cao tốc.
    """
    mode = normalize_mode(mode)
    issues: List[str] = []

    if not route or not route.get("polyline"):
        return False, ["Tuyến không có polyline hợp lệ."]

    if route.get("crosses_border"):
        issues.append("Tuyến có dấu hiệu đi ra ngoài lãnh thổ Việt Nam.")

    private_hit, private_detail = route_has_private_or_construction(route)
    if private_hit:
        issues.append(f"Tuyến có đoạn private/construction: {private_detail}")

    expressway_hit, expressway_detail = route_has_expressway(route)
    if mode == "motorbike" and expressway_hit:
        issues.append(f"Tuyến có đoạn cao tốc/ĐCT, không phù hợp với xe máy: {expressway_detail}")

    # Ô tô được phép đi cao tốc, nên không chặn expressway cho car.
    return len(issues) == 0, issues


def filter_routes_for_mode(routes: List[Dict[str, Any]] | None, mode: str | None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Tách routes thành hợp lệ và bị loại, lưu issue vào route['legal_issues']."""
    valid: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    for idx, route in enumerate(routes or []):
        if not route:
            continue
        ok, issues = validate_route_for_mode(route, mode)
        route["legal_checked"] = True
        route["legal_ok"] = bool(ok)
        route["legal_issues"] = issues
        route["legal_rank"] = idx
        if ok:
            valid.append(route)
        else:
            rejected.append(route)
    return valid, rejected


def is_reasonable_detour(original_km: float | int | None, new_km: float | int | None) -> bool:
    """Không nhận tuyến vòng quá xa phi lý."""
    try:
        old = float(original_km or 0.0)
        new = float(new_km or 0.0)
    except Exception:
        return True
    if old <= 0 or new <= 0:
        return True
    if old <= 30:
        return new <= old + 8.0
    if old <= 150:
        return new <= old * 1.30
    return new <= old + 40.0


def detour_limit_text(original_km: float | int | None) -> str:
    try:
        old = float(original_km or 0.0)
    except Exception:
        return "không quá xa phi lý"
    if old <= 30:
        return f"tối đa khoảng {old + 8.0:.1f} km"
    if old <= 150:
        return f"tối đa khoảng {old * 1.30:.1f} km"
    return f"tối đa khoảng {old + 40.0:.1f} km"



def is_reasonable_motorbike_avoid_expressway(original_km: float | int | None, new_km: float | int | None) -> bool:
    """Giới hạn riêng cho xe máy khi tuyến tham chiếu là tuyến cao tốc bị cấm.

    Không được so quá chặt với tuyến ô tô đi cao tốc, vì xe máy bắt buộc phải đi
    đường gom/quốc lộ nên dài hơn là bình thường. Vẫn có trần để tránh vòng phi lý.
    """
    try:
        old = float(original_km or 0.0)
        new = float(new_km or 0.0)
    except Exception:
        return True
    if old <= 0 or new <= 0:
        return True
    if old <= 30:
        limit = max(old + 25.0, old * 2.0, 55.0)
    elif old <= 60:
        # Case TP.HCM → Long Thành: tuyến hợp lệ xe máy ~58–62 km,
        # còn tuyến cao tốc bị cấm ngắn hơn nhiều. Cho phép đến khoảng 70 km.
        limit = max(old + 35.0, old * 1.75, 70.0)
    elif old <= 150:
        limit = max(old + 45.0, old * 1.55)
    else:
        limit = old + 80.0
    return new <= limit


def motorbike_avoid_expressway_limit_text(original_km: float | int | None) -> str:
    try:
        old = float(original_km or 0.0)
    except Exception:
        return "không quá xa phi lý"
    if old <= 30:
        limit = max(old + 25.0, old * 2.0, 55.0)
    elif old <= 60:
        limit = max(old + 35.0, old * 1.75, 70.0)
    elif old <= 150:
        limit = max(old + 45.0, old * 1.55)
    else:
        limit = old + 80.0
    return f"tối đa khoảng {limit:.1f} km"

# ─────────────────────────────────────────────────────────────────────────────
# Vehicle legal fallback routing
# ─────────────────────────────────────────────────────────────────────────────

def _route_distance_km_safe(route: Dict[str, Any] | None) -> float:
    try:
        if not route:
            return 0.0
        if route.get("distance_km") is not None:
            return float(route.get("distance_km") or 0.0)
        dist = route.get("distance")
        if dist is not None:
            dist = float(dist)
            return dist / 1000.0 if dist > 1000 else dist
    except Exception:
        pass
    return 0.0


def _dedupe_routes(routes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for r in routes or []:
        if not r or not r.get("polyline"):
            continue
        pl = r.get("polyline") or []
        if pl:
            key = (
                round(float(pl[0][0]), 4), round(float(pl[0][1]), 4),
                round(float(pl[-1][0]), 4), round(float(pl[-1][1]), 4),
                round(_route_distance_km_safe(r), 1),
                str(r.get("duration_text") or r.get("duration") or ""),
            )
        else:
            key = (round(_route_distance_km_safe(r), 1), str(r.get("label") or ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _make_detour_waypoints(origin: Tuple[float, float], destination: Tuple[float, float]) -> List[Tuple[float, float]]:
    """Tạo waypoint vòng quanh đường thẳng để ép OSRM thử tuyến khác.

    Không dùng dữ liệu Google. Đây chỉ là fallback mềm: nếu waypoint rơi vào nơi không có đường
    thì Router/OSRM sẽ tự fail và ta bỏ qua.
    """
    try:
        lat1, lon1 = float(origin[0]), float(origin[1])
        lat2, lon2 = float(destination[0]), float(destination[1])
        mid_lat = (lat1 + lat2) / 2.0
        mid_lon = (lon1 + lon2) / 2.0
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        # vector vuông góc, chuẩn hóa thô theo độ kinh/vĩ
        norm = (dlat * dlat + dlon * dlon) ** 0.5 or 1.0
        p_lat = -dlon / norm
        p_lon = dlat / norm
        # 1 độ vĩ khoảng 111km. Ở VN, 1 độ kinh khoảng 100-109km, dùng 105km để đủ tốt.
        waypoints: List[Tuple[float, float]] = []
        for km in (6, 10, 16, 24, 32):
            off_lat = p_lat * (km / 111.0)
            off_lon = p_lon * (km / 105.0)
            waypoints.append((mid_lat + off_lat, mid_lon + off_lon))
            waypoints.append((mid_lat - off_lat, mid_lon - off_lon))
        # thêm các điểm quanh 1/3 và 2/3 tuyến để tránh trường hợp midpoint nằm trên cao tốc
        for frac in (0.33, 0.66):
            base_lat = lat1 + dlat * frac
            base_lon = lon1 + dlon * frac
            for km in (8, 16):
                off_lat = p_lat * (km / 111.0)
                off_lon = p_lon * (km / 105.0)
                waypoints.append((base_lat + off_lat, base_lon + off_lon))
                waypoints.append((base_lat - off_lat, base_lon - off_lon))
        return waypoints
    except Exception:
        return []


def _add_candidate(candidates: List[Dict[str, Any]], route: Dict[str, Any] | None, source: str) -> None:
    if route and isinstance(route, dict) and route.get("polyline"):
        route.setdefault("fallback_source", source)
        route.setdefault("label", source)
        candidates.append(route)




def _combine_route_parts(parts: List[Dict[str, Any]], source: str = "Motorbike corridor") -> Dict[str, Any] | None:
    """Ghép nhiều route chặng thành một route tổng."""
    if not parts:
        return None
    combined_poly: List[List[float]] = []
    combined_steps: List[Dict[str, Any]] = []
    distance_km = 0.0
    duration_sec = 0.0
    for part in parts:
        if not part or not part.get("polyline"):
            return None
        pl = part.get("polyline") or []
        for p in pl:
            try:
                cur = [float(p[0]), float(p[1])]
            except Exception:
                continue
            if not combined_poly or (round(combined_poly[-1][0], 6), round(combined_poly[-1][1], 6)) != (round(cur[0], 6), round(cur[1], 6)):
                combined_poly.append(cur)
        if isinstance(part.get("steps"), list):
            combined_steps.extend([s for s in part.get("steps") if isinstance(s, dict)])
        distance_km += _route_distance_km_safe(part)
        try:
            dur = part.get("duration_seconds") or part.get("duration") or 0
            dur = float(dur)
            if dur > 0:
                # OSRM có thể trả duration giây; một số app trả phút/giờ text thì bỏ qua
                duration_sec += dur if dur > 120 else dur * 60.0
        except Exception:
            pass
    if len(combined_poly) < 2:
        return None
    out: Dict[str, Any] = dict(parts[0])
    out["polyline"] = combined_poly
    out["steps"] = combined_steps
    out["distance_km"] = distance_km
    out["distance_text"] = f"{distance_km:.1f} km" if distance_km else out.get("distance_text")
    if duration_sec:
        out["duration_seconds"] = duration_sec
    out["fallback_source"] = source
    out["label"] = source
    out["corridor_route"] = True
    return out


def _try_corridor_route(router: Any, origin: Tuple[float, float], destination: Tuple[float, float], corridor: Dict[str, Any], mode: str) -> List[Dict[str, Any]]:
    """Tạo route xe máy qua corridor bằng 2 cách: request waypoint tổng và ghép từng chặng."""
    out: List[Dict[str, Any]] = []
    waypoints = corridor.get("waypoints") or []
    if not waypoints:
        return out
    source = "Hành lang xe máy: " + str(corridor.get("name") or "corridor")

    # Cách 1: gọi Router một lần với nhiều waypoint nếu router hỗ trợ.
    try:
        r = router.get_route(origin, destination, mode=mode, waypoints=waypoints)
        _add_candidate(out, r, source)
    except Exception:
        pass

    # Cách 2: chắc hơn: gọi từng chặng rồi ghép polyline.
    try:
        pts = [origin] + list(waypoints) + [destination]
        parts: List[Dict[str, Any]] = []
        ok = True
        for a, b in zip(pts[:-1], pts[1:]):
            try:
                leg = router.get_route(a, b, mode=mode)
                if not leg or not leg.get("polyline"):
                    ok = False
                    break
                parts.append(leg)
            except Exception:
                ok = False
                break
        if ok and parts:
            combined = _combine_route_parts(parts, source=source + " · ghép chặng")
            _add_candidate(out, combined, source + " · ghép chặng")
    except Exception:
        pass
    return out

def find_vehicle_legal_routes(router: Any,
                              origin: Tuple[float, float],
                              destination: Tuple[float, float],
                              mode: str | None,
                              prefer_alternatives: bool = False,
                              max_routes: int = 3) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], str]:
    """Tìm tuyến hợp lệ với phương tiện bằng nhiều tầng fallback.

    Trả về: (valid_routes, rejected_routes, note)
    - Không dừng ngay khi OSRM trả tuyến cao tốc cho xe máy.
    - Thử: route chính → alternatives → waypoint vòng.
    - Không giới hạn km; chọn tuyến hợp lệ ngắn nhất theo phương tiện.
    """
    mode = normalize_mode(mode)
    candidates: List[Dict[str, Any]] = []
    rejected_all: List[Dict[str, Any]] = []
    notes: List[str] = []

    # 1) Tuyến chính
    try:
        r = router.get_route(origin, destination, mode=mode)
        _add_candidate(candidates, r, "Tuyến chính")
    except Exception as e:
        notes.append(f"Tuyến chính lỗi: {e}")

    # 2) Alternatives luôn thử cho xe máy nếu tuyến chính có thể bị cao tốc.
    try:
        alt_count = 5 if mode == "motorbike" else (5 if prefer_alternatives else 3)
        alts = router.get_alternative_routes(origin, destination, mode=mode, count=alt_count) or []
        for i, r in enumerate(alts, 1):
            _add_candidate(candidates, r, f"Tuyến thay thế {i}")
    except Exception as e:
        notes.append(f"Tuyến thay thế lỗi: {e}")

    candidates = _dedupe_routes(candidates)
    reference_km = 0.0
    for r in candidates:
        reference_km = _route_distance_km_safe(r)
        if reference_km > 0:
            break

    valid, rejected = filter_routes_for_mode(candidates, mode)
    rejected_all.extend(rejected)
    if valid:
        # Sắp xếp hợp lệ theo khoảng cách vừa phải, giữ tối đa max_routes.
        valid.sort(key=lambda r: _route_distance_km_safe(r) or 10**9)
        return valid[:max_routes], rejected_all, "✅ Đã tìm được tuyến hợp lệ với phương tiện."

    # 3) Corridor fallback cho xe máy: ưu tiên hành lang địa phương có thật, không dùng waypoint ngẫu nhiên trước.
    corridor_candidates: List[Dict[str, Any]] = []
    if mode == "motorbike" and get_motorbike_corridor_candidates is not None:
        try:
            for corridor in get_motorbike_corridor_candidates(origin, destination):
                corridor_candidates.extend(_try_corridor_route(router, origin, destination, corridor, mode))
        except Exception as e:
            notes.append(f"Corridor fallback lỗi: {e}")

        corridor_candidates = _dedupe_routes(corridor_candidates)
        valid_c, rejected_c = filter_routes_for_mode(corridor_candidates, mode)
        rejected_all.extend(rejected_c)
        if valid_c:
            valid_c.sort(key=lambda r: _route_distance_km_safe(r) or 10**9)
            return valid_c[:max_routes], rejected_all, "✅ Tuyến chính bị loại, app đã chọn tuyến xe máy theo hành lang an toàn địa phương."

    # 4) Waypoint fallback cuối cùng: chỉ dùng khi không có corridor phù hợp.
    waypoint_candidates: List[Dict[str, Any]] = []
    if mode == "motorbike":
        for idx, wp in enumerate(_make_detour_waypoints(origin, destination), 1):
            try:
                r = router.get_route(origin, destination, mode=mode, waypoints=[wp])
                _add_candidate(waypoint_candidates, r, f"Tuyến vòng thử {idx}")
            except Exception:
                continue

        waypoint_candidates = _dedupe_routes(waypoint_candidates)
        # Không giới hạn km: lấy tuyến ngắn nhất trong các tuyến đáp ứng luật phương tiện.
        valid2, rejected2 = filter_routes_for_mode(waypoint_candidates, mode)
        rejected_all.extend(rejected2)
        if valid2:
            valid2.sort(key=lambda r: _route_distance_km_safe(r) or 10**9)
            return valid2[:max_routes], rejected_all, "✅ Tuyến chính bị loại, app đã chọn tuyến hợp lệ ngắn nhất theo phương tiện."

    note = "⚠️ App đã thử tuyến chính, tuyến thay thế và waypoint vòng nhưng chưa có tuyến hợp lệ."
    if notes:
        note += " " + " | ".join(notes[:2])
    return [], rejected_all, note



def find_legal_routes_with_fallback(router: Any,
                                    origin: Tuple[float, float],
                                    destination: Tuple[float, float],
                                    mode: str | None,
                                    count: int = 3,
                                    prefer_alternatives: bool = True):
    """Wrapper tương thích với app.py.

    App cũ gọi tên find_legal_routes_with_fallback(..., count=3).
    Bộ lọc mới dùng find_vehicle_legal_routes(..., max_routes=...).
    Hàm này nối 2 cách gọi để tránh NameError/TypeError.

    Trả về: (valid_routes, rejected_routes, attempts)
    """
    valid_routes, rejected_routes, note = find_vehicle_legal_routes(
        router=router,
        origin=origin,
        destination=destination,
        mode=mode,
        prefer_alternatives=prefer_alternatives,
        max_routes=count,
    )
    attempts = [note]
    try:
        if rejected_routes:
            attempts.append(f"Đã loại {len(rejected_routes)} tuyến không phù hợp với phương tiện.")
            for idx, r in enumerate(rejected_routes[:5], 1):
                issues = r.get("legal_issues") or []
                if issues:
                    attempts.append(f"Tuyến bị loại {idx}: " + "; ".join(map(str, issues[:2])))
    except Exception:
        pass
    return valid_routes, rejected_routes, attempts
