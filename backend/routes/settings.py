from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from database import get_database
from auth import get_current_user, get_admin_user
import datetime

router = APIRouter()

class GlossaryUpdate(BaseModel):
    content: str

@router.get("/glossary")
async def get_glossary(current_user: dict = Depends(get_current_user)):
    db = get_database()
    settings = await db.system_settings.find_one({"key": "military_glossary"})
    if settings and "value" in settings:
        return {"content": settings["value"]}
    return {"content": ""}

@router.put("/glossary")
async def update_glossary(glossary: GlossaryUpdate, current_user: dict = Depends(get_admin_user)):
    db = get_database()
    await db.system_settings.update_one(
        {"key": "military_glossary"},
        {"$set": {"value": glossary.content, "updated_at": datetime.datetime.utcnow(), "updated_by": current_user["email"]}},
        upsert=True
    )
    return {"message": "Glosario actualizado correctamente"}
