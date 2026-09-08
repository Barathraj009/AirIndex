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
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str = "VIEWER"
