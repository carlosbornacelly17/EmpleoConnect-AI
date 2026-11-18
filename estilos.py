"""Tema visual de EmpleoConnect AI (oscuro con degradado animado), se aplica con estilos.aplicar()."""

import base64
from pathlib import Path

import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
    --bg: #080B14;
    --bg-side: #0B0F1A;
    --card: #111827;
    --border: #1F2937;
    --border-hover: #374151;
    --input: #1F2937;
    --text: #E5E7EB;
    --muted: #9CA3AF;
    --accent: #6366F1;
    --accent-hover: #4F46E5;
    --accent-soft: rgba(99, 102, 241, 0.14);
    --amber: #F59E0B;
    --radius: 12px;
}

/* ---------- Base ---------- */
html, body, body p, body li, body label, body button, body input, body textarea,
body h1, body h2, body h3, body h4, body div[data-testid="stMarkdownContainer"] {
    font-family: 'Inter', -apple-system, 'Segoe UI', Roboto, sans-serif;
}
[data-testid="stIconMaterial"] { color: var(--muted) !important; }   /* íconos de Streamlit (flechas) */
.stApp {
    background-color: var(--bg);
    background-image: linear-gradient(160deg, #141C42 0%, #0B0F22 50%, #080B14 100%);
    background-attachment: fixed;
    color: var(--text);
    isolation: isolate;
}
/* Luces animadas: se encienden, se apagan y cambian de lugar (detrás de todo el contenido) */
.stApp::before, .stApp::after {
    content: ""; position: fixed; inset: -40%; z-index: -1; pointer-events: none;
    will-change: transform, opacity;
}
.stApp::before {
    background:
        radial-gradient(600px 600px at 20% 25%, rgba(99, 102, 241, 0.95), transparent 68%),
        radial-gradient(460px 460px at 80% 70%, rgba(139, 92, 246, 0.80), transparent 68%);
    animation: ec-luz-a 18s ease-in-out infinite;
}
.stApp::after {
    background:
        radial-gradient(480px 480px at 75% 20%, rgba(56, 189, 248, 0.65), transparent 68%),
        radial-gradient(600px 600px at 25% 80%, rgba(79, 70, 229, 0.85), transparent 68%);
    animation: ec-luz-b 23s ease-in-out infinite;
}
@keyframes ec-luz-a {
    0%   { transform: translate(0, 0) scale(1);        opacity: .85; }
    30%  { transform: translate(14%, 8%) scale(1.15);  opacity: .25; }
    55%  { transform: translate(-6%, 16%) scale(.95);  opacity: 1; }
    80%  { transform: translate(-14%, -6%) scale(1.1); opacity: .35; }
    100% { transform: translate(0, 0) scale(1);        opacity: .85; }
}
@keyframes ec-luz-b {
    0%   { transform: translate(0, 0) scale(1.05);     opacity: .3; }
    35%  { transform: translate(-16%, 10%) scale(.9);  opacity: .95; }
    65%  { transform: translate(10%, -12%) scale(1.2); opacity: .4; }
    100% { transform: translate(0, 0) scale(1.05);     opacity: .3; }
}
@media (prefers-reduced-motion: reduce) { .stApp::before, .stApp::after { animation: none; } }
[data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stApp"] { background: transparent !important; }
[data-testid="stHeader"], [data-testid="stHeader"] > div, [data-testid="stToolbar"] { background: transparent !important; box-shadow: none !important; }
[data-testid="stDecoration"] { display: none !important; }
[data-testid="stToolbar"], #MainMenu, footer { visibility: hidden; }
.block-container { max-width: 980px; padding-top: 2.5rem; padding-bottom: 4rem; }

h1, h2, h3, h4 { color: #F9FAFB; letter-spacing: -0.02em; font-weight: 650; }
h1 { font-size: 2rem; }
h2 { font-size: 1.45rem; }
h3 { font-size: 1.15rem; }
p, li, label, [data-testid="stMarkdownContainer"] { color: var(--text); }
[data-testid="stCaptionContainer"], .stCaption, small { color: var(--muted) !important; }
hr { border-color: var(--border) !important; opacity: 1; margin: 1.5rem 0; }
a { color: #818CF8; text-decoration: none; }
a:hover { color: #A5B4FC; text-decoration: underline; }

/* ---------- Barra lateral ---------- */
[data-testid="stSidebar"] {
    background: rgba(10, 14, 30, 0.50) !important;
    backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
    border-right: 1px solid rgba(99, 102, 241, 0.18);
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { font-size: 0.85rem; }
.ec-sesion { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); margin: 0 0 2px 0; }
.ec-correo { font-size: 0.9rem; color: var(--text); word-break: break-all; margin: 0 0 4px 0; }
.ec-rol { display: inline-block; font-size: 0.7rem; color: #A5B4FC; background: var(--accent-soft);
          border: 1px solid rgba(99, 102, 241, 0.35); border-radius: 999px; padding: 1px 9px; margin-bottom: 10px; }

/* ---------- Botones ---------- */
.stButton > button, [data-testid^="stBaseButton"] {
    border-radius: 10px;
    font-weight: 550;
    font-size: 0.9rem;
    transition: background .15s ease, border-color .15s ease, transform .15s ease, box-shadow .15s ease;
}
/* Principal: índigo (sin rojo) */
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {
    background: var(--accent);
    border: 1px solid var(--accent);
    color: #FFFFFF;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.4), 0 6px 18px -8px rgba(99, 102, 241, 0.6);
}
[data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover {
    background: var(--accent-hover);
    border-color: var(--accent-hover);
    color: #FFFFFF;
    transform: translateY(-1px);
}
[data-testid="stBaseButton-primary"]:focus-visible, [data-testid="stBaseButton-primaryFormSubmit"]:focus-visible {
    outline: none; box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.45);
}
/* Secundario: "ghost" con borde fino */
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-secondaryFormSubmit"] {
    background: transparent;
    border: 1px solid var(--border-hover);
    color: var(--text);
}
[data-testid="stBaseButton-secondary"]:hover, [data-testid="stBaseButton-secondaryFormSubmit"]:hover {
    background: rgba(255, 255, 255, 0.04);
    border-color: var(--accent);
    color: #FFFFFF;
}
[data-testid="stBaseButton-secondary"]:active, [data-testid="stBaseButton-primary"]:active { transform: translateY(0); }
[data-testid^="stBaseButton"]:disabled { opacity: 0.45; transform: none; }

/* ---------- Pestañas flotantes (pill) ---------- */
[role="tablist"] {
    background: rgba(17, 24, 39, 0.82);
    backdrop-filter: blur(10px);
    border: 1px solid var(--border) !important;
    border-radius: var(--radius);
    padding: 4px;
    gap: 2px;
    box-shadow: 0 10px 30px -12px rgba(0, 0, 0, 0.7);
    position: sticky;
    top: 3.4rem;
    z-index: 50;
    width: fit-content;
    max-width: 100%;
}
[role="tablist"]::after, [data-baseweb="tab-highlight"], [data-baseweb="tab-border"],
.react-aria-SelectionIndicator { display: none !important; }
[role="tab"] {
    background: transparent;
    border-radius: 9px;
    padding: 7px 16px;
    height: auto;
    cursor: pointer;
    border: none !important;
    transition: background .15s ease, color .15s ease;
}
[role="tab"] p { color: var(--muted) !important; font-size: 0.88rem; font-weight: 550; margin: 0; }
[role="tab"]:hover { background: rgba(255, 255, 255, 0.05); }
[role="tab"]:hover p { color: var(--text) !important; }
[role="tab"][aria-selected="true"] {
    background: var(--accent);
    box-shadow: 0 4px 14px -6px rgba(99, 102, 241, 0.8);
}
[role="tab"][aria-selected="true"] p { color: #FFFFFF !important; }
[role="tabpanel"] { padding-top: 1.4rem; }

/* ---------- Tarjetas del menú ---------- */
.st-key-card_chat, .st-key-card_cargos {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 1.6rem 1.6rem 1.4rem 1.6rem;
    min-height: 260px;
    transition: border-color .2s ease, transform .2s ease, box-shadow .2s ease;
}
.st-key-card_chat:hover, .st-key-card_cargos:hover {
    border-color: rgba(99, 102, 241, 0.65);
    transform: translateY(-4px);
    box-shadow: 0 18px 40px -18px rgba(99, 102, 241, 0.45);
}
.ec-card-num { font-size: 0.72rem; letter-spacing: 0.12em; color: #818CF8; font-weight: 600; margin-bottom: 0.6rem; }
.ec-card-titulo { font-size: 1.3rem; font-weight: 650; color: #F9FAFB; letter-spacing: -0.02em; line-height: 1.25; margin-bottom: 0.6rem; }
.ec-card-texto { font-size: 0.93rem; color: var(--muted); line-height: 1.55; margin-bottom: 1.2rem; }
.ec-hero-titulo { font-size: 2.3rem; font-weight: 700; letter-spacing: -0.03em; color: #F9FAFB; margin: 0.4rem 0 0.2rem 0; }
.ec-hero-sub { font-size: 1.02rem; color: var(--muted); margin-bottom: 2rem; }

/* ---------- Inputs ---------- */
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"],
[data-testid="stTextInputRootElement"], [data-testid="stTextAreaRootElement"], [data-testid="stNumberInputContainer"] {
    background: var(--input) !important;
    border-radius: 10px !important;
}
[data-baseweb="input"], [data-baseweb="textarea"],
[data-testid="stTextInputRootElement"], [data-testid="stTextAreaRootElement"] {
    border: 1px solid var(--border-hover) !important;
    transition: border-color .15s ease, box-shadow .15s ease;
}
[data-baseweb="input"]:focus-within, [data-baseweb="textarea"]:focus-within,
[data-testid="stTextInputRootElement"]:focus-within, [data-testid="stTextAreaRootElement"]:focus-within {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.30) !important;
}
[data-testid="stTextInputField"], [data-testid="stTextAreaField"], textarea, input[type="text"], input[type="password"] {
    background: transparent !important;
    color: var(--text) !important;
    caret-color: var(--accent);
}
input::placeholder, textarea::placeholder { color: #6B7280 !important; }
[data-testid="stForm"] {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.2rem;
}
[data-testid="stFileUploaderDropzone"] {
    background: var(--card);
    border: 1px dashed var(--border-hover);
    border-radius: var(--radius);
}
[data-testid="stFileUploaderDropzone"]:hover { border-color: var(--accent); }
[data-baseweb="radio"] > div:first-child, [data-baseweb="checkbox"] > span:first-child { border-color: var(--border-hover); }
[role="radiogroup"] [aria-checked="true"] > div:first-child,
[data-baseweb="checkbox"] [aria-checked="true"] { background-color: var(--accent) !important; border-color: var(--accent) !important; }

/* ---------- Alertas: contenedores semitransparentes (ámbar suave) ---------- */
[data-testid="stAlert"] {
    background: rgba(245, 158, 11, 0.08);
    border: 1px solid rgba(245, 158, 11, 0.28);
    border-radius: var(--radius);
    color: #FDE68A;
}
[data-testid="stAlert"] p, [data-testid="stAlert"] li { color: #FCD9A0 !important; }
[data-testid="stAlert"] svg { fill: #FBBF24; color: #FBBF24; }
[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) {
    background: rgba(16, 185, 129, 0.08); border-color: rgba(16, 185, 129, 0.28);
}
[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) p { color: #A7F3D0 !important; }
[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) svg { fill: #34D399; color: #34D399; }
[data-testid="stAlert"]:has([data-testid="stAlertContentError"]) {
    background: rgba(239, 68, 68, 0.07); border-color: rgba(239, 68, 68, 0.25);
}
[data-testid="stAlert"]:has([data-testid="stAlertContentError"]) p { color: #FCA5A5 !important; }
[data-testid="stAlert"]:has([data-testid="stAlertContentError"]) svg { fill: #F87171; color: #F87171; }

/* ---------- Chat: sin avatares ---------- */
[data-testid="stChatMessage"] {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1rem 1.2rem;
    margin-bottom: 0.7rem;
    gap: 0.9rem;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background: rgba(99, 102, 241, 0.08);
    border-color: rgba(99, 102, 241, 0.25);
}
/* Solo el usuario va sin avatar; la respuesta del asistente conserva el robot como distintivo */
[data-testid="stChatMessageAvatarUser"] { display: none !important; }
[data-testid="stChatMessageAvatarAssistant"] {
    background: #F97316 !important;
    border: none;
    border-radius: 10px;
    flex-shrink: 0;
    box-shadow: 0 4px 12px -4px rgba(249, 115, 22, 0.6);
}
[data-testid="stChatMessageAvatarAssistant"] svg, [data-testid="stChatMessageAvatarAssistant"] span {
    color: #FFFFFF !important; fill: #FFFFFF;
}

/* ---------- Métricas, expanders, tablas ---------- */
[data-testid="stMetric"] {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1rem 1.1rem;
}
[data-testid="stMetricLabel"] p { color: var(--muted) !important; font-size: 0.78rem; white-space: normal; }
[data-testid="stMetricLabel"] { white-space: normal; }
[data-testid="stMetricValue"] { color: #F9FAFB; font-weight: 650; letter-spacing: -0.02em; }
[data-testid="stExpander"] {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
}
[data-testid="stExpander"] summary:hover { color: #FFFFFF; }
[data-testid="stVegaLiteChart"], [data-testid="stArrowVegaLiteChart"] { background: transparent; border: none; padding: 0; overflow: hidden; }
[data-testid="stSidebar"] [data-testid="stMetric"] { padding: 0.7rem 0.9rem; }
[data-testid="stVegaLiteChart"] .vega-embed, [data-testid="stArrowVegaLiteChart"] .vega-embed { padding: 0 !important; max-width: 100%; }
[data-testid="stVegaLiteChart"] canvas, [data-testid="stArrowVegaLiteChart"] canvas { max-width: 100% !important; }

/* ---------- Diálogo (encuesta) ---------- */
[data-testid="stDialog"] div[role="dialog"] {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 16px;
}

/* ---------- Burbuja de aviso de la encuesta ---------- */
.ec-burbuja {
    background: var(--accent-soft);
    border: 1px solid rgba(99, 102, 241, 0.35);
    border-radius: 14px;
    padding: 12px 14px;
    font-size: 0.86rem;
    color: #C7D2FE;
    line-height: 1.45;
    margin-bottom: 10px;
}
.ec-burbuja b { color: #E0E7FF; }

/* ---------- Scrollbar discreta ---------- */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-thumb { background: #1F2937; border-radius: 8px; }
::-webkit-scrollbar-thumb:hover { background: #374151; }
</style>
"""


def _css_logo() -> str:
    """Logo de logo.png: arriba a la derecha en el login y abajo a la izquierda de la barra lateral con sesión."""
    ruta = Path(__file__).parent / "logo.png"
    if not ruta.exists():
        return ""
    b64 = base64.b64encode(ruta.read_bytes()).decode()
    img = f"background:url(data:image/png;base64,{b64}) no-repeat center / contain; pointer-events:none;"
    if st.session_state.get("usuario_id") is None:
        regla = ('[data-testid="stMain"]::after {content:""; position:fixed; top:18px; right:28px; '
                 f'width:46px; height:52px; z-index:5; {img} opacity:.95; '
                 'filter:drop-shadow(0 4px 14px rgba(99,102,241,.45)); }')
    else:
        regla = ('[data-testid="stSidebar"]::after {content:""; position:absolute; left:26px; bottom:22px; '
                 f'width:72px; height:80px; {img} background-position:left bottom; opacity:.95; '
                 'filter:drop-shadow(0 6px 18px rgba(99,102,241,.45)); }')
    return f"<style>{regla}</style>"


def aplicar() -> None:
    """Inyecta el CSS del tema. Llamar una vez por ejecución, después de set_page_config."""
    st.markdown(CSS + _css_logo(), unsafe_allow_html=True)
