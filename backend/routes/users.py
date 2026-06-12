import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from typing import List
from database import get_database
from auth import get_password_hash, get_current_user, get_admin_user, verify_password
from bson import ObjectId

router = APIRouter()


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    role: str
    created_at: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str = "user"


class UserUpdateRole(BaseModel):
    role: str


class PasswordChange(BaseModel):
    old_password: str
    new_password: str


class PasswordReset(BaseModel):
    new_password: str


@router.get("/", response_model=List[UserResponse])
async def list_users(current_user: dict = Depends(get_admin_user)):
    db = get_database()
    users_cursor = db.users.find()
    users = await users_cursor.to_list(length=100)

    return [
        UserResponse(
            id=str(user["_id"]),
            email=user["email"],
            role=user["role"],
            created_at=user["created_at"].isoformat()
            if hasattr(user["created_at"], "isoformat")
            else str(user["created_at"]),
        )
        for user in users
    ]


@router.post("/", response_model=UserResponse)
async def create_user(
    user_data: UserCreate, current_user: dict = Depends(get_admin_user)
):
    db = get_database()

    # Check if email exists
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="El correo ya está registrado")

    new_user = {
        "email": user_data.email,
        "password_hash": get_password_hash(user_data.password),
        "role": user_data.role,
        "created_at": datetime.datetime.utcnow(),
    }

    result = await db.users.insert_one(new_user)

    return UserResponse(
        id=str(result.inserted_id),
        email=new_user["email"],
        role=new_user["role"],
        created_at=new_user["created_at"].isoformat(),
    )


@router.put("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: str,
    role_data: UserUpdateRole,
    current_user: dict = Depends(get_admin_user),
):
    db = get_database()

    if role_data.role not in ["admin", "user"]:
        raise HTTPException(status_code=400, detail="Rol inválido")

    try:
        obj_id = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")

    user = await db.users.find_one({"_id": obj_id})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    await db.users.update_one({"_id": obj_id}, {"$set": {"role": role_data.role}})

    return UserResponse(
        id=str(user["_id"]),
        email=user["email"],
        role=role_data.role,
        created_at=user["created_at"].isoformat()
        if hasattr(user["created_at"], "isoformat")
        else str(user["created_at"]),
    )


@router.delete("/{user_id}")
async def delete_user(user_id: str, current_user: dict = Depends(get_admin_user)):
    db = get_database()

    try:
        obj_id = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")

    user = await db.users.find_one({"_id": obj_id})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Evitar que el admin se borre a sí mismo
    if user["email"] == current_user["email"]:
        raise HTTPException(
            status_code=400, detail="No puedes eliminar tu propia cuenta"
        )

    await db.users.delete_one({"_id": obj_id})
    return {"message": "Usuario eliminado exitosamente"}


@router.put("/me/password")
async def change_my_password(
    pass_data: PasswordChange, current_user: dict = Depends(get_current_user)
):
    db = get_database()

    user = await db.users.find_one({"email": current_user["email"]})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if not verify_password(pass_data.old_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")

    new_hash = get_password_hash(pass_data.new_password)
    await db.users.update_one(
        {"email": current_user["email"]}, {"$set": {"password_hash": new_hash}}
    )

    return {"message": "Contraseña actualizada exitosamente"}


@router.put("/{user_id}/reset-password")
async def reset_user_password(
    user_id: str, pass_data: PasswordReset, current_user: dict = Depends(get_admin_user)
):
    db = get_database()

    try:
        obj_id = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")

    user = await db.users.find_one({"_id": obj_id})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    new_hash = get_password_hash(pass_data.new_password)
    await db.users.update_one({"_id": obj_id}, {"$set": {"password_hash": new_hash}})

    return {"message": "Contraseña reseteada exitosamente"}
