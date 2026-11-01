# api/ai_engine.py
# AI Engine — xử lý ngôn ngữ tự nhiên, tạo câu chuyện, phân tích cảm xúc

import os
import json
from typing import Dict, List, Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Dùng OpenAI hoặc bất kỳ LLM nào bạn chọn
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("openai chưa được cài — AI Engine sẽ dùng template cứng")


class AIEngine:
    """
    Xử lý AI cho:
    - Câu chuyện văn hóa địa phương
    - Phân tích cảm xúc hành trình
    - Gợi ý thông minh theo ngữ cảnh
    - Tạo recap hành trình
    """

    def __init__(self):
        if OPENAI_AVAILABLE:
            openai.api_key = os.getenv("OPENAI_API_KEY", "")
        logger.info("AIEngine khởi động")

    def generate_cultural_story(
        self,
        place_name: str,
        province: str,
        tags: List[str],
    ) -> str:
        """Tạo câu chuyện văn hóa cho một điểm đến."""
        if OPENAI_AVAILABLE and openai.api_key:
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[{
                        "role": "user",
                        "content": (
                            f"Kể một câu chuyện ngắn (3-4 câu) thú vị về {place_name} "
                            f"ở {province}, Việt Nam. Phong cách: gần gũi, thú vị. "
                            f"Bao gồm: lịch sử hoặc truyền thuyết địa phương."
                        ),
                    }],
                    max_tokens=200,
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                logger.error(f"OpenAI lỗi: {e}")

        # Fallback template
        templates = {
            "temple":     f"{place_name} là nơi linh thiêng gắn liền với tín ngưỡng người Việt hàng trăm năm qua.",
            "waterfall":  f"Thác {place_name} ẩn mình giữa rừng già xanh mướt, từng là nơi người dân tộc thiểu số làm lễ cầu mưa.",
            "mountain":   f"Đỉnh núi này được người địa phương gọi là 'nóc nhà', nơi mây và đất trời gặp nhau.",
            "beach":      f"Bãi biển {place_name} từng là điểm dừng chân của thương thuyền ngày xưa, nay vẫn giữ vẻ bình yên hiếm có.",
            "market":     f"Chợ {place_name} họp từ tờ mờ sáng, nơi người dân quanh vùng mang nông sản tươi ngon nhất đến trao đổi.",
        }
        primary_tag = tags[0] if tags else "default"
        return templates.get(primary_tag, f"{place_name} là một điểm đến đặc sắc của {province}.")

    def generate_trip_recap(self, trip_summary: Dict) -> str:
        """Tạo đoạn văn recap hành trình."""
        title     = trip_summary.get("title", "Chuyến đi")
        mood      = trip_summary.get("summary", {}).get("mood_summary", "")
        best      = trip_summary.get("summary", {}).get("best_moment", "")
        stops     = trip_summary.get("summary", {}).get("total_checkpoints", 0)
        avg_emo   = trip_summary.get("summary", {}).get("avg_emotion", 3)

        if OPENAI_AVAILABLE and openai.api_key:
            try:
                prompt = (
                    f"Viết đoạn recap ngắn (4-5 câu, tiếng Việt, ấm áp, sâu sắc) "
                    f"cho chuyến đi '{title}'. "
                    f"Cảm xúc trung bình: {avg_emo}/5. "
                    f"Khoảnh khắc đẹp nhất: {best}. "
                    f"Tổng {stops} điểm dừng. "
                    f"Tông: {mood}"
                )
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=200,
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                logger.error(f"OpenAI recap lỗi: {e}")

        return (
            f"Chuyến đi '{title}' đã để lại nhiều kỷ niệm đáng nhớ. "
            f"Với {stops} điểm dừng và khoảnh khắc đẹp nhất tại {best}, "
            f"đây là một hành trình {mood.lower()} "
            f"sẽ mãi in đậm trong ký ức."
        )

    def suggest_next_destination(
        self,
        past_trips: List[Dict],
        current_location: str,
    ) -> str:
        """Gợi ý điểm đến tiếp theo dựa trên lịch sử hành trình."""
        if not past_trips:
            return "Hãy bắt đầu hành trình đầu tiên của bạn!"

        # Đơn giản: dựa trên điểm cảm xúc cao nhất trong quá khứ
        best_trip = max(
            past_trips,
            key=lambda t: t.get("summary", {}).get("avg_emotion", 0),
        )
        dest = best_trip.get("destination", "một nơi đặc biệt")
        return f"Dựa trên những chuyến đi của bạn, chúng tôi gợi ý ghé thăm lại {dest} hoặc khám phá vùng lân cận!"
