"""App principal de Streamlit para EmpleoConnect AI (correr con: streamlit run app.py)."""

import datetime
import html

import pandas as pd
import streamlit as st

import auth
import database
import estilos
import extraccion
import llm

st.set_page_config(page_title="EmpleoConnect AI", page_icon="💼", layout="centered")
estilos.aplicar()   # tema oscuro minimalista (estilos.py)

# Crea las tablas la primera vez que se ejecuta la app
database.inicializar_db()

# --- Estado de sesión ---
if "usuario_id" not in st.session_state:
    st.session_state.usuario_id = None
if "correo" not in st.session_state:
    st.session_state.correo = None
if "token" not in st.session_state:
    st.session_state.token = None
if "usos_agente2" not in st.session_state:
    st.session_state.usos_agente2 = False   # True cuando la persona ya obtuvo cargos en el agente 2
if "abrir_encuesta" not in st.session_state:
    st.session_state.abrir_encuesta = False
if "encuesta_aviso_cerrado" not in st.session_state:
    st.session_state.encuesta_aviso_cerrado = False
if "modo" not in st.session_state:
    st.session_state.modo = None   # None = menú | "chat" = agente 1 | "cargos" = agente 2

# Claves de session_state que usa la pantalla del agente 2 (agente2/vista_agente2.py)
CLAVES_AGENTE2 = ("a2_texto", "a2_sug", "a2_plan", "a2_cargo")


def limpiar_agente2():
    for k in CLAVES_AGENTE2:
        st.session_state.pop(k, None)


def elegir_modo(modo):
    limpiar_agente2()
    st.session_state.modo = modo


def ir_al_menu():
    st.session_state.modo = None
    limpiar_agente2()


def es_admin() -> bool:
    """El rol se lee SIEMPRE del JWT (firmado y con expiración), no de un flag editable."""
    return auth.es_admin(st.session_state.token)


def cerrar_sesion():
    st.session_state.usuario_id = None
    st.session_state.correo = None
    st.session_state.token = None
    st.session_state.encuesta_aviso_cerrado = False
    st.session_state.usos_agente2 = False
    ir_al_menu()


# VISTA: USUARIO NO AUTENTICADO -> Login / Registro
def vista_login():
    st.title("EmpleoConnect AI")
    st.caption("Asistente virtual inteligente para orientación laboral")

    tab_login, tab_registro = st.tabs(["Iniciar sesión", "Registrarse"])

    with tab_login:
        st.subheader("Iniciar sesión")
        correo = st.text_input("Correo electrónico", key="login_correo")
        contrasena = st.text_input("Contraseña", type="password", key="login_pass")

        eres_admin = st.radio("¿Eres admin?", ["No", "Sí"], horizontal=True, key="login_admin")
        codigo_admin = ""
        if eres_admin == "Sí":
            codigo_admin = st.text_input("Código de administrador", type="password", key="login_codigo")

        if st.button("Ingresar", type="primary"):
            exito, mensaje, token, usuario_id = auth.iniciar_sesion(
                correo, contrasena, como_admin=(eres_admin == "Sí"), codigo_admin=codigo_admin
            )
            if exito:
                st.session_state.usuario_id = usuario_id
                st.session_state.correo = correo.lower().strip()
                st.session_state.token = token
                st.success(mensaje)
                st.rerun()
            else:
                st.error(mensaje)

    with tab_registro:
        st.subheader("Crear cuenta nueva")
        correo_r = st.text_input("Correo electrónico", key="reg_correo")
        pass_r = st.text_input("Contraseña", type="password", key="reg_pass")
        pass_r2 = st.text_input("Confirmar contraseña", type="password", key="reg_pass2")

        if st.button("Registrarme"):
            exito, mensaje = auth.registrar_usuario(correo_r, pass_r, pass_r2)
            if exito:
                st.success(mensaje + " Ahora puedes iniciar sesión en la otra pestaña.")
            else:
                st.error(mensaje)


# VISTA: MENÚ DE MODOS (después de iniciar sesión)
def vista_menu():
    st.markdown('<div class="ec-hero-titulo">EmpleoConnect AI</div>'
                '<div class="ec-hero-sub">¿Qué quieres hacer hoy?</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="large")
    with col1:
        with st.container(key="card_chat"):
            st.markdown(
                '<div class="ec-card-num">01 · CHAT</div>'
                '<div class="ec-card-titulo">Chat de orientación</div>'
                '<div class="ec-card-texto">Haz preguntas sobre empleo, hojas de vida y entrevistas. '
                'Las respuestas se apoyan en la base de conocimiento, con fuentes.</div>',
                unsafe_allow_html=True)
            st.button("Ir al chat", type="primary", use_container_width=True,
                      on_click=elegir_modo, args=("chat",), key="menu_chat")
    with col2:
        with st.container(key="card_cargos"):
            st.markdown(
                '<div class="ec-card-num">02 · PERFIL</div>'
                '<div class="ec-card-titulo">¿A qué cargos puedes encaminarte?</div>'
                '<div class="ec-card-texto">Sube tu hoja de vida y descubre a qué carreras o cargos vas más '
                'encaminado/a, con cursos para fortalecer tu perfil.</div>',
                unsafe_allow_html=True)
            st.button("Analizar mi perfil", type="primary", use_container_width=True,
                      on_click=elegir_modo, args=("cargos",), key="menu_cargos")


# VISTA: AGENTE 2 (análisis de cargos), carpeta agente2/
def vista_cargos():
    st.title("EmpleoConnect AI")
    try:
        # Se importa aquí para que, si el agente 2 falla, el chat siga funcionando
        from agente2.vista_agente2 import mostrar_agente2
    except Exception as e:
        st.error("El análisis de cargos no está disponible en este momento. El chat sigue funcionando.")
        with st.expander("Detalle técnico"):
            st.code(str(e))
        return
    mostrar_agente2()
    if st.session_state.get("a2_sug"):          # ya obtuvo un resultado del agente 2
        st.session_state.usos_agente2 = True


# VISTA: USUARIO AUTENTICADO -> App principal
def vista_app():
    # Si el JWT (2 h) expiró o es inválido, se cierra la sesión
    if auth.verificar_token(st.session_state.token) is None:
        cerrar_sesion()
        st.warning("Tu sesión expiró. Inicia sesión de nuevo.")
        st.rerun()

    admin = es_admin()

    with st.sidebar:
        st.markdown(
            '<p class="ec-sesion">Sesión activa</p>'
            f'<p class="ec-correo">{html.escape(st.session_state.correo)}</p>'
            + ('<span class="ec-rol">Administrador</span>' if admin else ""),
            unsafe_allow_html=True,
        )
        if st.button("Cerrar sesión"):
            cerrar_sesion()
            st.rerun()

        if st.session_state.modo is not None:
            st.button("Volver al menú", on_click=ir_al_menu, key="volver_sidebar")

        if admin:
            st.divider()
            st.metric("Usuarios que usan EmpleoConnect AI", database.contar_usuarios())
            st.metric("Conversaciones totales", database.contar_conversaciones())
        else:
            aviso_encuesta()

    if st.session_state.abrir_encuesta and not admin:
        st.session_state.abrir_encuesta = False
        dialogo_encuesta()

    if st.session_state.modo is None:
        vista_menu()
        return

    st.button("← Volver al menú", on_click=ir_al_menu, key="volver_principal")
    if st.session_state.modo == "chat":
        vista_chat()
    else:
        vista_cargos()


PREGUNTAS_ENCUESTA_MIN = 2   # preguntas al chat tras las cuales se recuerda la encuesta


def pedir_encuesta():
    st.session_state.abrir_encuesta = True


@st.dialog("Encuesta de satisfacción", width="large")
def dialogo_encuesta():
    """Ventana emergente con la encuesta; se puede abrir desde cualquier pantalla."""
    vista_encuesta("dialogo")


def aviso_encuesta():
    """Burbuja en el espacio libre de la barra lateral (solo usuarios no admin)."""
    uid = st.session_state.usuario_id
    ya_respondio = database.obtener_encuesta_usuario(uid) is not None
    suficiente_uso = (st.session_state.usos_agente2 or
                      len(database.obtener_conversaciones_usuario(uid)) >= PREGUNTAS_ENCUESTA_MIN)

    st.divider()
    if ya_respondio or st.session_state.encuesta_aviso_cerrado or not suficiente_uso:
        # Entrada permanente a la encuesta, disponible desde cualquiera de los dos agentes
        st.button("Encuesta de satisfacción" if not ya_respondio else "Editar mi encuesta",
                  key="aviso_permanente", use_container_width=True, on_click=pedir_encuesta)
        return

    st.markdown(
        '<div class="ec-burbuja"><b>Tu opinión cuenta</b><br>'
        'Recuerda responder la encuesta de satisfacción. Te toma menos de 2 minutos.</div>',
        unsafe_allow_html=True,
    )
    st.button("Ir a la encuesta", key="aviso_ir", use_container_width=True,
              type="primary", on_click=pedir_encuesta)
    if st.button("Cerrar", key="aviso_cerrar", use_container_width=True):
        st.session_state.encuesta_aviso_cerrado = True
        st.rerun()


# Preguntas obligatorias de la encuesta (escala 1-5); para agregar una, ver CAMPOS_LIKERT en database.py
PREGUNTAS_ENCUESTA = [
    ("satisfaccion", "Satisfacción general", "En general, ¿qué tan satisfecho/a estás con EmpleoConnect AI?", "satisfaccion"),
    ("precision", "Precisión", "Las respuestas fueron correctas y coherentes con la información consultada.", "acuerdo"),
    ("pertinencia", "Pertinencia", "Las respuestas respondieron a lo que pregunté y se ajustaron a mi caso.", "acuerdo"),
    ("utilidad", "Utilidad", "Las respuestas me sirvieron para tomar decisiones sobre mi búsqueda de empleo.", "acuerdo"),
    ("confianza", "Confianza en las fuentes", "Confío en la información y en las fuentes que cita el asistente.", "acuerdo"),
    ("facilidad", "Facilidad de uso", "Usar la página fue fácil y entendí cómo funciona sin ayuda.", "acuerdo"),
]
ESCALAS = {   # texto de los extremos de cada escala 1-5
    "satisfaccion": "1 = nada satisfecho/a · 5 = muy satisfecho/a",
    "acuerdo": "1 = totalmente en desacuerdo · 5 = totalmente de acuerdo",
}
AGENTES = ["Chat de orientación", "¿A qué cargos puedes encaminarte?"]


def vista_encuesta(ctx: str = "tab"):
    """Encuesta de satisfacción: 6 preguntas obligatorias (1-5) y 3 opcionales. Menos de 2 minutos."""
    st.caption("Son 6 preguntas rápidas y 3 opcionales. Tus respuestas no muestran tu correo: el equipo "
               "solo ve promedios y comentarios.")
    st.caption("Pregunta 1: 1 = nada satisfecho/a, 5 = muy satisfecho/a. Preguntas 2 a 6: 1 = totalmente en "
               "desacuerdo, 5 = totalmente de acuerdo.")

    previa = database.obtener_encuesta_usuario(st.session_state.usuario_id)
    if previa:
        st.success("Ya respondiste la encuesta. ¡Gracias! Puedes actualizar tu respuesta abajo.")

    def previo(campo):
        return previa[campo] if previa is not None and campo in previa.keys() else None

    with st.form(f"form_encuesta_{ctx}"):
        respuestas = {}
        for n, (campo, _nombre, texto, escala) in enumerate(PREGUNTAS_ENCUESTA, start=1):
            opciones = [1, 2, 3, 4, 5]
            actual = previo(campo)
            respuestas[campo] = st.radio(
                f"{n}. {texto}", opciones, index=opciones.index(actual) if actual else None,
                horizontal=True, key=f"enc_{campo}_{ctx}", help=ESCALAS[escala])

        st.markdown("**Opcional**")
        notas = list(range(0, 11))
        rec_prev = previo("recomendacion")
        recomendacion = st.radio(
            "¿Qué tan probable es que recomiendes EmpleoConnect AI a un compañero? (0 = nada probable · 10 = muy probable)",
            notas, index=notas.index(rec_prev) if rec_prev is not None else None,
            horizontal=True, key=f"enc_rec_{ctx}")
        usados_prev = [a for a in (previo("agentes_usados") or "").split("|") if a in AGENTES]
        if previa is None:   # primera vez: sugerir lo que la persona realmente usó
            if database.obtener_conversaciones_usuario(st.session_state.usuario_id):
                usados_prev.append(AGENTES[0])
            if st.session_state.usos_agente2:
                usados_prev.append(AGENTES[1])
        usados = st.multiselect("¿Qué usaste?", AGENTES, default=usados_prev,
                                placeholder="Elige una o varias", key=f"enc_agentes_{ctx}")
        comentario = st.text_area(
            "¿Qué mejorarías o qué te resultó más útil?",
            value=(previo("comentario") or ""), max_chars=500, key=f"enc_com_{ctx}")
        enviado = st.form_submit_button("Enviar encuesta", type="primary", key=f"enc_env_{ctx}")

    if enviado:
        if any(v is None for v in respuestas.values()):
            st.error("Responde las 6 preguntas obligatorias (1 a 5) antes de enviar.")
        else:
            database.guardar_encuesta(
                st.session_state.usuario_id, respuestas, comentario, datetime.datetime.now().isoformat(),
                recomendacion=recomendacion, agentes_usados="|".join(usados),
            )
            st.success("¡Gracias por tu opinión!")
            st.rerun()


def vista_rendimiento():
    """Panel solo para admin: resultados agregados de la encuesta."""
    if not es_admin():   # verificación en el servidor, no solo ocultar la pestaña
        st.error("Acceso restringido a administradores.")
        return

    st.subheader("Rendimiento de la página según las encuestas")
    prom = database.promedios_encuesta()
    if prom is None:
        st.info("Todavía no hay respuestas de la encuesta.")
        return

    campos = prom["campos"]
    nombres = {c: nombre for c, nombre, _t, _e in PREGUNTAS_ENCUESTA}

    # --- Indicadores principales: respuestas, CSAT, calidad de respuestas (las 3 del paper) y NPS ---
    sat_dist = database.distribucion_encuesta("satisfaccion")
    sat_n = sum(c for _, c in sat_dist)
    sat_pct = 100 * sum(c for p, c in sat_dist if p >= 4) / sat_n if sat_n else None
    calidad = [campos[c][0] for c in ("precision", "pertinencia", "utilidad") if campos[c][0] is not None]
    nps = database.nps_encuesta()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Respuestas", prom["n"])
    k2.metric("Satisfacción (CSAT)", f"{sat_pct:.0f} %" if sat_pct is not None else "—",
              help="Porcentaje de personas que respondieron 4 o 5 en la satisfacción general.")
    k3.metric("Calidad de las respuestas", f"{sum(calidad) / len(calidad):.2f} / 5" if calidad else "—",
              help="Promedio de precisión, pertinencia y utilidad, las tres métricas del paper.")
    k4.metric("Recomendación (NPS)", f"{nps['nps']:+d}" if nps else "—",
              help="% de promotores (9-10) menos % de detractores (0-6). Va de -100 a +100.")

    st.divider()
    st.markdown("**Promedio por pregunta (1 a 5)**")
    cols = st.columns(len(PREGUNTAS_ENCUESTA))
    for col, (campo, nombre, _t, _e) in zip(cols, PREGUNTAS_ENCUESTA):
        p, n = campos[campo]
        col.metric(nombre, f"{p:.2f}" if p is not None else "—", help=f"{n} respuestas")

    st.markdown("**Distribución de puntajes (1 a 5)**")
    for fila in range(0, len(PREGUNTAS_ENCUESTA), 3):
        cols = st.columns(3)
        for col, (campo, nombre, _t, _e) in zip(cols, PREGUNTAS_ENCUESTA[fila:fila + 3]):
            with col:
                st.caption(nombre)
                dist = pd.DataFrame({"Respuestas": [x for _, x in database.distribucion_encuesta(campo)]},
                                    index=["1", "2", "3", "4", "5"])
                st.bar_chart(dist, color="#6366F1", height=150)

    usados = database.conteo_agentes_usados()
    if usados:
        st.markdown("**Qué usaron quienes respondieron**")
        st.bar_chart(pd.DataFrame({"Personas": usados}), color="#6366F1")
    if nps:
        st.caption(f"NPS con {nps['n']} respuesta(s): {nps['promotores']} promotores, "
                   f"{nps['pasivos']} pasivos y {nps['detractores']} detractores.")

    comentarios = database.comentarios_encuesta()
    st.markdown(f"**Comentarios ({len(comentarios)})**")
    if not comentarios:
        st.caption("Aún no hay comentarios.")
    for c in comentarios:
        extra = f" · satisfacción {c['satisfaccion']}" if c["satisfaccion"] else ""
        st.markdown(f"- _{c['fecha'][:10]}_{extra}: {c['comentario']}")

    columnas, filas = database.exportar_encuestas()
    st.download_button(
        "Descargar respuestas (CSV, sin correos)",
        data=pd.DataFrame(filas, columns=columnas).to_csv(index=False).encode("utf-8-sig"),
        file_name="encuestas_empleoconnect.csv", mime="text/csv")
    st.caption("Los datos se actualizan al recargar la página o interactuar con la app.")


def vista_chat():
    st.title("EmpleoConnect AI")

    admin = es_admin()
    if admin:
        tab_chat, tab_cv, tab_historial, tab_stats, tab_rend = st.tabs(
            ["Chat", "Mi hoja de vida", "Historial", "Estadísticas", "Rendimiento (encuestas)"]
        )
    else:
        tab_chat, tab_cv, tab_historial, tab_encuesta = st.tabs(
            ["Chat", "Mi hoja de vida", "Historial", "Encuesta"]
        )

    # CHAT (placeholder hasta conectar el LLM/RAG) ----------------
    with tab_chat:
        st.subheader("Asistente de orientación laboral")
        st.caption(
            "Conectado a Gemini con RAG: las respuestas se basan en la base de "
            "conocimiento de documentos_base/, con fuentes citadas."
        )

        documento_reciente = database.obtener_documento_mas_reciente(st.session_state.usuario_id)
        if documento_reciente:
            st.info(f"Usando tu hoja de vida más reciente para personalizar respuestas: **{documento_reciente['nombre_archivo']}**")
        else:
            st.warning("Aún no has subido una hoja de vida. Súbela en la pestaña 'Mi hoja de vida' para recibir respuestas personalizadas.")

        # --- Caja para escribir, arriba del todo ---
        with st.form(key="form_chat", clear_on_submit=True):
            pregunta = st.text_input("Escribe tu pregunta sobre empleo, hoja de vida, etc.")
            enviar = st.form_submit_button("Enviar", type="primary")

        if enviar and pregunta.strip():
            historial_previo = [
                {"mensaje": c["mensaje"], "respuesta": c["respuesta"]}
                for c in database.obtener_conversaciones_usuario(st.session_state.usuario_id)
            ]
            with st.spinner("Buscando en la base de conocimiento y pensando la respuesta..."):
                cv_texto = documento_reciente["texto_extraido"] if documento_reciente else None
                resultado = llm.generar_respuesta_rag(pregunta, historial_previo, cv_texto=cv_texto)

            # Guardamos la respuesta junto con las fuentes citadas, como texto plano
            respuesta_texto = resultado["respuesta"]
            if resultado["fuentes"]:
                lista_fuentes = "\n".join(
                    f"- {f['titulo']} ({f['fuente']}) {f['link']}" for f in resultado["fuentes"]
                )
                respuesta_texto += f"\n\n**Fuentes consultadas:**\n{lista_fuentes}"

            database.guardar_conversacion(
                st.session_state.usuario_id,
                pregunta,
                respuesta_texto,
                datetime.datetime.now().isoformat(),
            )
            st.rerun()

        st.divider()

        # --- Historial: el más reciente arriba, los más viejos abajo ---
        conversaciones = database.obtener_conversaciones_usuario(st.session_state.usuario_id)
        for conv in reversed(conversaciones):
            with st.chat_message("user"):
                st.write(conv["mensaje"])
            with st.chat_message("assistant"):
                st.write(conv["respuesta"])

    # CARGA DE HOJA DE VIDA ----------------
    with tab_cv:
        st.subheader("Sube tu hoja de vida")
        archivo = st.file_uploader("Formatos soportados: PDF o Word (.docx)", type=["pdf", "docx"])

        if archivo is not None and st.button("Procesar documento"):
            with st.spinner("Extrayendo texto del documento..."):
                try:
                    texto_extraido = extraccion.extraer_texto_para_rag(archivo)
                    database.guardar_documento(
                        st.session_state.usuario_id,
                        archivo.name,
                        texto_extraido,
                        datetime.datetime.now().isoformat(),
                    )
                    st.success("¡Documento procesado y guardado correctamente!")
                    with st.expander("Ver vista previa del texto extraído"):
                        st.text(texto_extraido[:1500])
                except Exception as e:
                    st.error(f"Error al procesar el archivo: {e}")

        st.divider()
        st.write("**Documentos guardados:**")
        documentos = database.obtener_documentos_usuario(st.session_state.usuario_id)
        if not documentos:
            st.caption("Aún no has subido ninguna hoja de vida.")
        else:
            for doc in documentos:
                with st.expander(f"{doc['nombre_archivo']} — {doc['fecha_carga']}"):
                    st.text(doc["texto_extraido"][:2000])

    # HISTORIAL ----------------
    with tab_historial:
        st.subheader("Historial de conversaciones")
        conversaciones = database.obtener_conversaciones_usuario(st.session_state.usuario_id)
        if not conversaciones:
            st.caption("Todavía no tienes conversaciones guardadas.")
        else:
            for conv in conversaciones:
                st.markdown(f"**{conv['fecha']}**")
                st.markdown(f"**Tú:** {conv['mensaje']}")
                st.markdown(f"**Asistente:** {conv['respuesta']}")
                st.divider()

    # ESTADÍSTICAS (solo admin) ----------------
    if admin:
        with tab_stats:
            st.subheader("Estadísticas de uso del sistema")

            col1, col2, col3 = st.columns(3)
            col1.metric("Usuarios que usan EmpleoConnect AI", database.contar_usuarios())
            col2.metric("Conversaciones totales", database.contar_conversaciones())
            col3.metric("Hojas de vida subidas", database.contar_documentos())

            st.divider()

            st.markdown("**Conversaciones por día (últimos 7 días)**")
            datos_conv = database.conversaciones_por_dia(dias=7)
            df_conv = pd.DataFrame(datos_conv, columns=["Fecha", "Conversaciones"]).set_index("Fecha")
            st.bar_chart(df_conv, color="#6366F1")

            st.markdown("**Usuarios registrados por día (últimos 7 días)**")
            datos_usuarios = database.usuarios_por_dia(dias=7)
            df_usuarios = pd.DataFrame(datos_usuarios, columns=["Fecha", "Usuarios nuevos"]).set_index("Fecha")
            st.bar_chart(df_usuarios, color="#6366F1")

            st.caption(
                "Estos datos se actualizan cada vez que recargas la página o interactúas "
                "con la app (Streamlit no se actualiza en tiempo real de forma automática)."
            )

        with tab_rend:
            vista_rendimiento()

    else:
        with tab_encuesta:
            st.subheader("Encuesta de satisfacción")
            vista_encuesta()


# ROUTER PRINCIPAL
if st.session_state.usuario_id is None:
    vista_login()
else:
    vista_app()
