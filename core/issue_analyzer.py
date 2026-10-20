"""
Rule-based analysis for SOP2 (issue / complaint reports).

Runs in microseconds, so most problem reports never need the LLM:

    "ไฟห้อง 202 ไม่ติด"  -> FACILITY, complete     -> save immediately
    "แอร์พัง"            -> FACILITY, no location  -> ask "ห้องไหน"
    "อาจารย์ ... ไม่ดี"   -> ACADEMIC, too vague    -> ask what happened
    "แจ้งปัญหาในสาขา"     -> vague                  -> ask what the problem is
"""

import re


# =========================
# Keyword tables
# =========================

# Words that mean "something is wrong"
PROBLEM_WORDS = [
    "พัง", "เสีย", "ชำรุด", "ไม่ติด", "ไม่ทำงาน", "ใช้ไม่ได้",
    "ใช้งานไม่ได้", "เข้าไม่ได้", "ล็อกอินไม่ได้", "ไม่เย็น",
    "ไม่ไหล", "รั่ว", "ซึม", "หัก", "แตก", "ไฟดับ", "กระพริบ",
    "หลุด", "ล่ม", "ค้าง", "error", "เหม็น", "สกปรก", "อุดตัน",
    "ตัน", "ไม่สะอาด", "ช็อต", "ไหม้", "ท่วม", "ไม่มีสัญญาณ",
    "หลุดบ่อย", "ช้ามาก", "เปิดไม่ติด", "ไม่ออก",
]

# Words that mean "a person behaved badly" (complaint)
CONDUCT_WORDS = [
    "พฤติกรรม", "ไม่เหมาะสม", "ไม่สุภาพ", "พูดจา", "ด่า",
    "ตะคอก", "ดูถูก", "เหยียด", "คุกคาม", "ล่วงละเมิด",
    "เลือกปฏิบัติ", "ไม่มาสอน", "มาสอนสาย", "ไม่ดี", "แย่",
    "ไม่ยุติธรรม", "บูลลี่", "รังแก", "ข่มขู่",
]

# Generic "I want to report something" with no detail
VAGUE_REPORT_WORDS = [
    "ปัญหา", "ร้องเรียน", "อยากแจ้ง", "ขอแจ้ง", "แจ้งเรื่อง",
    "รายงานเรื่อง", "complain",
]

# Serious issues: tell the student to also contact staff directly
URGENT_WORDS = [
    "ไฟไหม้", "ไฟช็อต", "ไฟดูด", "ควัน", "น้ำท่วม", "คุกคาม",
    "ล่วงละเมิด", "ทำร้าย", "ข่มขู่", "บาดเจ็บ", "อันตราย",
]

CATEGORY_OBJECTS = {
    "FACILITY": [
        "หลอดไฟ", "ไฟ", "แอร์", "เครื่องปรับอากาศ", "พัดลม",
        "ห้องน้ำ", "ส้วม", "ชักโครก", "ก๊อก", "ประตู", "หน้าต่าง",
        "โต๊ะ", "เก้าอี้", "ลิฟต์", "บันได", "หลังคา", "ปลั๊ก",
        "โปรเจคเตอร์", "โปรเจกเตอร์", "projector", "ไมค์", "ลำโพง",
        "จอ", "ทีวี", "กระดาน", "ไวท์บอร์ด", "น้ำ", "ที่จอดรถ",
        "ขยะ", "มด", "แมลง", "หนู", "กุญแจ", "ห้องเรียน",
    ],
    "IT": [
        "wifi", "wi-fi", "ไวไฟ", "อินเทอร์เน็ต", "อินเตอร์เน็ต",
        "เน็ต", "ระบบ", "เว็บ", "เว็บไซต์", "reg", "อีเมล",
        "email", "คอมพิวเตอร์", "คอม", "login", "รหัสผ่าน",
        "เครื่องพิมพ์", "ปริ้น", "printer", "แอป", "moodle",
    ],
    "ACADEMIC": [
        "อาจารย์", "อ.", "ผู้สอน", "การสอน", "ตารางเรียน",
        "ตารางสอบ", "ข้อสอบ", "เกรด", "หลักสูตร", "ผู้ช่วยสอน",
    ],
    "SERVICE": [
        "เจ้าหน้าที่", "พนักงาน", "บริการ", "ฝ่ายทะเบียน",
        "รปภ", "แม่บ้าน", "การให้บริการ",
    ],
}

# A location such as "ห้อง 202", "202", "ชั้น 3", "อาคาร", "SC-1203"
LOCATION_PATTERN = re.compile(
    r"(ห้อง\s*[a-zA-Z]{0,3}\s*-?\s*\d+"
    r"|(?<!\d)\d{3,4}(?!\d)"
    r"|ชั้น\s*\d+"
    r"|อาคาร|ตึก|โรงอาหาร|ห้องสมุด|ลานจอด|โถง|ทางเดิน|ล็อบบี้|lobby"
    r"|[a-zA-Z]{1,3}-?\d{3,4})",
    re.IGNORECASE,
)

# Something that identifies which course / person a complaint is about
SUBJECT_PATTERN = re.compile(
    r"(วิชา\s*\S+"
    r"|[a-zA-Z]{2,4}\s?\d{3}"
    r"|อาจารย์\s*(?!คนนี้|ท่านนี้|คนหนึ่ง|บางคน|ที่)[ก-๙a-zA-Z]{2,}"
    r"|อ\.\s*[ก-๙a-zA-Z]{2,}"
    r"|เจ้าหน้าที่\s*(?:ฝ่าย|ห้อง|ชื่อ)\S+)",
    re.IGNORECASE,
)

FOLLOWUP_QUESTIONS = {
    "VAGUE": (
        "ยินดีรับแจ้งปัญหาค่ะ 🛠️ รบกวนเล่ารายละเอียดเพิ่มเติมหน่อยนะคะ "
        "เช่น พบปัญหาอะไร และเกิดขึ้นที่ไหน "
        "(ตัวอย่าง: \"แอร์ห้อง 202 ไม่เย็น\")"
    ),
    "LOCATION": (
        "รับทราบค่ะ รบกวนแจ้งสถานที่ที่พบปัญหาด้วยนะคะ "
        "เช่น อาคาร / ชั้น / หมายเลขห้อง"
    ),
    "CONDUCT": (
        "ขอบคุณที่แจ้งเรื่องนี้ค่ะ 🙏 เพื่อให้ส่งต่อผู้รับผิดชอบได้ถูกต้อง "
        "รบกวนให้ข้อมูลเพิ่มเติมดังนี้ค่ะ\n"
        "- เป็นบุคคลใด หรือเกิดในรายวิชาใด\n"
        "- เหตุการณ์ที่เกิดขึ้นโดยสรุป\n"
        "- วัน/เวลาโดยประมาณ\n\n"
        "ข้อมูลนี้จะถูกส่งให้ผู้รับผิดชอบของคณะพิจารณาเท่านั้นค่ะ"
    ),
    "DETAIL": (
        "รบกวนอธิบายเพิ่มเติมอีกนิดนะคะ ว่าพบปัญหาอะไร "
        "และเกิดขึ้นที่ไหน/เมื่อไหร่"
    ),
}


def _contains_any(text, words):
    return [word for word in words if word in text]


def _detect_category(text):
    """Return the category whose object words match best (longest match wins ties)."""

    best_category = None
    best_score = 0

    for category, words in CATEGORY_OBJECTS.items():

        matched = _contains_any(text, words)

        score = sum(len(word) for word in matched)

        if score > best_score:
            best_category = category
            best_score = score

    return best_category


def analyze_issue(text):
    """
    Analyze a (possibly multi-turn, concatenated) issue description.

    Returns a dict:
        is_issue        - message looks like a problem / complaint
        category        - FACILITY / IT / ACADEMIC / SERVICE / OTHER
        complete        - enough detail to file the report
        missing         - which follow-up to ask (VAGUE / LOCATION / CONDUCT / DETAIL)
        urgent          - safety or harassment issue
        concrete        - real problem / conduct signal, not just "อยากแจ้งปัญหา"
    """

    normalized = " ".join(text.lower().split())

    # "ไฟล์" (file) contains "ไฟ" (light) -> avoid false FACILITY matches
    normalized = normalized.replace("ไฟล์", "file")

    problems = _contains_any(normalized, PROBLEM_WORDS)
    conducts = _contains_any(normalized, CONDUCT_WORDS)
    vague = _contains_any(normalized, VAGUE_REPORT_WORDS)
    urgent = bool(_contains_any(normalized, URGENT_WORDS))

    category = _detect_category(normalized)
    has_location = bool(LOCATION_PATTERN.search(normalized))
    has_subject = bool(SUBJECT_PATTERN.search(normalized))

    # Harassment "in the bathroom" is about a person, not the facility
    is_conduct = bool(conducts) and (
        category in {"ACADEMIC", "SERVICE", None} or urgent
    )

    is_issue = bool(
        vague
        or urgent
        or is_conduct
        or (problems and category)
    )

    result = {
        "is_issue": is_issue,
        "category": category or "OTHER",
        "complete": False,
        "missing": None,
        "urgent": urgent,
        "concrete": bool(urgent or is_conduct or (problems and category)),
    }

    if not is_issue:
        return result

    # Safety first: never delay an urgent report with follow-up questions
    if urgent:
        if is_conduct and category not in {"ACADEMIC", "SERVICE"}:
            result["category"] = "OTHER"
        result["complete"] = True
        return result

    # -------------------------
    # Complaint about a person
    # -------------------------

    if is_conduct:

        result["category"] = category or "OTHER"

        # Need: who / which course + a concrete description of what happened.
        # "อาจารย์คนนี้มีพฤติกรรมที่ไม่ดี" (no who, no what) -> ask.
        specific_conduct = [
            word for word in conducts
            if word not in {"พฤติกรรม", "ไม่ดี", "แย่", "ไม่เหมาะสม"}
        ]

        if has_subject and (specific_conduct or len(normalized) >= 60):
            result["complete"] = True
        else:
            result["missing"] = "CONDUCT"

        return result

    # -------------------------
    # Broken thing / system
    # -------------------------

    if problems and category:

        # Facilities must have a location; IT systems usually do not
        needs_location = category == "FACILITY"

        if needs_location and not has_location:
            result["missing"] = "LOCATION"
        else:
            result["complete"] = True

        return result

    # -------------------------
    # "อยากแจ้งปัญหา" with no detail
    # -------------------------

    result["missing"] = "VAGUE" if vague and not problems else "DETAIL"

    return result


def build_summary(text, category):
    """Short one-line summary for the issue list (no LLM needed)."""

    one_line = " ".join(text.split())

    if len(one_line) > 120:
        one_line = one_line[:117] + "..."

    return f"[{category}] {one_line}"
