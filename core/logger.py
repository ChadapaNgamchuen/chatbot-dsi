import uuid
from datetime import datetime

from core.config import (
    MOCK_MODE,
    LLM_MODEL,
)

from core.supabase_client import supabase


def save_interaction(
    tester_id,
    question,
    answer,
    response_time,
    success
):
    """
    Save chatbot interaction to Supabase.
    """

    interaction_id = str(
        uuid.uuid4()
    )

    model = (
        "mock"
        if MOCK_MODE
        else LLM_MODEL
    )

    timestamp = (
        datetime
        .now()
        .astimezone()
        .isoformat()
    )

    data = {
        "interaction_id": interaction_id,
        "tester_id": tester_id,
        "question": question,
        "answer": answer,
        "response_time": response_time,
        "success": success,
        "model": model,
        "timestamp": timestamp,
        "feedback": None,
        "feedback_at": None,
    }

    supabase.table(
        "chat_logs"
    ).insert(
        data
    ).execute()

    return interaction_id


def save_feedback(
    interaction_id,
    feedback
):
    """
    Save thumbs up/down feedback to Supabase.
    """

    if feedback not in {
        "up",
        "down",
    }:
        raise ValueError(
            "Feedback must be 'up' or 'down'"
        )

    feedback_at = (
        datetime
        .now()
        .astimezone()
        .isoformat()
    )

    supabase.table(
        "chat_logs"
    ).update({
        "feedback": feedback,
        "feedback_at": feedback_at,
    }).eq(
        "interaction_id",
        interaction_id
    ).execute()