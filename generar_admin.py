"""Genera un código aleatorio y su hash bcrypt por correo de administrador (uso: python generar_admin.py correo1 correo2 ...)."""
import secrets
import sys

import bcrypt

ALFABETO = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin 0/O/1/l/I


def generar_codigo(bloques: int = 3, largo: int = 4) -> str:
    return "-".join("".join(secrets.choice(ALFABETO) for _ in range(largo)) for _ in range(bloques))


if __name__ == "__main__":
    correos = [c.lower().strip() for c in sys.argv[1:]]
    if not correos:
        sys.exit("Uso: python generar_admin.py correo1 correo2 ...")

    entradas = []
    print("\nCÓDIGOS (entrégalos en privado; no se vuelven a mostrar):")
    for correo in correos:
        codigo = generar_codigo()
        h = bcrypt.hashpw(codigo.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        print(f"  {correo:40s} {codigo}")
        entradas.append(f'    "{correo}": "{h}",')

    print("\nPEGA ESTO dentro de ADMIN_HASHES en auth.py:\n")
    print("\n".join(entradas))
