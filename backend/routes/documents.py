import os
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends
from fastapi.responses import FileResponse
from database import get_database, get_qdrant
from services.ingest import process_and_index_file
from bson import ObjectId
from qdrant_client.http import models as qd_models
from auth import get_admin_user

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")

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

@router.post("/{folder_id}/documents/upload")
async def upload_documents(folder_id: str, files: List[UploadFile] = File(...), current_user: dict = Depends(get_admin_user)):
    MAX_TOTAL_SIZE = 100 * 1024 * 1024  # Límite total de 100 MB
    
    # 1. Validar extensiones de todos los archivos antes de procesar
    for file in files:
        if not file.filename.lower().endswith(('.pdf', '.docx', '.doc', '.txt')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Formato de archivo no soportado en '{file.filename}'. Utilice PDF, DOCX, DOC o TXT."
            )

    # 1.5. Validar tamaño total acumulado de todos los archivos
    total_size = 0
    for file in files:
        size = getattr(file, "size", None)
        if size is None:
            await file.seek(0, 2)
            size = await file.tell()
            await file.seek(0)
        total_size += size

    if total_size > MAX_TOTAL_SIZE:
        total_mb = total_size / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El tamaño total de los archivos ({total_mb:.2f} MB) excede el límite máximo permitido de 100 MB."
        )
            
    uploaded_metadata = []
    
    # 2. Procesar e indexar cada archivo
    for file in files:
        file_bytes = await file.read()
        try:
            doc_metadata = await process_and_index_file(file_bytes, file.filename, folder_id)
            uploaded_metadata.append(doc_metadata)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error en '{file.filename}': {str(e)}")
        except Exception as e:
            print(f"Error procesando archivo '{file.filename}': {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno al procesar e indexar el archivo '{file.filename}'."
            )
            
    return uploaded_metadata

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
        
    # 1.5 Eliminar archivo físico
    file_path = os.path.join(UPLOAD_DIR, folder_id, filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"Error borrando archivo físico {file_path}: {e}")
            
    # 1.8 Eliminar del índice Whoosh
    try:
        from services.search_whoosh import delete_document_index
        delete_document_index(folder_id, filename)
    except Exception as e:
        print(f"Error eliminando de Whoosh: {e}")

    # 2. Eliminar chunks de MongoDB
    await db.document_chunks.delete_many({"document_id": doc_id})

    # 3. Eliminar de MongoDB
    await db.documents.delete_one({"_id": oid})
    
    return {"message": "Documento eliminado correctamente", "id": doc_id}

@router.get("/documents/{doc_id}/download")
async def download_document(doc_id: str, inline: bool = False):
    db = get_database()
    try:
        oid = ObjectId(doc_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID de documento inválido.")
        
    doc = await db.documents.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")
        
    file_path = os.path.join(UPLOAD_DIR, doc["folder_id"], doc["filename"])
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Archivo físico no encontrado en el servidor.")
        
    if inline:
        ext = os.path.splitext(doc["filename"])[1].lower()
        media_types = {
            ".pdf": "application/pdf",
            ".txt": "text/plain",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        media_type = media_types.get(ext, "application/octet-stream")
        return FileResponse(file_path, media_type=media_type, content_disposition_type="inline")
        
    return FileResponse(file_path, filename=doc["filename"])
