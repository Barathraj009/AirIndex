from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token, TokenError
from app.models.auth import User, AuditLogEntry
from app.schemas.auth import (
    LoginRequest, TokenResponse, RefreshRequest, UserOut,
    OtpExchangeRequest, OtpVerifyRequest, OtpCheckUserResponse,
    RegisterWithOtpRequest, ChangePasswordRequest, SeedUserRequest,
    CheckUserRequest
)
from app.api.deps import get_current_user, _token_config

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/check-user")
def check_user(payload: CheckUserRequest, db: Session = Depends(get_db)):
    """Check if a user exists by email address."""
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    return OtpCheckUserResponse(
        exists=user is not None,
        email=payload.email.lower()
    )


@router.post("/register-with-otp", response_model=TokenResponse)
def register_with_otp(payload: RegisterWithOtpRequest, db: Session = Depends(get_db)):
    """Register a new user with username/password after OTP verification."""
    settings = get_settings()

    # Verify the OTP token
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

    # Check if user already exists
    existing_user = db.query(User).filter(User.email == otp_email).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_already_exists")

    # Check if username is taken
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="username_taken")

    # Create new user
    user = User(
        email=otp_email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
        role="VIEWER",
        is_active=True,
    )
    db.add(user)
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    # Generate tokens
    from app.core.security import Role
    config = _token_config()
    access = create_access_token(user.email, Role(user.role), config)
    refresh = create_refresh_token(user.email, config)

    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/login-with-password", response_model=TokenResponse)
def login_with_password(payload: LoginRequest, db: Session = Depends(get_db)):
    """Login with email and password (after OTP verification)."""
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")

    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")

    from app.core.security import Role
    config = _token_config()
    access = create_access_token(user.email, Role(user.role), config)
    refresh = create_refresh_token(user.email, config)

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/change-password")
def change_password(payload: ChangePasswordRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not verify_password(payload.old_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="incorrect_old_password")
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="password_too_short")
    current_user.hashed_password = hash_password(payload.new_password)
    db.add(AuditLogEntry(user_id=current_user.id, user_email=current_user.email, action="CHANGE_PASSWORD", entity_type="User", entity_id=str(current_user.id)))
    db.commit()
    return {"status": "password_updated"}



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


@router.post("/seed-user")
def seed_user(payload: SeedUserRequest, db: Session = Depends(get_db)):
    """Seed or update a user (dev only)."""
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        existing.hashed_password = hash_password(payload.password)
        existing.username = payload.username
        db.commit()
        return {"status": "updated", "email": payload.email, "username": payload.username}
    
    if db.query(User).filter(User.username == payload.username).first():
        return {"status": "username_taken", "username": payload.username}
    
    user = User(
        email=payload.email.lower(),
        username=payload.username,
        hashed_password=hash_password(payload.password),
        role="ADMIN",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"status": "created", "email": payload.email, "username": payload.username}
