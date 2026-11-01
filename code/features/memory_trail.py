"""
features/memory_trail.py — Ký ức hành trình
Fix: _load_trails() tự repair file JSON sai format / thiếu key "trips"
"""

import json
import os
import uuid
import base64
import shutil
from datetime import datetime
from typing import List, Dict, Optional

try:
    from utils.logger import setup_logger
    logger = setup_logger(__name__)
except Exception:
    import logging
    logger = logging.getLogger(__name__)

# ── Đường dẫn ────────────────────────────────────────────────────────────────
_HERE       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR    = os.path.join(_HERE, "data")
MEDIA_DIR   = os.path.join(DATA_DIR, "media")
TRAILS_FILE = os.path.join(DATA_DIR, "memory_trails.json")

os.makedirs(DATA_DIR,  exist_ok=True)
os.makedirs(MEDIA_DIR, exist_ok=True)

EMOTION_LABELS = {1: "😞", 2: "😐", 3: "😊", 4: "😄", 5: "🤩"}

_EMPTY = {"trips": {}}


def _load_trails() -> Dict:
    """
    Đọc file JSON. Tự xử lý mọi trường hợp lỗi:
      - File không tồn tại  → trả về {"trips": {}}
      - File rỗng           → trả về {"trips": {}}
      - JSON lỗi cú pháp   → xoá file cũ, trả về {"trips": {}}
      - Thiếu key "trips"   → tự thêm key rồi lưu lại
    """
    if not os.path.exists(TRAILS_FILE):
        return {"trips": {}}

    try:
        with open(TRAILS_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()

        if not content:                      # file rỗng
            return {"trips": {}}

        data = json.loads(content)

        if not isinstance(data, dict):       # format hoàn toàn sai
            _reset_file()
            return {"trips": {}}

        # Tự thêm key "trips" nếu thiếu — đây là nguyên nhân lỗi hiện tại
        if "trips" not in data:
            data["trips"] = {}
            _save_trails(data)              # ghi lại để sửa file

        # Đảm bảo trips là dict, không phải list hay gì khác
        if not isinstance(data["trips"], dict):
            data["trips"] = {}
            _save_trails(data)

        return data

    except json.JSONDecodeError:
        logger.warning("memory_trails.json bị lỗi JSON — reset file")
        _reset_file()
        return {"trips": {}}
    except Exception as e:
        logger.error(f"_load_trails lỗi: {e}")
        return {"trips": {}}


def _save_trails(data: Dict):
    with open(TRAILS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _reset_file():
    """Xoá file cũ và tạo lại file mới với format đúng."""
    try:
        if os.path.exists(TRAILS_FILE):
            # Backup trước khi xoá
            bak = TRAILS_FILE + ".bak"
            os.replace(TRAILS_FILE, bak)
        _save_trails({"trips": {}})
    except Exception as e:
        logger.error(f"_reset_file lỗi: {e}")


def _trip_media_dir(trip_id: str) -> str:
    d = os.path.join(MEDIA_DIR, trip_id)
    os.makedirs(d, exist_ok=True)
    return d


class MemoryTrailEngine:

    # ─────────────────────────────────────────────────────────────────────────
    # Trip CRUD
    # ─────────────────────────────────────────────────────────────────────────

    def start_trip(self, user_id: str, title: str,
                   origin_name: str, dest_name: str) -> Dict:
        trip_id = f"trip_{uuid.uuid4().hex[:8]}"
        data    = _load_trails()                    # luôn có key "trips" giờ
        data["trips"][trip_id] = {
            "trip_id":     trip_id,
            "user_id":     user_id,
            "title":       title,
            "origin":      origin_name,
            "destination": dest_name,
            "started_at":  datetime.now().isoformat(),
            "checkpoints": [],
            "summary":     {},
        }
        _save_trails(data)
        logger.info(f"Bắt đầu hành trình: {trip_id}")
        return data["trips"][trip_id]

    def get_user_trips(self, user_id: str) -> List[Dict]:
        data  = _load_trails()
        trips = [t for t in data["trips"].values()
                 if isinstance(t, dict) and t.get("user_id") == user_id]
        return sorted(trips, key=lambda x: x.get("started_at", ""), reverse=True)

    def get_trip(self, trip_id: str) -> Optional[Dict]:
        return _load_trails()["trips"].get(trip_id)

    def delete_trip(self, trip_id: str):
        data = _load_trails()
        if trip_id in data["trips"]:
            del data["trips"][trip_id]
            _save_trails(data)
        mdir = os.path.join(MEDIA_DIR, trip_id)
        if os.path.isdir(mdir):
            shutil.rmtree(mdir)

    # ─────────────────────────────────────────────────────────────────────────
    # Checkpoint
    # ─────────────────────────────────────────────────────────────────────────

    def add_checkpoint(self, trip_id: str,
                       lat: float, lon: float,
                       name: str,
                       emotion: int = 3,
                       note: str = "",
                       weather: str = "",
                       speed_kmh: float = 0,
                       music: str = "",
                       media_paths: Optional[List[str]] = None) -> Dict:
        data = _load_trails()
        trip = data["trips"].get(trip_id)
        if not trip:
            logger.error(f"Không tìm thấy trip_id: {trip_id}")
            return {}

        cp = {
            "cp_id":         f"cp_{uuid.uuid4().hex[:6]}",
            "timestamp":     datetime.now().isoformat(),
            "lat":           lat,
            "lon":           lon,
            "name":          name,
            "emotion":       emotion,
            "emotion_label": EMOTION_LABELS.get(emotion, "😊"),
            "note":          note,
            "weather":       weather,
            "speed_kmh":     speed_kmh,
            "music":         music,
            "media":         media_paths or [],
        }
        trip.setdefault("checkpoints", []).append(cp)
        trip["summary"] = self._build_summary(trip["checkpoints"])
        _save_trails(data)
        return cp

    def update_checkpoint_media(self, trip_id: str, cp_id: str,
                                media_paths: List[str]):
        data = _load_trails()
        trip = data["trips"].get(trip_id, {})
        for cp in trip.get("checkpoints", []):
            if cp["cp_id"] == cp_id:
                cp.setdefault("media", []).extend(media_paths)
                trip["summary"] = self._build_summary(trip["checkpoints"])
                _save_trails(data)
                return cp
        return {}

    # ─────────────────────────────────────────────────────────────────────────
    # Lưu media
    # ─────────────────────────────────────────────────────────────────────────

    def save_media_bytes(self, trip_id: str, data_b64: str,
                         ext: str, prefix: str = "media") -> str:
        """Nhận base64 string, decode và lưu vào data/media/<trip_id>/."""
        mdir     = _trip_media_dir(trip_id)
        filename = f"{prefix}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(mdir, filename)
        raw      = base64.b64decode(data_b64.split(",")[-1])
        with open(filepath, "wb") as f:
            f.write(raw)
        logger.info(f"Lưu media: {filepath} ({len(raw)//1024} KB)")
        return filepath

    def save_media_file(self, trip_id: str, uploaded_file) -> str:
        """Lưu UploadedFile của Streamlit."""
        mdir     = _trip_media_dir(trip_id)
        ext      = uploaded_file.name.rsplit(".", 1)[-1].lower()
        filename = f"upload_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(mdir, filename)
        with open(filepath, "wb") as f:
            f.write(uploaded_file.read())
        return filepath

    def get_trip_media(self, trip_id: str) -> List[str]:
        mdir = os.path.join(MEDIA_DIR, trip_id)
        if not os.path.isdir(mdir):
            return []
        return [os.path.join(mdir, f)
                for f in sorted(os.listdir(mdir))
                if os.path.isfile(os.path.join(mdir, f))]

    # ─────────────────────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────────────────────

    def _build_summary(self, checkpoints: List[Dict]) -> Dict:
        if not checkpoints:
            return {}
        emotions = [cp.get("emotion", 3) for cp in checkpoints]
        avg_emo  = sum(emotions) / len(emotions)
        best     = max(checkpoints, key=lambda c: c.get("emotion", 0))

        mood_summary = "😊 Bình thường"
        for (lo, hi), label in [
            ((4.5, 5.1), "🤩 Tuyệt vời"),
            ((3.5, 4.5), "😄 Vui vẻ"),
            ((2.5, 3.5), "😊 Bình thường"),
            ((1.5, 2.5), "😐 Không tốt lắm"),
            ((0.0, 1.5), "😞 Buồn"),
        ]:
            if lo <= avg_emo < hi:
                mood_summary = label
                break

        total_media = sum(len(cp.get("media", [])) for cp in checkpoints)
        return {
            "total_checkpoints": len(checkpoints),
            "avg_emotion":       round(avg_emo, 1),
            "mood_summary":      mood_summary,
            "best_moment":       best.get("name", ""),
            "best_emotion":      EMOTION_LABELS.get(best.get("emotion", 3), "😊"),
            "total_media":       total_media,
        }