from core.config import (MOCK_MODE,LLM_MODEL,LLM_API_KEY,)
from litellm import completion
from core.prompts import SYSTEM_PROMPT

def generate_response(user_message: str) -> str:
    """
    รับข้อความจากผู้ใช้
    แล้วส่งคำตอบของ chatbot กลับไป
    """

    # Mock Mode
    if MOCK_MODE:
        return (
            "นี่คือคำตอบจาก Mock Mode ค่ะ\n\n"
            f"คุณถามว่า: {user_message}"
        )

    # Real AI Mode
    response = completion(
        model=LLM_MODEL,
        api_key=LLM_API_KEY,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_message,
            },
        ],
    )

    return response.choices[0].message.content
