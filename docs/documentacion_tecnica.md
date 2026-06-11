# DOCUMENTACIÓN TÉCNICA: CHATIA

Esta documentación describe la arquitectura técnica de la aplicación, el diseño de la base de datos, el flujo de procesamiento de documentos y el pipeline de consulta híbrida (RAG).

---

## 1. Arquitectura del Sistema
ChatIA está compuesto por 5 servicios dockerizados coordinados mediante `docker-compose.yml`:

```
 ┌────────────────────────────────────────────────────────┐
 │                      Navegador Web                     │
 └───────────┬────────────────────────────────┬───────────┘
             │ HTTP / WebSockets              │ HTTP / WebSockets
 ┌───────────▼───────────┐        ┌───────────▼───────────┐
 │   chatia_frontend     │        │    chatia_backend     │
 │    (React + Vite)     │        │  (FastAPI + Uvicorn)  │
 └───────────────────────┘        └──────┬──────┬──────┬──┘
                                         │      │      │
      ┌──────────────────────────────────┘      │      └──────────────────────────────────┐
      │ Motor (MongoDB Client)                  │ Qdrant Client (gRPC/HTTP)               │ HTTP REST
┌─────▼──────────┐                        ┌─────▼──────────┐                        ┌─────▼──────────┐
│ chatia_mongodb │                        │ chatia_qdrant  │                        │ chatia_ollama  │
│  (Base NoSQL)  │                        │ (Base Vector)  │                        │  (Motor LLM)   │
└────────────────┘                        └────────────────┘                        └────────────────┘
```

* **Frontend (`chatia_frontend`):** Aplicación React 19 construida con Vite 8. Se ejecuta en Node.js y se sirve en el puerto `5173`.
* **Backend (`chatia_backend`):** API REST asíncrona construida en Python 3.11 con FastAPI y servida mediante Uvicorn en el puerto `8000`.
* **MongoDB (`chatia_mongodb`):** Base de datos relacional orientada a documentos expuesta internamente y mapeada en el puerto host `27018`.
* **Qdrant (`chatia_qdrant`):** Motor de base de datos vectorial para búsqueda semántica mapeada en el puerto host `6333`.
* **Ollama (`chatia_ollama`):** Motor local de inferencia de modelos LLM y embeddings expuesto en el puerto host `11434`.

---

## 2. Modelos de Datos (MongoDB)

El backend utiliza la librería asíncrona `motor` para interactuar con MongoDB. Los esquemas principales son:

### Colección `users`
Almacena las credenciales de acceso y privilegios del sistema.
```javascript
{
  "_id": ObjectId,
  "email": "usuario@dominio.com",
  "password_hash": "string (bcrypt)",
  "role": "admin" // o "user",
  "created_at": Date
}
```

### Colección `folders`
Representa los contenedores temáticos donde los usuarios agrupan archivos.
```javascript
{
  "_id": ObjectId,
  "name": "Historia",
  "description": "Documentos sobre historia militar.",
  "created_at": Date
}
```

### Colección `documents`
Guarda los metadatos generales de los archivos subidos al sistema.
```javascript
{
  "_id": ObjectId,
  "filename": "biografia.pdf",
  "folder_id": "string (ObjectId)",
  "chunk_count": Number (Cantidad de fragmentos),
  "status": "indexed", // o "processing"
  "tags": ["San Martin", "Historia", "Militar"], // Tags autogenerados
  "created_at": Date
}
```

### Colección `document_chunks`
Almacena los fragmentos individuales de texto extraídos de los documentos para auditoría e inspección.
```javascript
{
  "_id": ObjectId,
  "document_id": "string (ObjectId)",
  "folder_id": "string (ObjectId)",
  "filename": "biografia.pdf",
  "chunk_index": Number,
  "text": "Fragmento de texto de hasta 1500 caracteres...",
  "created_at": Date
}
```

### Colección `chat_sessions`
Registra el historial de conversaciones de los usuarios con el asistente.
```javascript
{
  "_id": ObjectId,
  "user_id": "usuario@dominio.com",
  "folder_id": "string (ObjectId)" // o null (búsqueda global),
  "title": "Consulta sobre San Martín",
  "messages": [
    {
      "role": "user" // o "assistant",
      "content": "Pregunta o respuesta...",
      "folder_name": "Historia" // (solo assistant),
      "filenames": ["biografia.pdf"] // (solo assistant),
      "execution_time": 1.45 // Tiempo en segundos (solo assistant),
      "created_at": Date
    }
  ],
  "created_at": Date
}
```

---

## 3. Pipeline de Ingesta Asíncrona (Non-Blocking)
Para evitar que el backend de FastAPI se congele y bloquee el servidor durante la carga de archivos pesados, todo el flujo de ingesta en `backend/services/ingest.py` corre de forma **asíncrona y no bloqueante**:

```
[Archivo Subido] 
       │
       ▼
[Guardado Físico] ──► /uploads/{folder_id}/{filename}
       │
       ▼
[Extracción de Texto] ──► Ejecutado en hilo secundario (asyncio.to_thread)
       │
       ▼
[Generación de Tags] ──► Consulta al LLM local (llama3.1)
       │
       ▼
[Chunking] ──► Splitter de texto (1500 chars / 300 overlap)
       │
       ▼
[Embeddings en Lote] ──► Generación asíncrona paralela (aembed_documents)
       │
       ▼
 ┌─────┴──────────────────────────────────────────────────────┐
 │             Subida Paralela de Índices (Hilos)             │
 ├──────────────────────────────┬─────────────────────────────┤
 │                              │                             │
 ▼                              ▼                             ▼
[Qdrant Upsert]         [Whoosh Indexer]             [MongoDB Registros]
(asyncio.to_thread)     (asyncio.to_thread)          (motor async)
```

1. **Extracción no bloqueante:** Los lectores (`pdfplumber`/`pypdf` para PDF, `python-docx` para Word y lectura de archivos de texto plano) se ejecutan mediante `await asyncio.to_thread(extractor, file_path)`.
2. **Generación de Tags:** El LLM local (`llama3.1` mediante Ollama) analiza de forma asíncrona los primeros 4000 caracteres del archivo y devuelve de 3 a 5 palabras clave.
3. **Chunking (Segmentación):** El texto se fragmenta usando `RecursiveCharacterTextSplitter` con un tamaño de 1500 caracteres y un solapamiento (overlap) de 300 caracteres para asegurar la cohesión contextual.
4. **Embeddings en Lote:** En lugar de iterar y consultar secuencialmente a Ollama por cada fragmento, se invoca `await embeddings.aembed_documents(chunks)` de una sola vez. Esto permite que Ollama procese la vectorización de forma asíncrona y paralela, liberando el bucle de eventos de FastAPI.
5. **Persistencia Híbrida:** 
   * Los vectores generados (vectores de 768 dimensiones del modelo `nomic-embed-text`) se suben a Qdrant encapsulando la llamada HTTP en `asyncio.to_thread(qdrant.upsert, ...)`.
   * El texto y sus metadatos se añaden al índice de Whoosh en disco mediante `asyncio.to_thread(index_document_chunks, ...)`.
   * Se registran metadatos y chunks en MongoDB usando el driver reactivo `motor`.

---

## 4. Motor de Búsqueda Híbrida y Fusión
El endpoint `/search/` realiza búsquedas combinadas:

1. **Recuperación Vectorial (Qdrant):**
   * Genera el embedding de la pregunta mediante `aembed_query` (asíncrono).
   * Consulta a Qdrant buscando similitud de coseno, aplicando filtros en caliente de tipo `FieldCondition` para `folder_id` y `filename` si se especifican.
2. **Recuperación Léxica (Whoosh):**
   * Consulta el índice de texto completo en la carpeta local `backend/whoosh_index`.
   * Utiliza el analizador de español (`LanguageAnalyzer("es")`) para aplicar filtrado morfológico (stemming) y omitir stop-words.
   * Devuelve recortes de texto formateados con el string de coincidencia exacta resaltado.
3. **Fusión de Resultados:**
   * Se combinan los resultados de ambos motores. Si un fragmento es recuperado por ambas vías, su puntuación se normaliza y se potencia, asegurando que las coincidencias textuales exactas y las conceptuales aparezcan al inicio.

---

## 5. Módulo RAG y Reranking Local Offline

Cuando se realiza una pregunta en el chat, la cadena de ejecución en `backend/services/rag.py` sigue estos pasos:

### Paso 1: Detector de Intenciones (Bypass de LLM)
Antes de invocar modelos pesados, se ejecuta una función regex: `detect_document_search_intent(query)`.
* **Propósito:** Captura preguntas estructuradas de búsqueda de archivos (ej. *"¿En qué documento habla de..."*).
* **Flujo:** Si da positivo, realiza una búsqueda rápida en Whoosh/Qdrant, **agrupa los fragmentos por documento en memoria** y responde al instante con formato Markdown `**`, salteándose por completo la llamada al LLM (tiempo medio de respuesta: **< 0.1 segundos**).

### Paso 2: Recuperación e Inferencia
Si no se detecta la intención del Paso 1, continúa el pipeline RAG tradicional:
1. **Búsqueda Vectorial:** Se obtienen los 20 mejores fragmentos de Qdrant según el vector de consulta de la pregunta.
2. **Reranker Local (FlashRank):**
   * La biblioteca `flashrank` está inicializada de forma perezosa en memoria usando el modelo ligero ONNX `ms-marco-MiniLM-L-12-v2`.
   * Los 20 fragmentos de Qdrant se envían a FlashRank, el cual ejecuta una comparación de relevancia local en CPU.
   * Se seleccionan únicamente los **3 fragmentos más relevantes** (`top_n=3`), descartando el resto.
3. **Inyección de Doctrina Militar (Glosario):**
   * Se lee el glosario base desde la colección de MongoDB `system_settings` (clave `military_glossary`) y se inyecta como fuente oficial de verdad en el prompt del sistema.
4. **Construcción y Generación del LLM:**
   * Se ensambla el prompt final inyectando el rol del usuario (Admin detallado vs User conciso y sin tecnicismos), el glosario y los 3 fragmentos depurados de FlashRank.
   * Se ejecuta la llamada asíncrona a Ollama LLaMA 3.1 (`await llm.ainvoke(prompt)`).
   * Al reducir el contexto a solo 3 fragmentos, el volumen de tokens procesado en CPU disminuye radicalmente, reduciendo el tiempo de generación en más de un 60%.
5. **Retorno y Medición de Tiempos:**
   * Se calcula el tiempo transcurrido en segundos (`execution_time`) y se retorna junto con la respuesta generada del chat.
