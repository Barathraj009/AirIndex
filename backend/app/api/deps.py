from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import Role, TokenConfig, decode_token, TokenError, has_permission
from app.models.auth import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def _token_config() -> TokenConfig:
    s = get_settings()
    return TokenConfig(
        secret_key=s.jwt_secret_key,
        algorithm=s.jwt_algorithm,
        access_token_expire_minutes=s.access_token_expire_minutes,
        refresh_token_expire_days=s.refresh_token_expire_days,
    )


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = decode_token(token, _token_config(), expected_type="access")
    except TokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e),
                             headers={"WWW-Authenticate": "Bearer"})

    user = db.query(User).filter(User.email == payload["sub"]).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user_not_found_or_inactive")
    return user


def require_permission(permission: str):
    """Usage: `current_user: User = Depends(require_permission("manage_routes"))`
    Checks the caller's role against the single-source-of-truth
    PERMISSIONS matrix in app.core.security, per spec section 9."""

    def _checker(user: User = Depends(get_current_user)) -> User:
        role = Role(user.role)
        if not has_permission(role, permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                 detail=f"role {role.value} lacks permission '{permission}'")
        return user

    return _checker
