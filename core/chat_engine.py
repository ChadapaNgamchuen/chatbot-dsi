"""
DSI Chatbot routing.

Pipeline (cheapest first, LLM only when rules are not confident):

    0. pending SOP2 follow-up  -> merge answer into the open issue
    1. GENERAL fast path       -> greetings / thanks
    2. rule-based router       -> SOP2 / SOP1 / FAQ in microseconds
    3. ONE DSPy / LLM call     -> ambiguous messages only
    4. rule-based fallback     -> if the LLM times out or fails

`state` is a small dict kept by the UI between turns (st.session_state).
It holds the issue that is still waiting for details, so a reply like
"ห้อง 202 ค่ะ" is attached to the earlier "แอร์พัง" instead of being
treated as a brand-new message.
"""

import time

from core.dspy_modules import request_processor
from core.form_service import (
    get_forms_for_classifier,
    get_form_by_id,
    get_form_hints,
    find_form_fast,
    find_form_comparison,
    format_form_answer,
    get_self_service_answer,
)
from core.faq_service import (
    get_faqs_for_classifier,
    get_faq_by_id,
    find_faq_fast,
)
from core.issue_analyzer import (
    analyze_issue,
    build_summary,
    FOLLOWUP_QUESTIONS,
)
from core.issue_service import save_issue


# Ask at most this many follow-up questions, then file the issue anyway
MAX_FOLLOWUPS = 2

VALID_CATEGORIES = {"FACILITY", "IT", "SERVICE", "ACADEMIC", "OTHER"}

CATEGORY_LABELS = {
    "FACILITY": "อาคารสถานที่ / อุปกรณ์",
    "IT": "ระบบไอที",
    "SERVICE": "การให้บริการ",
    "ACADEMIC": "การเรียนการสอน / อาจารย์",
    "OTHER": "อื่น ๆ",
}

# FAQ topics worth appending after a form answer ("ลาออกใช้เวลากี่วัน")
FAQ_ADDON_CATEGORIES = {
    "processing_time",
    "approval_process",
    "signature_process",
    "rejected_request",
    "refund",
}

CANCEL_WORDS = {"ยกเลิก", "ไม่แจ้งแล้ว", "ไม่เป็นไร", "cancel"}

# Asking again for the form that was just recommended
FILE_REQUEST_WORDS = [
    "ขอไฟล์", "ส่งไฟล์", "ไฟล์", "ขอฟอร์ม", "ขอแบบฟอร์ม",
    "ดาวน์โหลด", "โหลด", "ลิงก์", "ลิ้งค์", "pdf",
]

URGENT_NOTE = (
    "\n\n⚠️ หากเป็นเหตุฉุกเฉินหรือมีความเสี่ยงต่อความปลอดภัย "
    "กรุณาติดต่อเจ้าหน้าที่คณะหรือ รปภ. โดยตรงทันทีค่ะ"
)


def _normalize(text):
    return " ".join(text.strip().lower().split())


def get_general_fast_response(user_message):
    """
    Handle very clear general messages without calling the LLM.
    """

    text = _normalize(user_message)

    greetings = {
        "สวัสดี",
        "สวัสดีค่ะ",
        "สวัสดีครับ",
        "หวัดดี",
        "hello",
        "hi",
    }

    thanks = {
        "ขอบคุณ",
        "ขอบคุณค่ะ",
        "ขอบคุณครับ",
        "ขอบใจ",
        "thank you",
        "thanks",
    }

    capability_questions = {
        "chatbot นี้ทำอะไรได้บ้าง",
        "chatbot ทำอะไรได้บ้าง",
        "บอทนี้ทำอะไรได้บ้าง",
        "ทำอะไรได้บ้าง",
        "ช่วยอะไรได้บ้าง",
    }

    if text in greetings:

        return (
            "สวัสดีค่ะ 👋 "
            "DSI Chatbot ยินดีให้บริการค่ะ "
            "สามารถสอบถามเรื่องแบบฟอร์ม คำร้อง "
            "FAQ หรือแจ้งปัญหาได้เลยค่ะ"
        )

    if text in thanks:

        return (
            "ยินดีค่ะ 😊 "
            "หากมีคำถามเพิ่มเติมสามารถสอบถามได้เลยค่ะ"
        )

    if text in capability_questions:

        return (
            "DSI Chatbot สามารถช่วยได้ 2 เรื่องหลักค่ะ\n\n"
            "📄 แนะนำแบบฟอร์มและเอกสารที่ต้องใช้ "
            "(เช่น \"ลงทะเบียนไม่ทันต้องใช้ฟอร์มอะไร\")\n"
            "🛠️ รับแจ้งปัญหาหรือข้อร้องเรียน "
            "(เช่น \"แอร์ห้อง 202 พัง\")"
        )

    return None


# =========================
# SOP1 helpers
# =========================

def build_sop1_result(form, user_message):
    """
    Form answer, plus a related FAQ when the student also asked
    about the process (e.g. "ลาออกใช้เวลากี่วัน").
    """

    # Still within the registration period -> reg.tu.ac.th only, no form buttons
    self_service = get_self_service_answer(form, user_message)

    if self_service:
        return {
            "answer": self_service,
            "intent": "SOP1",
            "form": None,
        }

    answer = format_form_answer(form, user_message)

    faq = find_faq_fast(user_message)

    if faq and faq.get("category") in FAQ_ADDON_CATEGORIES:

        answer += (
            f"\n\n**💡 {faq['question']}**\n\n"
            f"{faq['answer']}"
        )

    return {
        "answer": answer,
        "intent": "SOP1",
        "form": form,
    }


# =========================
# SOP2 helpers
# =========================

def file_issue(text, category, tester_id, summary=None, urgent=False):
    """
    Save a complete issue and build the confirmation message.
    """

    if category not in VALID_CATEGORIES:
        category = "OTHER"

    summary = (summary or "").strip() or build_summary(text, category)

    if urgent:
        summary = f"[เร่งด่วน] {summary}"

    issue_id = save_issue(
        tester_id=tester_id,
        category=category,
        summary=summary,
        detail=text,
        original_message=text,
    )

    answer = (
        "✅ รับเรื่องแจ้งปัญหาเรียบร้อยแล้วค่ะ\n\n"
        f"หมวดหมู่: {CATEGORY_LABELS[category]}\n"
        f"สรุป: {summary}\n"
        f"หมายเลขการแจ้งปัญหา: **{issue_id}**\n\n"
        "ระบบได้ส่งเรื่องให้ผู้รับผิดชอบดำเนินการต่อแล้วค่ะ"
    )

    if urgent:
        answer += URGENT_NOTE

    return {
        "answer": answer,
        "intent": "SOP2",
        "issue_id": issue_id,
        "category": category,
        "issue_complete": True,
    }


def ask_issue_followup(text, category, question, asked, state, urgent=False):
    """
    Keep the issue open in `state` and ask for the missing detail.
    """

    state["pending_issue"] = {
        "text": text,
        "category": category,
        "asked": asked + 1,
        "urgent": urgent,
    }

    answer = question + "\n\n(พิมพ์ \"ยกเลิก\" หากไม่ต้องการแจ้งเรื่องนี้)"

    if urgent:
        answer += URGENT_NOTE

    return {
        "answer": answer,
        "intent": "SOP2",
        "issue_id": None,
        "issue_complete": False,
    }


def handle_issue_rules(text, tester_id, state, asked=0, fallback_category=None):
    """
    SOP2 without the LLM: decide complete vs. follow-up from rules.
    """

    analysis = analyze_issue(text)

    category = analysis["category"]

    if category == "OTHER" and fallback_category:
        category = fallback_category

    if analysis["complete"] or asked >= MAX_FOLLOWUPS:

        return file_issue(
            text,
            category,
            tester_id,
            urgent=analysis["urgent"],
        )

    question = FOLLOWUP_QUESTIONS[analysis["missing"] or "DETAIL"]

    return ask_issue_followup(
        text,
        category,
        question,
        asked,
        state,
        urgent=analysis["urgent"],
    )


def continue_pending_issue(user_message, pending, tester_id, state):
    """
    The student is answering our follow-up question.
    Merge the answer into the open issue and re-check completeness.
    """

    combined = f"{pending['text']} {user_message}".strip()

    analysis = analyze_issue(combined)

    # The student answered at least once with real content
    # -> good enough for complaints, which rules cannot fully judge
    answered_with_detail = len(_normalize(user_message)) >= 10

    if (
        analysis["complete"]
        or pending["asked"] >= MAX_FOLLOWUPS
        or (analysis["missing"] in {"CONDUCT", "DETAIL"} and answered_with_detail)
    ):

        category = analysis["category"]

        if category == "OTHER":
            category = pending["category"]

        return file_issue(
            combined,
            category,
            tester_id,
            urgent=analysis["urgent"] or pending.get("urgent", False),
        )

    return handle_issue_rules(
        combined,
        tester_id,
        state,
        asked=pending["asked"],
        fallback_category=pending["category"],
    )


# =========================
# LLM path
# =========================

def build_rule_hints(issue, form_hints):

    return (
        f"form_candidates={form_hints or 'none'}; "
        f"issue_signal={issue['is_issue']}; "
        f"issue_category={issue['category']}; "
        f"issue_missing={issue['missing'] or 'none'}"
    )


def handle_llm(user_message, conversation_history, tester_id, state, issue):

    llm_start = time.perf_counter()

    result = request_processor(
        conversation_history=conversation_history,
        user_message=user_message,
        available_forms=get_forms_for_classifier(),
        available_faqs=get_faqs_for_classifier(),
        rule_hints=build_rule_hints(issue, get_form_hints(user_message)),
    )

    print(
        f"[PERFORMANCE] DSPy/LLM: "
        f"{time.perf_counter() - llm_start:.3f} seconds"
    )

    intent = str(result.intent).strip().upper()

    if intent == "SOP1":

        form = get_form_by_id(str(result.form_id).strip().lower())

        if form is None:

            return {
                "answer": (
                    "ยังไม่พบแบบฟอร์มที่ตรงกับความต้องการค่ะ "
                    "รบกวนอธิบายเพิ่มเติมว่าต้องการดำเนินการเรื่องใด "
                    "เช่น ลาพัก ลาออก เพิ่ม-ถอนวิชา หรือลงทะเบียนล่าช้า"
                ),
                "intent": "SOP1",
                "form": None,
            }

        return build_sop1_result(form, user_message)

    if intent == "FAQ":

        faq = get_faq_by_id(str(result.faq_id).strip().lower())

        if faq is None:

            return {
                "answer": "ขออภัยค่ะ ยังไม่พบข้อมูลที่ตรงกับคำถามนี้",
                "intent": "FAQ",
                "faq_id": None,
            }

        return {
            "answer": faq["answer"],
            "intent": "FAQ",
            "faq_id": faq["faq_id"],
        }

    if intent == "SOP2":

        category = str(result.category).strip().upper()

        if category not in VALID_CATEGORIES:
            category = issue["category"]

        if result.issue_complete:

            return file_issue(
                user_message,
                category,
                tester_id,
                summary=str(result.summary),
                urgent=issue["urgent"],
            )

        question = str(result.reply).strip()

        if not question or question.lower() == "none":
            question = FOLLOWUP_QUESTIONS[issue["missing"] or "DETAIL"]

        return ask_issue_followup(
            user_message,
            category,
            question,
            asked=0,
            state=state,
            urgent=issue["urgent"],
        )

    # GENERAL (or anything unexpected)
    reply = str(result.reply).strip()

    if not reply or reply.lower() == "none":
        reply = (
            "DSI Chatbot สามารถช่วยแนะนำแบบฟอร์มคำร้อง "
            "และรับแจ้งปัญหาหรือข้อร้องเรียนได้ค่ะ"
        )

    return {
        "answer": reply,
        "intent": "GENERAL",
    }


def handle_llm_failure(user_message, tester_id, state, issue):
    """
    LLM timed out / failed: still give the best rule-based answer
    instead of a generic error.
    """

    if issue["is_issue"]:
        return handle_issue_rules(user_message, tester_id, state)

    form_hints = get_form_hints(user_message, limit=1)

    if form_hints:
        return build_sop1_result(get_form_by_id(form_hints[0]), user_message)

    return {
        "answer": (
            "ขออภัยค่ะ ตอนนี้ระบบ AI ใช้งานไม่ได้ชั่วคราว "
            "ยังเข้าใจคำถามนี้ไม่ชัดเจน รบกวนพิมพ์ให้เจาะจงขึ้นอีกนิดนะคะ เช่น\n"
            "📄 \"ลาพักต้องใช้ฟอร์มอะไร\"\n"
            "🛠️ \"แอร์ห้อง 202 ไม่เย็น\""
        ),
        "intent": "GENERAL",
    }


# =========================
# Main entry point
# =========================

def route_message(user_message, conversation_history, tester_id, state):
    """
    Returns (result_dict, path_name).
    """

    pending = state.pop("pending_issue", None)

    # -------------------------
    # 0. Answering a SOP2 follow-up
    # -------------------------

    if pending:

        if _normalize(user_message) in CANCEL_WORDS:

            return {
                "answer": "ยกเลิกการแจ้งปัญหาแล้วค่ะ หากต้องการความช่วยเหลือเพิ่มเติมพิมพ์มาได้เลยค่ะ",
                "intent": "SOP2",
                "issue_id": None,
                "issue_complete": False,
            }, "SOP2 CANCEL"

        # Student clearly switched topic (asks for a form / FAQ instead)
        switched_topic = (
            not analyze_issue(user_message)["concrete"]
            and (find_form_fast(user_message) or find_faq_fast(user_message))
        )

        if not switched_topic:

            return continue_pending_issue(
                user_message,
                pending,
                tester_id,
                state,
            ), "SOP2 FOLLOW-UP"

    # -------------------------
    # 1. Greetings / thanks
    # -------------------------

    general_fast = get_general_fast_response(user_message)

    if general_fast is not None:

        return {
            "answer": general_fast,
            "intent": "GENERAL",
        }, "GENERAL FAST PATH"

    # -------------------------
    # 2. Follow-up about the previous form ("ขอไฟล์หน่อย")
    # -------------------------

    last_form = get_form_by_id(state.get("last_form_id"))

    if (
        last_form
        and any(word in _normalize(user_message) for word in FILE_REQUEST_WORDS)
        and not find_form_fast(user_message)
    ):
        return {
            "answer": (
                f"ได้เลยค่ะ ดาวน์โหลด**{last_form.get('title', last_form['form_name'])}**"
                f"ได้จากปุ่มด้านล่างนี้ค่ะ"
            ),
            "intent": "SOP1",
            "form": last_form,
        }, "SOP1 FOLLOW-UP"

    # -------------------------
    # 3. Rule-based router
    # -------------------------

    issue = analyze_issue(user_message)

    # "ลาออกหรือพักเรียน ต่างกันยังไง" -> compare both forms
    comparison = find_form_comparison(user_message)

    if comparison and not issue["concrete"]:
        return {
            "answer": comparison["answer"],
            "intent": "SOP1",
            "form": comparison["form"],
        }, "SOP1 COMPARE"

    form = find_form_fast(user_message)

    # A concrete problem ("แอร์ห้อง 202 พัง") -> SOP2,
    # unless it also clearly asks for a form ("ลงทะเบียนไม่ทันเพราะระบบล่ม")
    # -> that mix goes to the LLM.
    if issue["concrete"] and not form:
        return handle_issue_rules(user_message, tester_id, state), "SOP2 FAST PATH"

    if form and not issue["concrete"]:
        return build_sop1_result(form, user_message), "SOP1 FAST PATH"

    if not issue["concrete"]:

        faq = find_faq_fast(user_message)

        if faq is not None:

            return {
                "answer": faq["answer"],
                "intent": "FAQ",
                "faq_id": faq["faq_id"],
            }, "FAQ FAST PATH"

        # "อยากแจ้งปัญหา" / "แจ้งปัญหาในสาขา" -> ask what the problem is
        if issue["is_issue"]:
            return handle_issue_rules(user_message, tester_id, state), "SOP2 FAST PATH"

    # -------------------------
    # 3. One LLM call
    # -------------------------

    try:

        return handle_llm(
            user_message,
            conversation_history,
            tester_id,
            state,
            issue,
        ), "LLM"

    except Exception as error:

        print(f"[LLM ERROR] {type(error).__name__}: {error}")

        return handle_llm_failure(
            user_message,
            tester_id,
            state,
            issue,
        ), "RULE FALLBACK"


def process_message(
    user_message: str,
    tester_id: str = "anonymous",
    conversation_history: str = "",
    state: dict | None = None,
) -> dict:
    """
    Returns a dict with answer, response_time, success, intent, ...
    and `state`, which the caller must pass back on the next turn.
    """

    state = dict(state or {})

    user_message = user_message.strip()

    if not user_message:
        return {
            "answer": "กรุณาพิมพ์คำถามก่อนค่ะ",
            "response_time": 0.0,
            "success": False,
            "intent": None,
            "state": state,
        }

    start_time = time.perf_counter()

    try:

        extra_data, path = route_message(
            user_message,
            conversation_history,
            tester_id,
            state,
        )

        success = True

    except Exception as error:

        print(f"Chatbot error: {error}")

        path = "ERROR"
        success = False

        extra_data = {
            "answer": (
                "ขออภัยค่ะ ระบบไม่สามารถประมวลผลคำขอได้ในขณะนี้ "
                "กรุณาลองใหม่อีกครั้งค่ะ"
            ),
            "intent": "ERROR",
        }

    # Remember the last form so "ขอไฟล์หน่อย" on the next turn knows which one
    if extra_data.get("form"):
        state["last_form_id"] = extra_data["form"]["form_id"]

    response_time = time.perf_counter() - start_time

    print(
        f"[PERFORMANCE] {path}: "
        f"{response_time:.3f} seconds"
    )

    return {
        "response_time": round(response_time, 3),
        "success": success,
        "state": state,
        **extra_data,
    }
