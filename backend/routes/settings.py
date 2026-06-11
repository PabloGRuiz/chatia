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
    
    # Frases y expresiones regulares por defecto (soportando plurales y concordancias)
    default_intents = [
        r"\ben\s+(qu[eé]|cual|cu[aá]les)\s+(documento|archivo|pdf|txt|docx|carpeta|ley|reglamento)s?\b",
        r"\bqu[eé]\s+(documento|archivo|pdf|txt|docx|ley|reglamento)s?\s+(hablan|habla|mencionan|menciona|tratan|trata|dicen|dice|son|es)\b",
        r"\bd[oó]nde\s+(se\s+)?(mencionan|menciona|dicen|dice|hablan|habla|nombran|nombra|encuentran|encuentra|leen|lee|citan|cita)\b",
        r"\b(buscar|encuentra|dame|mu[eé]strame)\s+(el|los|un|una|unas|unos)?\s*(documento|archivo|pdf|txt|docx|ley|reglamento)s?\b",
        r"\b(en\s+)?qu[eé]\s+parte\s+del?s?\s+(documento|archivo|pdf|txt|docx|ley|reglamento)s?\b",
        r"\b(tienes|hay)\s+(alg[uú]n|algunos|el|los|un|una|unos|unas)?\s*(documento|archivo|ley|reglamento)s?\b",
        r"\bcu[aá]les?\s+(son\s+|est[aá]n\s+)?(los\s+)?(documento|archivo|pdf|txt|docx|ley|reglamento)s?\s+(relacionados|asociados|vinculados|vinculado|relacionado|asociado)s?\b",
        r"\bcu[aá]les?\s+(documento|archivo|pdf|txt|docx|ley|reglamento)s?\s+(son\s+|est[aá]n\s+)?(relacionados|asociados|vinculados|vinculado|relacionado|asociado)s?\b",
        r"\b(documento|archivo|pdf|txt|docx|ley|reglamento)s?\s+(relacionados|asociados|vinculados|vinculado|relacionado|asociado)s?\s+a\b",
        r"\bqu[eé]\s+(documento|archivo|pdf|txt|docx|ley|reglamento)s?\s+(est[aá]n\s+)?(relacionados|asociados|vinculados|vinculado|relacionado|asociado)s?\s+(con|a)\b"
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

@router.delete("/intents")
async def reset_intents(current_user: dict = Depends(get_admin_user)):
    db = get_database()
    await db.system_settings.delete_one({"key": "intent_phrases"})
    return {"message": "Detector restablecido a frases por defecto"}
