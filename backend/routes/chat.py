from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from models import ChatRequest, ChatResponse, TruncateRequest, TitleUpdateRequest
from services.rag import run_rag_chain
from database import get_database
from auth import get_current_user
import datetime
import time

router = APIRouter()


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    # 1. Medir tiempo de ejecución y ejecutar el flujo RAG real con Langchain, Qdrant y Ollama
    start_time = time.time()
    response_text, source_documents = await run_rag_chain(
        request.query,
        request.folder_id,
        request.filenames,
        current_user.get("role", "user"),
    )
    execution_time = round(time.time() - start_time, 2)

    # 2. Obtener nombre de la carpeta
    db = get_database()
    folder_name = None
    if request.folder_id:
        folder = await db.folders.find_one({"_id": ObjectId(request.folder_id)})
        if folder:
            folder_name = folder.get("name")

    # 3. Guardar en MongoDB usando chat_sessions
    session_id = request.session_id

    user_msg = {
        "role": "user",
        "content": request.query,
        "created_at": datetime.datetime.utcnow(),
    }
    asst_msg = {
        "role": "assistant",
        "content": response_text,
        "folder_name": folder_name,
        "filenames": request.filenames,
        "execution_time": execution_time,
        "source_documents": source_documents,
        "created_at": datetime.datetime.utcnow(),
    }

    try:
        if session_id:
            # Anexar a sesión existente
            await db.chat_sessions.update_one(
                {"_id": ObjectId(session_id), "user_id": current_user["email"]},
                {"$push": {"messages": {"$each": [user_msg, asst_msg]}}},
            )
        else:
            # Crear nueva sesión
            new_session = {
                "user_id": current_user["email"],
                "folder_id": request.folder_id,
                "messages": [user_msg, asst_msg],
                "created_at": datetime.datetime.utcnow(),
            }
            result = await db.chat_sessions.insert_one(new_session)
            session_id = str(result.inserted_id)

    except Exception as e:
        print(f"Error al guardar mensaje en historial MongoDB: {e}")

    return ChatResponse(
        response=response_text,
        session_id=session_id,
        folder_name=folder_name,
        filenames=request.filenames,
        execution_time=execution_time,
        source_documents=source_documents,
    )


@router.get("/sessions")
async def get_sessions(current_user: dict = Depends(get_current_user)):
    db = get_database()
    cursor = db.chat_sessions.find(
        {"user_id": current_user["email"]},
        {
            "messages": {"$slice": 1},
            "created_at": 1,
        },  # Solo el primer mensaje para el título
    ).sort("created_at", -1)

    sessions = []
    async for doc in cursor:
        title = doc.get("title")
        if not title:
            title = "Nueva Consulta"
            if "messages" in doc and len(doc["messages"]) > 0:
                title = doc["messages"][0]["content"]
                # truncate title
                if len(title) > 30:
                    title = title[:30] + "..."

        sessions.append(
            {
                "id": str(doc["_id"]),
                "title": title,
                "created_at": doc.get("created_at").isoformat()
                if hasattr(doc.get("created_at"), "isoformat")
                else doc.get("created_at"),
            }
        )
    return sessions


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, current_user: dict = Depends(get_current_user)):
    db = get_database()
    try:
        session = await db.chat_sessions.find_one(
            {"_id": ObjectId(session_id), "user_id": current_user["email"]}
        )
        if not session:
            raise HTTPException(status_code=404, detail="Sesión no encontrada")

        session["id"] = str(session["_id"])
        del session["_id"]
        # Format dates for frontend
        if "created_at" in session and hasattr(session["created_at"], "isoformat"):
            session["created_at"] = session["created_at"].isoformat()
        for msg in session.get("messages", []):
            if "created_at" in msg and hasattr(msg["created_at"], "isoformat"):
                msg["created_at"] = msg["created_at"].isoformat()
        return session
    except Exception:
        raise HTTPException(status_code=400, detail="Error al buscar sesión")


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str, current_user: dict = Depends(get_current_user)
):
    db = get_database()
    try:
        result = await db.chat_sessions.delete_one(
            {"_id": ObjectId(session_id), "user_id": current_user["email"]}
        )
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=404, detail="Sesión no encontrada o no autorizada"
            )
        return {"message": "Sesión eliminada"}
    except Exception:
        raise HTTPException(status_code=400, detail="Error al eliminar sesión")


@router.put("/sessions/{session_id}/truncate")
async def truncate_session(
    session_id: str,
    req: TruncateRequest,
    current_user: dict = Depends(get_current_user),
):
    db = get_database()
    try:
        session = await db.chat_sessions.find_one(
            {"_id": ObjectId(session_id), "user_id": current_user["email"]}
        )
        if not session:
            raise HTTPException(
                status_code=404, detail="Sesión no encontrada o no autorizada"
            )

        # Slicing the array in Python and updating it
        truncated_messages = session.get("messages", [])[: req.index]
        await db.chat_sessions.update_one(
            {"_id": ObjectId(session_id)}, {"$set": {"messages": truncated_messages}}
        )
        return {"message": "Sesión truncada", "messages_count": len(truncated_messages)}
    except Exception:
        raise HTTPException(status_code=400, detail="Error al truncar sesión")


@router.put("/sessions/{session_id}/title")
async def update_session_title(
    session_id: str,
    req: TitleUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    db = get_database()
    try:
        result = await db.chat_sessions.update_one(
            {"_id": ObjectId(session_id), "user_id": current_user["email"]},
            {"$set": {"title": req.title}},
        )
        if result.matched_count == 0:
            raise HTTPException(
                status_code=404, detail="Sesión no encontrada o no autorizada"
            )
        return {"message": "Título actualizado exitosamente"}
    except Exception:
        raise HTTPException(status_code=400, detail="Error al actualizar título")
