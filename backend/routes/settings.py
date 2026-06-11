from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from database import get_database
from auth import get_current_user, get_admin_user
import datetime

router = APIRouter()

class GlossaryUpdate(BaseModel):
    content: str

class IntentsUpdate(BaseModel):
    intents: list[str]

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

@router.get("/intents")
async def get_intents(current_user: dict = Depends(get_current_user)):
    db = get_database()
    settings = await db.system_settings.find_one({"key": "intent_phrases"})
    if settings and "value" in settings:
        return {"intents": settings["value"]}
    
    # Frases y expresiones regulares por defecto
    default_intents = [
        r"\ben\s+(qu[eé]|cual|cu[aá]les)\s+(documento|archivo|pdf|txt|docx|carpeta|ley|reglamento)\b",
        r"\bqu[eé]\s+(documento|archivo|pdf|txt|docx|ley|reglamento)\s+(habla|menciona|trata|dice|es)\b",
        r"\bd[oó]nde\s+(se\s+)?(menciona|dice|habla|nombra|encuentra|lee|cita)\b",
        r"\b(buscar|encuentra|dame|mu[eé]strame)\s+(el|los|un)?\s*(documento|archivo|pdf|txt|docx|ley|reglamento)\b",
        r"\b(en\s+)?qu[eé]\s+parte\s+del?\s+(documento|archivo|pdf|txt|docx|ley|reglamento)\b",
        r"\b(tienes|hay)\s+(alg[uú]n|el|un)?\s*(documento|archivo|ley|reglamento)\b",
        r"\bcu[aá]les?\s+(son\s+)?(los\s+)?(documentos|archivos|pdf|txt|docx|leyes)\s+(relacionados|asociados)\b",
        r"\bdocumentos\s+(relacionados|asociados|vinculados)\s+a\b"
    ]
    return {"intents": default_intents}

@router.put("/intents")
async def update_intents(req: IntentsUpdate, current_user: dict = Depends(get_admin_user)):
    db = get_database()
    filtered_intents = [x.strip() for x in req.intents if x.strip()]
    await db.system_settings.update_one(
        {"key": "intent_phrases"},
        {"$set": {"value": filtered_intents, "updated_at": datetime.datetime.utcnow(), "updated_by": current_user["email"]}},
        upsert=True
    )
    return {"message": "Frases del detector actualizadas correctamente"}
