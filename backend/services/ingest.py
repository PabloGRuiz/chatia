import os
import uuid
import tempfile
import io
from typing import List
from docx import Document
from pypdf import PdfReader
import pdfplumber
from PIL import Image

from database import get_qdrant, get_database
from services.llm import get_embeddings, get_llm
import asyncio
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client.http import models as qd_models
import datetime

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")

def ocr_pdf(file_path: str) -> str:
    try:
        import fitz  # PyMuPDF
        import pytesseract
    except ImportError:
        print("Error: PyMuPDF (pymupdf) o pytesseract no están instalados. No se puede realizar OCR.")
        return ""
        
    text = ""
    try:
        doc = fitz.open(file_path)
        print(f"Iniciando OCR para el PDF: {file_path} ({len(doc)} páginas)...")
        for page_num in range(len(doc)):
            page = doc[page_num]
            # Usar un zoom de 2.0x para obtener buena calidad de imagen sin exceder el tiempo de procesamiento
            zoom = 2.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            
            # Obtener bytes de imagen e instanciar en PIL
            img_data = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_data))
            
            # Ejecutar OCR con idiomas español e inglés
            page_text = pytesseract.image_to_string(image, lang="spa+eng")
            if page_text.strip():
                text += f"\n--- Página {page_num + 1} (OCR) ---\n" + page_text + "\n"
        print("OCR finalizado exitosamente.")
    except Exception as e:
        print(f"Error durante el OCR del PDF: {e}")
    return text

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
    
    # Guardar permanentemente en backend/uploads/{folder_id}/{filename}
    folder_dir = os.path.join(UPLOAD_DIR, folder_id)
    os.makedirs(folder_dir, exist_ok=True)
    file_path = os.path.join(folder_dir, filename)
    
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    text = ""
    try:
        if ext == ".pdf":
            text = await asyncio.to_thread(extract_text_from_pdf, file_path)
            if not text.strip():
                print("No se pudo extraer texto seleccionable del PDF. Intentando OCR local...")
                text = await asyncio.to_thread(ocr_pdf, file_path)
        elif ext in [".doc", ".docx"]:
            text = await asyncio.to_thread(extract_text_from_docx, file_path)
        elif ext in [".txt"]:
            text = await asyncio.to_thread(extract_text_from_txt, file_path)
        else:
            raise ValueError(f"Extensión de archivo no soportada: {ext}")
    except Exception as e:
        # Si falla la extracción de texto, eliminamos el archivo guardado
        if os.path.exists(file_path):
            os.remove(file_path)
        raise e

    if not text.strip():
        # Si el texto está vacío, también eliminamos el archivo guardado
        if os.path.exists(file_path):
            os.remove(file_path)
        raise ValueError("No se pudo extraer texto del archivo. El archivo podría estar vacío, escaneado sin texto seleccionable, o el motor de OCR local no está disponible/configurado.")

    # 1.5 Generar etiquetas automáticamente (síncrono)
    tags = []
    try:
        llm = get_llm()
        sample_text = text[:4000]
        prompt = (
            "Analiza el siguiente texto y extrae exactamente 3 a 5 palabras clave o etiquetas cortas (máximo 2 palabras por etiqueta) que describan su contenido principal. "
            "Responde ÚNICAMENTE con las etiquetas separadas por comas, sin ninguna otra palabra, introducción o explicación.\n\n"
            f"Texto: {sample_text}"
        )
        if hasattr(llm, 'ainvoke'):
            tag_response = await llm.ainvoke(prompt)
        else:
            tag_response = await asyncio.to_thread(llm.invoke, prompt)
            
        tags = [t.strip().title() for t in tag_response.split(',') if t.strip()]
        tags = tags[:5]
    except Exception as e:
        print(f"Error generando etiquetas con LLM: {e}")

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
            vectors_config=qd_models.VectorParams(size=384, distance=qd_models.Distance.COSINE) # MiniLM usa 384
        )

    # 5. Generar embeddings en lote asíncrono
    try:
        vectors = await embeddings.aembed_documents(chunks)
    except Exception as e:
        print(f"Error generando embeddings con Ollama: {e}")
        raise RuntimeError("Error al comunicarse con Ollama para generar embeddings.")

    points = []
    for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
        point_id = str(uuid.uuid4())
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

    # Subir puntos a Qdrant en lote (no bloqueante)
    try:
        await asyncio.to_thread(qdrant.upsert, collection_name="documents", points=points)
    except Exception as e:
        print(f"Error subiendo puntos a Qdrant: {e}")
        raise RuntimeError("Error al guardar vectores en Qdrant.")

    # 5.5 Generar índice en Whoosh para búsqueda exacta y resúmenes (no bloqueante)
    try:
        from services.search_whoosh import index_document_chunks
        await asyncio.to_thread(index_document_chunks, folder_id, filename, chunks)
    except Exception as e:
        print(f"Error indexando fragmentos en Whoosh: {e}")

    # 6. Registrar documento en MongoDB para auditoría y administración
    doc_metadata = {
        "filename": filename,
        "folder_id": folder_id,
        "chunk_count": len(chunks),
        "status": "indexed",
        "tags": tags,
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
