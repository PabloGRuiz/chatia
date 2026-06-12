# FICHA TÉCNICA: CHATIA - ASISTENTE RAG Y GESTIÓN DOCUMENTAL

## 1. Información General
* **Nombre del Proyecto:** ChatIA - ESG Planeamiento (Ejército Argentino)
* **Propósito:** Asistente inteligente RAG (Retrieval-Augmented Generation) y gestión documental para consultar archivos locales clasificados por carpetas temáticas, integrando búsqueda híbrida y un glosario militar como doctrina base.
* **Modo de Despliegue:** Entorno local completamente dockerizado y autónomo (sin dependencias obligatorias de la nube).

---

## 2. Arquitectura de Software y Topología Docker
El sistema se compone de 5 contenedores orquestados mediante **Docker Compose**:

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

* **`chatia_frontend` (React + Vite):** Expuesto en el puerto `5173`. Interfaz web moderna con modo oscuro persistido en `localStorage` y soporte para visualización interactiva de coincidencias.
* **`chatia_backend` (FastAPI):** Expuesto en el puerto `8000`. API REST asíncrona que maneja la lógica RAG, el motor de indexación híbrida y la autenticación.
* **`chatia_mongodb` (MongoDB):** Puerto local `27018`. Guarda metadatos de documentos, carpetas, usuarios, roles, logs de chat y glosario militar.
* **`chatia_qdrant` (Qdrant):** Puertos `6333`/`6334`. Base de datos vectorial para almacenamiento y búsqueda semántica rápida de embeddings.
* **`chatia_ollama` (Ollama):** Puerto `11434`. Servidor local que ejecuta los modelos de IA generativa y embeddings.

---

## 3. Pila Tecnológica (Tech Stack)

### Frontend
* **Core:** React 19 (JavaScript), Vite 8 (Herramienta de construcción rápida).
* **Enrutamiento:** React Router Dom v7.
* **Estilos:** CSS puro (diseño premium, responsivo, soporte para modo oscuro, animaciones fluidas).
* **Iconografía:** Lucide React.

### Backend
* **Framework Web:** FastAPI (Python 3.11) + Uvicorn (servidor ASGI).
* **Orquestación RAG:** LangChain y LangChain Community.
* **Bases de Datos y Clientes:**
  * `motor`: Cliente asíncrono oficial para MongoDB.
  * `qdrant-client`: Cliente oficial para Qdrant DB.
  * `fastembed`: Librería de generación de embeddings locales rápidos e independientes de Ollama.
  * `whoosh`: Motor de búsqueda de texto completo e indexación léxica (100% Python).
* **Seguridad:** JSON Web Tokens (JWT), encriptación bcrypt para credenciales (`passlib`).
* **Librerías de Procesamiento de Archivos y OCR:**
  * `pdfplumber` (Lectura avanzada y estructurada de PDFs).
  * `pypdf` (Lector PDF secundario / fallback).
  * `python-docx` (Extracción de archivos Microsoft Word `.docx` / `.doc`).
  * `pymupdf` (PyMuPDF - Extracción de imágenes de páginas PDF para procesamiento OCR).
  * `pytesseract` (Enlace de Python para Tesseract OCR, digitalización de imágenes de texto).
* **Variables de Entorno:** Administradas con `python-dotenv`.

---

## 4. Motor de Búsqueda Híbrido (Semantic + Lexical)
El backend implementa una estrategia de recuperación híbrida para maximizar la relevancia de los resultados:

1. **Búsqueda Semántica (Qdrant):**
   * Convierte la consulta en un vector de **384 dimensiones** usando el modelo local `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` mediante la librería **FastEmbed**.
   * Realiza una búsqueda por similitud de coseno en la colección `documents`.
   * Permite filtrado exacto en caliente (`FieldCondition`) por `folder_id` y `filename` directamente en Qdrant.
2. **Búsqueda Léxica/Exacta (Whoosh):**
   * Índice de texto completo almacenado localmente en el volumen del servidor (`backend/whoosh_index`).
   * Configurado con `LanguageAnalyzer("es")` (analizador nativo en español que incluye stop-words y stemming).
   * Genera fragmentos (snippets) dinámicos con las palabras clave resaltadas en etiquetas HTML `<mark>` o Markdown `**`.
3. **Fusión Híbrida:**
   * Combina y normaliza las puntuaciones de ambos motores para ofrecer la mejor coincidencia exacta y contextualizada.
   * *Opcional:* Si se define `COHERE_API_KEY`, se aplica un paso de **Reranking** usando el modelo `rerank-multilingual-v2.0` de Cohere.

---

## 5. Módulo RAG y Detección de Intenciones (Intent Bypass)
* **Modelos de IA:**
  * **LLM Principal:** `phi3:mini` (u otro modelo local configurable en `.env`, ejecutándose en local sobre Ollama con un timeout robusto de 300s para evitar fallas en CPU).
  * **Embedding Model:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (FastEmbed local, 384 dimensiones).
* **Pipeline RAG Contextualizado:**
  * El prompt del sistema (`SYSTEM_PROMPT`) incluye obligatoriamente una sección de **Glosario y Doctrina Base** extraída de MongoDB. Sirve como fuente de verdad para definir jerarquías y traducir terminología o abreviaturas militares.
* **Personalización por Roles:**
  * **Administrador:** Respuestas detalladas que mencionan fuentes técnicas, nombres de archivos, fragmentos y referencias internas de base de datos.
  * **Usuario Común:** Respuestas ejecutivas, directas y sin tecnicismos del sistema (ocultando palabras como "Qdrant", "embeddings", "fragmentos", etc.).
* **Cortocircuito de Consulta de Archivo (Intent Bypass):**
  * Un sistema basado en expresiones regulares y términos literales detecta si el usuario está haciendo una pregunta puramente de búsqueda de documentos (ej. *"¿En qué archivo se menciona..."*, *"¿Dónde habla del reglamento..."*).
  * **Comportamiento:** Salta por completo la llamada al LLM (ahorrando tiempo de procesamiento y tokens locales). Realiza una búsqueda directa y veloz en Whoosh y Qdrant, agrupa los fragmentos por documento y devuelve de forma instantánea una lista estructurada con las palabras buscadas resaltadas en negrita.

---

## 6. Pipeline de Ingesta de Documentos
Cuando un usuario con rol de Administrador sube un documento:
1. **Validaciones en Carga:**
   * **Tamaño Máximo:** Se valida que el tamaño total acumulado de los archivos subidos en una sola petición no exceda los **100 MB**.
   * **Extensiones Soportadas:** Se comprueba que los archivos pertenezcan a las extensiones válidas (`.pdf`, `.docx`, `.doc`, `.txt`).
2. **Almacenamiento:** Guarda físicamente el archivo en `backend/uploads/{folder_id}/{filename}`.
3. **Extracción de Texto y Fallback OCR:** 
   * Parsea el contenido seleccionable según la extensión (`.pdf`, `.docx`, `.doc`, `.txt`).
   * **Soporte OCR Local:** Si es un documento PDF y el extractor no detecta ningún texto digitalizado o seleccionable (por ejemplo, fotocopias de doctrina histórica o reglamentos antiguos escaneados), el backend activa automáticamente el pipeline de OCR local en segundo plano. Éste renderiza las páginas a imágenes de alta definición usando PyMuPDF y extrae el texto mediante Tesseract OCR (idiomas: `spa+eng`).
4. **Etiquetado por IA:** Envía los primeros 4000 caracteres al LLM local para autogenerar entre 3 y 5 etiquetas (tags) conceptuales del archivo.
5. **Chunking (Segmentación):** Divide el texto en fragmentos con un tamaño máximo de 1500 caracteres y una superposición (overlap) de 300 caracteres utilizando `RecursiveCharacterTextSplitter`.
6. **Indexación Vectorial:** Genera embeddings locales de 384 dimensiones usando `FastEmbed` y los sube en lote a Qdrant.
7. **Indexación Léxica:** Escribe los fragmentos en el índice local de Whoosh.
8. **Persistencia en MongoDB:** Registra el documento en la colección `documents` y almacena los fragmentos individuales en `document_chunks` para referencias y auditorías futuras.
