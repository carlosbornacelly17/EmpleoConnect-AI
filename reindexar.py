"""Reconstruye embeddings_store.json de forma incremental y tolerante al límite de la API (uso: python reindexar.py)."""

import json
import os
import time

import conocimiento as c

PAUSA_ENTRE_LLAMADAS = 0.7   # segundos entre llamadas reales a la API (~85 por minuto)
ESPERA_TRAS_429 = 35         # segundos de espera cuando la API responde 429
MAX_REINTENTOS = 8

ARCHIVO_PARCIAL = os.path.join(
    os.path.dirname(c.ARCHIVO_EMBEDDINGS), "embeddings_cache_parcial.json"
)


def _cargar_cache() -> dict:
    """Devuelve {texto_del_fragmento: embedding} con lo que ya está calculado."""
    cache = {}
    if os.path.exists(c.ARCHIVO_EMBEDDINGS):
        with open(c.ARCHIVO_EMBEDDINGS, "r", encoding="utf-8") as f:
            for r in json.load(f):
                cache[r["texto"]] = r["embedding"]
    if os.path.exists(ARCHIVO_PARCIAL):
        with open(ARCHIVO_PARCIAL, "r", encoding="utf-8") as f:
            cache.update(json.load(f))
    return cache


def _es_limite_de_cuota(error: Exception) -> bool:
    return (
        getattr(error, "code", None) == 429
        or "429" in str(error)
        or "RESOURCE_EXHAUSTED" in str(error)
    )


def _embedding_con_reintentos(texto: str) -> list:
    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            return c._generar_embedding(texto)
        except Exception as e:
            if _es_limite_de_cuota(e) and intento < MAX_REINTENTOS:
                print(
                    f"   Límite de la API alcanzado. Esperando {ESPERA_TRAS_429} s "
                    f"(intento {intento}/{MAX_REINTENTOS})...",
                    flush=True,
                )
                time.sleep(ESPERA_TRAS_429)
            else:
                raise


def main():
    if not os.path.isdir(c.CARPETA_DOCUMENTOS):
        raise SystemExit(f"No existe la carpeta: {c.CARPETA_DOCUMENTOS}")

    # 1) Leer y fragmentar todos los documentos (sin usar la API)
    fragmentos = []
    for nombre in sorted(os.listdir(c.CARPETA_DOCUMENTOS)):
        if not nombre.endswith(".txt"):
            continue
        doc = c._parsear_documento(os.path.join(c.CARPETA_DOCUMENTOS, nombre))
        for i, texto in enumerate(c._dividir_en_fragmentos(doc["contenido"])):
            fragmentos.append({
                "archivo": doc["archivo"],
                "titulo": doc["titulo"],
                "fuente": doc["fuente"],
                "link": doc["link"],
                "fragmento_num": i,
                "texto": texto,
            })

    cache = _cargar_cache()
    por_calcular = [f for f in fragmentos if f["texto"] not in cache]

    print(f"Documentos .txt encontrados: {len({f['archivo'] for f in fragmentos})}")
    print(f"Fragmentos totales: {len(fragmentos)}")
    print(f"Reutilizados (ya tenían embedding): {len(fragmentos) - len(por_calcular)}")
    print(f"Por calcular con la API: {len(por_calcular)}\n", flush=True)

    # 2) Calcular solo lo que falta
    nuevos = 0
    try:
        for f in fragmentos:
            if f["texto"] in cache:
                continue
            cache[f["texto"]] = _embedding_con_reintentos(f["texto"])
            nuevos += 1
            print(f"   [{nuevos}/{len(por_calcular)}] {f['archivo']} (fragmento {f['fragmento_num']})", flush=True)
            time.sleep(PAUSA_ENTRE_LLAMADAS)
    except BaseException:
        with open(ARCHIVO_PARCIAL, "w", encoding="utf-8") as fp:
            json.dump(cache, fp, ensure_ascii=False)
        print(
            f"\nSe interrumpió el proceso. Se guardó el avance ({nuevos} embeddings "
            f"nuevos) en {ARCHIVO_PARCIAL}.\nVuelve a ejecutar este script para continuar."
        )
        raise

    # 3) Escribir el índice final de forma segura
    registros = []
    for f in fragmentos:
        registro = dict(f)
        registro["embedding"] = cache[f["texto"]]
        registros.append(registro)

    temporal = c.ARCHIVO_EMBEDDINGS + ".tmp"
    with open(temporal, "w", encoding="utf-8") as fp:
        json.dump(registros, fp, ensure_ascii=False)
    os.replace(temporal, c.ARCHIVO_EMBEDDINGS)

    if os.path.exists(ARCHIVO_PARCIAL):
        os.remove(ARCHIVO_PARCIAL)

    print(f"\nListo. embeddings_store.json actualizado con {len(registros)} fragmentos "
          f"({nuevos} calculados ahora).")


if __name__ == "__main__":
    main()
