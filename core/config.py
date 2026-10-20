import os
import certifi
from dotenv import load_dotenv

# โหลดค่าจากไฟล์ .env
load_dotenv()

# Configure trust before DSPy/LiteLLM create their HTTP clients or SSL contexts.
# Keep an explicit CA bundle from the environment/.env (e.g. a corporate CA).
if not os.environ.get("SSL_CERT_FILE"):
    os.environ["SSL_CERT_FILE"] = certifi.where()

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

# "low" = Gemini thinks less -> much faster (~3s vs ~9s).
# Set to empty string to use the model default.
LLM_REASONING_EFFORT = os.getenv(
    "LLM_REASONING_EFFORT",
    "low"
).strip()

# Seconds before an LLM request is abandoned (prevents multi-minute hangs)
LLM_TIMEOUT = int(os.getenv(
    "LLM_TIMEOUT",
    "20"
))

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
