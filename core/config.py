import os
from dotenv import load_dotenv

# โหลดค่าจากไฟล์ .env
load_dotenv()

# App Settings
APP_NAME = os.getenv(
    "APP_NAME",
    "DSI Chatbot"
)

# Mock Mode
MOCK_MODE = (
    os.getenv("MOCK_MODE", "true")
    .strip()
    .lower()
    == "true"
)

# LLM Settings
LLM_MODEL = os.getenv(
    "LLM_MODEL",
    "gemini/gemini-3.8-flash"
)

LLM_API_KEY = os.getenv(
    "LLM_API_KEY",
    ""
)

TEST_PASSWORD = os.getenv(
    "TEST_PASSWORD",
    ""
)

SUPABASE_URL = os.getenv(
    "SUPABASE_URL",
    ""
)

SUPABASE_SECRET_KEY = os.getenv(
    "SUPABASE_SECRET_KEY",
    ""
)