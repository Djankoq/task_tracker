from hashlib import sha256

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuthSession, User


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
