from supabase import create_client, Client

from core.config import (
    SUPABASE_URL,
    SUPABASE_SECRET_KEY,
)


if not SUPABASE_URL:
    raise ValueError(
        "SUPABASE_URL is missing"
    )

if not SUPABASE_SECRET_KEY:
    raise ValueError(
        "SUPABASE_SECRET_KEY is missing"
    )


supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY
)