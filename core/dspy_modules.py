import dspy
from typing import Literal

from core.config import (
    LLM_MODEL,
    LLM_API_KEY
)


# =========================
# Configure DSPy
# =========================

lm = dspy.LM(
    LLM_MODEL,
    api_key=LLM_API_KEY
)

dspy.configure(lm=lm)


# =========================
# ROUTER
# =========================

class IntentRouter(dspy.Signature):
    """
    Classify the student's latest message
    into the appropriate chatbot workflow.

    SOP1:
    Questions or requests related to academic forms,
    registration, leave, resignation, course add/drop,
    cross-program registration, or other academic petitions.

    SOP2:
    Problems, complaints, service issues,
    system issues, facilities, or other issues
    that the student wants to report.

    FAQ:
    Questions about procedures such as processing time,
    submission channels, approval, signatures,
    required documents, refunds, or request procedures.

    GENERAL:
    Greetings, thanks, casual conversation,
    or messages unrelated to SOP1, SOP2, or FAQ.
    """

    conversation_history: str = dspy.InputField(
        desc="Previous conversation"
    )

    user_message: str = dspy.InputField(
        desc="Latest student message"
    )

    intent: Literal[
        "SOP1",
        "SOP2",
        "FAQ",
        "GENERAL"
    ] = dspy.OutputField(
        desc="Selected workflow"
    )


# =========================
# MAIN REQUEST PROCESSOR
# =========================

class RequestProcessor(dspy.Signature):
    """
    Analyze the student's message and complete
    the appropriate workflow.

    SOP1:
    Academic form requests.
    Select only a form ID from available_forms.

    FAQ:
    Questions about academic request procedures.
    Select only an FAQ ID from available_faqs.

    SOP2:
    Problems or complaints.

    For SOP2:
    - Check whether the student provided a concrete problem.
    - "แจ้งปัญหาในสาขา" = incomplete.
    - "มีปัญหาค่ะ" = incomplete.
    - "อยากแจ้งปัญหา" = incomplete.
    - "หลอดไฟเสียที่ห้อง 202" = complete.
    - "ระบบลงทะเบียนเข้าไม่ได้" = complete.
    - If incomplete, set issue_complete="no".
    - If complete, set issue_complete="yes".
    - If incomplete, ask a short follow-up question.
    - Never invent missing issue details.

    GENERAL:
    Greetings, thanks, or questions about
    what this chatbot can do.

    Rules:
    - Never invent a form or FAQ.
    - Use only provided information.
    - For unused fields, return "none".
    """

    # -------------------------
    # Inputs
    # -------------------------

    conversation_history: str = dspy.InputField(
        desc="Previous conversation"
    )

    user_message: str = dspy.InputField(
        desc="Latest student message"
    )

    available_forms: str = dspy.InputField(
        desc="Available academic forms"
    )

    available_faqs: str = dspy.InputField(
        desc="Available FAQs"
    )

    # -------------------------
    # Intent
    # -------------------------

    intent: Literal[
        "SOP1",
        "SOP2",
        "FAQ",
        "GENERAL"
    ] = dspy.OutputField(
        desc="Selected workflow"
    )

    # -------------------------
    # SOP1
    # -------------------------

    form_id: Literal[
        "f001",
        "f002",
        "f003",
        "f004",
        "f005",
        "f006",
        "none"
    ] = dspy.OutputField(
        desc="Form ID for SOP1, otherwise none"
    )

    # -------------------------
    # FAQ
    # -------------------------

    faq_id: Literal[
        "faq001",
        "faq002",
        "faq003",
        "faq004",
        "faq005",
        "faq006",
        "faq007",
        "faq008",
        "faq009",
        "faq010",
        "none"
    ] = dspy.OutputField(
        desc="FAQ ID for FAQ intent, otherwise none"
    )

    # -------------------------
    # SOP2
    # -------------------------

    category: Literal[
        "FACILITY",
        "IT",
        "SERVICE",
        "ACADEMIC",
        "OTHER",
        "none"
    ] = dspy.OutputField(
        desc="Issue category for SOP2, otherwise none"
    )

    summary: str = dspy.OutputField(
        desc="Issue summary for SOP2, otherwise none"
    )

    detail: str = dspy.OutputField(
        desc="Issue detail for SOP2, otherwise none"
    )

    issue_complete: Literal[
        "yes",
        "no",
        "none"
    ] = dspy.OutputField(
        desc=(
            "yes if SOP2 has enough concrete issue detail, "
            "no if more detail is needed, otherwise none"
        )
    )

    followup_question: str = dspy.OutputField(
        desc=(
            "Short Thai question asking for missing issue "
            "details when SOP2 is incomplete, otherwise none"
        )
    )

    # -------------------------
    # SOP2 / GENERAL Reply
    # -------------------------

    reply: str = dspy.OutputField(
        desc=(
            "Short polite Thai reply for SOP2 or GENERAL, "
            "otherwise none"
        )
    )


# =========================
# SOP1 — FORM SELECTION
# Old module kept for reference
# =========================

class SOP1FormSelector(dspy.Signature):
    """
    Select the most appropriate academic form.

    Rules:
    - Select only from available_forms.
    - Never invent a form ID.
    - Do not invent form names, PDF files,
      or required documents.
    - If no form clearly matches, return "none".
    """

    conversation_history: str = dspy.InputField(
        desc="Previous conversation"
    )

    user_message: str = dspy.InputField(
        desc="Latest student request"
    )

    available_forms: str = dspy.InputField(
        desc="Available form IDs, names, and descriptions"
    )

    form_id: Literal[
        "f001",
        "f002",
        "f003",
        "f004",
        "f005",
        "f006",
        "none"
    ] = dspy.OutputField(
        desc="Best matching form ID"
    )

    reason: str = dspy.OutputField(
        desc="Short reason for selecting the form"
    )


# =========================
# SOP2 — ISSUE REPORT
# Old module kept for reference
# =========================

class SOP2IssueProcessor(dspy.Signature):
    """
    Process a student's problem or complaint.

    Do not invent missing information.
    """

    conversation_history: str = dspy.InputField(
        desc="Previous conversation"
    )

    user_message: str = dspy.InputField(
        desc="Latest student issue message"
    )

    category: Literal[
        "FACILITY",
        "IT",
        "SERVICE",
        "ACADEMIC",
        "OTHER"
    ] = dspy.OutputField(
        desc="Issue category"
    )

    summary: str = dspy.OutputField(
        desc="Short issue summary"
    )

    detail: str = dspy.OutputField(
        desc="Issue details from the student's message"
    )

    reply_to_student: str = dspy.OutputField(
        desc="Short polite Thai acknowledgement"
    )


# =========================
# FAQ
# Old module kept for reference
# =========================

class FAQSelector(dspy.Signature):
    """
    Select the FAQ that best matches the student's question.

    Rules:
    - Select only from available_faqs.
    - Never invent an FAQ ID.
    - Return "none" if no FAQ matches.
    """

    user_message: str = dspy.InputField(
        desc="Latest student question"
    )

    available_faqs: str = dspy.InputField(
        desc="Available FAQ questions and keywords"
    )

    faq_id: Literal[
        "faq001",
        "faq002",
        "faq003",
        "faq004",
        "faq005",
        "faq006",
        "faq007",
        "faq008",
        "faq009",
        "faq010",
        "none"
    ] = dspy.OutputField(
        desc="Best matching FAQ ID"
    )


# =========================
# GENERAL
# Old module kept for reference
# =========================

class GeneralResponse(dspy.Signature):
    """
    Respond to general conversation.

    The chatbot supports:
    1. Academic forms
    2. FAQ about academic request procedures
    3. Problem or complaint reporting

    Do not claim capabilities outside this scope.
    """

    conversation_history: str = dspy.InputField(
        desc="Previous conversation"
    )

    user_message: str = dspy.InputField(
        desc="Latest student message"
    )

    reply: str = dspy.OutputField(
        desc="Short polite Thai response within chatbot scope"
    )


# =========================
# Modules
# =========================

router = dspy.Predict(IntentRouter)

form_selector = dspy.Predict(
    SOP1FormSelector
)

issue_processor = dspy.Predict(
    SOP2IssueProcessor
)

faq_selector = dspy.Predict(
    FAQSelector
)

general_response = dspy.Predict(
    GeneralResponse
)

# Main module currently used by chat_engine.py
request_processor = dspy.Predict(
    RequestProcessor
)