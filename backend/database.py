from motor.motor_asyncio import AsyncIOMotorClient
from qdrant_client import QdrantClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGODB_URL", "mongodb://root:example@localhost:27018")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")


class Database:
    client: AsyncIOMotorClient = None
    qdrant: QdrantClient = None
    db = None


db = Database()


async def connect_to_db():
    print(f"Conectando a MongoDB en {MONGO_URL}...")
    db.client = AsyncIOMotorClient(MONGO_URL)
    db.db = db.client.chatia

    print(f"Conectando a Qdrant en {QDRANT_URL}...")
    db.qdrant = QdrantClient(url=QDRANT_URL)


async def close_db_connection():
    if db.client is not None:
        db.client.close()
    if db.qdrant is not None:
        db.qdrant.close()


def get_database():
    return db.db


def get_qdrant():
    return db.qdrant
