"""Interfaz del Agente 2: perfiles de la base local o recomendaciones generales con Gemini."""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import habilidades_y_cursos as hc  # noqa: E402


@st.cache_data(show_spinner=False)
def _nombre(perfil_archivo: str) -> str:
    return hc.nombre_cargo(perfil_archivo)


def _limpiar_estado():
    for k in ("a2_texto", "a2_sug", "a2_plan", "a2_cargo", "a2_empleos", "a2_plan_tipo"):
        st.session_state.pop(k, None)


def _esc(t: str) -> str:
    return (t or "").replace("[", "(").replace("]", ")")


def _mostrar_etiqueta_afinidad(valor: str) -> str:
    etiquetas = {
        "directa": "Directamente relacionado",
        "relacionada": "Relacionado con tu perfil",
        "alternativa": "Opción alternativa",
    }
    return etiquetas.get(valor, "Relacionado con tu perfil")


def _mostrar_ofertas_cargo(ofertas_por_cargo, cargo):
    registro = next((x for x in (ofertas_por_cargo or []) if x.get("cargo") == cargo), None)
    if not registro:
        st.caption("No hay ofertas descargadas para este cargo en esta consulta.")
        return
    if registro.get("ofertas"):
        for oferta in registro["ofertas"]:
            with st.container(border=True):
                st.markdown(f"**[{_esc(oferta.get('titulo', 'Oferta laboral'))}]({oferta.get('link', '')})**")
                datos = [
                    oferta.get("empresa", ""),
                    oferta.get("ubicacion", ""),
                    oferta.get("fuente", ""),
                ]
                st.caption(" · ".join(x for x in datos if x))
    else:
        st.info("No se pudieron extraer ofertas en esta consulta. Puedes abrir las búsquedas directas:")
    enlaces = registro.get("enlaces", {})
    c1, c2 = st.columns(2)
    if enlaces.get("linkedin"):
        c1.markdown(f"[Buscar en LinkedIn]({enlaces['linkedin']})")
    if enlaces.get("computrabajo"):
        c2.markdown(f"[Buscar en Computrabajo]({enlaces['computrabajo']})")


def _mostrar_resumen(sug, ofertas):
    st.subheader("Resumen de tu perfil")
    if sug.get("profesion_identificada"):
        st.markdown(f"**Área identificada:** {sug['profesion_identificada']}")
    if sug.get("resumen"):
        st.write(sug["resumen"])

    fortalezas = sug.get("fortalezas", [])
    if fortalezas:
        st.markdown("**Fortalezas identificadas**")
        st.write(" · ".join(fortalezas))

    total_ofertas = sum(len(x.get("ofertas", [])) for x in (ofertas or []))
    c1, c2, c3 = st.columns(3)
    c1.metric("Cargos sugeridos", len(sug.get("sugerencias", [])))
    c2.metric("Ofertas encontradas", total_ofertas)
    if fortalezas:
        c3.metric("Fortalezas", len(fortalezas))
    else:
        c3.metric("Perfiles locales", "Coincidencia")


def _mostrar_recomendaciones_generales(sug, ofertas):
    st.subheader("Cargos que podrían encajar contigo")
    st.caption(
        "Estas alternativas se generan a partir de tu formación, experiencia y habilidades. "
        "La afinidad es orientativa: revisa los requisitos de cada vacante."
    )
    recomendaciones = sug.get("recomendaciones_generales", [])
    for indice, rec in enumerate(recomendaciones, start=1):
        cargo = rec["cargo"]
        with st.container(border=True):
            st.markdown(f"### {indice}. {cargo}")
            st.caption(_mostrar_etiqueta_afinidad(rec.get("afinidad", "relacionada")))
            st.write(rec.get("motivo", ""))
            habilidades = rec.get("habilidades_relevantes", [])
            por_desarrollar = rec.get("habilidades_a_desarrollar", [])
            if habilidades:
                st.markdown("**Competencias que ya aparecen en tu CV**")
                st.write(" · ".join(habilidades))
            if por_desarrollar:
                st.markdown("**Competencias que conviene fortalecer**")
                st.write(" · ".join(por_desarrollar))
            with st.expander(f"Consultar ofertas para {cargo}"):
                _mostrar_ofertas_cargo(ofertas, cargo)


def _mostrar_recomendaciones_catalogo(sug, ofertas):
    st.subheader("Cargos que podrían encajar con tu perfil")
    st.caption(
        "El orden se basa en la similitud entre tu hoja de vida y los perfiles ocupacionales de la base."
    )
    for indice, perfil in enumerate(sug.get("sugerencias", []), start=1):
        cargo = _nombre(perfil)
        with st.container(border=True):
            st.markdown(f"### {indice}. {cargo}")
            st.caption("Coincidencia con un perfil ocupacional de la base local")
            with st.expander(f"Consultar ofertas para {cargo}"):
                _mostrar_ofertas_cargo(ofertas, cargo)


def _mostrar_curso(doc):
    with st.container(border=True):
        titulo = _esc(doc.get("titulo", "Curso recomendado"))
        link = doc.get("link", "")
        if link:
            st.markdown(f"**[{titulo}]({link})**")
        else:
            st.markdown(f"**{titulo}**")
        fuente = hc.fuente_visible(doc) if hasattr(hc, "fuente_visible") else doc.get("fuente", "")
        if fuente:
            st.caption(fuente)


def _mostrar_plan(plan):
    st.divider()
    st.subheader(f"Ruta de formación: {plan['cargo']}")
    if plan.get("motivo"):
        st.info(plan["motivo"])

    analisis = plan.get("analisis", {})
    presentes = analisis.get("presentes", [])
    faltantes = analisis.get("faltantes", [])

    tab_resumen, tab_cursos, tab_guias = st.tabs(
        ["Competencias", "Cursos y formación", "Guías para tu CV"]
    )

    with tab_resumen:
        c1, c2 = st.columns(2)
        c1.metric("Competencias identificadas", len(presentes))
        c2.metric("Por fortalecer", len(faltantes))

        if presentes:
            st.markdown("**Lo que ya aportas**")
            for item in presentes:
                with st.container(border=True):
                    st.markdown(f"**{item.get('habilidad', '')}**")
                    if item.get("evidencia"):
                        st.caption(item["evidencia"])
        if faltantes:
            st.markdown("**Competencias para desarrollar**")
            for item in faltantes:
                with st.container(border=True):
                    st.markdown(f"**{item.get('habilidad', '')}**")
                    st.caption(f"Prioridad: {item.get('prioridad', 'complementaria').capitalize()}")
        if not presentes and not faltantes:
            st.info("No se generó un desglose de competencias para este cargo.")

    with tab_cursos:
        organizacion = hc.organizar_plan(plan)
        del_perfil = organizacion.get("del_perfil", [])
        adicionales = organizacion.get("adicionales", [])

        if del_perfil:
            st.markdown("**Cursos relacionados con el cargo**")
            columnas = st.columns(2)
            for i, item in enumerate(del_perfil):
                with columnas[i % 2]:
                    _mostrar_curso(item["doc"])
                    if item.get("cubre"):
                        st.caption("Te ayuda con: " + ", ".join(item["cubre"]))

        if adicionales:
            st.markdown("**Cursos para fortalecer habilidades específicas**")
            for item in adicionales:
                st.markdown(f"**{item['habilidad']}**")
                columnas = st.columns(2)
                for i, curso in enumerate(item.get("cursos", [])):
                    with columnas[i % 2]:
                        _mostrar_curso(curso)

        if not del_perfil and not adicionales:
            st.info(
                "No encontramos cursos suficientemente relacionados en las fuentes consultadas. "
                "Puedes revisar las habilidades por desarrollar y buscar formación adicional."
            )

    with tab_guias:
        guias = plan.get("guias", [])
        if guias:
            st.markdown("Material de apoyo para mejorar tu hoja de vida y prepararte para entrevistas.")
            columnas = st.columns(2)
            for i, guia in enumerate(guias):
                with columnas[i % 2]:
                    _mostrar_curso(guia)
        else:
            st.info("No hay guías adicionales disponibles en este momento.")


def mostrar_agente2():
    st.header("Orientación de carrera y oportunidades")
    st.caption(
        "Analizamos tu hoja de vida para identificar cargos relacionados, oportunidades laborales "
        "y formación que puede ayudarte a avanzar."
    )

    with st.container(border=True):
        acepto = st.checkbox(
            "Entiendo que el texto de mi hoja de vida se envía a la API de Gemini (Google) para analizarlo."
        )
        archivo = st.file_uploader(
            "Sube tu hoja de vida (PDF o Word)",
            type=["pdf", "docx"],
            on_change=_limpiar_estado,
        )
        if st.button(
            "Analizar mi hoja de vida",
            disabled=not (acepto and archivo),
            type="primary",
            use_container_width=True,
        ):
            try:
                with st.spinner("Leyendo tu CV, identificando competencias y buscando cargos..."):
                    texto = hc.extraer_texto_bytes(archivo.name, archivo.getvalue())
                    if len(texto) < 200:
                        st.error(
                            "No pudimos extraer suficiente texto. Comprueba que el PDF tenga texto "
                            "seleccionable y no sea únicamente una imagen escaneada."
                        )
                        return
                    st.session_state["a2_texto"] = texto
                    st.session_state["a2_sug"] = hc.sugerir_cargos(texto)
                    st.session_state.pop("a2_plan", None)
                    st.session_state.pop("a2_cargo", None)
                    sug_nueva = st.session_state["a2_sug"]

                    ofertas = []
                    if sug_nueva["tipo"] == "con_perfil":
                        ofertas = hc.empleos_para_sugerencias(sug_nueva["sugerencias"])
                    elif sug_nueva["tipo"] == "general":
                        ofertas = hc.empleos_para_cargos_libres(sug_nueva["sugerencias"])
                    st.session_state["a2_empleos"] = ofertas
            except Exception as e:
                st.error("No pudimos analizar tu hoja de vida. Comprueba la conexión con Gemini e inténtalo de nuevo.")
                with st.expander("Detalle técnico"):
                    st.code(str(e))
                return

    sug = st.session_state.get("a2_sug")
    if not sug:
        return

    ofertas = st.session_state.get("a2_empleos", [])

    if sug["tipo"] == "sin_perfil":
        st.warning(
            "No encontramos una coincidencia suficientemente clara ni pudimos generar alternativas "
            "automáticas para este CV. Te mostramos recursos generales mientras revisamos el perfil."
        )
        for guia in sug.get("guias", []):
            _mostrar_curso(guia)
        return

    _mostrar_resumen(sug, ofertas)

    if sug["tipo"] == "general":
        _mostrar_recomendaciones_generales(sug, ofertas)
        opciones = [r["cargo"] for r in sug.get("recomendaciones_generales", [])]
        recomendacion_por_cargo = {
            r["cargo"]: r for r in sug.get("recomendaciones_generales", [])
        }
        etiqueta = "Elige un cargo para ver tu ruta de formación"
    else:
        _mostrar_recomendaciones_catalogo(sug, ofertas)
        opciones = sug.get("sugerencias", [])
        recomendacion_por_cargo = {}
        etiqueta = "Elige un perfil ocupacional para ver tu ruta de formación"

    if not opciones:
        return

    elegido = st.radio(
        etiqueta,
        opciones,
        format_func=(lambda x: x) if sug["tipo"] == "general" else _nombre,
        key="a2_cargo",
    )
    if st.button("Preparar mi ruta de formación", type="primary", use_container_width=True):
        try:
            with st.spinner("Buscando cursos y organizando tus competencias..."):
                if sug["tipo"] == "general":
                    plan = hc.plan_para_cargo_general(
                        st.session_state["a2_texto"],
                        recomendacion_por_cargo[elegido],
                    )
                else:
                    plan = hc.plan_para_cargo(st.session_state["a2_texto"], elegido)
                st.session_state["a2_plan"] = plan
        except Exception as e:
            st.error("No pudimos preparar la ruta de formación.")
            with st.expander("Detalle técnico"):
                st.code(str(e))
            return

    plan = st.session_state.get("a2_plan")
    if plan:
        _mostrar_plan(plan)


if __name__ == "__main__":
    mostrar_agente2()
