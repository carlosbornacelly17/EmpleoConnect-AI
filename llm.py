"""Conexión con el LLM (Gemini) y generación de respuestas con RAG."""

import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

import conocimiento

load_dotenv()  # lee las variables definidas en el archivo .env

API_KEY = os.getenv("GEMINI_API_KEY")

MODELO = "gemini-3.5-flash-lite"

SYSTEM_PROMPT_RAG = (
    "Eres el asistente virtual de EmpleoConnect AI, una herramienta de orientación "
    "laboral para estudiantes universitarios y profesionales recién graduados. "
    "Responde ÚNICAMENTE con base en los FRAGMENTOS DE CONTEXTO que se te entregan, "
    "que provienen de documentos confiables sobre orientación laboral. Si la información "
    "necesaria NO está en el contexto, dilo en una frase en vez de inventar con "
    "conocimiento general.\n\n"
    "ESTILO DE LA RESPUESTA (muy importante):\n"
    "- Máximo 120 palabras. Que se lea en menos de un minuto.\n"
    "- Empieza con la respuesta directa en 1 o 2 frases. Sin saludos ni introducciones.\n"
    "- Usa lenguaje sencillo, como si le explicaras a un estudiante; evita tecnicismos y "
    "frases largas. Si usas un término técnico, explícalo en pocas palabras.\n"
    "- Si hay varios pasos o consejos, usa una lista de 3 a 4 viñetas cortas (una línea "
    "cada una). No uses títulos ni negritas en exceso.\n"
    "- No repitas la pregunta ni resumas al final. No menciones ni listes las fuentes: "
    "la página las muestra aparte.\n"
    "- Si la pregunta es muy amplia, da lo esencial y ofrece profundizar en un punto con una "
    "frase final corta.\n\n"
    "Si los fragmentos de distintas fuentes recomiendan cosas diferentes (por ejemplo, la "
    "extensión ideal de la hoja de vida), resúmelo en una línea indicando qué dice cada "
    "fuente; no elijas una sola.\n\n"
    "Si además se te entrega la HOJA DE VIDA DEL USUARIO, personaliza la respuesta con "
    "1 o 2 observaciones concretas (una fortaleza o un vacío) sacadas de ella. No inventes "
    "datos del usuario que no estén en su hoja de vida."
)

MAX_CARACTERES_CV = 3000  # para no saturar el contexto con hojas de vida muy largas


def _get_client():
    if not API_KEY:
        raise RuntimeError(
            "No se encontró GEMINI_API_KEY. Verifica que exista un archivo .env "
            "en la raíz del proyecto con la línea: GEMINI_API_KEY=tu_key_aqui"
        )
    return genai.Client(api_key=API_KEY)


def generar_respuesta_rag(pregunta: str, historial: list[dict] | None = None, cv_texto: str | None = None) -> dict:
    """Genera una respuesta con RAG; retorna un dict con "respuesta" y "fuentes"."""
    try:
        fragmentos = conocimiento.buscar_fragmentos_relevantes(pregunta, top_k=4)

        if not fragmentos:
            return {
                "respuesta": "⚠️ No se pudo acceder a la base de conocimiento. "
                             "Verifica que la carpeta documentos_base exista y tenga archivos.",
                "fuentes": [],
            }

        contexto = ""
        for i, frag in enumerate(fragmentos, start=1):
            contexto += f"[Fragmento {i} — Fuente: {frag['titulo']} ({frag['fuente']})]\n{frag['texto']}\n\n"

        client = _get_client()

        contenido = SYSTEM_PROMPT_RAG + "\n\n--- CONTEXTO (documentos de orientación laboral) ---\n\n" + contexto

        if cv_texto:
            cv_recortado = cv_texto[:MAX_CARACTERES_CV]
            contenido += "--- HOJA DE VIDA DEL USUARIO ---\n\n" + cv_recortado + "\n\n"

        if historial:
            contenido += "--- CONVERSACIÓN PREVIA ---\n\n"
            for turno in historial[-5:]:
                contenido += f"Usuario: {turno['mensaje']}\nAsistente: {turno['respuesta']}\n\n"

        contenido += f"--- PREGUNTA ACTUAL ---\nUsuario: {pregunta}\nAsistente:"

        response = client.models.generate_content(
            model=MODELO,
            contents=contenido,
            config=types.GenerateContentConfig(temperature=0.3, max_output_tokens=1200),
        )

        # Fuentes únicas (sin duplicar si varios fragmentos vienen del mismo documento)
        fuentes_unicas = {}
        for frag in fragmentos:
            fuentes_unicas[frag["archivo"]] = {
                "titulo": frag["titulo"],
                "fuente": frag["fuente"],
                "link": frag["link"],
            }

        return {
            "respuesta": response.text.strip(),
            "fuentes": list(fuentes_unicas.values()),
        }

    except RuntimeError as e:
        return {"respuesta": f"⚠️ {e}", "fuentes": []}
    except Exception as e:
        return {"respuesta": f"⚠️ Ocurrió un error al generar la respuesta con RAG: {e}", "fuentes": []}
