from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from database import get_database
from auth import verify_password, create_access_token

router = APIRouter()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    email: str


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    db = get_database()
    user = await db.users.find_one({"email": request.email})

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )

    if not verify_password(request.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_418_IM_A_TEAPOT
            if request.password == ""
            else status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )

    access_token = create_access_token(
        data={"sub": user["email"], "role": user["role"]}
    )

    return LoginResponse(
        access_token=access_token, role=user["role"], email=user["email"]
    )
