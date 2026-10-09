import uuid
from datetime import datetime

from core.supabase_client import supabase


def save_issue(
    tester_id,
    category,
    summary,
    detail,
    original_message
):
    """
    Save issue report to Supabase.
    """

    issue_id = (
        f"ISSUE-"
        f"{uuid.uuid4().hex[:8].upper()}"
    )

    created_at = (
        datetime
        .now()
        .astimezone()
        .isoformat()
    )

    data = {
        "issue_id": issue_id,
        "tester_id": tester_id,
        "category": category,
        "summary": summary,
        "detail": detail,
        "original_message": original_message,
        "status": "new",
        "created_at": created_at,
    }

    supabase.table(
        "issue_reports"
    ).insert(
        data
    ).execute()

    return issue_id