import os
import json
import hmac
import hashlib
import base64
import logging
import requests

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks

app = FastAPI()
logger = logging.getLogger(__name__)

LINE_API = "https://api.line.me/v2/bot/message/push"


@app.get("/health")
def health():
    return {"status": "ok"}


def send_to_line(user_id: str, text: str):
    token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]

    response = requests.post(
        LINE_API,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "to": user_id,
            "messages": [
                {"type": "text", "text": text[:4900]}
            ],
        },
        timeout=15,
    )
    response.raise_for_status()



def handle_message(user_id: str, user_text: str):
    try:
        mode = os.getenv("BOT_MODE", "echo")

        if mode == "echo":
            answer = f"LINE เชื่อมต่อสำเร็จ! คุณส่งว่า: {user_text}"

        else:
            # Reuse the existing Chatbot Engine
            from core.chat_engine import process_message

            tester_id = "line_" + hashlib.sha256(
                user_id.encode("utf-8")
            ).hexdigest()[:16]

            result = process_message(
                user_message=user_text,
                tester_id=tester_id,
                conversation_history=[],
            )

            answer = result.get("answer") or "ไม่พบคำตอบค่ะ"

            # เพิ่มตรงนี้: ดึงลิงก์ PDF จาก forms.json
            form = result.get("form") or {}

            for pdf in form.get("pdf_files", []):
                pdf_url = pdf.get("url")
                label = pdf.get("label", "แบบฟอร์ม")

                if pdf_url:
                    answer += f"\n\n📥 {label}\n{pdf_url}"

    except Exception:
        logger.exception("Chatbot processing failed")
        answer = "ขออภัยค่ะ ระบบขัดข้อง กรุณาลองใหม่อีกครั้ง"

    try:
        send_to_line(user_id, answer)
    except Exception:
        logger.exception("Sending LINE message failed")



@app.post("/callback")
async def callback(request: Request, background_tasks: BackgroundTasks):
    raw_body = await request.body()
    signature = request.headers.get("x-line-signature", "")
    secret = os.environ["LINE_CHANNEL_SECRET"]

    expected = base64.b64encode(
        hmac.new(
            secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")

    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=403, detail="Invalid signature")

    payload = json.loads(raw_body)

    for event in payload.get("events", []):
        if event.get("type") != "message":
            continue

        message = event.get("message", {})
        if message.get("type") != "text":
            continue

        user_id = event.get("source", {}).get("userId")
        text = message.get("text", "")

        if user_id and text:
            background_tasks.add_task(
                handle_message, user_id, text
            )

    return {"ok": True}
