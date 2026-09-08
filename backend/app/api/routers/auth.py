from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token, TokenError
from app.models.auth import User
from app.schemas.auth import LoginRequest, TokenResponse, RefreshRequest, UserOut, OtpExchangeRequest
from app.api.deps import get_current_user, _token_config

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not user.is_active or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")

    from app.core.security import Role
    config = _token_config()
    access = create_access_token(user.email, Role(user.role), config)
    refresh = create_refresh_token(user.email, config)

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    config = _token_config()
    try:
        decoded = decode_token(payload.refresh_token, config, expected_type="refresh")
    except TokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    user = db.query(User).filter(User.email == decoded["sub"]).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user_not_found_or_inactive")

    from app.core.security import Role
    access = create_access_token(user.email, Role(user.role), config)
    new_refresh = create_refresh_token(user.email, config)
    return TokenResponse(access_token=access, refresh_token=new_refresh)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/otp/exchange", response_model=TokenResponse)
def otp_exchange(payload: OtpExchangeRequest, db: Session = Depends(get_db)):
    settings = get_settings()
    try:
        otp_payload = jwt.decode(
            payload.otp_token,
            settings.otp_service_jwt_secret,
            algorithms=["HS256"],
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_otp_token")

    otp_email = otp_payload.get("email", "").lower()
    if not otp_email or otp_payload.get("authMethod") != "gmail-otp":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_otp_token")

    if otp_email != payload.email.lower():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="email_mismatch")

    email = otp_email
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(
            email=email,
            hashed_password=hash_password(""),
            role="ADMIN",
            is_active=True,
        )
        db.add(user)

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    from app.core.security import Role
    config = _token_config()
    access = create_access_token(user.email, Role(user.role), config)
    refresh = create_refresh_token(user.email, config)

    return TokenResponse(access_token=access, refresh_token=refresh)
