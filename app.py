import streamlit as st
from pathlib import Path

from core.config import APP_NAME, TEST_PASSWORD
from core.prompts import WELCOME_MESSAGE, SAMPLE_QUESTIONS
from core.chat_engine import process_message
from core.logger import save_interaction, save_feedback


# Project Path
BASE_DIR = Path(__file__).resolve().parent


# Page Configuration
st.set_page_config(
    page_title=APP_NAME,
    page_icon="💬",
    layout="centered"
)


# =========================
# Session State
# =========================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "tester_id" not in st.session_state:
    st.session_state.tester_id = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

# Multi-turn chatbot state (e.g. an issue report waiting for details)
if "chat_state" not in st.session_state:
    st.session_state.chat_state = {}


# =========================
# Login Page
# =========================

def show_login():

    st.title(APP_NAME)

    st.subheader("เข้าสู่ระบบสำหรับผู้ทดสอบ")

    tester_id = st.text_input(
        "ชื่อหรือรหัสผู้ทดสอบ",
        placeholder="เช่น tester_001"
    )

    password = st.text_input(
        "รหัสผ่าน",
        type="password"
    )

    consent = st.checkbox(
        "ฉันยินยอมเข้าร่วมการทดสอบ "
        "และจะไม่พิมพ์ข้อมูลส่วนบุคคลหรือข้อมูลที่มีความละเอียดอ่อน"
    )

    if st.button(
        "เข้าสู่ระบบ",
        type="primary",
        use_container_width=True
    ):

        tester_id = tester_id.strip()

        if not tester_id:
            st.warning("กรุณากรอกชื่อหรือรหัสผู้ทดสอบ")
            return

        if password != TEST_PASSWORD:
            st.error("รหัสผ่านไม่ถูกต้อง")
            return

        if not consent:
            st.warning(
                "กรุณายืนยันการยินยอมก่อนเริ่มการทดสอบ"
            )
            return

        st.session_state.logged_in = True
        st.session_state.tester_id = tester_id

        st.rerun()


def build_conversation_history(max_messages=6):
    """
    Build recent conversation history for DSPy.
    Limit messages to reduce token usage.
    """

    history = []

    for message in st.session_state.messages[-max_messages:]:

        role = message.get("role")
        content = message.get("content", "").strip()

        if not content:
            continue

        if role == "user":
            history.append(
                f"Student: {content}"
            )

        elif role == "assistant":
            history.append(
                f"Assistant: {content}"
            )

    return "\n".join(history)

# =========================
# Process Question
# =========================

def ask_chatbot(question):

    # Build history BEFORE adding the new question
    conversation_history = build_conversation_history()

    # Show/save user message
    st.session_state.messages.append({
        "role": "user",
        "content": question
    })

    with st.spinner("กำลังประมวลผล..."):

        result = process_message(
            user_message=question,
            tester_id=st.session_state.tester_id,
            conversation_history=conversation_history,
            state=st.session_state.chat_state
        )

    st.session_state.chat_state = result["state"]

    interaction_id = save_interaction(
        tester_id=st.session_state.tester_id,
        question=question,
        answer=result["answer"],
        response_time=result["response_time"],
        success=result["success"]
    )

    st.session_state.messages.append({
        "role": "assistant",
        "content": result["answer"],
        "interaction_id": interaction_id,
        "response_time": result["response_time"],
        "feedback": None,
        "intent": result.get("intent"),
        "form": result.get("form")
    })

# =========================
# Chat Page
# =========================

def show_chat():

    st.title(APP_NAME)

    st.caption(
        f"Tester: {st.session_state.tester_id}"
    )

    # -------------------------
    # Logout
    # -------------------------

    if st.button("ออกจากระบบ"):

        st.session_state.logged_in = False
        st.session_state.tester_id = None
        st.session_state.messages = []
        st.session_state.pending_question = None
        st.session_state.chat_state = {}

        st.rerun()

    st.divider()

    # -------------------------
    # Welcome Message
    # -------------------------

    if len(st.session_state.messages) == 0:

        st.info(WELCOME_MESSAGE)

        st.write("**ตัวอย่างคำถาม**")

        for index, question in enumerate(SAMPLE_QUESTIONS):

            if st.button(
                question,
                key=f"sample_{index}",
                use_container_width=True
            ):

                st.session_state.pending_question = question

                st.rerun()

    # -------------------------
    # Pending Sample Question
    # -------------------------

    if st.session_state.pending_question:

        question = st.session_state.pending_question

        st.session_state.pending_question = None

        ask_chatbot(question)

        st.rerun()

    # -------------------------
    # Chat History
    # -------------------------

    for message in st.session_state.messages:

        with st.chat_message(message["role"]):

            st.write(message["content"])

            # Only assistant messages have feedback / PDF
            if message["role"] == "assistant":

                # =========================
                # SOP1 PDF Download
                # =========================

                form = message.get("form")

                if form:

                    for index, pdf in enumerate(form.get("pdf_files", [])):

                        pdf_path = BASE_DIR / pdf["file"]

                        try:
                            pdf_data = pdf_path.read_bytes()

                        except OSError:

                            st.warning(
                                f"ไม่สามารถอ่านไฟล์ PDF: {pdf['label']} "
                                f"({pdf_path.name})"
                            )
                            continue

                        st.download_button(
                            label=f"📄 ดาวน์โหลด{pdf['label']}",
                            data=pdf_data,
                            file_name=pdf_path.name,
                            mime="application/pdf",
                            key=(
                                f"download_"
                                f"{message['interaction_id']}_{index}"
                            )
                        )

                # =========================
                # Response Time
                # =========================

                response_time = message.get(
                    "response_time"
                )

                if response_time is not None:

                    st.caption(
                        f"Response time: "
                        f"{response_time:.3f} seconds"
                    )

                # =========================
                # Feedback
                # =========================

                interaction_id = message.get(
                    "interaction_id"
                )

                current_feedback = message.get(
                    "feedback"
                )

                if (
                    interaction_id
                    and current_feedback is None
                ):

                    col1, col2, col3 = st.columns(
                        [1, 1, 6]
                    )

                    with col1:

                        if st.button(
                            "👍",
                            key=f"up_{interaction_id}"
                        ):

                            save_feedback(
                                interaction_id,
                                "up"
                            )

                            message["feedback"] = "up"

                            st.rerun()

                    with col2:

                        if st.button(
                            "👎",
                            key=f"down_{interaction_id}"
                        ):

                            save_feedback(
                                interaction_id,
                                "down"
                            )

                            message["feedback"] = "down"

                            st.rerun()

                elif current_feedback == "up":

                    st.caption(
                        "ขอบคุณสำหรับ Feedback 👍"
                    )

                elif current_feedback == "down":

                    st.caption(
                        "ขอบคุณสำหรับ Feedback 👎"
                    )

    # -------------------------
    # Chat Input
    # -------------------------

    user_input = st.chat_input(
        "พิมพ์คำถามที่นี่..."
    )

    if user_input:

        ask_chatbot(user_input)

        st.rerun()


# =========================
# Main
# =========================

if st.session_state.logged_in:

    show_chat()

else:

    show_login()
