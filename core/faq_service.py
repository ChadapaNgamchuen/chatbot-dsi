import json
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

FAQ_PATH = (
    BASE_DIR
    / "resources"
    / "faq.json"
)


@lru_cache(maxsize=1)
def load_faqs():
    """Load all FAQs (cached: read the file only once)."""

    with open(
        FAQ_PATH,
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def get_faq_ids():
    return [faq["faq_id"] for faq in load_faqs()]


def get_faq_by_id(faq_id):
    """Find FAQ by ID."""

    for faq in load_faqs():
        if faq["faq_id"] == faq_id:
            return faq

    return None


@lru_cache(maxsize=1)
def get_faqs_for_classifier():
    """Prepare FAQ data for DSPy."""

    faqs = load_faqs()

    simplified_faqs = []

    for faq in faqs:
        simplified_faqs.append({
            "faq_id": faq["faq_id"],
            "question": faq["question"],
            "keywords": faq["keywords"]
        })

    return json.dumps(
        simplified_faqs,
        ensure_ascii=False
    )

def find_faq_fast(user_message):
    """
    Fast FAQ matching with confidence scoring.

    Clear matches:
        -> return FAQ immediately

    Ambiguous matches:
        -> return None
        -> let DSPy / LLM handle the question
    """

    text = (
        user_message
        .strip()
        .lower()
    )

    faqs = load_faqs()

    candidates = []

    for faq in faqs:

        # ถ้ามี FAQ ที่เกี่ยวกับการเลือกแบบฟอร์มโดยตรง
        # ไม่ให้ Fast Path ดักไว้ก่อน SOP1
        if faq.get("category") == "late_registration":
            continue

        score = 0
        matched_keywords = []

        for keyword in faq.get("keywords", []):

            keyword_normalized = (
                keyword
                .strip()
                .lower()
            )

            if not keyword_normalized:
                continue

            if keyword_normalized in text:

                matched_keywords.append(
                    keyword
                )

                # phrase ที่ยาว/เฉพาะเจาะจง
                # ให้คะแนนมากกว่า keyword สั้น ๆ
                if len(keyword_normalized) >= 8:
                    score += 2

                else:
                    score += 1

        if score > 0:

            candidates.append({
                "faq": faq,
                "score": score,
                "matched_keywords": matched_keywords,
            })


    # ไม่เจออะไรเลย
    if not candidates:
        return None


    # เรียงคะแนนจากมากไปน้อย
    candidates.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    best = candidates[0]

    second_score = (
        candidates[1]["score"]
        if len(candidates) > 1
        else 0
    )


    print(
        "[FAQ FAST PATH]",
        "best=",
        best["faq"]["faq_id"],
        "score=",
        best["score"],
        "matched=",
        best["matched_keywords"],
    )


    # =========================
    # Confidence check
    # =========================

    # ต้องได้อย่างน้อย 2 คะแนน
    if best["score"] < 2:
        return None

    # ถ้า FAQ สองตัวคะแนนเท่ากัน
    # ถือว่ายังไม่มั่นใจ
    if best["score"] == second_score:
        return None


    return best["faq"]