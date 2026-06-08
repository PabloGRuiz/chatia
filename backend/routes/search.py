from fastapi import APIRouter, Depends
from services.rag import search_qdrant
from auth import get_admin_user
from database import get_database

router = APIRouter()

@router.get("/")
async def semantic_search(query: str, current_user: dict = Depends(get_admin_user)):
    # Buscar en Qdrant (top 20 fragmentos)
    docs = await search_qdrant(query, top_k=20)
    
    if not docs:
        return []

    # Agrupar por documento (filename + folder_id) manteniendo el mayor score
    results_map = {}
    for doc in docs:
        key = f"{doc['folder_id']}_{doc['filename']}"
        if key not in results_map or doc['score'] > results_map[key]['score']:
            results_map[key] = doc

    # Enriquecer con los metadatos de MongoDB (las etiquetas) y convertir score a porcentaje
    db = get_database()
    final_results = []
    
    for key, doc in results_map.items():
        # Buscar el archivo en Mongo
        mongo_doc = await db.documents.find_one({
            "filename": doc['filename'],
            "folder_id": doc['folder_id']
        })
        
        # Calcular porcentaje (similitud coseno suele estar entre 0 y 1, lo pasamos a 0-100)
        percentage = min(100, max(0, int(doc['score'] * 100)))
        
        tags = mongo_doc.get("tags", []) if mongo_doc else []
        
        final_results.append({
            "id": str(mongo_doc["_id"]) if mongo_doc else None,
            "filename": doc['filename'],
            "folder_id": doc['folder_id'],
            "tags": tags,
            "match_percentage": percentage,
            "score": doc['score']
        })
    
    # Ordenar por porcentaje descendente
    final_results.sort(key=lambda x: x['match_percentage'], reverse=True)
    
    return final_results
