"""Base de datos SQLite: usuarios, documentos, conversaciones, encuestas e intentos_admin."""

import sqlite3
import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "empleoconnect.db"


def get_connection():
    """Crea (si no existe) y retorna una conexión a la base de datos."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # permite acceder a columnas por nombre
    conn.execute("PRAGMA foreign_keys = ON")  # activa integridad referencial
    return conn


def inicializar_db():
    """Crea las tablas si no existen todavía. Se debe llamar al iniciar la app."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            correo TEXT UNIQUE NOT NULL,
            password_hash BLOB NOT NULL,
            fecha_registro TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            nombre_archivo TEXT NOT NULL,
            texto_extraido TEXT NOT NULL,
            fecha_carga TEXT NOT NULL,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            mensaje TEXT NOT NULL,
            respuesta TEXT NOT NULL,
            fecha TEXT NOT NULL,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS encuestas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL UNIQUE,
            precision INTEGER NOT NULL CHECK (precision BETWEEN 1 AND 5),
            pertinencia INTEGER NOT NULL CHECK (pertinencia BETWEEN 1 AND 5),
            utilidad INTEGER NOT NULL CHECK (utilidad BETWEEN 1 AND 5),
            comentario TEXT,
            fecha TEXT NOT NULL,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS intentos_admin (
            correo TEXT PRIMARY KEY,
            fallos INTEGER NOT NULL DEFAULT 0,
            bloqueado_hasta TEXT
        )
    """)

    _migrar_encuestas(conn)

    conn.commit()
    conn.close()


# Preguntas Likert (1 a 5) de la encuesta; _migrar_encuestas crea la columna de cada campo nuevo
CAMPOS_LIKERT = ("precision", "pertinencia", "utilidad", "satisfaccion", "confianza", "facilidad")


def _migrar_encuestas(conn) -> None:
    """Agrega a la tabla `encuestas` las columnas que falten, sin tocar las respuestas ya guardadas."""
    existentes = {r["name"] for r in conn.execute("PRAGMA table_info(encuestas)").fetchall()}
    for campo in CAMPOS_LIKERT:
        if campo not in existentes:
            conn.execute(f"ALTER TABLE encuestas ADD COLUMN {campo} INTEGER CHECK ({campo} BETWEEN 1 AND 5)")
    if "recomendacion" not in existentes:
        conn.execute("ALTER TABLE encuestas ADD COLUMN recomendacion INTEGER CHECK (recomendacion BETWEEN 0 AND 10)")
    if "agentes_usados" not in existentes:
        conn.execute("ALTER TABLE encuestas ADD COLUMN agentes_usados TEXT")


# Funciones de acceso a datos (CRUD básico) usadas por auth.py / app.py

def crear_usuario(correo: str, password_hash: bytes, fecha_registro: str) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO usuarios (correo, password_hash, fecha_registro) VALUES (?, ?, ?)",
        (correo, password_hash, fecha_registro),
    )
    conn.commit()
    conn.close()


def obtener_usuario_por_correo(correo: str):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM usuarios WHERE correo = ?", (correo,)
    ).fetchone()
    conn.close()
    return row


def guardar_documento(usuario_id: int, nombre_archivo: str, texto_extraido: str, fecha_carga: str) -> None:
    conn = get_connection()
    conn.execute(
        """INSERT INTO documentos (usuario_id, nombre_archivo, texto_extraido, fecha_carga)
           VALUES (?, ?, ?, ?)""",
        (usuario_id, nombre_archivo, texto_extraido, fecha_carga),
    )
    conn.commit()
    conn.close()


def obtener_documentos_usuario(usuario_id: int):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM documentos WHERE usuario_id = ? ORDER BY fecha_carga DESC",
        (usuario_id,),
    ).fetchall()
    conn.close()
    return rows


def obtener_documento_mas_reciente(usuario_id: int):
    """Retorna la última hoja de vida cargada por el usuario, o None si no ha cargado ninguna."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM documentos WHERE usuario_id = ? ORDER BY fecha_carga DESC LIMIT 1",
        (usuario_id,),
    ).fetchone()
    conn.close()
    return row


def guardar_conversacion(usuario_id: int, mensaje: str, respuesta: str, fecha: str) -> None:
    conn = get_connection()
    conn.execute(
        """INSERT INTO conversaciones (usuario_id, mensaje, respuesta, fecha)
           VALUES (?, ?, ?, ?)""",
        (usuario_id, mensaje, respuesta, fecha),
    )
    conn.commit()
    conn.close()


def obtener_conversaciones_usuario(usuario_id: int):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM conversaciones WHERE usuario_id = ? ORDER BY fecha ASC",
        (usuario_id,),
    ).fetchall()
    conn.close()
    return rows


def contar_usuarios() -> int:
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    conn.close()
    return total


def contar_conversaciones() -> int:
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM conversaciones").fetchone()[0]
    conn.close()
    return total


def contar_documentos() -> int:
    """Total de hojas de vida subidas por todos los usuarios."""
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM documentos").fetchone()[0]
    conn.close()
    return total


def conversaciones_por_dia(dias: int = 7) -> list[tuple[str, int]]:
    """Conversaciones por día de los últimos `dias` días, con 0 en los días sin datos."""
    hoy = datetime.date.today()
    fechas = [(hoy - datetime.timedelta(days=i)).isoformat() for i in range(dias - 1, -1, -1)]

    conn = get_connection()
    rows = conn.execute(
        """
        SELECT substr(fecha, 1, 10) AS dia, COUNT(*) AS cantidad
        FROM conversaciones
        WHERE substr(fecha, 1, 10) >= ?
        GROUP BY dia
        """,
        (fechas[0],),
    ).fetchall()
    conn.close()

    conteo_por_dia = {row["dia"]: row["cantidad"] for row in rows}
    return [(fecha, conteo_por_dia.get(fecha, 0)) for fecha in fechas]


def usuarios_por_dia(dias: int = 7) -> list[tuple[str, int]]:
    """Usuarios nuevos por día de los últimos `dias` días."""
    hoy = datetime.date.today()
    fechas = [(hoy - datetime.timedelta(days=i)).isoformat() for i in range(dias - 1, -1, -1)]

    conn = get_connection()
    rows = conn.execute(
        """
        SELECT substr(fecha_registro, 1, 10) AS dia, COUNT(*) AS cantidad
        FROM usuarios
        WHERE substr(fecha_registro, 1, 10) >= ?
        GROUP BY dia
        """,
        (fechas[0],),
    ).fetchall()
    conn.close()

    conteo_por_dia = {row["dia"]: row["cantidad"] for row in rows}
    return [(fecha, conteo_por_dia.get(fecha, 0)) for fecha in fechas]


# Encuesta de satisfacción

def guardar_encuesta(usuario_id: int, respuestas: dict, comentario: str, fecha: str,
                     recomendacion: int | None = None, agentes_usados: str = "") -> None:
    """Guarda la encuesta del usuario (actualiza si ya había respondido)."""
    campos = [c for c in CAMPOS_LIKERT if c in respuestas]
    columnas = ["usuario_id", *campos, "recomendacion", "agentes_usados", "comentario", "fecha"]
    valores = [usuario_id, *(int(respuestas[c]) for c in campos),
               recomendacion, agentes_usados or None, comentario.strip() or None, fecha]
    marcas = ", ".join("?" for _ in columnas)
    actualizar = ", ".join(f"{c} = excluded.{c}" for c in columnas if c != "usuario_id")
    conn = get_connection()
    conn.execute(
        f"INSERT INTO encuestas ({', '.join(columnas)}) VALUES ({marcas}) "
        f"ON CONFLICT(usuario_id) DO UPDATE SET {actualizar}",
        valores,
    )
    conn.commit()
    conn.close()


def obtener_encuesta_usuario(usuario_id: int):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM encuestas WHERE usuario_id = ?", (usuario_id,)
    ).fetchone()
    conn.close()
    return row


def contar_encuestas() -> int:
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM encuestas").fetchone()[0]
    conn.close()
    return total


def promedios_encuesta():
    """Promedio y número de respuestas por pregunta de la encuesta, o None si no hay datos."""
    conn = get_connection()
    n = conn.execute("SELECT COUNT(*) FROM encuestas").fetchone()[0]
    if n == 0:
        conn.close()
        return None
    campos = {}
    for c in CAMPOS_LIKERT:
        prom, cant = conn.execute(f"SELECT AVG({c}), COUNT({c}) FROM encuestas").fetchone()
        campos[c] = (prom, cant)
    conn.close()
    return {"n": n, "campos": campos}


def distribucion_encuesta(campo: str) -> list[tuple[int, int]]:
    """Cantidad de respuestas por puntaje 1..5 para una pregunta."""
    if campo not in CAMPOS_LIKERT:
        raise ValueError("campo inválido")
    conn = get_connection()
    rows = conn.execute(
        f"SELECT {campo} AS p, COUNT(*) AS c FROM encuestas WHERE {campo} IS NOT NULL GROUP BY {campo}"
    ).fetchall()
    conn.close()
    conteo = {r["p"]: r["c"] for r in rows}
    return [(p, conteo.get(p, 0)) for p in range(1, 6)]


def nps_encuesta():
    """Net Promoter Score (% promotores menos % detractores), o None si nadie respondió."""
    conn = get_connection()
    rows = conn.execute("SELECT recomendacion FROM encuestas WHERE recomendacion IS NOT NULL").fetchall()
    conn.close()
    notas = [r["recomendacion"] for r in rows]
    if not notas:
        return None
    n = len(notas)
    prom = sum(1 for x in notas if x >= 9)
    det = sum(1 for x in notas if x <= 6)
    return {"n": n, "promotores": prom, "pasivos": n - prom - det, "detractores": det,
            "nps": round(100 * (prom - det) / n)}


def conteo_agentes_usados() -> dict:
    """Cuántas personas dijeron haber usado cada agente (campo opcional de la encuesta)."""
    conn = get_connection()
    rows = conn.execute("SELECT agentes_usados FROM encuestas WHERE agentes_usados IS NOT NULL").fetchall()
    conn.close()
    conteo: dict = {}
    for r in rows:
        for a in r["agentes_usados"].split("|"):
            if a:
                conteo[a] = conteo.get(a, 0) + 1
    return conteo


def comentarios_encuesta():
    """Comentarios no vacíos, anónimos (sin correo), del más reciente al más antiguo."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT fecha, satisfaccion, utilidad, agentes_usados, comentario
           FROM encuestas WHERE comentario IS NOT NULL ORDER BY fecha DESC"""
    ).fetchall()
    conn.close()
    return rows


def exportar_encuestas():
    """Todas las respuestas SIN usuario_id ni correo (para analizar o citar en el paper)."""
    conn = get_connection()
    cols = ["fecha", *CAMPOS_LIKERT, "recomendacion", "agentes_usados", "comentario"]
    rows = conn.execute(f"SELECT {', '.join(cols)} FROM encuestas ORDER BY fecha").fetchall()
    conn.close()
    return cols, [tuple(r) for r in rows]


# Control de intentos del código de administrador

MAX_INTENTOS_ADMIN = 3
BLOQUEO_ADMIN_SEG = 120


def segundos_bloqueo_admin(correo: str) -> int:
    """Segundos que faltan para que se levante el bloqueo (0 si no está bloqueado)."""
    conn = get_connection()
    row = conn.execute(
        "SELECT bloqueado_hasta FROM intentos_admin WHERE correo = ?", (correo,)
    ).fetchone()
    conn.close()
    if row is None or not row["bloqueado_hasta"]:
        return 0
    restante = (datetime.datetime.fromisoformat(row["bloqueado_hasta"])
                - datetime.datetime.now()).total_seconds()
    return max(0, int(restante) + (1 if restante % 1 else 0))


def registrar_fallo_admin(correo: str) -> int:
    """Suma un intento fallido de admin y bloquea al llegar al máximo; retorna los intentos restantes."""
    conn = get_connection()
    row = conn.execute(
        "SELECT fallos FROM intentos_admin WHERE correo = ?", (correo,)
    ).fetchone()
    fallos = (row["fallos"] if row else 0) + 1
    if fallos >= MAX_INTENTOS_ADMIN:
        hasta = (datetime.datetime.now()
                 + datetime.timedelta(seconds=BLOQUEO_ADMIN_SEG)).isoformat()
        conn.execute(
            """INSERT INTO intentos_admin (correo, fallos, bloqueado_hasta) VALUES (?, 0, ?)
               ON CONFLICT(correo) DO UPDATE SET fallos = 0, bloqueado_hasta = excluded.bloqueado_hasta""",
            (correo, hasta),
        )
        restantes = 0
    else:
        conn.execute(
            """INSERT INTO intentos_admin (correo, fallos, bloqueado_hasta) VALUES (?, ?, NULL)
               ON CONFLICT(correo) DO UPDATE SET fallos = excluded.fallos""",
            (correo, fallos),
        )
        restantes = MAX_INTENTOS_ADMIN - fallos
    conn.commit()
    conn.close()
    return restantes


def limpiar_fallos_admin(correo: str) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM intentos_admin WHERE correo = ?", (correo,))
    conn.commit()
    conn.close()
