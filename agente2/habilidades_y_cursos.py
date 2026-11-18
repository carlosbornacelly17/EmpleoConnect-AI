"""Agente 2: habilidades faltantes del CV para un cargo, cursos recomendados y guías de hoja de vida."""
import json
import re
from functools import lru_cache
import sys
import time
import unicodedata
from pathlib import Path

import numpy as np

import matcher_cargos as m

try:                                       # scraping web (Coursera, Computrabajo, LinkedIn)
    import scraper as sc
except Exception as _e:                    # sin requests/bs4 la app sigue con la base de documentos
    print(f"scraper no disponible: {_e}")
    sc = None

MODELO_LLM = "gemini-3.5-flash-lite"      # el mismo modelo que usa llm.py del agente 1
CARPETA_PERFILES = m.RUTA_AGENTE1 / "documentos_base"
MAX_FALTANTES = 6
UMBRAL_SIMILITUD = 0.63                   # similitud mínima con el mejor perfil para mostrar cargos (provisional)
MARGEN_AREA_CLARA = 0.10                  # diferencia mínima entre el 1.º y el 2.º del clasificador (0.10 = 10 puntos)
MOSTRAR_SIN_CURSO = False                 # True: lista también las habilidades que no tienen curso en la base
CURSOS_POR_HABILIDAD = 2                  # máximo de cursos por habilidad

PREFIJOS_FORMACION = ("sena_", "cisco_", "aws_", "microsoft_", "python_institute_")
PREFIJOS_GUIAS = ("guia_", "instructivo_", "modelo_", "recomendaciones_")

ACENTOS = {"´a": "á", "´e": "é", "´ı": "í", "´i": "í", "´o": "ó", "´u": "ú",
           "´A": "Á", "´E": "É", "´I": "Í", "´O": "Ó", "´U": "Ú", "˜n": "ñ", "˜N": "Ñ"}
STOP = {"curso", "sena", "complementario", "programa", "formacion", "virtual", "titulada"}


# utilidades
def _limpiar(texto: str) -> str:
    for malo, bueno in ACENTOS.items():
        texto = texto.replace(malo, bueno)
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def extraer_texto_pdf(ruta) -> str:
    import pymupdf
    return _limpiar("\n".join(p.get_text() for p in pymupdf.open(ruta)))


def extraer_texto_bytes(nombre: str, datos: bytes) -> str:
    """Texto de un PDF, un Word (.docx) o un .txt recibido en memoria (por ejemplo, desde Streamlit)."""
    ext = Path(nombre).suffix.lower()
    if ext == ".pdf":
        import pymupdf
        texto = "\n".join(p.get_text() for p in pymupdf.open(stream=datos, filetype="pdf"))
    elif ext == ".docx":
        import io
        import docx
        d = docx.Document(io.BytesIO(datos))
        partes = [par.text for par in d.paragraphs]
        for tabla in d.tables:
            for fila in tabla.rows:
                partes.extend(c.text for c in fila.cells)
        texto = "\n".join(partes)
    else:
        texto = datos.decode("utf-8", errors="ignore")
    return _limpiar(texto)


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]+", " ", t)


def _tokens(t: str) -> set:
    return {w for w in _norm(t).split() if len(w) >= 4 and w not in STOP}


def tipo_documento(archivo: str) -> str:
    if archivo.startswith("perfil_"):
        return "perfil"
    if archivo.startswith(PREFIJOS_FORMACION):
        return "formacion"
    if archivo.startswith(PREFIJOS_GUIAS):
        return "guia_cv"
    if re.match(r"\d\d_", archivo):
        return "entrevista"
    if archivo.startswith("empleo_"):
        return "empleo"
    return "otro"


# base de documentos
_docs = None


def cargar_docs() -> dict:
    """{'sena_kmeans_python': {titulo, fuente, link, tipo, matriz(n x dim)}, ...} sin los perfiles."""
    global _docs
    if _docs is None:
        registros = json.loads(m.ARCHIVO_EMBEDDINGS.read_text(encoding="utf-8"))
        grupos = {}
        for r in registros:
            nombre = r["archivo"][:-4] if r["archivo"].endswith(".txt") else r["archivo"]
            if tipo_documento(nombre) == "perfil":
                continue
            g = grupos.setdefault(nombre, {"titulo": r.get("titulo", nombre), "fuente": r.get("fuente", ""),
                                           "link": r.get("link", ""), "tipo": tipo_documento(nombre), "vecs": [], "intro": ""})
            g["vecs"].append(r["embedding"])
            if r.get("fragmento_num", 0) == 0 or not g["intro"]:
                g["intro"] = r.get("texto", "")
        _docs = {}
        for nombre, g in grupos.items():
            mat = np.array(g.pop("vecs"), dtype=np.float64)
            g["matriz"] = mat / np.linalg.norm(mat, axis=1, keepdims=True)
            g["archivo"] = nombre
            _docs[nombre] = g
    return _docs


# perfiles
def leer_perfil(nombre: str) -> dict:
    texto = (CARPETA_PERFILES / f"{nombre}.txt").read_text(encoding="utf-8")
    bloques = [b.strip() for b in re.split(r"\n\s*\n", texto) if b.strip()]
    secciones = {}
    for b in bloques[1:]:                      # el primer bloque es el encabezado Titulo/Fuente/Link
        cabecera, _, cuerpo = b.partition("\n")
        clave = _norm(cabecera.split(":", 1)[-1]).strip()
        secciones[clave] = cuerpo.strip()
    t = re.search(r"titulo:\s*(.+)", texto, re.IGNORECASE)
    cargo = t.group(1).strip() if t else nombre
    cargo = re.sub(r"^perfil ocupacional:\s*", "", cargo, flags=re.IGNORECASE)
    cargo = re.sub(r"\s*\(\d{4}\)\s*$", "", cargo)
    return {"nombre": nombre, "cargo": cargo, "secciones": secciones, "texto": texto}


def texto_seccion(perfil: dict, claves) -> str:
    return "\n".join(c for k, c in perfil["secciones"].items() if any(p in k for p in claves))


def cursos_del_perfil(perfil: dict) -> list:
    """Documentos de formación cuyo título aparece en la sección 'formación y certificaciones'."""
    sec_tokens = _tokens(texto_seccion(perfil, ("formacion", "certificacion")))
    salida = []
    for d in cargar_docs().values():
        if d["tipo"] != "formacion":
            continue
        t = _tokens(d["titulo"])
        if t and len(t & sec_tokens) / len(t) >= 0.8:
            salida.append(d)
    return salida


# análisis con Gemini
def _parse_json(texto: str):
    texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto.strip())
    return json.loads(texto)


def _llm_json(prompt: str):
    cliente = m._get_cliente()
    for intento in range(4):
        try:
            r = cliente.models.generate_content(
                model=MODELO_LLM, contents=prompt,
                config={"response_mime_type": "application/json", "temperature": 0})
            return _parse_json(r.text)
        except Exception as e:
            print(f"  reintento {intento + 1}: {str(e)[:100]}")
            time.sleep(10 * (intento + 1))
    raise RuntimeError("No se pudo obtener el análisis de habilidades.")


def analizar_habilidades(cv_texto: str, perfil: dict) -> dict:
    requisitos = texto_seccion(perfil, ("habilidades tecnicas", "tecnologias")) or perfil["texto"]
    prompt = f"""Eres un orientador laboral. Compara el CV con las habilidades que pide el perfil del cargo "{perfil['cargo']}".

REGLAS:
- Usa SOLO habilidades o conocimientos que aparezcan nombrados en el texto del perfil. No inventes otros.
- Una habilidad está "presente" si el CV la menciona, la demuestra, o muestra formación, cursos o proyectos
  relacionados con ella (aunque sea de nivel inicial). Solo es "faltante" si no hay ninguna señal en el CV.
- Devuelve como máximo {MAX_FALTANTES} faltantes, los más importantes primero. Cada una con un nombre corto (2 a 6 palabras).
- "prioridad": "esencial" si el perfil la lista como esencial, "complementaria" si es opcional.
- "evidencia": máximo 8 palabras tomadas del CV. No copies datos personales.
- Responde SOLO con JSON con esta forma:
{{"presentes": [{{"habilidad": "...", "evidencia": "..."}}], "faltantes": [{{"habilidad": "...", "prioridad": "esencial"}}]}}

PERFIL:
{requisitos}

CV:
{cv_texto[:6000]}
"""
    datos = _llm_json(prompt)
    datos["presentes"] = datos.get("presentes", [])
    datos["faltantes"] = datos.get("faltantes", [])[:MAX_FALTANTES]
    return datos


# recomendaciones
@lru_cache(maxsize=8)
def _embedding_consulta(consulta: str) -> np.ndarray:
    """Embedding de una consulta fija, calculado una sola vez por sesión del servidor."""
    return m.embedding(consulta)


def _mejores_docs(consulta: str, tipos, k: int) -> list:
    q = _embedding_consulta(consulta)
    puntajes = []
    for d in cargar_docs().values():
        if d["tipo"] in tipos:
            puntajes.append((float((d["matriz"] @ q).max()), d))
    puntajes.sort(key=lambda x: x[0], reverse=True)
    return [{"titulo": d["titulo"], "fuente": d["fuente"], "link": d["link"],
             "archivo": d["archivo"], "similitud": s} for s, d in puntajes[:k]]


def _cursos_de_la_base(habilidades: list, cargo: str) -> dict:
    """Respaldo: Gemini elige, solo entre los cursos de la base, los que enseñan cada habilidad."""
    if not habilidades:
        return {}
    catalogo = {d["archivo"]: d for d in cargar_docs().values() if d["tipo"] == "formacion"}
    lineas = []
    for archivo, d in catalogo.items():
        resumen = re.sub(r"\s+", " ", d["intro"])[:250]
        lineas.append(f"- id: {archivo} | {d['titulo']} | {resumen}")
    prompt = f"""Eres un orientador laboral. Para cada habilidad de la lista, elige entre los cursos del CATALOGO
(máximo {CURSOS_POR_HABILIDAD}) los que la enseñan directamente. El contexto es el cargo "{cargo}".

REGLAS:
- Usa SOLO ids que aparezcan en el catálogo.
- Si ningún curso cubre claramente la habilidad, devuelve una lista vacía. No fuerces coincidencias por palabras parecidas.
- Responde SOLO con JSON con esta forma: {{"<habilidad>": ["id1", "id2"], ...}}

HABILIDADES:
{json.dumps(habilidades, ensure_ascii=False)}

CATALOGO:
""" + "\n".join(lineas)
    datos = _llm_json(prompt)
    por_clave = {_norm(k).strip(): v for k, v in datos.items()} if isinstance(datos, dict) else {}
    salida = {}
    for hab in habilidades:
        ids = por_clave.get(_norm(hab).strip(), [])
        salida[hab] = [{"titulo": catalogo[i]["titulo"], "fuente": catalogo[i]["fuente"],
                        "link": catalogo[i]["link"], "archivo": i}
                       for i in ids if i in catalogo][:CURSOS_POR_HABILIDAD]
    return salida


def cursos_para_habilidades(habilidades: list, cargo: str) -> dict:
    """Cursos por habilidad faltante: primero Coursera y, si falla, la base de documentos."""
    if not habilidades:
        return {}
    salida = {h: [] for h in habilidades}
    if sc is not None:
        try:
            salida.update(sc.cursos_coursera_para(habilidades, CURSOS_POR_HABILIDAD))
        except Exception as e:
            print(f"  Coursera falló, uso la base: {str(e)[:100]}")
    faltan = [h for h in habilidades if not salida.get(h)]
    if faltan:
        base = _cursos_de_la_base(faltan, cargo)
        for h in faltan:
            salida[h] = base.get(h, [])
    return salida


def cursos_del_cargo(perfil: dict) -> list:
    """Cursos para el cargo: primero Coursera y, si no hay, los que sugiere el perfil."""
    if sc is not None:
        try:
            cursos = sc.buscar_cursos_coursera(perfil["cargo"], 4)
            if cursos:
                return cursos
        except Exception as e:
            print(f"  Coursera falló, uso la base: {str(e)[:100]}")
    return cursos_del_perfil(perfil)


def empleos_para_sugerencias(sugerencias: list) -> list:
    """Ofertas de LinkedIn y Computrabajo para cada cargo sugerido; nunca lanza error."""
    nombres = [nombre_cargo(s) for s in sugerencias]
    if sc is None:
        return []
    try:
        return sc.empleos_para_cargos(nombres)
    except Exception as e:
        print(f"  Empleos: falló el scraping: {str(e)[:100]}")
        return []


def guias_para_cv(k: int = 3) -> list:
    return _mejores_docs("cómo elaborar y mejorar mi hoja de vida y prepararme para una entrevista de trabajo",
                         ("guia_cv", "entrevista"), k)


# flujo completo
def nombre_cargo(perfil_archivo: str) -> str:
    """Nombre legible del cargo (sale del título del perfil)."""
    try:
        return leer_perfil(perfil_archivo)["cargo"]
    except Exception:
        return perfil_archivo.replace("perfil_", "").replace("_", " ").capitalize()



def sugerir_cargos_generales(texto: str) -> dict:
    """Genera cargos alternativos con Gemini a partir del CV cuando la base no tiene un perfil cercano."""
    prompt = f"""Actúa como orientador laboral para el mercado de trabajo de Colombia.
Analiza la hoja de vida y propone hasta 5 cargos realistas incluso si la profesión no existe
en un catálogo predefinido.

REGLAS IMPORTANTES:
- Basa cada sugerencia en la formación, experiencia, funciones o competencias que aparezcan en el CV.
- No inventes títulos, licencias, matrículas profesionales, experiencia ni certificaciones.
- Distingue entre cargos directamente relacionados con la profesión y opciones adyacentes
  que aprovechen habilidades transferibles.
- Si el CV tiene poca experiencia, considera cargos junior, auxiliares, asistentes o de entrada.
- No propongas cargos que requieran una licencia profesional que el CV no demuestra.
- Evita repetir el mismo cargo con nombres diferentes.
- Incluye de 3 a 5 habilidades demostradas en el CV y de 2 a 4 habilidades concretas por fortalecer
  para cada cargo.
- El motivo debe explicar brevemente qué elemento del CV respalda la recomendación.
- No inventes ofertas laborales ni cursos. Solo recomienda nombres de cargos.
- Responde SOLO JSON válido, sin Markdown, con esta estructura:
{{
  "profesion_identificada": "profesión o área más probable",
  "resumen": "resumen profesional de máximo 45 palabras, sin datos personales",
  "fortalezas": ["fortaleza 1", "fortaleza 2"],
  "recomendaciones": [
    {{
      "cargo": "nombre del cargo",
      "afinidad": "directa|relacionada|alternativa",
      "motivo": "justificación breve basada en el CV",
      "habilidades_relevantes": ["habilidad demostrada 1", "habilidad demostrada 2"],
      "habilidades_a_desarrollar": ["habilidad 1", "habilidad 2"]
    }}
  ]
}}

HOJA DE VIDA:
{texto[:7000]}
"""
    datos = _llm_json(prompt)
    if not isinstance(datos, dict):
        raise RuntimeError("Gemini devolvió una respuesta de recomendaciones con formato no válido.")

    def _lista_texto(valor, max_items, max_chars=100):
        if isinstance(valor, str):
            valor = [valor]
        if not isinstance(valor, list):
            return []
        return [str(x).strip()[:max_chars] for x in valor if str(x).strip()][:max_items]

    recomendaciones = datos.get("recomendaciones", [])
    if not isinstance(recomendaciones, list):
        recomendaciones = []
    limpias = []
    vistos = set()
    for item in recomendaciones:
        if not isinstance(item, dict):
            continue
        cargo = re.sub(r"\s+", " ", str(item.get("cargo", ""))).strip()
        clave = _norm(cargo)
        if not cargo or clave in vistos:
            continue
        vistos.add(clave)
        afinidad = str(item.get("afinidad", "relacionada")).lower()
        if afinidad not in {"directa", "relacionada", "alternativa"}:
            afinidad = "relacionada"
        limpias.append({
            "cargo": cargo[:90],
            "afinidad": afinidad,
            "motivo": str(item.get("motivo", "Relacionado con la formación o experiencia descrita en tu CV."))[:350],
            "habilidades_relevantes": _lista_texto(item.get("habilidades_relevantes", []), 5, 80),
            "habilidades_a_desarrollar": _lista_texto(item.get("habilidades_a_desarrollar", []), 4, 80),
        })
        if len(limpias) == 5:
            break
    if not limpias:
        raise RuntimeError("Gemini no generó cargos profesionales utilizables para este CV.")
    return {
        "profesion_identificada": str(datos.get("profesion_identificada", "Perfil profesional por determinar"))[:120],
        "resumen": str(datos.get("resumen", ""))[:500],
        "fortalezas": _lista_texto(datos.get("fortalezas", []), 6, 100),
        "recomendaciones": limpias,
    }


def sugerir_cargos(texto: str) -> dict:
    """Busca cargos en perfiles locales y, si no hay buena coincidencia, los genera con Gemini."""
    from cargar_modelo_onnx import clasificar

    cats = clasificar(texto, k=3)
    tabla = json.loads(m.ARCHIVO_TABLA.read_text(encoding="utf-8"))
    sims = m.similitudes_por_cargo(texto)
    mejor = max(sims.values()) if sims else 0.0
    margen = (cats[0]["probabilidad"] - cats[1]["probabilidad"]) if len(cats) > 1 else 0.0
    categoria = cats[0]["categoria"] if cats else ""
    cobertura = tabla.get(categoria, {}).get("cobertura", "")
    con_perfil = mejor >= UMBRAL_SIMILITUD

    if con_perfil:
        sugerencias = [r["cargo"] for r in m.ordenar(sims, {}, k=5)]
        return {
            "tipo": "con_perfil",
            "clasificador": cats,
            "sugerencias": sugerencias,
            "guias": [],
            "similitud_max": mejor,
            "margen": margen,
            "area_clara": margen >= MARGEN_AREA_CLARA and cobertura == "ninguna",
        }

    # Si no existe coincidencia suficiente, no se detiene el flujo: se generan cargos desde el CV.
    try:
        general = sugerir_cargos_generales(texto)
        return {
            "tipo": "general",
            "clasificador": cats,
            "sugerencias": [r["cargo"] for r in general["recomendaciones"]],
            "recomendaciones_generales": general["recomendaciones"],
            "profesion_identificada": general["profesion_identificada"],
            "resumen": general["resumen"],
            "fortalezas": general["fortalezas"],
            "guias": guias_para_cv(),
            "similitud_max": mejor,
            "margen": margen,
            "area_clara": margen >= MARGEN_AREA_CLARA and cobertura == "ninguna",
        }
    except Exception as e:
        print(f"  No se pudieron generar cargos generales: {str(e)[:180]}")
        return {
            "tipo": "sin_perfil",
            "clasificador": cats,
            "sugerencias": [],
            "guias": guias_para_cv(),
            "similitud_max": mejor,
            "margen": margen,
            "area_clara": margen >= MARGEN_AREA_CLARA and cobertura == "ninguna",
        }


def empleos_para_cargos_libres(cargos: list) -> list:
    """Busca ofertas para nombres de cargos generados por Gemini, sin exigir un perfil local."""
    if not cargos or sc is None:
        return []
    try:
        # Dos resultados por fuente y cargo: limita peticiones cuando hay varias recomendaciones.
        return sc.empleos_para_cargos(cargos[:5], por_fuente=2)
    except Exception as e:
        print(f"  Empleos para cargos generales: {str(e)[:150]}")
        return []


def plan_para_cargo_general(texto: str, recomendacion: dict) -> dict:
    """Construye una ruta de formación para un cargo sugerido por Gemini."""
    cargo = recomendacion["cargo"]
    faltantes = [
        {"habilidad": h, "prioridad": "complementaria"}
        for h in recomendacion.get("habilidades_a_desarrollar", [])[:4]
    ]
    presentes = [
        {"habilidad": h, "evidencia": "Identificada en la hoja de vida"}
        for h in recomendacion.get("habilidades_relevantes", [])[:5]
    ]

    cursos_cargo = []
    if sc is not None:
        try:
            cursos_cargo = sc.buscar_cursos_coursera(cargo, 4)
        except Exception as e:
            print(f"  Coursera para {cargo}: {str(e)[:120]}")

    recomendaciones = {f["habilidad"]: [] for f in faltantes}
    if faltantes:
        try:
            recomendaciones = cursos_para_habilidades(
                [f["habilidad"] for f in faltantes], cargo
            )
        except Exception as e:
            print(f"  Cursos por habilidad para {cargo}: {str(e)[:120]}")

    # Si la búsqueda por el cargo no trajo cursos, reunir cursos asociados a las habilidades.
    if not cursos_cargo:
        vistos = set()
        for lista in recomendaciones.values():
            for curso in lista:
                clave = curso.get("link") or curso.get("archivo") or curso.get("titulo")
                if clave not in vistos:
                    vistos.add(clave)
                    cursos_cargo.append(curso)
                if len(cursos_cargo) >= 4:
                    break
            if len(cursos_cargo) >= 4:
                break

    try:
        guias = guias_para_cv()
    except Exception as e:
        print(f"  Guías no disponibles: {str(e)[:120]}")
        guias = []

    return {
        "tipo": "general",
        "cargo_analizado": cargo,
        "cargo": cargo,
        "motivo": recomendacion.get("motivo", ""),
        "afinidad": recomendacion.get("afinidad", "relacionada"),
        "analisis": {"presentes": presentes, "faltantes": faltantes},
        "recomendaciones": recomendaciones,
        "cursos_del_perfil": cursos_cargo,
        "guias": guias,
    }

def plan_para_cargo(texto: str, perfil_nombre: str) -> dict:
    """Paso 2: para el cargo elegido, cursos del perfil, temas a profundizar y guías."""
    perfil = leer_perfil(perfil_nombre)
    analisis = analizar_habilidades(texto, perfil)
    recomendaciones = cursos_para_habilidades([f["habilidad"] for f in analisis["faltantes"]], perfil["cargo"])
    return {"cargo_analizado": perfil_nombre, "cargo": perfil["cargo"], "analisis": analisis,
            "recomendaciones": recomendaciones, "cursos_del_perfil": cursos_del_cargo(perfil),
            "guias": guias_para_cv()}


def analizar_cv(texto: str, perfil_forzado: str = None) -> dict:
    """Los dos pasos juntos (para la terminal)."""
    s = sugerir_cargos(texto)
    if s["tipo"] in {"sin_perfil", "general"} and perfil_forzado is None:
        return s
    elegido = perfil_forzado or s["sugerencias"][0]
    return {**plan_para_cargo(texto, elegido), "tipo": "con_perfil",
            "clasificador": s["clasificador"], "sugerencias": s["sugerencias"]}


def _fuente_corta(f: str) -> str:
    f = re.sub(r"\s*\(consultado[^)]*\)", "", f)
    return f.split(",")[0].strip()


def fuente_visible(d: dict) -> str:
    """La fuente, salvo que el título ya la nombre (ej. 'Curso SENA: ...' + 'SENA')."""
    f = _fuente_corta(d.get("fuente", ""))
    primera = _norm(f).split()[:1]
    if not f or (primera and primera[0] in _norm(d["titulo"])):
        return ""
    return f


def organizar_plan(plan: dict) -> dict:
    """Evita repetir cursos: separa los del perfil y deja como adicionales solo los de temas no cubiertos."""
    del_perfil = {d["archivo"]: {"doc": d, "cubre": []} for d in plan["cursos_del_perfil"]}
    adicionales = []
    for f in plan["analisis"]["faltantes"]:
        hab = f["habilidad"]
        nuevos = []
        for d in plan["recomendaciones"].get(hab, []):
            if d["archivo"] in del_perfil:
                del_perfil[d["archivo"]]["cubre"].append(hab)
            else:
                nuevos.append(d)
        if nuevos:
            adicionales.append({"habilidad": hab, "cursos": nuevos})
    return {"del_perfil": list(del_perfil.values()), "adicionales": adicionales}


def _imprimir_docs(docs, sangria="    "):
    for d in docs:
        sim = f"  [similitud {d['similitud']:.3f}]" if "similitud" in d else ""
        fuente = f" ({fuente_visible(d)})" if fuente_visible(d) else ""
        print(f"{sangria}- {d['titulo']}{fuente}{sim}")
        if d["link"]:
            print(f"{sangria}  {d['link']}")


def imprimir_resultado(r: dict):
    print("Clasificador: " + ", ".join(f"{c['categoria']} {c['probabilidad']*100:.0f}%" for c in r["clasificador"]))
    if r["tipo"] == "sin_perfil":
        print("\nNo encontramos cargos para este CV. Guías útiles para cualquier profesión:")
        _imprimir_docs(r.get("guias", []), "  ")
        return
    if r["tipo"] == "general":
        print(f"\nÁrea identificada: {r.get('profesion_identificada', 'Por determinar')}")
        print(r.get("resumen", ""))
        print("\nCargos recomendados:")
        for rec in r.get("recomendaciones_generales", []):
            print(f"  - {rec['cargo']} [{rec.get('afinidad', 'relacionada')}]")
            print(f"    {rec.get('motivo', '')}")
        _imprimir_docs(r.get("guias", []), "  ")
        return

    print("\nCargos posibles: " + ", ".join(r["sugerencias"]))
    print(f"\nAnálisis para: {r['cargo_analizado']}")

    org = organizar_plan(r)
    if org["del_perfil"]:
        print("\nCursos que el propio perfil sugiere para este cargo:")
        for it in org["del_perfil"]:
            _imprimir_docs([it["doc"]], "  ")
            if it["cubre"]:
                print(f"    Te ayuda con: {', '.join(it['cubre'])}")
    if org["adicionales"]:
        print("\nPara profundizar (temas del perfil que tu CV no muestra con claridad):")
        for a in org["adicionales"]:
            print(f"  - {a['habilidad']}")
            _imprimir_docs(a["cursos"])
    elif r["analisis"]["faltantes"] and not any(it["cubre"] for it in org["del_perfil"]):
        print("\nNo encontramos en la base cursos claramente relacionados con las habilidades que faltan.")
    sin_curso = [f for f in r["analisis"]["faltantes"] if not r["recomendaciones"].get(f["habilidad"])]
    if MOSTRAR_SIN_CURSO and sin_curso:
        print("\nOtros temas del perfil que el CV no muestra (sin curso en la base):")
        for f in sin_curso:
            print(f"  - {f['habilidad']} [{f.get('prioridad', '')}]")

    print("\nGuías de hoja de vida y entrevista:")
    _imprimir_docs(r["guias"], "  ")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Uso: python habilidades_y_cursos.py ruta\\al\\cv.(pdf|docx|txt) [perfil_xxx]")
    ruta = Path(sys.argv[1])
    texto = extraer_texto_bytes(ruta.name, ruta.read_bytes())
    imprimir_resultado(analizar_cv(texto, sys.argv[2] if len(sys.argv) > 2 else None))
