"""
core/ml_risk_model.py
─────────────────────
Random Forest Risk Model cho TripSmart Pro.

Chức năng:
  1. Đọc data/risk_points_vietnam.csv
  2. Sinh dữ liệu huấn luyện tổng hợp từ BUILTIN_HAZARD_ZONES + CSV
  3. Train Random Forest classifier (3 class: low / medium / high)
  4. Lưu model  → models/risk_model.pkl
  5. Lưu metrics → models/risk_metrics.json
  6. Cung cấp MLRiskModel.predict(lat, lon) cho app.py

Cột CSV dùng (không phân biệt hoa/thường):
    lat, lon, radius_km, score, type, label, icon, desc
"""

from __future__ import annotations

import csv
import json
import os
import pickle
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

warnings.filterwarnings("ignore")

# ── Đường dẫn ───────────────────────────────────────────────────────────────
_HERE        = Path(__file__).parent.resolve()
_PROJECT     = _HERE.parent if _HERE.name == "core" else _HERE
CSV_PATH     = _PROJECT / "data"  / "risk_points_vietnam.csv"
MODEL_DIR    = _PROJECT / "models"
MODEL_PATH   = MODEL_DIR / "risk_model.pkl"
METRICS_PATH = MODEL_DIR / "risk_metrics.json"

# ── Nhãn rủi ro ─────────────────────────────────────────────────────────────
RISK_LABELS  = {0: "Thấp", 1: "Trung bình", 2: "Cao"}
RISK_COLORS  = {0: "#21c354", 1: "#ffa500", 2: "#ff4b4b"}
RISK_EMOJI   = {0: "🟢", 1: "🟡", 2: "🔴"}

# ── Zone tích hợp sẵn (copy nhỏ gọn từ risk_engine để độc lập) ─────────────
_BUILTIN_ZONES = [
    {"lat": 22.33, "lon": 103.84, "radius_km": 25, "score": 0.85, "type": "landslide"},
    {"lat": 21.38, "lon": 103.02, "radius_km": 20, "score": 0.80, "type": "landslide"},
    {"lat": 22.10, "lon": 104.87, "radius_km": 18, "score": 0.78, "type": "landslide"},
    {"lat": 15.12, "lon": 108.19, "radius_km": 15, "score": 0.72, "type": "geological"},
    {"lat": 14.35, "lon": 108.00, "radius_km": 20, "score": 0.70, "type": "landslide"},
    {"lat": 11.91, "lon": 108.43, "radius_km": 12, "score": 0.62, "type": "landslide"},
    {"lat": 11.50, "lon": 108.07, "radius_km": 15, "score": 0.65, "type": "landslide"},
    {"lat": 13.79, "lon": 109.22, "radius_km": 10, "score": 0.55, "type": "geological"},
    {"lat": 10.34, "lon": 105.32, "radius_km": 30, "score": 0.80, "type": "flood"},
    {"lat": 10.82, "lon": 106.63, "radius_km": 25, "score": 0.68, "type": "flood"},
    {"lat": 15.88, "lon": 108.34, "radius_km": 20, "score": 0.75, "type": "flood"},
    {"lat": 17.47, "lon": 106.60, "radius_km": 25, "score": 0.72, "type": "flood"},
    {"lat": 20.86, "lon": 106.06, "radius_km": 20, "score": 0.65, "type": "flood"},
    {"lat": 16.07, "lon": 108.22, "radius_km": 15, "score": 0.60, "type": "flood"},
    {"lat": 21.83, "lon": 104.14, "radius_km": 15, "score": 0.70, "type": "bad_road"},
    {"lat": 21.88, "lon": 104.67, "radius_km": 12, "score": 0.68, "type": "bad_road"},
    {"lat": 16.20, "lon": 107.95, "radius_km": 18, "score": 0.73, "type": "bad_road"},
    {"lat": 12.90, "lon": 108.44, "radius_km": 12, "score": 0.62, "type": "bad_road"},
    {"lat": 14.24, "lon": 108.88, "radius_km": 10, "score": 0.60, "type": "bad_road"},
]

# ── Feature names (thứ tự phải khớp với _build_features) ────────────────────
FEATURE_NAMES = [
    "lat", "lon",
    "dist_nearest_km",        # khoảng cách đến zone nguy hiểm gần nhất
    "nearest_score",          # điểm rủi ro của zone gần nhất
    "is_landslide_zone",      # có nằm trong vùng sạt lở không
    "is_flood_zone",          # có nằm trong vùng lũ không
    "is_bad_road_zone",       # có nằm trong vùng đường xấu không
    "is_geological_zone",     # có nằm trong vùng địa chất yếu không
    "zone_count_5km",         # số lượng zone trong bán kính 5 km
    "max_score_10km",         # score cao nhất trong bán kính 10 km
    "lat_normalized",         # lat chuẩn hóa về [0,1] trong bbox VN
    "lon_normalized",         # lon chuẩn hóa về [0,1] trong bbox VN
]


# ════════════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════════════

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Trả về khoảng cách (km) giữa 2 điểm toạ độ."""
    R = 6371.0
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi  = np.radians(lat2 - lat1)
    dlam  = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlam / 2) ** 2
    return R * 2 * np.arcsin(np.sqrt(a))


def _load_csv(path: Path) -> List[Dict]:
    """Đọc CSV rủi ro, trả về list dict."""
    if not path.exists():
        print(f"[MLRiskModel] CSV không tìm thấy: {path}")
        return []
    zones = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [h.strip().lower() for h in (reader.fieldnames or [])]
        for row in reader:
            try:
                zones.append({
                    "lat":       float(row["lat"]),
                    "lon":       float(row["lon"]),
                    "radius_km": float(row.get("radius_km") or 15),
                    "score":     float(row.get("score") or 0.65),
                    "type":      str(row.get("type") or "geological").strip(),
                })
            except (KeyError, ValueError):
                pass
    print(f"[MLRiskModel] Đọc CSV: {len(zones)} điểm từ {path.name}")
    return zones


def _score_to_label(score: float) -> int:
    """Chuyển điểm rủi ro 0-1 → nhãn 0/1/2."""
    if score >= 0.65:
        return 2   # Cao
    if score >= 0.40:
        return 1   # Trung bình
    return 0       # Thấp


def _build_features(lat: float, lon: float, all_zones: List[Dict]) -> np.ndarray:
    """Tính 12 feature cho 1 điểm toạ độ."""
    dist_nearest  = float("inf")
    nearest_score = 0.0
    is_landslide  = 0
    is_flood      = 0
    is_bad_road   = 0
    is_geo        = 0
    count_5km     = 0
    max_10km      = 0.0

    for z in all_zones:
        d = _haversine(lat, lon, z["lat"], z["lon"])
        if d < dist_nearest:
            dist_nearest  = d
            nearest_score = z["score"]
        if d <= z["radius_km"]:
            t = z["type"]
            if t == "landslide":  is_landslide = 1
            if t == "flood":      is_flood     = 1
            if t == "bad_road":   is_bad_road  = 1
            if t == "geological": is_geo       = 1
        if d <= 5.0:
            count_5km += 1
        if d <= 10.0 and z["score"] > max_10km:
            max_10km = z["score"]

    if dist_nearest == float("inf"):
        dist_nearest = 999.0

    lat_norm = (lat  - 8.0)  / (23.4 - 8.0)
    lon_norm = (lon - 102.1) / (109.5 - 102.1)

    return np.array([
        lat, lon,
        min(dist_nearest, 999.0),
        nearest_score,
        is_landslide,
        is_flood,
        is_bad_road,
        is_geo,
        count_5km,
        max_10km,
        lat_norm,
        lon_norm,
    ], dtype=np.float32)


# ════════════════════════════════════════════════════════════════════════════
# TRAINING
# ════════════════════════════════════════════════════════════════════════════

def _generate_training_data(all_zones: List[Dict]) -> Tuple[np.ndarray, np.ndarray]:
    """
    Sinh dữ liệu huấn luyện:
      - Mỗi zone → nhiều điểm mẫu bên trong bán kính (nhãn từ score)
      - Thêm điểm an toàn ngẫu nhiên khắp Việt Nam (nhãn = 0)
    """
    rng = np.random.default_rng(42)
    X_rows, y_rows = [], []

    # ── Điểm từ các zone nguy hiểm ──────────────────────────────────────────
    for z in all_zones:
        n_samples = max(8, int(z["radius_km"] * 2))
        for _ in range(n_samples):
            # Lấy mẫu ngẫu nhiên trong hình tròn bán kính
            angle  = rng.uniform(0, 2 * np.pi)
            frac   = rng.uniform(0, 1.0)            # 0 = tâm, 1 = rìa
            r_deg  = (z["radius_km"] / 111.0) * frac
            slat   = z["lat"] + r_deg * np.cos(angle)
            slon   = z["lon"] + r_deg * np.sin(angle)
            # Điểm càng gần tâm → rủi ro càng cao
            sample_score = z["score"] * (1.0 - 0.4 * frac)
            label = _score_to_label(sample_score)
            feats = _build_features(slat, slon, all_zones)
            X_rows.append(feats)
            y_rows.append(label)

    # ── Điểm "an toàn" ngẫu nhiên trên lãnh thổ VN ─────────────────────────
    n_safe = max(300, len(X_rows) // 2)
    for _ in range(n_safe):
        slat = rng.uniform(8.5,  23.3)
        slon = rng.uniform(102.2, 109.4)
        feats = _build_features(slat, slon, all_zones)
        # Nếu điểm rơi vào zone thì tính nhãn bình thường, không ép = 0
        max_s = feats[FEATURE_NAMES.index("max_score_10km")]
        label = _score_to_label(max_s * 0.7)  # giảm nhẹ → ưu tiên class 0
        X_rows.append(feats)
        y_rows.append(label)

    X = np.vstack(X_rows)
    y = np.array(y_rows, dtype=np.int32)
    return X, y


def train_and_save() -> Dict:
    """
    Train Random Forest, lưu model + metrics, trả về dict kết quả.
    Gọi hàm này 1 lần khi setup project.
    """
    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import cross_val_score, train_test_split
        from sklearn.metrics import (
            accuracy_score, f1_score, classification_report
        )
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import Pipeline
    except ImportError:
        return {"error": "scikit-learn chưa được cài. Chạy: pip install scikit-learn"}

    print("\n[MLRiskModel] ═══ BẮT ĐẦU TRAINING ═══")

    # 1. Load zones
    csv_zones   = _load_csv(CSV_PATH)
    all_zones   = _BUILTIN_ZONES + csv_zones
    print(f"[MLRiskModel] Tổng zones: {len(all_zones)} (builtin={len(_BUILTIN_ZONES)}, csv={len(csv_zones)})")

    # 2. Sinh dữ liệu
    X, y = _generate_training_data(all_zones)
    print(f"[MLRiskModel] Dataset: {len(X)} mẫu | nhãn: {dict(zip(*np.unique(y, return_counts=True)))}")

    # 3. Split train/test
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    # 4. Pipeline: scaler + Random Forest
    model = Pipeline([
        ("scaler", StandardScaler()),
        ("rf", RandomForestClassifier(
            n_estimators=200,
            max_depth=12,
            min_samples_leaf=3,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )),
    ])
    model.fit(X_tr, y_tr)

    # 5. Đánh giá
    y_pred   = model.predict(X_te)
    accuracy = float(accuracy_score(y_te, y_pred))
    f1_macro = float(f1_score(y_te, y_pred, average="macro", zero_division=0))
    f1_weighted = float(f1_score(y_te, y_pred, average="weighted", zero_division=0))

    # Cross-val 5-fold
    cv_scores = cross_val_score(model, X, y, cv=5, scoring="f1_macro", n_jobs=-1)

    # Feature importance (từ RF bên trong pipeline)
    rf_step       = model.named_steps["rf"]
    importances   = rf_step.feature_importances_.tolist()
    feat_imp_dict = dict(zip(FEATURE_NAMES, [round(v, 4) for v in importances]))

    report = classification_report(y_te, y_pred,
                                   target_names=list(RISK_LABELS.values()),
                                   output_dict=True, zero_division=0)

    metrics = {
        "accuracy":    round(accuracy, 4),
        "f1_macro":    round(f1_macro, 4),
        "f1_weighted": round(f1_weighted, 4),
        "cv_f1_mean":  round(float(cv_scores.mean()), 4),
        "cv_f1_std":   round(float(cv_scores.std()), 4),
        "n_samples":   int(len(X)),
        "n_train":     int(len(X_tr)),
        "n_test":      int(len(X_te)),
        "n_zones":     int(len(all_zones)),
        "n_csv_zones": int(len(csv_zones)),
        "feature_importance": feat_imp_dict,
        "class_report": report,
    }

    # 6. Lưu model
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"model": model, "zones": all_zones, "features": FEATURE_NAMES}, f)

    # 7. Lưu metrics
    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    print(f"[MLRiskModel] Accuracy : {accuracy:.2%}")
    print(f"[MLRiskModel] F1 macro : {f1_macro:.2%}")
    print(f"[MLRiskModel] CV F1    : {cv_scores.mean():.2%} ± {cv_scores.std():.2%}")
    print(f"[MLRiskModel] Model lưu: {MODEL_PATH}")
    print(f"[MLRiskModel] Metrics  : {METRICS_PATH}")
    print("[MLRiskModel] ═══ TRAINING XONG ═══\n")

    return metrics


# ════════════════════════════════════════════════════════════════════════════
# INFERENCE
# ════════════════════════════════════════════════════════════════════════════

class MLRiskModel:
    """
    Wrapper dùng trong app.py.

    Dùng:
        model = MLRiskModel()
        result = model.predict(lat, lon)
    """

    def __init__(self):
        self._model     = None
        self._zones     = []
        self._metrics   = {}
        self._ready     = False
        self._error     = ""
        self._load()

    # ── Load ────────────────────────────────────────────────────────────────
    def _load(self):
        # Nếu model chưa tồn tại → tự train
        if not MODEL_PATH.exists():
            print("[MLRiskModel] Chưa có model → bắt đầu train...")
            try:
                train_and_save()
            except Exception as e:
                self._error = f"Train thất bại: {e}"
                print(f"[MLRiskModel] ❌ {self._error}")
                return

        # Load model
        try:
            with open(MODEL_PATH, "rb") as f:
                payload = pickle.load(f)
            self._model   = payload["model"]
            self._zones   = payload.get("zones", _BUILTIN_ZONES)
            self._ready   = True
            print(f"[MLRiskModel] ✅ Model loaded từ {MODEL_PATH}")
        except Exception as e:
            self._error = f"Load model lỗi: {e}"
            print(f"[MLRiskModel] ❌ {self._error}")

        # Load metrics
        if METRICS_PATH.exists():
            try:
                with open(METRICS_PATH, encoding="utf-8") as f:
                    self._metrics = json.load(f)
            except Exception:
                pass

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def metrics(self) -> Dict:
        return self._metrics

    @property
    def error(self) -> str:
        return self._error

    # ── Predict ─────────────────────────────────────────────────────────────
    def predict(self, lat: float, lon: float) -> Dict:
        """
        Dự đoán rủi ro tại toạ độ (lat, lon).

        Trả về dict:
          label        : "Thấp" / "Trung bình" / "Cao"
          class_id     : 0 / 1 / 2
          emoji        : 🟢 / 🟡 / 🔴
          color        : hex color
          proba        : [p_low, p_medium, p_high]
          proba_pct    : {"Thấp": "12%", "Trung bình": "45%", "Cao": "43%"}
          confidence   : xác suất class được chọn
          top_features : list[{"name", "importance", "value"}]
          error        : "" hoặc thông báo lỗi
        """
        if not self._ready:
            return {"error": self._error or "Model chưa sẵn sàng", "label": "N/A",
                    "class_id": -1, "emoji": "⚫", "color": "#888", "confidence": 0.0,
                    "proba": [], "proba_pct": {}, "top_features": []}

        try:
            feats = _build_features(lat, lon, self._zones).reshape(1, -1)
            pred_id    = int(self._model.predict(feats)[0])
            proba      = self._model.predict_proba(feats)[0].tolist()
            confidence = float(max(proba))

            proba_pct = {
                RISK_LABELS[i]: f"{p:.0%}"
                for i, p in enumerate(proba)
            }

            # Feature importance × giá trị tuyệt đối (để rank ảnh hưởng)
            rf      = self._model.named_steps["rf"]
            imp     = rf.feature_importances_
            feat_vals = feats[0]
            top_feat = sorted(
                [{"name": FEATURE_NAMES[i],
                  "importance": round(float(imp[i]), 4),
                  "value": round(float(feat_vals[i]), 4)}
                 for i in range(len(FEATURE_NAMES))],
                key=lambda x: x["importance"], reverse=True
            )[:5]

            return {
                "label":       RISK_LABELS[pred_id],
                "class_id":    pred_id,
                "emoji":       RISK_EMOJI[pred_id],
                "color":       RISK_COLORS[pred_id],
                "proba":       proba,
                "proba_pct":   proba_pct,
                "confidence":  confidence,
                "top_features": top_feat,
                "error":       "",
            }

        except Exception as e:
            return {"error": str(e), "label": "Lỗi", "class_id": -1,
                    "emoji": "⚫", "color": "#888", "confidence": 0.0,
                    "proba": [], "proba_pct": {}, "top_features": []}

    # ── Retrain ─────────────────────────────────────────────────────────────
    def retrain(self) -> Dict:
        """Huấn luyện lại model (dùng khi CSV mới được thêm vào)."""
        result = train_and_save()
        if "error" not in result:
            self._load()
        return result

    # ── Dự đoán dùng cho route forecast ────────────────────────────────────
    def predict_point_risk(self, lat: float, lon: float) -> str:
        """
        Dự đoán rủi ro tại một điểm trên tuyến (chỉ dựa trên đặc trưng địa lý).
        Trả về: "low" / "medium" / "high" / "very_high"
        """
        result = self.predict(lat, lon)
        if result.get("error"):
            return "low"
        return self._class_id_to_level(result["class_id"], result["confidence"])

    def predict_route_point_risk(
        self,
        lat: float,
        lon: float,
        eta_time=None,
        weather_data: Optional[Dict] = None,
        hazard_features: Optional[Dict] = None,
    ) -> Dict:
        """
        Dự đoán rủi ro tại một điểm trên tuyến vào thời điểm dự kiến đi qua (eta_time),
        có tính thêm rủi ro thời tiết tại thời điểm đó.

        Tham số:
            lat, lon         : tọa độ điểm
            eta_time         : datetime dự kiến đi qua điểm này (có thể None)
            weather_data     : dict trả về từ WeatherAPI (get_current/forecast/get_weather_risk),
                               cần có "risk_score" trong [0,1] nếu có
            hazard_features  : dict từ RiskEngine.extract_risk_features_for_point (tuỳ chọn,
                               dùng để hiển thị giải thích, không bắt buộc cho dự đoán)

        Trả về dict:
            level         : "low" / "medium" / "high" / "very_high"
            score         : điểm rủi ro tổng hợp 0-1 (địa lý + thời tiết)
            geo_score     : điểm rủi ro địa lý (từ model ML)
            weather_score : điểm rủi ro thời tiết tại eta_time (0 nếu không có dữ liệu)
            label         : nhãn tiếng Việt ("Thấp"/"Trung bình"/"Cao"/"Rất cao")
            confidence    : độ tin cậy của model ML
            eta_time      : trả lại eta_time (để app.py hiển thị)
            error         : "" hoặc thông báo lỗi
        """
        ml_result = self.predict(lat, lon)
        if ml_result.get("error"):
            return {
                "level": "low", "score": 0.0, "geo_score": 0.0,
                "weather_score": 0.0, "label": "N/A", "confidence": 0.0,
                "eta_time": eta_time, "error": ml_result["error"],
            }

        # Điểm rủi ro địa lý từ proba của model: P(medium)*0.5 + P(high)*1.0
        proba = ml_result.get("proba", [1.0, 0.0, 0.0])
        if len(proba) == 3:
            geo_score = proba[1] * 0.5 + proba[2] * 1.0
        else:
            geo_score = {"Thấp": 0.2, "Trung bình": 0.5, "Cao": 0.85}.get(
                ml_result.get("label", "Thấp"), 0.2
            )

        # Điểm rủi ro thời tiết tại thời điểm eta_time
        weather_score = 0.0
        if weather_data:
            weather_score = float(weather_data.get("risk_score", 0) or 0)

        # SCORE V2 — Segment Risk theo công thức:
        # R_i = αG_i + βW_i + γT_i + δI_i
        # Hiện tại app chưa có traffic/incident realtime chuẩn nên mặc định T_i = I_i = 0.
        # Giai đoạn này dùng α=0.6 cho địa lý và β=0.4 cho thời tiết theo ETA.
        traffic_score = 0.0
        incident_score = 0.0
        if weather_data:
            # Cho phép sau này truyền thêm traffic_score / incident_score qua weather_data
            # hoặc context ngoài mà không phải sửa lại chữ ký hàm.
            traffic_score = float(weather_data.get("traffic_score", 0) or 0)
            incident_score = float(weather_data.get("incident_score", 0) or 0)

        alpha, beta, gamma, delta = 0.60, 0.40, 0.0, 0.0
        if traffic_score > 0 or incident_score > 0:
            alpha, beta, gamma, delta = 0.35, 0.25, 0.20, 0.20

        combined = (
            alpha * geo_score
            + beta * weather_score
            + gamma * traffic_score
            + delta * incident_score
        )
        combined = max(0.0, min(1.0, combined))

        level = self._score_to_level(combined)
        label_map = {
            "low": "Thấp", "medium": "Trung bình",
            "high": "Cao", "very_high": "Rất cao",
        }

        return {
            "level": level,
            "score": round(combined, 3),
            "geo_score": round(geo_score, 3),
            "weather_score": round(weather_score, 3),
            "traffic_score": round(traffic_score, 3),
            "incident_score": round(incident_score, 3),
            "weights": {"geo": alpha, "weather": beta, "traffic": gamma, "incident": delta},
            "label": label_map.get(level, "Thấp"),
            "confidence": ml_result.get("confidence", 0.0),
            "eta_time": eta_time,
            "error": "",
        }

    @staticmethod
    def _score_to_level(score: float) -> str:
        if score >= 0.80:
            return "very_high"
        if score >= 0.65:
            return "high"
        if score >= 0.40:
            return "medium"
        return "low"

    @staticmethod
    def _class_id_to_level(class_id: int, confidence: float) -> str:
        if class_id == 2:
            return "very_high" if confidence >= 0.75 else "high"
        if class_id == 1:
            return "medium"
        return "low"


# ════════════════════════════════════════════════════════════════════════════
# CLI: chạy trực tiếp để train
# ════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    metrics = train_and_save()
    if "error" in metrics:
        print(f"❌ {metrics['error']}")
    else:
        print(f"\n📊 Kết quả training:")
        print(f"  Accuracy   : {metrics['accuracy']:.2%}")
        print(f"  F1 macro   : {metrics['f1_macro']:.2%}")
        print(f"  F1 weighted: {metrics['f1_weighted']:.2%}")
        print(f"  CV F1      : {metrics['cv_f1_mean']:.2%} ± {metrics['cv_f1_std']:.2%}")
        print(f"\n🔑 Feature quan trọng nhất:")
        for k, v in sorted(metrics["feature_importance"].items(),
                            key=lambda x: x[1], reverse=True)[:5]:
            bar = "█" * int(v * 40)
            print(f"  {k:25s} {bar:40s} {v:.4f}")