from hashlib import pbkdf2_hmac, sha256
from secrets import token_hex

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuthSession, User


def hash_password(password: str) -> str:
    salt = token_hex(16)
    digest = pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 600_000)
    return f"pbkdf2_sha256$600000${salt}${digest.hex()}"


def get_user_by_session_token(db: Session, token: str) -> User | None:
    token_hash = sha256(token.encode("utf-8")).digest()
    statement = (
        select(User)
        .join(User.auth_sessions)
        .where(
            User.is_active.is_(True),
            AuthSession.token_hash == token_hash,
            AuthSession.expires_at > func.statement_timestamp(),
            AuthSession.revoked_at.is_(None),
        )
    )
    return db.scalar(statement)
