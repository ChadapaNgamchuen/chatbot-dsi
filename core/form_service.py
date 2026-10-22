import json
from functools import lru_cache
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
FORMS_PATH = BASE_DIR / "resources" / "forms.json"

# Score >= this is confident enough to answer without the LLM
STRONG_SCORE = 2


@lru_cache(maxsize=1)
def load_forms():
    """
    Load all forms from forms.json (cached: read the file only once).
    """

    with open(
        FORMS_PATH,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


def get_form_ids():
    return [form["form_id"] for form in load_forms()]


def get_form_by_id(form_id):
    """
    Find a form by its form ID.
    """

    for form in load_forms():

        if form["form_id"] == form_id:
            return form

    return None


@lru_cache(maxsize=1)
def get_forms_for_classifier():
    """
    Prepare form information for DSPy (compact JSON = fewer tokens = faster).
    """

    simplified_forms = [
        {
            "form_id": form["form_id"],
            "form_name": form["form_name"],
            "description": form["description"],
        }
        for form in load_forms()
    ]

    return json.dumps(
        simplified_forms,
        ensure_ascii=False,
    )


# "ยังไม่อยากลาออก" must not count as a request to resign
NEGATIONS = ["ไม่อยาก", "ไม่ต้องการ", "ไม่ได้อยาก", "ไม่คิดจะ", "ไม่ได้จะ", "ไม่"]


def _mentions(text, keyword):
    """
    True if keyword appears in text without a negation right before it.
    """

    keyword = keyword.lower()
    start = text.find(keyword)

    while start != -1:

        before = text[:start].rstrip()

        if not any(before.endswith(neg) for neg in NEGATIONS):
            return True

        start = text.find(keyword, start + 1)

    return False


def score_forms(user_message):
    """
    Keyword scoring for every form.
    Keywords live in forms.json, so staff can add synonyms without code changes.

    strong keyword = 2 points, weak keyword = 1 point.
    Negated keywords ("ไม่อยากลาออก") are ignored.
    Returns candidates sorted by score (highest first).
    """

    text = " ".join(user_message.lower().split())

    candidates = []

    for form in load_forms():

        rules = form.get("keywords", {})

        score = 0
        matched = []

        for keyword in rules.get("strong", []):

            if _mentions(text, keyword):
                score += 2
                matched.append(keyword)

        for keyword in rules.get("weak", []):

            if _mentions(text, keyword):
                score += 1
                matched.append(keyword)

        if score > 0:

            candidates.append({
                "form_id": form["form_id"],
                "score": score,
                "matched": matched,
            })

    candidates.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    return candidates


def find_form_fast(user_message):
    """
    Fast form matching for clear academic form requests.

    Clear matches:
        -> return form immediately

    Ambiguous matches:
        -> return None
        -> let DSPy / LLM handle the question
    """

    candidates = score_forms(user_message)

    if not candidates:
        return None

    best = candidates[0]

    second_score = (
        candidates[1]["score"]
        if len(candidates) > 1
        else 0
    )

    print(
        "[SOP1 FAST PATH]",
        "best=",
        best["form_id"],
        "score=",
        best["score"],
        "matched=",
        best["matched"],
    )

    # Confidence too low
    if best["score"] < STRONG_SCORE:
        return None

    # Ambiguous between two forms
    if best["score"] == second_score:
        return None

    return get_form_by_id(
        best["form_id"]
    )


def get_form_hints(user_message, limit=3):
    """
    Weak / ambiguous keyword matches, passed to the LLM as hints
    so it can choose between close candidates more accurately.
    """

    return [
        item["form_id"]
        for item in score_forms(user_message)[:limit]
    ]


COMPARE_WORDS = ["ต่างกัน", "แตกต่าง", "ความต่าง", "เลือกอะไร", "อันไหนดี", "แบบไหนดี", "ดีกว่า", " vs "]


def find_form_comparison(user_message):
    """
    "ลาออกหรือพักเรียน ต่างกันยังไง" -> explain both forms side by side
    instead of picking one. Comparison texts live in forms.json ("compare_with").

    Returns {"answer", "form"} where "form" carries both forms' PDFs, or None.
    """

    text = " " + " ".join(user_message.lower().split()) + " "

    if not any(word in text for word in COMPARE_WORDS):
        return None

    matched_ids = {item["form_id"] for item in score_forms(user_message)}

    for form in load_forms():

        for other_id, comparison in form.get("compare_with", {}).items():

            if form["form_id"] in matched_ids and other_id in matched_ids:

                other = get_form_by_id(other_id)

                pdf_files = []
                for pdf in form["pdf_files"] + other["pdf_files"]:
                    if pdf not in pdf_files:
                        pdf_files.append(pdf)

                return {
                    "answer": comparison,
                    "form": {**form, "pdf_files": pdf_files},
                }

    return None


def get_self_service_answer(form, user_message):
    """
    Student says the period is still open ("ยังไม่เลยกำหนด อยากเพิ่มวิชา")
    -> short answer only: do it at reg.tu.ac.th, no form needed.
    Late or unspecified timing -> None (show the form answer instead).
    """

    self_service = form.get("self_service")

    if not self_service:
        return None

    text = " ".join(user_message.lower().split())

    if (
        any(word in text for word in self_service.get("in_period_any", []))
        and not any(word in text for word in self_service.get("unless_any", []))
    ):
        return self_service["text"]

    return None


def _bullets(items):
    return "\n".join(f"- {item}" for item in items)


def format_form_answer(form, user_message=""):
    """
    Build the SOP1 answer text (shared by the fast path and the LLM path).
    Sections are separated by blank lines so Streamlit markdown keeps them apart.
    """

    sections = []

    # Forms that can also be done online -> "กรณีต้องยื่นแบบฟอร์ม"
    if form.get("self_service"):
        form_heading = "📄 กรณีต้องยื่นแบบฟอร์ม"
    else:
        form_heading = "📄 แบบฟอร์มที่ต้องใช้"

    title = form.get("title", form["form_name"])
    form_section = f"**{form_heading}**\n\n**{title}**"

    if form.get("when_to_use"):
        form_section += (
            "\n\nจำเป็นต้องใช้แบบฟอร์มนี้หากอยู่ในกรณีต่อไปนี้\n\n"
            + _bullets(form["when_to_use"])
        )
    else:
        form_section += f"\n\n{form['description']}"

    sections.append(form_section)

    if form.get("details"):
        sections.append(f"**ℹ️ ข้อควรทราบ**\n\n{_bullets(form['details'])}")

    if form.get("note"):
        sections.append(f"> **หมายเหตุ:** {form['note']}")

    sections.append(f"**📋 เอกสารที่ต้องแนบ**\n\n{_bullets(form['requirements'])}")

    sections.append(
        "**✉️ ช่องทางการยื่น**\n\n"
        "ยื่นที่เจ้าหน้าที่หลักสูตรโดยตรง หรือส่งทางอีเมล "
        "ดาวน์โหลดแบบฟอร์มได้จากปุ่มด้านล่างค่ะ"
    )

    return "\n\n".join(sections)
