from fastapi import APIRouter, Depends
from services.rag import search_qdrant
from services.search_whoosh import search_keywords
from auth import get_admin_user
from database import get_database

router = APIRouter()

@router.get("/")
async def hybrid_search(query: str, current_user: dict = Depends(get_admin_user)):
    # 1. Ejecutar búsqueda léxica (exacta) en Whoosh y semántica en Qdrant
    try:
        whoosh_results = search_keywords(query, limit=20, markdown_highlights=False)
    except Exception as e:
        print(f"Error buscando en Whoosh: {e}")
        whoosh_results = []
        
    qdrant_results = await search_qdrant(query, top_k=20)
    
    if not whoosh_results and not qdrant_results:
        return []

    # 2. Agrupar por documento (folder_id, filename) y combinar scores
    doc_matches = {} # (folder_id, filename) -> { "semantic_score": float, "lexical_score": float, "snippet": str }
    
    # Procesar resultados semánticos (Qdrant)
    for hit in qdrant_results:
        key = (hit["folder_id"], hit["filename"])
        if key not in doc_matches:
            doc_matches[key] = {
                "semantic_score": hit["score"],
                "lexical_score": 0.0,
                "snippet": hit["text"][:200] + "..."
            }
        else:
            doc_matches[key]["semantic_score"] = max(doc_matches[key]["semantic_score"], hit["score"])

    # Procesar resultados léxicos (Whoosh)
    for rank, hit in enumerate(whoosh_results):
        key = (hit["folder_id"], hit["filename"])
        # Asignamos un score basado en el rank del resultado en Whoosh (de 1.0 para el primero a 0.5 para el 20vo)
        pseudo_lexical_score = max(0.5, 1.0 - (rank * 0.025))
        if key not in doc_matches:
            doc_matches[key] = {
                "semantic_score": 0.0,
                "lexical_score": pseudo_lexical_score,
                "snippet": hit["snippet"]
            }
        else:
            doc_matches[key]["lexical_score"] = pseudo_lexical_score
            # Priorizamos el snippet de Whoosh con la palabra clave resaltada
            doc_matches[key]["snippet"] = hit["snippet"]

    # 3. Enriquecer con los metadatos de MongoDB (las etiquetas) y calcular score combinado
    db = get_database()
    final_results = []
    
    for (folder_id, filename), match in doc_matches.items():
        # Buscar el archivo en Mongo
        mongo_doc = await db.documents.find_one({
            "filename": filename,
            "folder_id": folder_id
        })
        
        sem = match["semantic_score"]
        lex = match["lexical_score"]
        
        # Combinación de scores
        if sem > 0.0 and lex > 0.0:
            # Encontrado por ambos caminos (muy buena coincidencia)
            combined_score = max(sem, 0.6) + 0.15
        elif sem > 0.0:
            combined_score = sem
        else:
            # Encontrado sólo por Whoosh (coincidencia exacta)
            combined_score = lex * 0.7
            
        combined_score = min(1.0, max(0.0, combined_score))
        percentage = int(combined_score * 100)
        
        tags = mongo_doc.get("tags", []) if mongo_doc else []
        
        final_results.append({
            "id": str(mongo_doc["_id"]) if mongo_doc else None,
            "filename": filename,
            "folder_id": folder_id,
            "tags": tags,
            "match_percentage": percentage,
            "score": combined_score,
            "snippet": match["snippet"]
        })
    
    # Ordenar por porcentaje descendente
    final_results.sort(key=lambda x: x['match_percentage'], reverse=True)
    
    return final_results
