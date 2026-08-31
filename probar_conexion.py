"""Prueba de conexión con la API institucional CIMA.

POST https://apicima.colegiocima.edu.pe:8086/api/v2/authentication/with/user

Uso:
    python probar_conexion.py USUARIO CONTRASENA
"""

import json
import sys

import requests
import jwt

URL = "https://apicima.colegiocima.edu.pe:8086/api/v2/authentication/with/user"
ID_SYSTEM = 21


def ip_publica() -> str:
    """Devuelve la IP pública de tu conexión a internet."""
    return requests.get("https://api.ipify.org", timeout=10).text.strip()


def main() -> None:
    if len(sys.argv) != 3:
        print("Uso: python probar_conexion.py USUARIO CONTRASENA")
        raise SystemExit(2)

    username, password = sys.argv[1], sys.argv[2]

    payload = {
        "username": username,
        "password": password,
        "idSystem": ID_SYSTEM,
        "identifier": ip_publica(),
    }

    print("POST", URL)
    print("Body:", json.dumps({**payload, "password": "***"}, ensure_ascii=False))

    response = requests.post(
        URL,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=15,
    )

    print("\nStatus:", response.status_code)
    try:
        token = response.json()["content"]["token"]
        token = token.replace("Bearer" , "").strip()
        payload = jwt.decode(token, options={"verify_signature": False})
        print(payload)
    except ValueError:
        print(response.text)


if __name__ == "__main__":
    main()
