# ChatIA - Asistente RAG y Gestión Documental

ChatIA es un Asistente Inteligente de consultas y análisis de documentos diseñado para el ámbito de planeamiento y doctrina militar (ESG - Ejército Argentino). La aplicación corre completamente de forma local y offline mediante contenedores Docker, integrando bases de datos vectoriales y tradicionales para ofrecer una búsqueda híbrida y generación de respuestas contextualizadas en tiempo real.

---

## 📚 Documentación del Proyecto
Para conocer más detalles sobre el funcionamiento y arquitectura del sistema, consulta los siguientes manuales:

* **[Documentación Funcional (Manual del Usuario)](docs/documentacion_funcional.md):** Guía práctica para usuarios y administradores sobre cómo utilizar el chat, el buscador híbrido y gestionar carpetas o archivos.
* **[Documentación Técnica de la Arquitectura](docs/documentacion_tecnica.md):** Detalle técnico de los esquemas de bases de datos (MongoDB/Qdrant), el pipeline de ingesta de archivos asíncrono y no bloqueante, y la lógica de búsqueda y reranking local (FlashRank).
* **[Ficha Técnica General](FICHA_TECNICA.md):** Ficha técnica con la pila tecnológica (Tech Stack), puertos expuestos, modelos locales de IA utilizados (LLM configurable en .env y modelo de embeddings local FastEmbed) y especificaciones del entorno de contenedores.
* **[Guía de Diseño de Interfaz](DESIGN.md):** Especificación original de la arquitectura general, el sidebar jerárquico y los endpoints de la API.

---

## 🛠️ Requisitos e Instalación Local

### Requisitos Previos
* **Docker** y **Docker Compose** instalados en el sistema host.
* Al menos 12 GB de RAM en el host (se reduce de 16 GB gracias a la optimización de modelos ligeros).

### Instrucciones de Despliegue
1. **Configurar las Variables de Entorno:**
   Copia el archivo de ejemplo `.env.example` como `.env`:
   ```bash
   cp .env.example .env
   ```
   *Nota: Ajusta los valores de puertos o el modelo de lenguaje (LLM_MODEL) si es necesario.*

2. **Compilar y Levantar los Contenedores:**
   Ejecuta el siguiente comando en la raíz del proyecto para descargar las imágenes y compilar la API:
   ```bash
   docker compose up --build -d
   ```
   Esto levantará los 5 servicios del sistema:
   * **Frontend (React + Vite):** Accesible en [http://localhost:5173](http://localhost:5173)
   * **Backend (FastAPI):** Accesible en [http://localhost:8000](http://localhost:8000) (con Swagger interactivo en `/docs`)
   * **MongoDB (Base de Datos):** Mapeado en el puerto host `27018`
   * **Qdrant (Base Vectorial):** Accesible en [http://localhost:6333](http://localhost:6333) (Dashboard de Qdrant en el navegador)
   * **Ollama (Motor de IA):** Puerto `11434`

3. **Descarga de Modelos Locales en Ollama (Primer Inicio):**
   Una vez que el contenedor de Ollama esté corriendo, debes descargar el modelo de lenguaje (LLM) que tengas configurado en el archivo `.env` (el valor por defecto es `phi3:mini`). Ejecuta el siguiente comando desde tu terminal:
   ```bash
   # Descargar el LLM configurado (ejemplo para el valor por defecto: phi3:mini)
   docker exec -it chatia_ollama ollama run phi3:mini
   ```
   *Nota: El modelo de embeddings (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`) se gestiona localmente mediante la biblioteca `FastEmbed` de Qdrant en el backend y se descarga automáticamente en el primer inicio.*

4. **Sembrado de Datos Iniciales (Opcional):**
   Para pre-cargar un usuario administrador por defecto y un glosario base en la base de datos, ejecuta el script de sembrado del backend:
   ```bash
   docker exec -it chatia_backend python seed.py
   ```
   *Credenciales del Administrador creadas por defecto:*
   * **Email:** `admin@ejercito.mil.ar`
   * **Contraseña:** `admin123`
