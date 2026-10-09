import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

FAQ_PATH = (
    BASE_DIR
    / "resources"
    / "faq.json"
)


def load_faqs():
    """Load all FAQs."""

    with open(
        FAQ_PATH,
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def get_faq_by_id(faq_id):
    """Find FAQ by ID."""

    faqs = load_faqs()

    for faq in faqs:
        if faq["faq_id"] == faq_id:
            return faq

    return None


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