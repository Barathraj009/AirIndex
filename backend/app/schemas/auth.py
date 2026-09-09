from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: int
    email: str
    username: str | None = None
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


class OtpExchangeRequest(BaseModel):
    otp_token: str
    email: EmailStr


class OtpVerifyRequest(BaseModel):
    email: EmailStr
    otp: str


class OtpCheckUserResponse(BaseModel):
    exists: bool
    email: str


class RegisterWithOtpRequest(BaseModel):
    email: EmailStr
    otp: str
    username: str
    password: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str = "VIEWER"


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class CheckUserRequest(BaseModel):
    email: EmailStr


class SeedUserRequest(BaseModel):
    email: EmailStr
    username: str
    password: str


class UserRoleUpdate(BaseModel):
    role: str

