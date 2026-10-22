from typing import Literal
from core.config import (
    LLM_MODEL,
    LLM_API_KEY,
    LLM_API_BASE,
    LLM_REASONING_EFFORT,
    LLM_TIMEOUT,
)
from core.form_service import get_form_ids
from core.faq_service import get_faq_ids
import dspy


# =========================
# Configure DSPy
# =========================
# Latency settings:
# - reasoning_effort="low": Gemini thinks less -> ~3s instead of ~9s
# - timeout + no retries: never hang for minutes on a slow/failed request;
#   chat_engine falls back to rule-based answers instead of waiting
# - temperature=0: same question -> same answer (and DSPy cache hits)

lm_kwargs = {
    "temperature": 0,
    "timeout": 180,
    "num_retries": 0,
}

if LLM_REASONING_EFFORT:
    lm_kwargs["reasoning_effort"] = LLM_REASONING_EFFORT

# Hugging Face router etc. (LLM_MODEL must then start with "openai/")
if LLM_API_BASE:
    lm_kwargs["api_base"] = LLM_API_BASE

lm = dspy.LM(
    LLM_MODEL,
    api_key=LLM_API_KEY,
    **lm_kwargs
)

try:
    dspy.configure(lm=lm)
except RuntimeError:
    # ถูกตั้งค่าไว้แล้วจาก thread อื่น (เกิดตอน Streamlit โหลดโค้ดใหม่) ใช้ค่าเดิมต่อได้
    pass


# IDs are generated from forms.json / faq.json,
# so adding a form or FAQ never requires editing this file.
FormId = Literal[tuple(get_form_ids() + ["none"])]
FaqId = Literal[tuple(get_faq_ids() + ["none"])]


# =========================
# MAIN REQUEST PROCESSOR
# =========================

class RequestProcessor(dspy.Signature):
    """
    You are DSI Chatbot for students of the faculty. Classify the student's
    latest message (using conversation_history for context) and fill the fields.

    SOP1 - the student wants to DO something academic and needs a form
    (add/drop, resign, leave of absence, late registration, cross-program,
    general petition). Pick form_id from available_forms. If the student's need
    is academic but no specific form fits, pick the general petition form.

    FAQ - a question about the petition PROCESS (how long, who signs, where to
    submit, documents, rejected request, refund). Pick faq_id from available_faqs.

    SOP2 - the student reports a PROBLEM or COMPLAINT about the faculty:
    broken facilities (lights, air-con, projector, toilet), IT systems (wifi,
    reg system), services/staff, or a lecturer's behaviour/teaching.
    issue_complete=True only if we know WHAT the problem is AND enough to act on it:
      - facility -> needs a location (building/floor/room)
      - complaint about a person -> needs who/which course AND what happened
      - "แจ้งปัญหาในสาขา", "มีปัญหาค่ะ", "อยากร้องเรียน" -> incomplete
    If incomplete, reply = ONE short polite Thai question asking only for what is missing.
    Never invent details the student did not say.

    GENERAL - greetings, thanks, what the bot can do, or off-topic.
    reply = short polite Thai answer; say the bot helps with forms (SOP1)
    and problem reports (SOP2) when the request is out of scope.

    If a GENERAL reply suggests a form, also set form_id to that form.
    Never show internal ids (f001, faq002) in reply; call forms by their Thai name.

    rule_hints are keyword signals from a fast pre-check; use them as hints only.
    Use only the provided forms/FAQs. For fields that do not apply use "none" / "".
    """

    conversation_history: str = dspy.InputField(
        desc="Previous conversation (may be empty)"
    )

    user_message: str = dspy.InputField(
        desc="Latest student message"
    )

    available_forms: str = dspy.InputField(
        desc="Available academic forms (JSON)"
    )

    available_faqs: str = dspy.InputField(
        desc="Available FAQs (JSON)"
    )

    rule_hints: str = dspy.InputField(
        desc="Keyword pre-check signals"
    )

    intent: Literal[
        "SOP1",
        "SOP2",
        "FAQ",
        "GENERAL"
    ] = dspy.OutputField()

    form_id: FormId = dspy.OutputField(
        desc="SOP1, or a GENERAL reply that suggests a form; otherwise none"
    )

    faq_id: FaqId = dspy.OutputField(
        desc="FAQ only, otherwise none"
    )

    category: Literal[
        "FACILITY",
        "IT",
        "SERVICE",
        "ACADEMIC",
        "OTHER",
        "none"
    ] = dspy.OutputField(
        desc="SOP2 only, otherwise none"
    )

    issue_complete: bool = dspy.OutputField(
        desc="SOP2 only: enough detail to file the report"
    )

    summary: str = dspy.OutputField(
        desc="SOP2 only: one-line Thai summary of the issue, otherwise empty"
    )

    reply: str = dspy.OutputField(
        desc=(
            "Thai text: follow-up question for incomplete SOP2, "
            "or the answer for GENERAL; otherwise empty"
        )
    )


# Main module used by chat_engine.py
request_processor = dspy.Predict(
    RequestProcessor
)
