"""RAG: lee documentos, genera embeddings con Gemini y busca fragmentos por similitud coseno."""

import os
import re
import json
import math

from dotenv import load_dotenv
from google import genai

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODELO_EMBEDDING = "gemini-embedding-001"  # ajustar si el nombre exacto cambia en tu cuenta

CARPETA_DOCUMENTOS = os.path.join(os.path.dirname(__file__), "documentos_base")
ARCHIVO_EMBEDDINGS = os.path.join(os.path.dirname(__file__), "embeddings_store.json")

TAMANO_FRAGMENTO = 800  # caracteres aprox. por fragmento
SOLAPAMIENTO = 100      # caracteres que se repiten entre fragmentos consecutivos


def _get_client():
    if not API_KEY:
        raise RuntimeError(
            "No se encontró GEMINI_API_KEY. Verifica tu archivo .env"
        )
    return genai.Client(api_key=API_KEY)


# 1. Lectura y parseo de documentos

def _parsear_documento(ruta_archivo: str) -> dict:
    """Lee un .txt y separa el encabezado (titulo/fuente/link) del contenido."""
    with open(ruta_archivo, "r", encoding="utf-8") as f:
        texto = f.read()

    titulo = re.search(r"titulo:\s*(.+)", texto, re.IGNORECASE)
    fuente = re.search(r"fuente:\s*(.+)", texto, re.IGNORECASE)
    link = re.search(r"link:\s*(.+)", texto, re.IGNORECASE)

    # El contenido es todo lo que viene después de las 3 líneas de encabezado
    lineas = texto.split("\n")
    idx_contenido = 0
    campos_encontrados = 0
    for i, linea in enumerate(lineas):
        if re.match(r"(titulo|fuente|link):", linea, re.IGNORECASE):
            campos_encontrados += 1
            idx_contenido = i + 1
        elif campos_encontrados >= 3:
            break

    contenido = "\n".join(lineas[idx_contenido:]).strip()

    return {
        "archivo": os.path.basename(ruta_archivo),
        "titulo": titulo.group(1).strip() if titulo else os.path.basename(ruta_archivo),
        "fuente": fuente.group(1).strip() if fuente else "Fuente no especificada",
        "link": link.group(1).strip() if link else "",
        "contenido": contenido,
    }


def _dividir_en_fragmentos(texto: str) -> list[str]:
    """Divide un texto largo en fragmentos con un poco de solapamiento entre ellos."""
    fragmentos = []
    inicio = 0
    while inicio < len(texto):
        fin = inicio + TAMANO_FRAGMENTO
        fragmento = texto[inicio:fin].strip()
        if fragmento:
            fragmentos.append(fragmento)
        inicio += TAMANO_FRAGMENTO - SOLAPAMIENTO
    return fragmentos


# 2. Generación de embeddings

def _generar_embedding(texto: str) -> list[float]:
    client = _get_client()
    response = client.models.embed_content(
        model=MODELO_EMBEDDING,
        contents=texto,
    )
    return response.embeddings[0].values


def construir_base_conocimiento(forzar: bool = False) -> int:
    """Indexa los documentos (fragmenta y genera embeddings); retorna la cantidad de fragmentos."""
    if os.path.exists(ARCHIVO_EMBEDDINGS) and not forzar:
        with open(ARCHIVO_EMBEDDINGS, "r", encoding="utf-8") as f:
            datos = json.load(f)
        return len(datos)

    if not os.path.isdir(CARPETA_DOCUMENTOS):
        raise FileNotFoundError(
            f"No se encontró la carpeta '{CARPETA_DOCUMENTOS}'. "
            "Verifica que exista y contenga los archivos .txt de la base de conocimiento."
        )

    registros = []
    for nombre_archivo in sorted(os.listdir(CARPETA_DOCUMENTOS)):
        if not nombre_archivo.endswith(".txt"):
            continue
        ruta = os.path.join(CARPETA_DOCUMENTOS, nombre_archivo)
        doc = _parsear_documento(ruta)
        fragmentos = _dividir_en_fragmentos(doc["contenido"])

        for i, fragmento in enumerate(fragmentos):
            embedding = _generar_embedding(fragmento)
            registros.append({
                "archivo": doc["archivo"],
                "titulo": doc["titulo"],
                "fuente": doc["fuente"],
                "link": doc["link"],
                "fragmento_num": i,
                "texto": fragmento,
                "embedding": embedding,
            })

    with open(ARCHIVO_EMBEDDINGS, "w", encoding="utf-8") as f:
        json.dump(registros, f, ensure_ascii=False)

    return len(registros)


# 3. Búsqueda por similitud

def _similitud_coseno(v1: list[float], v2: list[float]) -> float:
    producto_punto = sum(a * b for a, b in zip(v1, v2))
    norma1 = math.sqrt(sum(a * a for a in v1))
    norma2 = math.sqrt(sum(b * b for b in v2))
    if norma1 == 0 or norma2 == 0:
        return 0.0
    return producto_punto / (norma1 * norma2)


def buscar_fragmentos_relevantes(pregunta: str, top_k: int = 4) -> list[dict]:
    """Retorna los `top_k` fragmentos más relevantes para la pregunta."""
    if not os.path.exists(ARCHIVO_EMBEDDINGS):
        construir_base_conocimiento()

    with open(ARCHIVO_EMBEDDINGS, "r", encoding="utf-8") as f:
        registros = json.load(f)

    if not registros:
        return []

    embedding_pregunta = _generar_embedding(pregunta)

    for r in registros:
        r["score"] = _similitud_coseno(embedding_pregunta, r["embedding"])

    registros_ordenados = sorted(registros, key=lambda r: r["score"], reverse=True)
    return registros_ordenados[:top_k]
