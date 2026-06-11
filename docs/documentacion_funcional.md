# DOCUMENTACIÓN FUNCIONAL: CHATIA

Esta documentación está orientada a los usuarios finales y administradores del sistema, detallando el funcionamiento práctico de la aplicación, sus módulos principales y los flujos de trabajo recomendados.

---

## 1. Introducción
**ChatIA** es un Asistente Inteligente de Consultas y Búsqueda Documental enfocado en el ámbito del planeamiento y la doctrina militar (ESG - Ejército Argentino). La herramienta permite centralizar grandes volúmenes de documentos, clasificarlos por temáticas y realizar consultas complejas en lenguaje natural, recibiendo respuestas contextualizadas e inmediatas basadas únicamente en los documentos autorizados.

---

## 2. Gestión de Carpetas y Documentos (Módulo de Administración)

El sistema organiza la información de forma estructurada en **Carpetas Temáticas** que contienen **Documentos**.

### Acceso y Roles
* **Rol Administrador (`admin`):** Es el único que tiene permisos para crear y borrar carpetas, así como para subir y eliminar documentos.
* **Rol Usuario (`user`):** Tiene acceso de lectura a las carpetas y documentos para acotar sus búsquedas, pero no puede modificarlos.

### Flujo de Trabajo del Administrador
1. **Creación de una Carpeta:**
   * Haz clic en el botón de creación de carpeta en el panel de administración.
   * Asigna un nombre (ej. *Historia*, *Reglamentos*) y una descripción opcional.
2. **Subida de Archivos:**
   * Selecciona la carpeta correspondiente.
   * Haz clic en el botón de subir archivo. El sistema soporta formatos **PDF (`.pdf`)**, **Microsoft Word (`.docx`, `.doc`)** y **Texto Plano (`.txt`)**.
   * Durante la subida, el sistema realiza el procesamiento en segundo plano (extracción de texto, generación de etiquetas por IA e indexación semántica y de palabras clave). El archivo se listará de inmediato en el panel.
3. **Eliminación de Documentos/Carpetas:**
   * Puedes borrar un documento individual haciendo clic en el icono de papelera. Esto eliminará los metadatos de la base de datos, el archivo físico del servidor y purgará los vectores de búsqueda del motor para evitar respuestas obsoletas.
   * Si eliminas una carpeta, se purgarán automáticamente todos sus documentos asociados.

---

## 3. Buscador Semántico y Léxico (Pestaña "Búsqueda")

La pestaña de búsqueda independiente permite realizar consultas de palabras o conceptos sin interactuar con el chat.

* **Búsqueda Inteligente (Híbrida):** Combina el entendimiento conceptual (búsqueda semántica) con la coincidencia de palabras específicas (búsqueda léxica).
* **Filtros Dinámicos:** Puedes realizar búsquedas globales en toda la base de datos, acotarlas a una carpeta en particular, o seleccionar múltiples documentos específicos de una lista.
* **Recortes Resaltados (Snippets):** Por cada coincidencia encontrada, el buscador devuelve el fragmento del documento donde se halla la respuesta, con las palabras consultadas resaltadas en amarillo brillante (`<mark>`).
* **Descarga e Inspección:** Cada resultado incluye un enlace directo para abrir o descargar el documento original desde el servidor para su verificación.

---

## 4. Asistente Inteligente (Chatbot RAG)

El chatbot interactivo permite "conversar" con tus documentos usando lenguaje natural.

### Alcance de Consulta (Barra Lateral)
Antes de preguntar, puedes definir el contexto de la conversación utilizando la barra lateral:
* **Ámbito General:** Si no seleccionas nada, el chatbot buscará en toda la base de datos.
* **Ámbito de Carpeta:** Al hacer clic en una carpeta (ej. *Historia*), el chat mostrará `Consultado en: Historia (Toda la carpeta)` y solo usará la información de esa carpeta.
* **Ámbito de Archivo:** Al seleccionar un documento específico dentro de una carpeta, las consultas se limitarán estrictamente a la información de ese archivo.

### Detección Automática de Intenciones (Bypass instantáneo)
El asistente incluye un motor inteligente para agilizar consultas directas de archivos:
* Si preguntas algo como *"¿En qué documento se habla de San Martín?"* o *"¿Qué archivo contiene la doctrina militar?"*, el sistema detecta que buscas la ubicación de la información en lugar de una redacción compleja.
* **Configuración Dinámica:** Los administradores disponen de una pestaña llamada **"Ajustes Detector"** en el panel lateral, desde la cual pueden ver la lista completa de frases e incluso añadir nuevos términos o expresiones regulares avanzadas en tiempo real.
* **Beneficio:** Evita procesar la respuesta mediante el LLM (ahorrando tiempo y uso de hardware). El chatbot te devolverá de forma **instantánea** la lista de documentos y los fragmentos exactos agrupados por archivo, con las palabras buscadas resaltadas en negrita (`**`).

### Respuestas Personalizadas por Rol
* **Para Administradores:** Las respuestas del chat detallan el origen técnico de los datos (mencionando archivos y secciones exactas) permitiendo auditar la precisión del sistema.
* **Para Usuarios Comunes:** Las respuestas son directas, concisas y ejecutivas, evitando jerga técnica (como "vectores", "embeddings", etc.) para facilitar la lectura inmediata.

### Historial de Conversación
Las sesiones de chat se guardan automáticamente en la barra lateral.
* Puedes hacer clic en una sesión antigua para reanudar la conversación.
* Puedes renombrar el título de la sesión o eliminarla por completo.
* Cada respuesta del asistente muestra en la parte superior el tiempo exacto que tardó en generarse (ej. `Respuesta generada en 1.25 segundos`), lo que te ayuda a comprobar la agilidad del motor local.
