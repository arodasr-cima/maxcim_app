"""Prueba de conexión con la API institucional CIMA: login + listar aulas.

Duplicado de probar_conexion.py que además encadena la llamada al endpoint
de aulas de un docente, para observar la forma real de esa respuesta antes
de mapearla en services/institutional.py.

1. POST https://apicima.colegiocima.edu.pe:8086/api/v2/authentication/with/user
2. GET  https://apicima.colegiocima.edu.pe:8086/api/v2/gradesection/list/group/user/{idDocente}
   con Authorization: Bearer <token> — {idDocente} es el idLogueo del token
   decodificado en el paso 1 (confirmado: no es idPersona, que devuelve []).

Uso:
    python probar_conexion_aulas.py USUARIO CONTRASENA [ID_DOCENTE]

ID_DOCENTE es opcional: si no se indica, se usa el claim `idLogueo` del
token. Pásalo explícitamente para probar otro valor.
"""

import json
import sys

import requests
import jwt

LOGIN_URL = "https://apicima.colegiocima.edu.pe:8086/api/v2/authentication/with/user"
AULAS_URL_TEMPLATE = (
    "https://apicima.colegiocima.edu.pe:8086/api/v2/gradesection/list/group/user/{id_docente}"
)
ID_SYSTEM = 21


def ip_publica() -> str:
    """Devuelve la IP pública de tu conexión a internet."""
    return requests.get("https://api.ipify.org", timeout=10).text.strip()


def main() -> None:
    if len(sys.argv) not in (3, 4):
        print("Uso: python probar_conexion_aulas.py USUARIO CONTRASENA [ID_DOCENTE]")
        raise SystemExit(2)

    username, password = sys.argv[1], sys.argv[2]
    id_docente_override = sys.argv[3] if len(sys.argv) == 4 else None

    login_payload = {
        "username": username,
        "password": password,
        "idSystem": ID_SYSTEM,
        "identifier": ip_publica(),
    }

    print("POST", LOGIN_URL)
    print("Body:", json.dumps({**login_payload, "password": "***"}, ensure_ascii=False))

    login_response = requests.post(
        LOGIN_URL,
        json=login_payload,
        headers={"Content-Type": "application/json"},
        timeout=15,
    )

    print("\nStatus:", login_response.status_code)
    try:
        raw_token = login_response.json()["content"]["token"]
    except ValueError:
        print(login_response.text)
        return

    token = raw_token.replace("Bearer", "").strip()
    claims = jwt.decode(token, options={"verify_signature": False})
    print(claims)

    id_docente = id_docente_override or str(claims.get("idLogueo") or "")
    if not id_docente:
        print("\nNo se encontró idLogueo en el token y no se pasó ID_DOCENTE por CLI.")
        raise SystemExit(1)

    aulas_url = AULAS_URL_TEMPLATE.format(id_docente=id_docente)
    print("\nGET", aulas_url)
    print("idDocente usado:", id_docente, "(override)" if id_docente_override else "(desde idLogueo)")

    aulas_response = requests.get(
        aulas_url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout=15,
    )

    print("\nStatus:", aulas_response.status_code)
    try:
        print(json.dumps(aulas_response.json(), ensure_ascii=False, indent=2))
    except ValueError:
        print(aulas_response.text)


if __name__ == "__main__":
    main()
