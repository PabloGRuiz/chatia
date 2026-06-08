from fastapi import APIRouter, UploadFile, File, HTTPException, status
from database import get_database, get_qdrant
from services.ingest import process_and_index_file
from bson import ObjectId
from qdrant_client.http import models as qd_models

router = APIRouter()

@router.get("/{folder_id}/documents")
async def list_documents(folder_id: str):
    db = get_database()
    docs = await db.documents.find({"folder_id": folder_id}).to_list(100)
    for doc in docs:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
        if "created_at" in doc and isinstance(doc["created_at"], str) == False:
            doc["created_at"] = doc["created_at"].isoformat()
    return docs

from auth import get_admin_user
from fastapi import Depends

@router.post("/{folder_id}/documents/upload")
async def upload_document(folder_id: str, file: UploadFile = File(...), current_user: dict = Depends(get_admin_user)):
    if not file.filename.lower().endswith(('.pdf', '.docx', '.doc', '.txt')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de archivo no soportado. Utilice PDF, DOCX, DOC o TXT."
        )
    
    file_bytes = await file.read()
    try:
        doc_metadata = await process_and_index_file(file_bytes, file.filename, folder_id)
        return doc_metadata
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        print(f"Error procesando archivo: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al procesar e indexar el archivo.")

@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, current_user: dict = Depends(get_admin_user)):
    db = get_database()
    qdrant = get_qdrant()
    
    try:
        oid = ObjectId(doc_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID de documento inválido.")
        
    doc = await db.documents.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")
        
    filename = doc["filename"]
    folder_id = doc["folder_id"]
    
    # 1. Eliminar fragmentos de Qdrant
    try:
        qdrant.delete(
            collection_name="documents",
            points_selector=qd_models.FilterSelector(
                filter=qd_models.Filter(
                    must=[
                        qd_models.FieldCondition(key="filename", match=qd_models.MatchValue(value=filename)),
                        qd_models.FieldCondition(key="folder_id", match=qd_models.MatchValue(value=folder_id))
                    ]
                )
            )
        )
    except Exception as e:
        print(f"Error borrando de Qdrant: {e}")
        
    # 2. Eliminar chunks de MongoDB
    await db.document_chunks.delete_many({"document_id": doc_id})

    # 3. Eliminar de MongoDB
    await db.documents.delete_one({"_id": oid})
    
    return {"message": "Documento eliminado correctamente", "id": doc_id}
