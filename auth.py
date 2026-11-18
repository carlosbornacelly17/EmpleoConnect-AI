"""Autenticación de usuarios con bcrypt (contraseñas) y JWT (sesión), apoyada en database.py."""

import datetime
import json
import os
import secrets

import bcrypt
import jwt
from dotenv import load_dotenv

import database

load_dotenv()

# Clave secreta del JWT (JWT_SECRET_KEY en .env; si falta, se genera una al arrancar)
SECRET_KEY = os.getenv("JWT_SECRET_KEY") or secrets.token_hex(32)

# Administradores: correo -> hash bcrypt de su código (variable ADMIN_HASHES en .env, formato JSON)
ADMIN_HASHES: dict[str, str] = json.loads(os.getenv("ADMIN_HASHES") or "{}")

# Hash falso para que validar un correo que no es admin tarde lo mismo
_HASH_FALSO = bcrypt.hashpw(b"hash-falso", bcrypt.gensalt()).decode("utf-8")

MENSAJE_ADMIN_INVALIDO = "Código de administrador incorrecto."


def verificar_codigo_admin(correo: str, codigo: str) -> tuple[bool, str]:
    """Valida el código de administrador de `correo` (3 fallos seguidos bloquean 2 minutos)."""
    correo = correo.lower().strip()

    restante = database.segundos_bloqueo_admin(correo)
    if restante > 0:
        return False, f"Demasiados intentos. Intenta de nuevo en {restante} segundos."

    hash_admin = ADMIN_HASHES.get(correo)
    ok = bcrypt.checkpw(
        (codigo or "").strip().encode("utf-8"),
        (hash_admin or _HASH_FALSO).encode("utf-8"),
    )
    if ok and hash_admin is not None:
        database.limpiar_fallos_admin(correo)
        return True, ""

    restantes = database.registrar_fallo_admin(correo)
    if restantes == 0:
        return False, (f"{MENSAJE_ADMIN_INVALIDO} Acceso bloqueado "
                       f"{database.BLOQUEO_ADMIN_SEG // 60} minutos.")
    return False, f"{MENSAJE_ADMIN_INVALIDO} Intentos restantes: {restantes}."


def registrar_usuario(correo: str, contrasena: str, confirmacion: str) -> tuple[bool, str]:
    """Registra un nuevo usuario; retorna (exito, mensaje)."""
    correo = correo.lower().strip()

    if not correo or "@" not in correo:
        return False, "Ingresa un correo electrónico válido."

    if database.obtener_usuario_por_correo(correo) is not None:
        return False, f"El correo '{correo}' ya está registrado."

    if contrasena != confirmacion:
        return False, "Las contraseñas no coinciden."

    if len(contrasena) < 6:
        return False, "La contraseña debe tener al menos 6 caracteres."

    salt = bcrypt.gensalt()
    hash_password = bcrypt.hashpw(contrasena.encode("utf-8"), salt)
    fecha_registro = datetime.datetime.now().isoformat()

    database.crear_usuario(correo, hash_password, fecha_registro)
    return True, f"¡Usuario '{correo}' registrado exitosamente!"


def iniciar_sesion(correo: str, contrasena: str, como_admin: bool = False, codigo_admin: str = ""):
    """Verifica credenciales y genera un JWT con el rol; retorna (exito, mensaje, token, usuario_id)."""
    correo = correo.lower().strip()
    usuario = database.obtener_usuario_por_correo(correo)

    if usuario is None:
        return False, "Usuario no encontrado o credenciales incorrectas.", None, None

    if not bcrypt.checkpw(contrasena.encode("utf-8"), usuario["password_hash"]):
        return False, "Contraseña incorrecta.", None, None

    rol = "usuario"
    if como_admin:
        ok_admin, msg_admin = verificar_codigo_admin(correo, codigo_admin)
        if not ok_admin:
            return False, msg_admin, None, None
        rol = "admin"

    payload = {
        "sub": correo,
        "user_id": usuario["id"],
        "rol": rol,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2),  # JWT exige UTC
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")

    saludo = f"¡Bienvenido, {correo}!" + (" (administrador)" if rol == "admin" else "")
    return True, saludo, token, usuario["id"]


def verificar_token(token: str):
    """Valida un token JWT y retorna su payload, o None si es inválido/expirado."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def es_admin(token: str) -> bool:
    """True solo si el token es válido, no ha expirado y trae rol admin."""
    payload = verificar_token(token) if token else None
    return bool(payload and payload.get("rol") == "admin")
