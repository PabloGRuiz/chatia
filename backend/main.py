from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import connect_to_db, close_db_connection
from contextlib import asynccontextmanager
from routes import chat, auth, folders, documents, users, settings, search
from seed import seed_users

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_db()
    try:
        await seed_users()
    except Exception as e:
        print(f"Error seeding users: {e}")
        
    # Reindexar fragmentos existentes en Whoosh para sincronización
    try:
        from database import get_database
        from services.search_whoosh import index_document_chunks
        db = get_database()
        print("Sincronizando índice de Whoosh con MongoDB...")
        cursor = db.document_chunks.find({})
        chunks_map = {} # (folder_id, filename) -> list of (chunk_index, text)
        async for chunk_doc in cursor:
            key = (chunk_doc["folder_id"], chunk_doc["filename"])
            if key not in chunks_map:
                chunks_map[key] = []
            chunks_map[key].append((chunk_doc["chunk_index"], chunk_doc.get("text", "")))
            
        for (folder_id, filename), chunks_list in chunks_map.items():
            chunks_list.sort(key=lambda x: x[0])
            sorted_chunks = [c[1] for c in chunks_list]
            index_document_chunks(folder_id, filename, sorted_chunks)
        print("Sincronización de Whoosh finalizada.")
    except Exception as e:
        print(f"Error al sincronizar Whoosh: {e}")
        
    yield
    await close_db_connection()

app = FastAPI(title="Chat IA API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "API de Chat IA con MongoDB y Qdrant"}

app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(folders.router, prefix="/folders", tags=["folders"])
app.include_router(documents.router, prefix="/folders", tags=["documents"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(settings.router, prefix="/settings", tags=["settings"])
app.include_router(search.router, prefix="/search", tags=["search"])
