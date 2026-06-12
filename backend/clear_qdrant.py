from database import get_qdrant, connect_to_db, close_db_connection
import asyncio


async def clear_documents_collection():
    await connect_to_db()
    qdrant = get_qdrant()

    # Check if exists and drop it
    try:
        collections = qdrant.get_collections().collections
        if any(c.name == "documents" for c in collections):
            print("Borrando la colección antigua 'documents' de Qdrant...")
            qdrant.delete_collection("documents")
            print(
                "Colección borrada exitosamente. Será recreada con la nueva dimensión (384) al subir un archivo o buscar."
            )
        else:
            print("La colección 'documents' no existe.")
    except Exception as e:
        print(f"Error operando en Qdrant: {e}")
    finally:
        await close_db_connection()


if __name__ == "__main__":
    asyncio.run(clear_documents_collection())
