import os
import uuid
import tempfile
from typing import List
from docx import Document
from pypdf import PdfReader
import pdfplumber

from database import get_qdrant, get_database
from services.llm import get_embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client.http import models as qd_models
import datetime

def extract_text_from_pdf(file_path: str) -> str:
    text = ""
    # Intentamos primero con pdfplumber ya que extrae mejor el formato y tablas
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"Error con pdfplumber: {e}, reintentando con pypdf...")
        
    # Fallback a pypdf
    if not text.strip():
        try:
            reader = PdfReader(file_path)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        except Exception as e:
            print(f"Error con pypdf: {e}")
            
    return text

def extract_text_from_docx(file_path: str) -> str:
    try:
        doc = Document(file_path)
        return "\n".join([paragraph.text for paragraph in doc.paragraphs])
    except Exception as e:
        print(f"Error leyendo DOCX: {e}")
        return ""

def extract_text_from_txt(file_path: str) -> str:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, "r", encoding="latin-1") as f:
                return f.read()
        except Exception as e:
            print(f"Error leyendo TXT: {e}")
            return ""
    except Exception as e:
        print(f"Error leyendo TXT: {e}")
        return ""

async def process_and_index_file(file_bytes: bytes, filename: str, folder_id: str) -> dict:
    ext = os.path.splitext(filename)[1].lower()
    
    # 1. Guardar temporalmente el archivo para procesarlo
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
        temp_file.write(file_bytes)
        temp_path = temp_file.name

    text = ""
    try:
        if ext == ".pdf":
            text = extract_text_from_pdf(temp_path)
        elif ext in [".doc", ".docx"]:
            text = extract_text_from_docx(temp_path)
        elif ext in [".txt"]:
            text = extract_text_from_txt(temp_path)
        else:
            raise ValueError(f"Extensión de archivo no soportada: {ext}")
    finally:
        # Borrar el archivo temporal
        if os.path.exists(temp_path):
            os.remove(temp_path)

    if not text.strip():
        raise ValueError("No se pudo extraer texto del archivo (el archivo podría estar vacío o escaneado sin OCR).")

    # 2. Dividir el texto en fragmentos (Chunking)
    # Aumentamos el tamaño para que fechas e información relacionada no queden separadas
    splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=300)
    chunks = splitter.split_text(text)
    
    if not chunks:
        raise ValueError("El archivo no contiene fragmentos válidos para indexar.")

    # 3. Inicializar clientes
    qdrant = get_qdrant()
    embeddings = get_embeddings()
    db = get_database()
    
    # 4. Asegurarse que la colección Qdrant exista
    collections = qdrant.get_collections().collections
    exists = any(c.name == "documents" for c in collections)
    if not exists:
        qdrant.create_collection(
            collection_name="documents",
            vectors_config=qd_models.VectorParams(size=768, distance=qd_models.Distance.COSINE) # nomic-embed-text usa 768
        )

    # 5. Generar embeddings e insertar en Qdrant
    points = []
    for idx, chunk in enumerate(chunks):
        point_id = str(uuid.uuid4())
        try:
            vector = embeddings.embed_query(chunk)
            points.append(
                qd_models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "folder_id": folder_id,
                        "filename": filename,
                        "text": chunk,
                        "chunk_index": idx
                    }
                )
            )
        except Exception as e:
            print(f"Error generando embedding para el fragmento {idx}: {e}")
            raise RuntimeError("Error al comunicarse con Ollama para generar embeddings.")

    # Subir puntos a Qdrant en lotes
    qdrant.upsert(collection_name="documents", points=points)

    # 6. Registrar documento en MongoDB para auditoría y administración
    doc_metadata = {
        "filename": filename,
        "folder_id": folder_id,
        "chunk_count": len(chunks),
        "status": "indexed",
        "created_at": datetime.datetime.utcnow()
    }
    
    res = await db.documents.insert_one(doc_metadata)
    doc_id_str = str(res.inserted_id)
    doc_metadata["_id"] = doc_id_str

    # 7. Registrar los chunks individuales en MongoDB para visualización/inspección
    mongo_chunks = []
    for idx, chunk in enumerate(chunks):
        mongo_chunks.append({
            "document_id": doc_id_str,
            "folder_id": folder_id,
            "filename": filename,
            "chunk_index": idx,
            "text": chunk,
            "created_at": datetime.datetime.utcnow()
        })
    if mongo_chunks:
        await db.document_chunks.insert_many(mongo_chunks)

    return doc_metadata
