import json
from datetime import datetime, timedelta, timezone
from dashboard.sessions import hash_session_id
from src.database.session_repository import SessionRepository
from src.database.connection import DatabaseManager

db = DatabaseManager()
repo = SessionRepository(db)

# Create admin session
admin_sid = secrets.token_urlsafe(32)
admin_hash = hash_session_id(admin_sid)

admin_data = {
    "admin_authenticated": True,
    "admin_user_id": 1,
    "admin_username": "admin",
    "admin_role": "Administrator",
    "role": "Administrator",
    "is_admin": True,
}

expires_at = datetime.now(timezone.utc) + timedelta(hours=2)

repo.save_session(
    session_hash=admin_hash,
    session_data=admin_data,
    expires_at=expires_at,
    account_id="1",
    account_type="admin"
)

# Create user session
user_sid = secrets.token_urlsafe(32)
user_hash = hash_session_id(user_sid)
user_data = {
    "authenticated": True,
    "user_id": 1,
    "username": "user",
    "role": "User",
}
repo.save_session(
    session_hash=user_hash,
    session_data=user_data,
    expires_at=expires_at,
    account_id="1",
    account_type="user"
)

print(json.dumps({
    "admin_sid": admin_sid,
    "user_sid": user_sid,
    "sample_opp_id": "3e6db3a4-d80b-46d5-837d-51e962a8f550"
}))
