import os
import asyncio
from typing import List, Dict, Any
from database import get_qdrant, get_database
from services.llm import get_llm, get_embeddings
from qdrant_client.http import models as qd_models

# Intento de importar cohere. Si no está instalado, se manejará de forma segura.
try:
    import cohere
except ImportError:
    cohere = None

COHERE_API_KEY = os.getenv("COHERE_API_KEY", "")

SYSTEM_PROMPT = (
    "Eres un agente inteligente de búsqueda y análisis documental. Tu función es consultar la "
    "base de datos vectorial Qdrant, recuperar los fragmentos más relevantes de los documentos "
    "disponibles, y responder al usuario con información precisa, fundamentada y bien estructurada.\n\n"
    "Instrucciones:\n"
    "- Utiliza la pregunta del usuario como consulta semántica para Qdrant.\n"
    "- Si se ha seleccionado un documento en específico para la búsqueda, enfoca tu análisis y respuesta únicamente en ese documento y no inventes datos de otras fuentes.\n"
    "- Si la búsqueda es sobre una carpeta completa, recupera todos los fragmentos relevantes, incluso si provienen de diferentes documentos, y analízalos y combínalos para ofrecer una respuesta coherente.\n"
    "- No inventes ni supongas datos de fuentes totalmente ajenas. Sin embargo, debes utilizar y cruzar activamente la información del GLOSARIO / DOCTRINA BASE como fuente de verdad complementaria para enriquecer, traducir abreviaturas, corregir omisiones y completar datos que falten o estén incompletos en los documentos recuperados.\n"
    "- Cuando cites información, usa frases textuales si son precisas o listas específicas (por ejemplo, anexos, nombres o ítems).\n"
    "- Si la información recuperada permite una síntesis analítica o comparativa, preséntala claramente.\n"
    "- Si no existe información suficiente o relevante en el contexto proporcionado (incluyendo el glosario), responde exactamente: \"No tengo la información solicitada en mi base de datos.\"\n"
    "- Tu objetivo final es ofrecer respuestas que integren información real, textual y comprobable de los documentos almacenados y del glosario base, priorizando la precisión y fidelidad de los datos."
)

async def search_qdrant(query: str, folder_id: str = None, filenames: List[str] = None, top_k: int = 6) -> List[Dict[str, Any]]:
    qdrant = get_qdrant()
    embeddings = get_embeddings()
    
    # 1. Generar embedding de la query
    try:
        # Use aembed_query if available, otherwise fallback to to_thread
        if hasattr(embeddings, 'aembed_query'):
            query_vector = await embeddings.aembed_query(query)
        else:
            query_vector = await asyncio.to_thread(embeddings.embed_query, query)
    except Exception as e:
        print(f"Error generando embedding de query: {e}")
        return []
    
    # 2. Configurar filtro por folder_id y/o filename si existen
    must_conditions = []
    if folder_id:
        must_conditions.append(
            qd_models.FieldCondition(
                key="folder_id",
                match=qd_models.MatchValue(value=folder_id)
            )
        )
    if filenames and len(filenames) > 0:
        if len(filenames) == 1:
            must_conditions.append(
                qd_models.FieldCondition(
                    key="filename",
                    match=qd_models.MatchValue(value=filenames[0])
                )
            )
        else:
            must_conditions.append(
                qd_models.FieldCondition(
                    key="filename",
                    match=qd_models.MatchAny(any=filenames)
                )
            )
        
    qdrant_filter = None
    if must_conditions:
        qdrant_filter = qd_models.Filter(must=must_conditions)
    # 3. Buscar en Qdrant
    try:
        # Primero nos aseguramos de que la colección existe en Qdrant antes de buscar
        collections = await asyncio.to_thread(qdrant.get_collections)
        exists = any(c.name == "documents" for c in collections.collections)
        if not exists:
            # Crear la colección si no existe
            await asyncio.to_thread(
                qdrant.create_collection,
                collection_name="documents",
                vectors_config=qd_models.VectorParams(size=768, distance=qd_models.Distance.COSINE) # Nomic usa 768
            )
            return []
            
        response = await asyncio.to_thread(
            qdrant.query_points,
            collection_name="documents",
            query=query_vector,
            query_filter=qdrant_filter,
            limit=top_k
        )
        
        return [
            {
                "text": hit.payload.get("text", ""),
                "filename": hit.payload.get("filename", ""),
                "folder_id": hit.payload.get("folder_id", ""),
                "score": hit.score
            }
            for hit in response.points
        ]
    except Exception as e:
        print(f"Error buscando en Qdrant: {e}")
        return []

# Intento de importar flashrank. Si no está instalado, se manejará de forma segura.
try:
    from flashrank import Ranker, RerankRequest
    _flashrank_ranker = None
except ImportError:
    Ranker = None
    _flashrank_ranker = None

def get_flashrank_ranker():
    global _flashrank_ranker
    if _flashrank_ranker is None and Ranker is not None:
        try:
            cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "flashrank_cache")
            os.makedirs(cache_dir, exist_ok=True)
            # Usamos el modelo ms-marco-MiniLM-L-12-v2 que tiene buen soporte multilingüe y de español
            _flashrank_ranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir=cache_dir)
        except Exception as e:
            print(f"Error inicializando FlashRank: {e}")
            _flashrank_ranker = None
    return _flashrank_ranker

async def rerank_documents(query: str, docs: List[Dict[str, Any]], top_n: int = 3) -> List[Dict[str, Any]]:
    if not docs:
        return []

    # 1. Intentar usar FlashRank local primero (offline y rápido en CPU)
    ranker = get_flashrank_ranker()
    if ranker is not None:
        try:
            passages = []
            for idx, doc in enumerate(docs):
                passages.append({
                    "id": idx,  # guardamos el índice original como ID
                    "text": doc["text"]
                })
            
            # Ejecutar rerank en un hilo para no bloquear el loop asíncrono
            results = await asyncio.to_thread(
                ranker.rerank,
                query=query,
                passages=passages
            )
            
            reranked_docs = []
            for res in results[:top_n]:
                orig_idx = int(res["id"])
                orig_doc = docs[orig_idx]
                orig_doc["rerank_score"] = float(res["score"])
                reranked_docs.append(orig_doc)
                
            return reranked_docs
        except Exception as e:
            print(f"Error rerankeando con FlashRank: {e}")
            # Fallback si falla

    # 2. Fallback a Cohere si no está disponible FlashRank pero hay API key
    if COHERE_API_KEY and cohere:
        try:
            co = cohere.Client(COHERE_API_KEY)
            documents = [doc["text"] for doc in docs]
            response = await asyncio.to_thread(
                co.rerank,
                model="rerank-multilingual-v2.0",
                query=query,
                documents=documents,
                top_n=top_n
            )
            
            reranked_docs = []
            for result in response.results:
                idx = result.index
                reranked_docs.append(docs[idx])
            return reranked_docs
        except Exception as e:
            print(f"Error rerankeando con Cohere: {e}")
            
    # Si todo falla, devolver los primeros top_n sin reordenar
    return docs[:top_n]

import re
from bson import ObjectId

async def detect_document_search_intent(query: str) -> bool:
    """
    Detecta si el usuario tiene la intención explícita de buscar archivos,
    documentos, leyes o reglamentos en la base de datos de manera directa.
    Ejemplos: "¿En qué archivo...", "¿Qué ley...", "dónde se menciona...", etc.
    """
    query_clean = query.lower().strip()
    
    # 1. Intentar cargar patrones personalizados desde MongoDB
    try:
        db = get_database()
        settings = await db.system_settings.find_one({"key": "intent_phrases"})
        if settings and "value" in settings and isinstance(settings["value"], list) and len(settings["value"]) > 0:
            intent_patterns = settings["value"]
        else:
            intent_patterns = []
    except Exception as e:
        print(f"Error cargando frases de intención de DB: {e}")
        intent_patterns = []
        
    # 2. Si no hay en DB, usar las por defecto
    if not intent_patterns:
        intent_patterns = [
            r"\ben\s+(qu[eé]|cual|cu[aá]les)\s+(documento|archivo|pdf|txt|docx|carpeta|ley|reglamento)s?\b",
            r"\bqu[eé]\s+(documento|archivo|pdf|txt|docx|ley|reglamento)s?\s+(hablan|habla|mencionan|menciona|tratan|trata|dicen|dice|son|es)\b",
            r"\bd[oó]nde\s+(se\s+)?(mencionan|menciona|dicen|dice|hablan|habla|nombran|nombra|encuentran|encuentra|leen|lee|citan|cita)\b",
            r"\b(buscar|encuentra|dame|mu[eé]strame)\s+(el|los|un|una|unas|unos)?\s*(documento|archivo|pdf|txt|docx|ley|reglamento)s?\b",
            r"\b(en\s+)?qu[eé]\s+parte\s+del?s?\s+(documento|archivo|pdf|txt|docx|ley|reglamento)s?\b",
            r"\b(tienes|hay)\s+(alg[uú]n|algunos|el|los|un|una|unos|unas)?\s*(documento|archivo|ley|reglamento)s?\b",
            r"\bcu[aá]les?\s+(son\s+|est[aá]n\s+)?(los\s+)?(documento|archivo|pdf|txt|docx|ley|reglamento)s?\s+(relacionados|asociados|vinculados|vinculado|relacionado|asociado)s?\b",
            r"\bcu[aá]les?\s+(documento|archivo|pdf|txt|docx|ley|reglamento)s?\s+(son\s+|est[aá]n\s+)?(relacionados|asociados|vinculados|vinculado|relacionado|asociado)s?\b",
            r"\b(documento|archivo|pdf|txt|docx|ley|reglamento)s?\s+(relacionados|asociados|vinculados|vinculado|relacionado|asociado)s?\s+a\b",
            r"\bqu[eé]\s+(documento|archivo|pdf|txt|docx|ley|reglamento)s?\s+(est[aá]n\s+)?(relacionados|asociados|vinculados|vinculado|relacionado|asociado)s?\s+(con|a)\b"
        ]
        
    for pattern in intent_patterns:
        # Si parece una expresión regular compleja
        if any(c in pattern for c in ['\\', '*', '+', '?', '^', '$', '(', ')', '[', ']']):
            try:
                if re.search(pattern, query_clean):
                    return True
            except Exception as e:
                print(f"Patrón regex inválido '{pattern}': {e}")
        else:
            # Búsqueda literal
            if pattern.lower().strip() in query_clean:
                return True
            
    return False

async def get_source_documents_metadata(unique_docs: List[tuple]) -> List[Dict[str, Any]]:
    db = get_database()
    source_docs = []
    for folder_id, filename in unique_docs:
        try:
            query_filter = {"filename": filename}
            if folder_id:
                if isinstance(folder_id, str) and len(folder_id) == 24:
                    query_filter["folder_id"] = folder_id
            
            doc = await db.documents.find_one(query_filter)
            if doc:
                source_docs.append({
                    "id": str(doc["_id"]),
                    "filename": filename,
                    "folder_id": str(doc["folder_id"])
                })
        except Exception as e:
            print(f"Error recuperando metadatos para {filename}: {e}")
    return source_docs

async def run_rag_chain(query: str, folder_id: str = None, filenames: List[str] = None, user_role: str = "user") -> tuple[str, List[Dict[str, Any]]]:
    # 0. Cortocircuito para búsqueda de archivos si se detecta intención
    if await detect_document_search_intent(query):
        try:
            from services.search_whoosh import search_keywords
            whoosh_matches = search_keywords(query, folder_id=folder_id, filenames=filenames, limit=6, markdown_highlights=True)
        except Exception as e:
            print(f"Error buscando por palabras clave en Whoosh para cortocircuito: {e}")
            whoosh_matches = []
            
        db = get_database()
        
        if whoosh_matches:
            # Agrupar coincidencias por documento
            grouped_matches = {}  # (folder_id, filename) -> list of snippets
            for match in whoosh_matches:
                key = (match["folder_id"], match["filename"])
                if key not in grouped_matches:
                    grouped_matches[key] = []
                # Evitar agregar fragmentos idénticos
                s = match["snippet"].strip()
                if s not in grouped_matches[key]:
                    grouped_matches[key].append(s)
            
            response_parts = ["He encontrado coincidencias exactas para tu búsqueda en los siguientes documentos:\n"]
            for idx, ((fid, fname), snippets) in enumerate(grouped_matches.items()):
                folder_doc = await db.folders.find_one({"_id": ObjectId(fid)}) if fid else None
                folder_name = folder_doc.get("name") if folder_doc else "General"
                
                response_parts.append(f"{idx+1}. Documento: **{fname}** (Carpeta: *{folder_name}*):")
                for snippet in snippets:
                    response_parts.append(f"   > ... {snippet} ...\n")
            
            response_parts.append("\n¿Deseas que profundice en el contenido de alguno de estos documentos o tienes otra pregunta?")
            
            unique_docs = list(grouped_matches.keys())
            source_docs = await get_source_documents_metadata(unique_docs)
            return "\n".join(response_parts), source_docs
        else:
            # Fallback semántico (Qdrant) si Whoosh no encuentra nada, pero formateado de forma directa
            qdrant_matches = await search_qdrant(query, folder_id=folder_id, filenames=filenames, top_k=6)
            if qdrant_matches:
                # Agrupar por documento
                grouped_matches = {}
                for match in qdrant_matches:
                    key = (match["folder_id"], match["filename"])
                    if key not in grouped_matches:
                        grouped_matches[key] = []
                    s = match["text"][:250].strip() + "..."
                    if s not in grouped_matches[key]:
                        grouped_matches[key].append(s)
                
                response_parts = ["No encontré coincidencias exactas, pero he hallado estos fragmentos relacionados por concepto:\n"]
                for idx, ((fid, fname), snippets) in enumerate(grouped_matches.items()):
                    folder_doc = await db.folders.find_one({"_id": ObjectId(fid)}) if fid else None
                    folder_name = folder_doc.get("name") if folder_doc else "General"
                    
                    response_parts.append(f"{idx+1}. Documento: **{fname}** (Carpeta: *{folder_name}*):")
                    for snippet in snippets:
                        response_parts.append(f"   > ... {snippet} ...\n")
                
                response_parts.append("\n¿Deseas que responda una pregunta en base a estos textos o prefieres buscar algo diferente?")
                
                unique_docs = list(grouped_matches.keys())
                source_docs = await get_source_documents_metadata(unique_docs)
                return "\n".join(response_parts), source_docs
                
            return "No he encontrado ningún documento en la base de datos que mencione esos términos de búsqueda.", []

    # 1. Recuperar de Qdrant (buscamos un top_k más alto para luego rerankear y no perder contexto)
    docs = await search_qdrant(query, folder_id, filenames, top_k=20)
    
    # 2. Rerankear (local con FlashRank, fallback a Cohere)
    reranked_docs = await rerank_documents(query, docs, top_n=3)
    
    # 3. Recuperar el Glosario Base Militar de MongoDB
    db = get_database()
    settings = await db.system_settings.find_one({"key": "military_glossary"})
    glossary_text = settings["value"] if settings and "value" in settings else ""

    # 4. Formatear Contexto
    context = ""
    if reranked_docs:
        context_parts = []
        for idx, doc in enumerate(reranked_docs):
            context_parts.append(f"[Documento {idx+1}: {doc['filename']}]\n{doc['text']}")
        context = "\n\n".join(context_parts)
    else:
        # Si no hay documentos en Qdrant, respondemos directamente con el mensaje predeterminado
        return "No tengo la información solicitada en mi base de datos.", []
        
    # 5. Ajustar el Prompt según el rol
    role_instruction = ""
    if user_role == "admin":
        role_instruction = (
            "INSTRUCCIÓN DE ROL (ADMINISTRADOR):\n"
            "Eres un asistente técnico. Puedes detallar el proceso técnico de cómo encontraste la información, "
            "hacer referencia explícita a la base de datos (por ejemplo, 'consultando Qdrant'), "
            "y mencionar de qué documento y fragmento obtuviste cada dato, de forma detallada y extensa."
        )
    else:
        role_instruction = (
            "INSTRUCCIÓN DE ROL (USUARIO COMÚN):\n"
            "Eres un asistente directo, claro y profesional. Tu respuesta debe ser concisa, escueta y fácil de entender. "
            "Bajo NINGÚN concepto menciones términos técnicos de tu arquitectura interna como 'Qdrant', 'bases de datos vectoriales', "
            "'fragmentos', o 'embeddings'. Solo entrega la información solicitada de manera directa, citando el nombre del documento si es útil, pero sin aburrir al usuario con detalles técnicos."
        )

    glossary_section = ""
    if glossary_text:
        glossary_section = (
            "GLOSARIO / DOCTRINA BASE (INFORMACIÓN DE REFERENCIA OBLIGATORIA Y FUENTE DE VERDAD):\n"
            "Usa esta información oficial obligatoria para complementar jerarquías, traducir siglas/abreviaturas, "
            "y corregir cualquier dato omitido, incompleto o erróneo de los documentos recuperados. "
            "El contenido de este glosario es de la más alta prioridad y verídico:\n"
            f"{glossary_text}\n"
        )

    # 6. Construir Prompt final
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"{role_instruction}\n\n"
        f"{glossary_section}\n"
        f"Contexto recuperado de la base de datos:\n{context}\n\n"
        f"Pregunta del usuario: {query}\n\n"
        f"Respuesta estructurada:"
    )
    
    # 7. Generar con LLM (Ollama / LLaMA 3.1)
    try:
        llm = get_llm()
        if hasattr(llm, 'ainvoke'):
            response = await llm.ainvoke(prompt)
        else:
            response = await asyncio.to_thread(llm.invoke, prompt)
            
        # Obtener metadatos de documentos fuente únicos
        unique_docs = list(set((doc.get("folder_id"), doc.get("filename")) for doc in reranked_docs if doc.get("filename")))
        source_docs = await get_source_documents_metadata(unique_docs)
        
        return response, source_docs
    except Exception as e:
        print(f"Error generando respuesta con Ollama: {e}")
        return "Lo siento, ocurrió un error interno al conectar con el modelo LLaMA local o la petición fue cancelada.", []
