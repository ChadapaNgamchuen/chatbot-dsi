import time

from core.dspy_modules import request_processor

from core.form_service import (
    get_forms_for_classifier,
    get_form_by_id,
)

from core.faq_service import (
    get_faqs_for_classifier,
    get_faq_by_id,
)

from core.issue_service import save_issue


def process_message(
    user_message: str,
    tester_id: str = "anonymous",
    conversation_history: str = ""
) -> dict:

    user_message = user_message.strip()

    if not user_message:
        return {
            "answer": "กรุณาพิมพ์คำถามก่อนค่ะ",
            "response_time": 0.0,
            "success": False,
            "intent": None,
        }

    start_time = time.perf_counter()

    try:

        # =========================
        # ONE DSPy / LLM CALL
        # =========================

        result = request_processor(
            conversation_history=conversation_history,
            user_message=user_message,
            available_forms=get_forms_for_classifier(),
            available_faqs=get_faqs_for_classifier(),
        )

        intent = str(
            result.intent
        ).strip().upper()


        # =========================
        # SOP1 — ACADEMIC FORM
        # =========================

        if intent == "SOP1":

            form_id = str(
                result.form_id
            ).strip().lower()

            if form_id == "none":

                answer = (
                    "ยังไม่พบแบบฟอร์มที่ตรงกับความต้องการค่ะ "
                    "กรุณาอธิบายเพิ่มเติมว่าต้องการดำเนินการเรื่องใด"
                )

                form = None

            else:

                form = get_form_by_id(form_id)

                if form is None:
                    raise ValueError(
                        f"Form ID not found: {form_id}"
                    )

                requirements = "\n".join(
                    f"- {item}"
                    for item in form["requirements"]
                )

                answer = (
                    f"📄 แบบฟอร์มที่แนะนำ\n"
                    f"{form['form_name']}\n\n"
                    f"📋 เอกสารที่ต้องใช้\n"
                    f"{requirements}"
                )

            extra_data = {
                "intent": "SOP1",
                "form": form,
            }


        # =========================
        # SOP2 — ISSUE REPORT
        # =========================

        elif intent == "SOP2":

            issue_complete = str(
                result.issue_complete
            ).strip().lower()

            # -------------------------
            # Issue details incomplete
            # -------------------------

            if issue_complete != "yes":

                followup = str(
                    result.followup_question
                ).strip()

                if (
                    not followup
                    or followup.lower() == "none"
                ):
                    followup = (
                        "รบกวนแจ้งรายละเอียดของปัญหาที่พบเพิ่มเติมค่ะ "
                        "เช่น ปัญหาคืออะไร และเกิดขึ้นที่ไหน"
                    )

                answer = followup

                extra_data = {
                    "intent": "SOP2",
                    "issue_id": None,
                    "issue_complete": False,
                }

            # -------------------------
            # Issue details complete
            # -------------------------

            else:

                category = str(
                    result.category
                ).strip().upper()

                valid_categories = {
                    "FACILITY",
                    "IT",
                    "SERVICE",
                    "ACADEMIC",
                    "OTHER",
                }

                if category not in valid_categories:
                    category = "OTHER"

                summary = str(
                    result.summary
                ).strip()

                detail = str(
                    result.detail
                ).strip()

                reply = (
                        "รับเรื่องแจ้งปัญหาเรียบร้อยแล้วค่ะ "
                        "ระบบได้บันทึกข้อมูลเพื่อดำเนินการต่อค่ะ"
                    )

                issue_id = save_issue(
                    tester_id=tester_id,
                    category=category,
                    summary=summary,
                    detail=detail,
                    original_message=user_message
                )

                answer = (
                    f"{reply}\n\n"
                    f"หมายเลขการแจ้งปัญหา: **{issue_id}**"
                )

                extra_data = {
                    "intent": "SOP2",
                    "issue_id": issue_id,
                    "category": category,
                    "issue_complete": True,
                }


        # =========================
        # FAQ
        # =========================

        elif intent == "FAQ":

            faq_id = str(
                result.faq_id
            ).strip().lower()

            if faq_id == "none":

                answer = (
                    "ขออภัยค่ะ "
                    "ยังไม่พบข้อมูลที่ตรงกับคำถามนี้"
                )

            else:

                faq = get_faq_by_id(faq_id)

                if faq is None:
                    raise ValueError(
                        f"FAQ ID not found: {faq_id}"
                    )

                answer = faq["answer"]

            extra_data = {
                "intent": "FAQ",
                "faq_id": faq_id,
            }


        # =========================
        # GENERAL
        # =========================

        elif intent == "GENERAL":

            reply = str(
                result.reply
            ).strip()

            if (
                not reply
                or reply.lower() == "none"
            ):
                reply = (
                    "สวัสดีค่ะ DSI Chatbot สามารถช่วยแนะนำ "
                    "แบบฟอร์มคำร้อง และรับแจ้งปัญหาหรือข้อร้องเรียนได้ค่ะ"
                )

            answer = reply

            extra_data = {
                "intent": "GENERAL"
            }


        # =========================
        # UNKNOWN INTENT
        # =========================

        else:

            raise ValueError(
                f"Unknown intent: {intent}"
            )

        success = True


    except Exception as error:

        print(f"Chatbot error: {error}")

        answer = (
            "ขออภัยค่ะ ระบบไม่สามารถประมวลผลคำขอได้ในขณะนี้ "
            "กรุณาลองใหม่อีกครั้งค่ะ"
        )

        success = False

        extra_data = {
            "intent": "ERROR"
        }


    # =========================
    # Response Time
    # =========================

    response_time = (
        time.perf_counter()
        - start_time
    )

    return {
        "answer": answer,
        "response_time": round(response_time, 3),
        "success": success,
        **extra_data,
    }