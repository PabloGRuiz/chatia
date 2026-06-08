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
