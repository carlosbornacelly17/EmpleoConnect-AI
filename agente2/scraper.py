"""Agente 2: datos web (cursos de Coursera, empleos de LinkedIn y Computrabajo); nunca lanza excepciones y sus selectores HTML son frágiles."""
import logging
import os
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

log = logging.getLogger("scraper")

SCRAPING_ACTIVO = os.getenv("SCRAPING_ACTIVO", "1") != "0"
TIMEOUT = 8                    # segundos por petición
CACHE_OK = 60 * 60             # una búsqueda con resultados se recuerda 1 hora
CACHE_VACIA = 2 * 60           # una búsqueda sin resultados se recuerda 2 minutos (para no insistir)
MAX_HILOS = 6

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
}

_cache = {}


# utilidades
def _get(url, params=None):
    r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r


def _con_cache(clave, funcion):
    """Ejecuta funcion() y recuerda el resultado. Si falla o no hay resultados, devuelve []."""
    ahora = time.time()
    hit = _cache.get(clave)
    if hit and hit[0] > ahora:
        return hit[1]
    try:
        resultado = funcion() or []
    except Exception as e:                      # red caída, 403/429, HTML distinto, JSON raro...
        log.warning("scraper %s falló: %s", clave[0], str(e)[:150])
        resultado = []
    _cache[clave] = (ahora + (CACHE_OK if resultado else CACHE_VACIA), resultado)
    return resultado


def _slug(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def _termino_busqueda(cargo: str) -> str:
    """'Analista de datos (2024)' -> 'Analista de datos'."""
    return re.sub(r"\s*\(.*?\)\s*", " ", cargo).strip()


def _texto(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)) if el else ""


# Coursera (cursos)
def _coursera_api(consulta: str, limite: int) -> list:
    r = _get("https://api.coursera.org/api/courses.v1",
             params={"q": "search", "query": consulta, "limit": limite, "fields": "name,slug"})
    cursos = []
    for e in r.json().get("elements", []):
        if e.get("name") and e.get("slug"):
            cursos.append({"titulo": e["name"], "fuente": "Coursera", "archivo": f"coursera:{e['slug']}",
                           "link": f"https://www.coursera.org/learn/{e['slug']}"})
    return cursos[:limite]


def _parsear_coursera_html(html: str | bytes, limite: int) -> list:
    soup = BeautifulSoup(html, "html.parser")
    vistos, cursos = set(), []
    for a in soup.select("a[href^='/learn/']"):
        slug = a["href"].split("?")[0].strip("/").split("/")[1] if a["href"].count("/") >= 2 else ""
        if not slug or slug in vistos:
            continue
        titulo = _texto(a)
        if len(titulo) < 8:                     # enlace sin texto útil: se arma el título desde el slug
            titulo = slug.replace("-", " ").capitalize()
        vistos.add(slug)
        cursos.append({"titulo": titulo, "fuente": "Coursera", "archivo": f"coursera:{slug}",
                       "link": f"https://www.coursera.org/learn/{slug}"})
    return cursos[:limite]


def _coursera_html(consulta: str, limite: int) -> list:
    r = _get("https://www.coursera.org/search", params={"query": consulta})
    return _parsear_coursera_html(r.content, limite)


def buscar_cursos_coursera(consulta: str, limite: int = 3) -> list:
    """Cursos de Coursera para una consulta. Primero la API pública; si no responde, la página de búsqueda."""
    if not SCRAPING_ACTIVO or not consulta.strip():
        return []

    def _buscar():
        try:
            cursos = _coursera_api(consulta, limite)
            if cursos:
                return cursos
        except Exception as e:
            log.info("Coursera API sin resultados (%s); pruebo la página de búsqueda", str(e)[:100])
        return _coursera_html(consulta, limite)

    return _con_cache(("coursera", consulta.lower(), limite), _buscar)


def cursos_coursera_para(habilidades: list, por_habilidad: int = 2) -> dict:
    """{habilidad: [cursos]} consultando Coursera en paralelo (una petición por habilidad)."""
    if not habilidades:
        return {}
    with ThreadPoolExecutor(max_workers=MAX_HILOS) as ex:
        resultados = list(ex.map(lambda h: buscar_cursos_coursera(h, por_habilidad), habilidades))
    return dict(zip(habilidades, resultados))


# Computrabajo (empleos)
def _parsear_computrabajo(html: str, limite: int) -> list:
    soup = BeautifulSoup(html, "html.parser")
    ofertas = []
    for art in soup.select("article.box_offer, article[class*='box_offer']"):
        a = art.select_one("h2 a, a.js-o-link")
        if not a or not a.get("href"):
            continue
        empresa = _texto(art.select_one("a[href*='/empresas/'], a.fc_base.t_ellipsis, p.dIB.fs16 a"))
        ubicacion = _texto(art.select_one("p.fs16.fc_base.mt5 span.mr10, span.mr10"))
        ofertas.append({"titulo": _texto(a), "empresa": empresa, "ubicacion": ubicacion,
                        "fuente": "Computrabajo",
                        "link": urljoin("https://co.computrabajo.com", a["href"]).split("#")[0]})
        if len(ofertas) >= limite:
            break
    return [o for o in ofertas if o["titulo"]]


def _computrabajo(cargo: str, limite: int) -> list:
    termino = _termino_busqueda(cargo)
    try:                                         # ruta "bonita": /trabajo-de-<cargo>
        r = _get(f"https://co.computrabajo.com/trabajo-de-{_slug(termino)}")
        ofertas = _parsear_computrabajo(r.text, limite)
        if ofertas:
            return ofertas
    except Exception as e:
        log.info("Computrabajo (ruta por cargo) falló: %s", str(e)[:100])
    r = _get("https://co.computrabajo.com/empleos", params={"q": termino})   # ruta alterna con ?q=
    return _parsear_computrabajo(r.text, limite)


def buscar_empleos_computrabajo(cargo: str, limite: int = 4) -> list:
    if not SCRAPING_ACTIVO or not cargo.strip():
        return []
    return _con_cache(("computrabajo", cargo.lower(), limite), lambda: _computrabajo(cargo, limite))


# LinkedIn (empleos, búsqueda pública)
def _parsear_linkedin(html: str, limite: int) -> list:
    soup = BeautifulSoup(html, "html.parser")
    ofertas = []
    for card in soup.select("div.base-card, li"):
        a = card.select_one("a.base-card__full-link, a[href*='/jobs/view/']")
        titulo = _texto(card.select_one(".base-search-card__title, h3"))
        if not a or not titulo or not a.get("href"):
            continue
        ofertas.append({"titulo": titulo,
                        "empresa": _texto(card.select_one(".base-search-card__subtitle, h4")),
                        "ubicacion": _texto(card.select_one(".job-search-card__location")),
                        "fuente": "LinkedIn",
                        "link": a["href"].split("?")[0]})
    unicas, vistos = [], set()                   # <li> y <div> anidados pueden duplicar la misma oferta
    for o in ofertas:
        if o["link"] not in vistos:
            vistos.add(o["link"])
            unicas.append(o)
    return unicas[:limite]


def _linkedin(cargo: str, limite: int) -> list:
    r = _get("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search",
             params={"keywords": _termino_busqueda(cargo), "location": "Colombia", "start": 0})
    return _parsear_linkedin(r.text, limite)     # LinkedIn suele responder 429/999 si detecta bots: queda en []


def buscar_empleos_linkedin(cargo: str, limite: int = 4) -> list:
    if not SCRAPING_ACTIVO or not cargo.strip():
        return []
    return _con_cache(("linkedin", cargo.lower(), limite), lambda: _linkedin(cargo, limite))


# enlaces de "ver más" (no hacen scraping)
def enlaces_busqueda(cargo: str) -> dict:
    termino = _termino_busqueda(cargo)
    return {"linkedin": f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(termino)}&location=Colombia",
            "computrabajo": f"https://co.computrabajo.com/trabajo-de-{quote(_slug(termino))}"}


# todo junto: empleos para varios cargos
def empleos_para_cargos(cargos: list, por_fuente: int = 3) -> list:
    """Ofertas de LinkedIn y Computrabajo por cargo, en paralelo; si LinkedIn falla se muestran más de Computrabajo."""
    if not cargos:
        return []
    tareas = [(c, f) for c in cargos for f in ("linkedin", "computrabajo")]

    def _una(t):
        cargo, fuente = t
        if fuente == "linkedin":
            return buscar_empleos_linkedin(cargo, por_fuente)
        return buscar_empleos_computrabajo(cargo, por_fuente * 2)

    with ThreadPoolExecutor(max_workers=MAX_HILOS) as ex:
        res = dict(zip(tareas, ex.map(_una, tareas)))

    salida = []
    for c in cargos:
        li, ct = res[(c, "linkedin")], res[(c, "computrabajo")]
        ofertas = li[:por_fuente] + ct[:por_fuente if li else por_fuente * 2]
        salida.append({"cargo": c, "ofertas": ofertas, "enlaces": enlaces_busqueda(c)})
    return salida


if __name__ == "__main__":
    # Prueba rápida desde la terminal:  python scraper.py "analista de datos"
    import sys
    logging.basicConfig(level=logging.INFO)
    consulta = " ".join(sys.argv[1:]) or "analista de datos"
    print("== Coursera ==")
    for c in buscar_cursos_coursera(consulta, 5):
        print(" -", c["titulo"], c["link"])
    print("== Computrabajo ==")
    for o in buscar_empleos_computrabajo(consulta, 5):
        print(" -", o["titulo"], "|", o["empresa"], "|", o["ubicacion"], o["link"])
    print("== LinkedIn ==")
    for o in buscar_empleos_linkedin(consulta, 5):
        print(" -", o["titulo"], "|", o["empresa"], "|", o["ubicacion"], o["link"])
