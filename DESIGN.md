# ESG - Planeamiento - EJÉRCITO ARGENTINO
## Asistente Inteligente RAG y Gestión Documental

**Objetivo principal**: Migrar y modernizar el asistente inteligente hacia una plataforma completa con interfaz moderna (React), gestión de usuarios y roles, sistema de carpetas temáticas indexadas, y filtrado híbrido de búsqueda. Todo bajo un entorno local dockerizado.

### Arquitectura General

El sistema está orquestado mediante `docker-compose` y se compone de:
1. **Frontend (React + Vite)**: Interfaz de usuario dinámica, responsiva, con estética premium y soporte para **Modo Oscuro** (persistido localmente mediante `localStorage`).
2. **Backend (Python + FastAPI)**: API REST que maneja la lógica de negocio, autenticación, gestión de documentos y la cadena RAG.
3. **MongoDB**: Base de datos principal para almacenar colecciones de:
   - Usuarios y Roles (`users`)
   - Carpetas Temáticas (`folders`)
   - Metadatos de Documentos (`documents`)
   - Historial de Auditoría de Chats (`chat_messages`)
4. **Qdrant**: Base de datos vectorial para el almacenamiento de fragmentos indexados (embeddings) y recuperación semántica de contexto.
5. **Ollama**: Motor de IA generativa para LLM locales y generación de embeddings vectoriales.

---

### Componentes de IA y LangChain

1. **Modelos (Ollama Local)**:
   - `llama3.1`: Para generación de respuestas (LLM).
   - `nomic-embed-text`: Para la creación de embeddings vectoriales.
   - *(Opcional)* `moondream`: Soporte OCR visual.

2. **Base Vectorial (Qdrant)**:
   - Los embeddings se almacenan en una colección única llamada `documents`.
   - Cada fragmento de texto vectorial (punto) contiene metadatos payload clave: `folder_id` y `filename`.
   - Se aplican filtros Qdrant de tipo `FieldCondition` en tiempo de búsqueda para restringir los fragmentos de contexto recuperados a una carpeta completa o a un archivo en específico.

3. **Pipeline Principal (RAG)**:
   - El usuario selecciona una carpeta o un archivo de la barra lateral para acotar la consulta.
   - Envía la pregunta y el frontend transmite `query`, `folder_id` (opcional) y `filename` (opcional).
   - Generación de embedding de la consulta usando `nomic-embed-text`.
   - Recuperación en Qdrant aplicando filtros `folder_id` y/o `filename`.
   - Reranking opcional mediante la API de Cohere (si está disponible `COHERE_API_KEY`).
   - Construcción del prompt integrando los fragmentos recuperados en el contexto y las directivas de comportamiento del sistema.
   - Invocación de Ollama `llama3.1` para generar la respuesta final estructurada.

---

### Barra Lateral y Modos de Búsqueda

El sidebar izquierdo implementa un árbol jerárquico dinámico:
- **Carpetas Temáticas**: Se pueden contraer/expandir. Al hacer clic sobre el nombre de una carpeta, se activa la búsqueda global sobre **todos** los documentos de esa carpeta (`(Toda la carpeta)`).
- **Documentos**: Aparecen identados debajo de su carpeta correspondiente al expandirla. Al hacer clic en un documento específico, el alcance del RAG se limita **únicamente** a la información contenida en dicho archivo.

---

### Sistema de Usuarios y Roles

La plataforma cuenta con dos roles principales gestionados mediante tokens JWT:
- **Administrador**:
  - Puede gestionar carpetas (crear, eliminar).
  - Puede subir y eliminar documentos de las carpetas (chunking e ingesta automática).
  - Accede a la administración de usuarios y roles.
- **Usuario Común**:
  - Accede al chatbot de consultas en el panel principal.
  - Selecciona carpetas y archivos para acotar el contexto de su consulta.

---

### Endpoints de la API (FastAPI Backend)

**Autenticación**:
- `POST /auth/login` (Recibe email y password, devuelve token JWT y rol)

**Carpetas (Administración)**:
- `GET /folders` (Lista todas las carpetas)
- `POST /folders/` (Crea una nueva carpeta con nombre y descripción)
- `DELETE /folders/{id}` (Elimina una carpeta, sus documentos asociados en DB y sus vectores en Qdrant)

**Documentos**:
- `GET /folders/{folder_id}/documents` (Obtiene todos los metadatos de documentos pertenecientes a una carpeta)
- `POST /folders/{folder_id}/documents/upload` (Carga un archivo PDF, Word o TXT, realiza la segmentación en fragmentos, extrae embeddings y guarda los vectores en Qdrant vinculados a `folder_id` y `filename`)
- `DELETE /folders/documents/{id}` (Elimina un documento y purga sus vectores correspondientes de Qdrant)

**Chat (RAG)**:
- `POST /chat/` (Recibe `ChatRequest` conteniendo `query`, `folder_id` y `filename`. Ejecuta el pipeline RAG y retorna la respuesta de la IA)

---

### Docker y Despliegue

Servicios definidos en `docker-compose.yml`:
- `mongodb`: Base de datos NoSQL persistida localmente.
- `qdrant`: Base vectorial con almacenamiento en disco.
- `ollama`: Servidor local para inferencia local de IA.
- `backend`: Aplicación FastAPI expuesta en el puerto `8000`.
- `frontend`: Aplicación React + Vite expuesta en el puerto `5173`. Cuenta con observador por polling (`usePolling: true`) habilitado para asegurar la sincronización de archivos en sistemas host Windows.