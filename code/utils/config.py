import os

# ============================================================
# ĐỌC .ENV NHẸ, KHÔNG BẮT BUỘC python-dotenv
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))


def _load_env_file() -> None:
    """Nạp biến môi trường từ file .env ở thư mục gốc project nếu có."""
    env_path = os.path.join(PROJECT_DIR, ".env")
    if not os.path.exists(env_path):
        return

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        # Không làm app crash nếu .env lỗi format
        pass


_load_env_file()


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


# ============================================================
# API KEYS
# Ưu tiên lấy từ .env / biến môi trường. Không hard-code key trong code.
# ============================================================
GOOGLE_MAPS_API_KEY = _env("GOOGLE_MAPS_API_KEY", "YOUR_GOOGLE_MAPS_API_KEY")
OPENWEATHER_API_KEY = _env("OPENWEATHER_API_KEY", "YOUR_OPENWEATHER_API_KEY")
OPENROUTE_API_KEY   = _env("OPENROUTE_API_KEY", "YOUR_OPENROUTE_API_KEY")

# ============================================================
# GIỚI HẠN LÃNH THỔ VIỆT NAM
# ============================================================
VIETNAM_BOUNDS = {
    "min_lat": 8.18,
    "max_lat": 23.39,
    "min_lon": 102.14,
    "max_lon": 109.46,
}

# ============================================================
# NGƯỠNG RỦI RO
# ============================================================
DANGER_THRESHOLD       = 0.70
MODERATE_RISK          = 0.40
GEOLOGICAL_RISK_HIGH   = 0.75
FLOOD_RISK_HIGH        = 0.65
LANDSLIDE_RISK_HIGH    = 0.70

# ============================================================
# SOS
# ============================================================
SOS_POLICE     = "113"
SOS_FIRE       = "114"
SOS_AMBULANCE  = "115"
SOS_RESCUE     = "1800599920"

# ============================================================
# HUMAN-AWARE ROUTING
# ============================================================
HUMAN_PROFILES = {
    "elderly":      {"max_drive_hours": 2, "rest_interval_km": 50},
    "night_driver": {"avoid_dark_roads": True, "avoid_mountain": True},
    "motion_sick":  {"avoid_curves": True, "max_elevation_change": 200},
    "stressed":     {"prefer_scenic": True, "avoid_traffic": True},
    "family":       {"rest_interval_km": 80, "prefer_safe": True},
}

# ============================================================
# ĐƯỜNG DẪN DỮ LIỆU
# ============================================================
DATA_DIR              = os.path.join(PROJECT_DIR, "data")
VIETNAM_ZONES_FILE    = os.path.join(DATA_DIR, "vietnam_zones.json")
GEOLOGICAL_FILE       = os.path.join(DATA_DIR, "geological.json")
CULTURAL_FILE         = os.path.join(DATA_DIR, "cultural_stories.json")
MEMORY_TRAIL_FILE     = os.path.join(DATA_DIR, "memory_trails.json")
USER_ALIASES_FILE     = os.path.join(DATA_DIR, "user_aliases.json")  # Địa danh user tự thêm

# ============================================================
# CÀI ĐẶT BẢN ĐỒ
# ============================================================
DEFAULT_MAP_CENTER = [16.0, 106.0]
DEFAULT_ZOOM       = 6
MAP_TILE_URL       = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"

# ============================================================
# LOGGING
# ============================================================
LOG_LEVEL = "INFO"
LOG_FILE  = "app.log"