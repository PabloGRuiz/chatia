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
                "score": hit.score
            }
            for hit in response.points
        ]
    except Exception as e:
        print(f"Error buscando en Qdrant: {e}")
        return []

async def rerank_documents(query: str, docs: List[Dict[str, Any]], top_n: int = 3) -> List[Dict[str, Any]]:
    if not COHERE_API_KEY or not docs or not cohere:
        # Si no hay API key o no está instalada la librería, devolvemos el top original
        return docs[:top_n]
        
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
        return docs[:top_n]

async def run_rag_chain(query: str, folder_id: str = None, filenames: List[str] = None, user_role: str = "user") -> str:
    # 1. Recuperar de Qdrant (buscamos un top_k más alto para luego rerankear y no perder contexto)
    docs = await search_qdrant(query, folder_id, filenames, top_k=20)
    
    # 2. Rerankear con Cohere (opcional, pasamos más documentos)
    reranked_docs = await rerank_documents(query, docs, top_n=8)
    
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
        return "No tengo la información solicitada en mi base de datos."
        
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
        return response
    except Exception as e:
        print(f"Error generando respuesta con Ollama: {e}")
        return "Lo siento, ocurrió un error interno al conectar con el modelo LLaMA local o la petición fue cancelada."
