"""Agente 2: ranking de cargos comparando el embedding del CV con los perfiles de embeddings_store.json."""
import json
import os
import re
import time
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from google import genai

def _ubicar_agente1() -> Path:
    """Carpeta del agente 1: variable RUTA_AGENTE1 o, si no existe, la carpeta madre de agente2/."""
    for c in (os.getenv("RUTA_AGENTE1"), Path(__file__).resolve().parent.parent):
        if c and (Path(c) / "embeddings_store.json").exists():
            return Path(c)
    return Path(__file__).resolve().parent.parent


RUTA_AGENTE1 = _ubicar_agente1()
load_dotenv(Path(__file__).parent / ".env", override=False)
load_dotenv(RUTA_AGENTE1 / ".env", override=True)

MODELO_EMBEDDING = "gemini-embedding-001"   # debe ser el mismo que usa conocimiento.py
ARCHIVO_EMBEDDINGS = RUTA_AGENTE1 / "embeddings_store.json"
ARCHIVO_TABLA = Path(__file__).parent / "categoria_a_cargos.json"

# Valores iniciales, SIN calibrar. Ajustar después de medir con CVs reales.
UMBRAL_CLASIFICADOR = 0.40   # el clasificador solo cuenta si su top 1 supera esto
PESO_CLASIFICADOR = 0.10     # cuánto puede sumar el clasificador a la similitud
MAX_CARACTERES_CV = 6000

_cliente = None
_perfiles = None


def _get_cliente():
    global _cliente
    if _cliente is None:
        clave = os.getenv("GEMINI_API_KEY")
        if not clave:
            raise RuntimeError("No se encontró GEMINI_API_KEY (revisa el .env del agente 1 o crea uno aquí).")
        _cliente = genai.Client(api_key=clave)
    return _cliente


def embedding(texto: str) -> np.ndarray:
    for intento in range(5):
        try:
            r = _get_cliente().models.embed_content(
                model=MODELO_EMBEDDING, contents=texto[:MAX_CARACTERES_CV]
            )
            v = np.array(r.embeddings[0].values, dtype=np.float64)
            return v / np.linalg.norm(v)
        except Exception as e:
            print(f"  reintento {intento + 1}: {str(e)[:100]}")
            time.sleep(15 * (intento + 1))
    raise RuntimeError("No se pudo calcular el embedding del CV.")


def cargar_perfiles() -> dict:
    """{'perfil_contable': matriz (n_fragmentos x dim) normalizada, ...}"""
    global _perfiles
    if _perfiles is None:
        registros = json.loads(ARCHIVO_EMBEDDINGS.read_text(encoding="utf-8"))
        grupos = {}
        for r in registros:
            if r["archivo"].startswith("perfil_"):
                grupos.setdefault(r["archivo"][:-4], []).append(r["embedding"])
        _perfiles = {}
        for nombre, vecs in grupos.items():
            m = np.array(vecs, dtype=np.float64)
            _perfiles[nombre] = m / np.linalg.norm(m, axis=1, keepdims=True)
    return _perfiles


def similitudes_por_cargo(texto: str, emb: np.ndarray = None) -> dict:
    """Similitud del CV con cada perfil: promedio de sus 2 fragmentos más parecidos."""
    if emb is None:
        emb = embedding(texto)
    salida = {}
    for nombre, matriz in cargar_perfiles().items():
        sims = np.sort(matriz @ emb)[::-1]
        salida[nombre] = float(sims[:2].mean())
    return salida


def bonus_clasificador(categorias: list) -> dict:
    """categorias = salida de clasificar(): [{'categoria':..., 'probabilidad':...}, ...]"""
    if not categorias or categorias[0]["probabilidad"] < UMBRAL_CLASIFICADOR:
        return {}
    tabla = json.loads(ARCHIVO_TABLA.read_text(encoding="utf-8"))
    bonus = {}
    for c in categorias:
        for cargo in tabla.get(c["categoria"], {}).get("cargos", []):
            bonus[cargo] = bonus.get(cargo, 0.0) + PESO_CLASIFICADOR * c["probabilidad"]
    return bonus


def ordenar(sims: dict, bonus: dict, k: int = 3) -> list:
    filas = [
        {"cargo": c, "similitud": s, "bonus": bonus.get(c, 0.0), "puntaje": s + bonus.get(c, 0.0)}
        for c, s in sims.items()
    ]
    return sorted(filas, key=lambda f: f["puntaje"], reverse=True)[:k]


def recomendar_cargos(texto: str, k: int = 3, usar_clasificador: bool = True) -> list:
    sims = similitudes_por_cargo(texto)
    bonus = {}
    if usar_clasificador:
        from cargar_modelo_onnx import clasificar
        bonus = bonus_clasificador(clasificar(texto, k=3))
    return ordenar(sims, bonus, k)


if __name__ == "__main__":
    import sys
    texto = Path(sys.argv[1]).read_text(encoding="utf-8")
    for f in recomendar_cargos(texto):
        print(f"{f['cargo']}: similitud {f['similitud']:.3f} | bonus {f['bonus']:.3f} | puntaje {f['puntaje']:.3f}")
