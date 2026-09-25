# Remediación de la auditoría de seguridad

Registro de los cambios aplicados sobre los 23 hallazgos de `SECURITY_AUDIT.md`.
Cada entrada indica qué se cambió en el repo y qué queda como trabajo
operativo (rotación de secretos, infraestructura, historial Git) que el código
no puede resolver por sí solo.

## C-01 — Credencial institucional real versionada

**Estado:** código corregido. Rotación e historial: pendientes (operativo).

Antes, las pruebas y la documentación de integración usaban una credencial de
CIMA con pinta de real y la identidad de una persona concreta:

| Valor retirado | Reemplazo ficticio |
|---|---|
| usuario `orodasr` / `sub: orodasr` | `docente.demo` |
| contraseña `72737674` | `clave-demo-no-real` |
| `idPersona: 70385` | `1000001` |
| `RODAS ROSALES OSCAR ALEXIS` / `Rodas Rosales Oscar Alexis` | `DOCENTE DEMO UNO` / `Docente Demo Uno` |
| `idLogueo: 9716` | `500001` |
| `oscar.rodas@colegiocima.edu.pe` | `docente.demo@colegiocima.edu.pe` |

Archivos: `tests/test_institutional.py`, `tests/test_google_login.py`,
`tests/test_materials_robot_api.py`, `services/institutional.py` (comentario),
`models.py` (comentarios), `docs/integration-contract.md` (ejemplos).

`tests/test_institutional.py` lleva ahora un comentario en `make_cima_jwt`
dejando constancia de que **antes había datos reales** y de que las pruebas
deben correr siempre con valores ficticios.

**Pendiente (operativo, urgente):**

1. Rotar `orodasr` / `72737674` contra CIMA y revisar los logs de acceso de
   esa cuenta por uso no autorizado.
2. Purgar el valor del historial Git (`git filter-repo` o BFG) y forzar push;
   avisar a quien tenga clones.
3. Añadir secret scanning en CI y en pre-commit (p.ej. gitleaks o trufflehog).

## C-02 — Secreto del robot igual al marcador público

**Estado:** código corregido. Rotación del valor real: aplicada en el `.env`
local; falta coordinar el nuevo valor con el robot y purgar el historial.

- `app.py`: nuevo helper `_require_strong_secret()` y `PUBLISHED_PLACEHOLDER_SECRETS`.
  En `create_app`, con `DEMO_MODE=false` y fuera de `TESTING`, el arranque
  **falla** si `MAXCIM_WEBHOOK_SECRET` está vacío, es un marcador de
  `.env.example` (`cambia-este-secreto-compartido`, `maxcim-demo-isolated-webhook`,
  `changeme`, sin distinguir mayúsculas) o mide menos de 32 caracteres.
- `.env.example`: `MAXCIM_WEBHOOK_SECRET` queda vacío con instrucción de
  generación.
- `.env` local: el marcador se reemplazó por un valor aleatorio de 64 hex.
- Pruebas: `tests/test_interactions.py` usa un secreto de 45 chars y añade
  `test_create_app_rejects_weak_webhook_secret_in_production` (parametrizado:
  vacío, marcador, marcador en mayúsculas, corto).

**Pendiente (operativo):**

1. Poner el mismo valor nuevo en la configuración del robot MAXCIM.
2. Guardar el secreto en un gestor de secretos, no en `.env` plano en el host.
3. Un secreto distinto por robot cuando haya más de uno.
4. Revisar logs de `/api/*` por uso previo del marcador público.
5. Purgar `cambia-este-secreto-compartido` del historial Git junto con C-01.

## A-01 — HTTP directo y cookie de sesión sin `Secure`

**Estado:** código corregido. Terminación TLS: pendiente (operativo).

La sesión de la docente viaja entera en la cookie firmada `maxcim_session`
(incluye el JWT de CIMA cifrado con Fernet). El `.env` ponía
`SESSION_COOKIE_SECURE=false` y ese valor llegaba al despliegue real.

- `app.py` `create_app`, con `DEMO_MODE=false` y fuera de `TESTING`:
  - `SESSION_COOKIE_SECURE` se **fuerza a `True`** ignorando el `.env` (se
    registra un warning si venía en `false`).
  - `PREFERRED_URL_SCHEME="https"`.
  - `app.wsgi_app` se envuelve con `ProxyFix(x_for=1, x_proto=1, x_host=1)`
    para leer esquema/host reales del terminador TLS.
- `add_security_headers`: cabecera `Strict-Transport-Security:
  max-age=63072000; includeSubDomains` en no-demo.
- Los tres puntos que armaban URLs externas (`google_redirect_uri` y dos rutas
  de la API robot) usan `PREFERRED_URL_SCHEME` en vez de inferir de la cookie.
- `.env.example`: comentario aclarando que `SESSION_COOKIE_SECURE` solo aplica
  en demo; en no-demo se ignora.
- Prueba: `test_create_app_forces_https_session_in_production`.

**Pendiente (operativo):**

1. Poner un terminador TLS delante de Gunicorn (Caddy/nginx/Traefik) que
   además redirija HTTP→HTTPS.
2. Dejar de publicar el puerto HTTP de Gunicorn hacia el exterior en
   `docker-compose.yml` / el host.

## A-02 — `DEMO_MODE` es fail-open

**Estado:** código corregido.

Demo es un bypass de autenticación completo (cualquier credencial, login
Google de un clic, toda llamada robot autorizada, CSRF omitido). Antes se
activaba solo con que faltara la variable.

- `app.py:108`: `env_bool("DEMO_MODE", False)`. Olvidar la variable ahora
  arranca en producción, no en demo.
- `app.py` `create_app`: con `DEMO_MODE=true` y fuera de `TESTING`, si la base
  efectiva no es `sqlite:` el arranque **falla** con `RuntimeError`. Cubre el
  escenario del hallazgo: contenedor con MySQL persistente y demo olvidado.
- `.env.example`: comentario explicando que demo es un bypass, que el default
  es producción y que no puede convivir con MySQL.
- Prueba: `test_create_app_refuses_demo_mode_on_a_remote_database`.

No se añadió un segundo flag de confirmación: el check de SQLite ya cubre el
caso realista (un despliegue real siempre tiene base real). Detectar hostname
público o volúmenes persistentes desde el proceso no es fiable.

## A-03 — La API robot permite lecturas entre todos los tenants

**Estado:** endurecido (defensa en profundidad). Sigue con un secreto único
compartido: hay un solo robot, así que no se hicieron credenciales por robot.
El objetivo del cambio es que un secreto filtrado no permita barrer la base.

- `get_material` (`GET /api/materials/<id>`): el identificador de la docente
  pasa a ser **obligatorio** (`require_identifier=True`), igual que ya lo
  exigía la descarga por archivo. Sin él ya no se recorren los IDs enteros.
- `list_interacciones` (`GET /api/interacciones`): exige identificador de
  docente y filtra por dueño con un `JOIN` a `Material.fk_user`. Solo devuelve
  interacciones de materiales de esa docente.
- `download_interaccion_audio` (`GET /api/interacciones/<id>/audio`): exige
  identificador y verifica que el material de la interacción pertenece a la
  docente; `403` en caso contrario.
- `docs/integration-contract.md` §2.2, §2.3.1 y §2.4 actualizados.
- Pruebas actualizadas en `test_materials_robot_api.py`, `test_interactions.py`
  y `test_demo_environment.py`.

**Enganchado con A-05:** las conversaciones libres (`id_material` NULL) no
tienen dueña, así que con este filtro **no las devuelve la API del robot**.
Se cierra en A-05 dándoles docente + aula.

**Pendiente (si algún día hay más de un robot):** credencial por robot ligada
a una docente/tenant y derivar la docente del principal autenticado en vez del
query param.
