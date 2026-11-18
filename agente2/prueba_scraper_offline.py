"""Pruebas sin internet del scraper y su respaldo (python prueba_scraper_offline.py)."""
import types

import scraper as sc

HTML_CT = """<div><article class="box_offer"><h2><a class="js-o-link" href="/ofertas-de-trabajo/oferta-de-trabajo-de-analista-ABC123#lc=ListOffers">Analista de datos</a></h2>
<p class="dIB fs16 fc_base mt5"><a class="fc_base t_ellipsis" href="/empresas/acme-1">ACME S.A.S</a></p>
<p class="fs16 fc_base mt5"><span class="mr10">Barranquilla, Atlántico</span></p></article>
<article class="box_offer"><h2><a href="/ofertas-de-trabajo/oferta-2">Analista BI [Senior]</a></h2></article></div>"""

HTML_LI = """<ul><li><div class="base-card"><a class="base-card__full-link" href="https://co.linkedin.com/jobs/view/analista-123?trk=x"></a>
<h3 class="base-search-card__title">Data Analyst</h3><h4 class="base-search-card__subtitle">Empresa X</h4>
<span class="job-search-card__location">Bogotá, Colombia</span></div></li></ul>"""

HTML_COURSERA = """<a href="/learn/sql-for-data-science?query=sql">SQL for Data Science</a><a href="/learn/python"></a>
<a href="/learn/sql-for-data-science">duplicado</a>"""


def ok(cond, msg):
    print(("OK   " if cond else "FALLA"), msg)
    assert cond, msg


# --- parseadores
ct = sc._parsear_computrabajo(HTML_CT, 5)
ok(len(ct) == 2 and ct[0]["empresa"] == "ACME S.A.S" and "Barranquilla" in ct[0]["ubicacion"], "Computrabajo: parsea título, empresa y ubicación")
ok(ct[0]["link"].startswith("https://co.computrabajo.com/") and "#" not in ct[0]["link"], "Computrabajo: enlace absoluto y limpio")
li = sc._parsear_linkedin(HTML_LI, 5)
ok(len(li) == 1 and li[0]["link"] == "https://co.linkedin.com/jobs/view/analista-123", "LinkedIn: parsea y quita parámetros del enlace")
cr = sc._parsear_coursera_html(HTML_COURSERA, 5)
ok([c["archivo"] for c in cr] == ["coursera:sql-for-data-science", "coursera:python"], "Coursera HTML: sin duplicados y título desde el slug si falta")

# --- fallos: nunca deben lanzar excepción
def falla(*a, **k):
    raise RuntimeError("sin internet")

sc._get = falla
sc._cache.clear()
ok(sc.buscar_cursos_coursera("sql") == [], "Coursera caído -> []")
ok(sc.buscar_empleos_computrabajo("analista") == [], "Computrabajo caído -> []")
ok(sc.buscar_empleos_linkedin("analista") == [], "LinkedIn caído -> []")
r = sc.empleos_para_cargos(["Analista de datos (2024)"])
ok(r[0]["ofertas"] == [] and "linkedin.com" in r[0]["enlaces"]["linkedin"], "Todo caído -> sin ofertas pero con enlaces de búsqueda")

# --- LinkedIn falla, Computrabajo responde: se muestran más ofertas de Computrabajo
def solo_ct(url, params=None):
    if "computrabajo" in url:
        return types.SimpleNamespace(text=HTML_CT)
    raise RuntimeError("429")

sc._get = solo_ct
sc._cache.clear()
r = sc.empleos_para_cargos(["Analista de datos"])
ok(len(r[0]["ofertas"]) == 2 and all(o["fuente"] == "Computrabajo" for o in r[0]["ofertas"]), "LinkedIn falla -> Computrabajo cubre")

# --- API de Coursera con respuesta JSON
sc._cache.clear()
sc._get = lambda url, params=None: types.SimpleNamespace(json=lambda: {"elements": [{"name": "Python Basics", "slug": "python-basics"}]})
c = sc.buscar_cursos_coursera("python", 3)
ok(c and c[0]["link"] == "https://www.coursera.org/learn/python-basics" and c[0]["fuente"] == "Coursera", "Coursera API: curso con enlace")

# --- interruptor
sc.SCRAPING_ACTIVO = False
ok(sc.buscar_cursos_coursera("python") == [], "SCRAPING_ACTIVO=0 apaga el scraping")
sc.SCRAPING_ACTIVO = True

# --- respaldo hacia la base en habilidades_y_cursos
import habilidades_y_cursos as hc

llamadas = []
hc._cursos_de_la_base = lambda hs, cargo: (llamadas.append(list(hs)) or {h: [{"titulo": "Curso base", "fuente": "SENA", "link": "", "archivo": "sena_x"}] for h in hs})
hc.sc = types.SimpleNamespace(cursos_coursera_para=lambda hs, n: {"SQL": [{"titulo": "SQL Coursera", "fuente": "Coursera", "link": "u", "archivo": "coursera:sql"}], "PLC": []})
r = hc.cursos_para_habilidades(["SQL", "PLC"], "cargo")
ok(r["SQL"][0]["fuente"] == "Coursera" and r["PLC"][0]["fuente"] == "SENA" and llamadas == [["PLC"]], "Habilidad sin Coursera -> solo esa va a la base")

hc.sc = types.SimpleNamespace(cursos_coursera_para=falla)
llamadas.clear()
r = hc.cursos_para_habilidades(["SQL", "PLC"], "cargo")
ok(all(v[0]["fuente"] == "SENA" for v in r.values()) and llamadas == [["SQL", "PLC"]], "Coursera lanza error -> todo cae a la base")

hc.cursos_del_perfil = lambda perfil: ["BASE"]
hc.sc = types.SimpleNamespace(buscar_cursos_coursera=lambda c, n: [])
ok(hc.cursos_del_cargo({"cargo": "X"}) == ["BASE"], "Cursos del cargo: Coursera vacío -> base")
hc.sc = None
ok(hc.cursos_del_cargo({"cargo": "X"}) == ["BASE"], "Cursos del cargo: sin módulo scraper -> base")
ok(hc.empleos_para_sugerencias([]) == [], "Empleos sin scraper -> []")

print("\nTodas las pruebas offline pasaron.")
