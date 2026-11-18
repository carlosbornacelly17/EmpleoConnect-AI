"""Prueba offline de la ruta de recomendaciones generales (python prueba_ruta_general_offline.py)."""
import sys
import types

import habilidades_y_cursos as hc


def _clasificador_falso(texto, k=3):
    return [
        {"categoria": "HEALTHCARE", "probabilidad": 0.80},
        {"categoria": "HR", "probabilidad": 0.12},
        {"categoria": "TEACHER", "probabilidad": 0.08},
    ]


sys.modules["cargar_modelo_onnx"] = types.SimpleNamespace(clasificar=_clasificador_falso)
hc.m.similitudes_por_cargo = lambda texto: {}  # Fuerza el camino sin perfil local.

hc._llm_json = lambda prompt: {
    "profesion_identificada": "Psicología",
    "resumen": "Perfil con formación en psicología y experiencia de acompañamiento.",
    "fortalezas": ["Escucha activa", "Entrevistas", "Orientación"],
    "recomendaciones": [
        {
            "cargo": "Psicóloga organizacional",
            "afinidad": "directa",
            "motivo": "La formación y la experiencia de acompañamiento son transferibles.",
            "habilidades_relevantes": ["Entrevistas", "Comunicación"],
            "habilidades_a_desarrollar": ["Selección por competencias", "Legislación laboral"],
        },
        {
            "cargo": "Analista de selección",
            "afinidad": "relacionada",
            "motivo": "Puede aplicar habilidades de entrevista y evaluación.",
            "habilidades_relevantes": ["Entrevistas", "Evaluación"],
            "habilidades_a_desarrollar": ["Reclutamiento digital"],
        },
    ],
}
hc.guias_para_cv = lambda k=3: []
hc.sc = None

resultado = hc.sugerir_cargos(
    "Hoja de vida de prueba con formación en Psicología y experiencia en orientación."
)
assert resultado["tipo"] == "general"
assert resultado["profesion_identificada"] == "Psicología"
assert len(resultado["recomendaciones_generales"]) == 2

plan = hc.plan_para_cargo_general(
    "Hoja de vida de prueba",
    resultado["recomendaciones_generales"][0],
)
assert plan["cargo"] == "Psicóloga organizacional"
assert len(plan["analisis"]["faltantes"]) == 2
assert plan["cursos_del_perfil"] == []

print("OK  Profesión fuera del catálogo: genera recomendaciones")
print("OK  Cargos con afinidad, justificación y competencias")
print("OK  Ruta de formación disponible aunque no haya conexión de scraping")
print("Todas las pruebas de la ruta general pasaron.")
