"""Prueba de conexión con la API institucional CIMA: login + aulas + alumnos.

Duplicado de probar_conexion_aulas.py que además encadena la llamada al
endpoint de alumnos de un aula, para observar la forma real de esa
respuesta antes de mapearla en services/institutional.py.

1. POST https://apicima.colegiocima.edu.pe:8086/api/v2/authentication/with/user
2. GET  https://apicima.colegiocima.edu.pe:8086/api/v2/gradesection/list/group/user/{idLogueo}
3. GET  https://apicima.colegiocima.edu.pe:8086/api/v2/studentschool/list/gradesectiongroup/{idGradoSection}/type/{type}/order/{order}
   con Authorization: Bearer <token> — {idGradoSection} y {type} salen del
   primer aula devuelta en el paso 2 (o del ID que pases por CLI); {order}
   siempre se manda "A" (ascendente).

Uso:
    python probar_conexion_alumnos.py USUARIO CONTRASENA [ID_AULA] [TYPE]

ID_AULA y TYPE son opcionales: si no se indican, se usa la primera aula que
devuelva el listado del paso 2.
"""

import json
import sys

import requests
import jwt

LOGIN_URL = "https://apicima.colegiocima.edu.pe:8086/api/v2/authentication/with/user"
AULAS_URL_TEMPLATE = (
    "https://apicima.colegiocima.edu.pe:8086/api/v2/gradesection/list/group/user/{id_docente}"
)
ALUMNOS_URL_TEMPLATE = (
    "https://apicima.colegiocima.edu.pe:8086/api/v2/studentschool/list/gradesectiongroup/"
    "{id_aula}/type/{tipo}/order/{orden}"
)
ID_SYSTEM = 21


def ip_publica() -> str:
    """Devuelve la IP pública de tu conexión a internet."""
    return requests.get("https://api.ipify.org", timeout=10).text.strip()


def main() -> None:
    if len(sys.argv) not in (3, 4, 5):
        print("Uso: python probar_conexion_alumnos.py USUARIO CONTRASENA [ID_AULA] [TYPE]")
        raise SystemExit(2)

    username, password = sys.argv[1], sys.argv[2]
    id_aula_override = sys.argv[3] if len(sys.argv) >= 4 else None
    tipo_override = sys.argv[4] if len(sys.argv) == 5 else None

    login_payload = {
        "username": username,
        "password": password,
        "idSystem": ID_SYSTEM,
        "identifier": ip_publica(),
    }

    print("POST", LOGIN_URL)
    login_response = requests.post(
        LOGIN_URL,
        json=login_payload,
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    print("Status:", login_response.status_code)
    try:
        raw_token = login_response.json()["content"]["token"]
    except ValueError:
        print(login_response.text)
        return

    token = raw_token.replace("Bearer", "").strip()
    claims = jwt.decode(token, options={"verify_signature": False})
    id_logueo = str(claims.get("idLogueo") or "")
    print("idLogueo:", id_logueo)

    id_aula = id_aula_override
    tipo = tipo_override

    if not id_aula:
        aulas_url = AULAS_URL_TEMPLATE.format(id_docente=id_logueo)
        print("\nGET", aulas_url)
        aulas_response = requests.get(
            aulas_url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=15,
        )
        print("Status:", aulas_response.status_code)
        aulas = aulas_response.json()
        if not aulas:
            print("\nEl docente no tiene aulas; pasa ID_AULA y TYPE por CLI para probar igual.")
            return
        primera = aulas[0]
        id_aula = str(primera["id"])
        tipo = tipo or str(primera.get("type") or "N")
        print("Primera aula:", json.dumps(primera, ensure_ascii=False))

    tipo = tipo or "N"

    alumnos_url = ALUMNOS_URL_TEMPLATE.format(id_aula=id_aula, tipo=tipo, orden="A")
    print("\nGET", alumnos_url)
    alumnos_response = requests.get(
        alumnos_url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout=15,
    )
    print("Status:", alumnos_response.status_code)
    try:
        print(json.dumps(alumnos_response.json(), ensure_ascii=False, indent=2))
    except ValueError:
        print(alumnos_response.text)


if __name__ == "__main__":
    main()
