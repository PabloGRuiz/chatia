from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from database import get_database, get_qdrant
from bson import ObjectId
from qdrant_client.http import models as qd_models
import datetime

router = APIRouter()

class FolderCreate(BaseModel):
    name: str
    description: str = ""

@router.get("/")
async def list_folders():
    db = get_database()
    folders = await db.folders.find().to_list(100)
    for folder in folders:
        folder["id"] = str(folder["_id"])
        del folder["_id"]
        if "created_at" in folder and isinstance(folder["created_at"], str) == False:
            folder["created_at"] = folder["created_at"].isoformat()
    return folders

from auth import get_admin_user
from fastapi import Depends

@router.post("/")
async def create_folder(folder: FolderCreate, current_user: dict = Depends(get_admin_user)):
    db = get_database()
    new_folder = {
        "name": folder.name,
        "description": folder.description,
        "created_at": datetime.datetime.utcnow()
    }
    res = await db.folders.insert_one(new_folder)
    return {
        "id": str(res.inserted_id),
        "name": folder.name,
        "description": folder.description
    }

@router.delete("/{folder_id}")
async def delete_folder(folder_id: str, current_user: dict = Depends(get_admin_user)):
    db = get_database()
    qdrant = get_qdrant()
    
    try:
        oid = ObjectId(folder_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID de carpeta inválido.")
        
    folder = await db.folders.find_one({"_id": oid})
    if not folder:
        raise HTTPException(status_code=404, detail="Carpeta no encontrada.")
        
    # 1. Eliminar todos los vectores asociados a esta carpeta en Qdrant
    try:
        qdrant.delete(
            collection_name="documents",
            points_selector=qd_models.FilterSelector(
                filter=qd_models.Filter(
                    must=[
                        qd_models.FieldCondition(key="folder_id", match=qd_models.MatchValue(value=folder_id))
                    ]
                )
            )
        )
    except Exception as e:
        print(f"Error borrando vectores de carpeta {folder_id} en Qdrant: {e}")
        
    # 2. Eliminar metadatos de documentos asociados en MongoDB
    await db.documents.delete_many({"folder_id": folder_id})
    
    # 3. Eliminar la carpeta en MongoDB
    await db.folders.delete_one({"_id": oid})
    
    return {"message": "Carpeta eliminada correctamente", "id": folder_id}
