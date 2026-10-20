"""Run from the project root: .venv/bin/python -m scripts.check_gemini."""

import os
import sys

# Bootstrap CA trust before importing DSPy or constructing any clients.
from core.config import LLM_API_KEY, LLM_MODEL

from core.dspy_modules import lm
from core.faq_service import find_faq_fast
from core.form_service import find_form_fast


MESSAGE = "หนูมีเรื่องเกี่ยวกับการเรียนแต่ไม่แน่ใจว่าต้องทำยังไง"


def main():
    if not LLM_API_KEY:
        print("FAIL: LLM_API_KEY is missing; check your local .env.", file=sys.stderr)
        return 1

    if find_form_fast(MESSAGE) is not None or find_faq_fast(MESSAGE) is not None:
        print("FAIL: Test message now matches a Fast Path.", file=sys.stderr)
        return 1

    print("Python:", sys.executable)
    print("CA bundle:", os.environ["SSL_CERT_FILE"])
    print("Model:", LLM_MODEL)
    print("Message:", MESSAGE)
    print("Calling the configured dspy.LM directly (cache disabled).", flush=True)

    # Exercise the same LM used by fallback without executing workflow side effects.
    test_lm = lm.copy(cache=False, num_retries=0, timeout=90)
    try:
        result = test_lm(MESSAGE)
    except Exception as exc:
        # Some provider errors include request details; never print the API key.
        detail = str(exc).replace(LLM_API_KEY, "[REDACTED]")
        print(f"FAIL: {type(exc).__name__}: {detail}", file=sys.stderr)
        return 1

    print("PASS: Gemini/DSPy returned a response over verified TLS.")
    print("Reply:", result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
