from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    first_login: bool
    role: str
    landing_page: str


class TokenData(BaseModel):
    user_id: int
    email: str
    role: str
