# EmpleoConnect AI

Asistente web para estudiantes y recién egresados de la Universidad del Norte que ayuda en la búsqueda de empleo. Proyecto académico (Grupo 8, Universidad del Norte). Es un prototipo de demostración y no reemplaza la asesoría profesional de empleo.

## Qué hace

- **Agente 1 – Chat con RAG:** responde dudas sobre hoja de vida, entrevistas, habilidades y formación, a partir de una base de 68 documentos, y cita las fuentes. Las respuestas son cortas y en tono natural.
- **Agente 2 – Análisis de hoja de vida:** clasifica el CV con un modelo DistilBERT (ONNX), sugiere hasta 5 cargos y arma un plan de formación con cursos y ofertas de empleo.
- **Web scraping:** cursos de Coursera y ofertas de LinkedIn y Computrabajo. Si una página falla, el sistema usa su base de documentos.
- **Plataforma:** registro y login (bcrypt + JWT), roles de administrador, estadísticas de uso y encuesta de satisfacción.

## Tecnologías

Python · Streamlit · SQLite · Google Gemini (embeddings y generación) · ONNX Runtime · requests + BeautifulSoup

## Instalación

1. Clona el repositorio y entra a la carpeta:
   ```
   git clone https://github.com/carlosbornacelly17/EmpleoConnect-AI.git
   cd EmpleoConnect-AI
   ```
2. Crea y activa un entorno virtual, e instala las dependencias:
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **Descarga el modelo del clasificador.** Es muy grande para el repositorio. Bájalo desde la sección [Releases](https://github.com/carlosbornacelly17/EmpleoConnect-AI/releases) (`modelo_cv.onnx`) y guárdalo en `agente2/modelo_onnx/`.
4. Copia `.env.example` como `.env` y completa los valores:
   ```
   GEMINI_API_KEY=tu_clave_de_gemini
   JWT_SECRET_KEY=cadena_aleatoria_larga
   ADMIN_HASHES='{"correo@uninorte.edu.co": "hash_bcrypt"}'
   ```
   - La clave de Gemini se obtiene en Google AI Studio.
   - Para `JWT_SECRET_KEY`: `python -c "import secrets; print(secrets.token_hex(32))"`
   - Para cada administrador: `python generar_admin.py correo@uninorte.edu.co` genera su código y su hash.
5. Ejecuta la app:
   ```
   streamlit run app.py
   ```

## Estructura

| Ruta | Contenido |
|---|---|
| `app.py` | Interfaz principal (login, menú, chat, encuesta, paneles de admin) |
| `auth.py`, `database.py` | Autenticación y base de datos SQLite |
| `llm.py`, `conocimiento.py` | Chat con RAG y base de conocimiento |
| `agente2/` | Análisis de hoja de vida, clasificador y scraping |
| `documentos_base/` | Documentos de la base de conocimiento |
| `embeddings_store.json` | Embeddings de los documentos (3072 dimensiones) |
| `reindexar.py` | Reconstruye los embeddings tras cambiar documentos |

## Privacidad

El texto de la hoja de vida se envía a la API de Gemini para generar embeddings y respuestas, y el agente 2 pide consentimiento antes de analizarla. Al scraping solo se envían títulos de cargo y habilidades, nunca el texto del CV. Diseño alineado con la Ley 1581 de 2012; algunas medidas, como el enmascaramiento de datos y el borrado automático, aún no están implementadas.

## Autores

Grupo 8 – Universidad del Norte: Carlos Bornacelly, Cristian Acurio, Fabio Jaimes y Luis Toro.
