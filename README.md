# MAXCIM · Demostración funcional

MAXCIM es una aplicación Flask que demuestra el flujo docente de un robot educativo orientado al fortalecimiento de habilidades sociocomunicativas. Incluye tablero de aulas, biblioteca inteligente de lecturas, generación demostrativa de audios y preguntas, y planificación de sesiones.

## Inicio rápido

Requisitos: Python 3.11 o superior.

```bash
python -m venv .venv
```

En Windows:

```powershell
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
python app.py
```

En Linux o macOS:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python app.py
```

Abre `http://127.0.0.1:5000`.

Credenciales ficticias incluidas:

- Correo: `docente@maxcim.demo`
- Contraseña: `MaxcimDemo2026!`

## Qué funciona sin servicios externos

- Inicio y cierre de sesión con protección CSRF.
- Dashboard responsive con datos ficticios.
- Lectura local de TXT, PDF y DOCX.
- Resumen y preguntas deterministas en modo demostración.
- Audio WAV demostrativo reproducible desde el navegador.
- Guardado privado de materiales y descargas autorizadas.
- Filtro por habilidad, búsqueda y eliminación de material.
- Creación y actualización de sesiones educativas.
- SQLite y datos iniciales automáticos.

## Activar Gemini real

Configura estas variables en `.env`:

```dotenv
DEMO_MODE=false
GOOGLE_API_KEY=tu_clave
```

El código usará los modelos configurados mediante `GEMINI_MODEL`, `GEMINI_TTS_MODEL` y `GEMINI_TTS_VOICE`.

## Activar el acceso oficial de CIMA

La autenticación institucional es independiente del modo de Gemini. Copia `.env.example` a `.env` y configura:

```dotenv
AUTH_PROVIDER=cima
SECRET_KEY=un_valor_aleatorio_largo_y_persistente
CIMA_TOKEN_ENCRYPTION_KEY=una_clave_fernet_independiente
CIMA_API_IDENTIFIER=identificador_confirmado_por_cima
CIMA_API_TEACHER_ID_CLAIM=claim_confirmado_por_cima
SESSION_COOKIE_SECURE=true
```

La clave Fernet se genera una vez con:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Después, cada docente escribe su correo institucional o usuario y su contraseña en `/login`. La contraseña se envía a la API CIMA únicamente durante el acceso y no se almacena. El JWT queda cifrado del lado servidor; la cookie solo contiene un identificador aleatorio de sesión.

La integración implementa los cuatro endpoints entregados por CIMA: autenticación con usuario, autenticación con correo, aulas del docente y alumnos del aula. La interfaz solo utiliza `idPerson`, nombre y apellido del alumno; descarta foto, correo institucional y DNI.

El proveedor todavía debe confirmar el nombre exacto del claim estable y único que contiene `idDocente`, además del significado operativo de `identifier`. Fuera de pruebas, MAXCIM no arranca sin ese claim explícito; también falla de forma cerrada si es inexistente y nunca sustituye una caída de CIMA con datos ficticios.

El arranque oficial exige HTTPS, verificación TLS y cookie `Secure`. Para una prueba estrictamente local sobre HTTP se puede activar conscientemente `CIMA_ALLOW_INSECURE_LOCAL_COOKIES=true`; esa excepción no debe usarse en un despliegue compartido.

Con `AUTO_CREATE_DB=true`, SQLAlchemy crea las tres tablas nuevas de integración. Antes de usar `AUTO_CREATE_DB=false` en una base institucional existente, el equipo de despliegue debe versionar y ejecutar la migración equivalente para `cima_identities`, `cima_sessions` y `cima_learning_sessions`.

## Activar el acceso institucional con Google

MAXCIM también permite que los docentes entren con su cuenta administrada de Google Workspace. Crea un cliente OAuth de tipo **Aplicación web** y registra exactamente esta URI local:

```text
http://127.0.0.1:5000/login/google/callback
```

En Google Auth Platform configura la audiencia como **Internal** para el Workspace de CIMA y completa el branding con datos institucionales. Si la consola solo permite audiencia **External**, agrega los usuarios de prueba y completa el proceso de publicación requerido antes de habilitar el sistema.

Luego configura:

```dotenv
AUTH_PROVIDER=google
SECRET_KEY=un_valor_aleatorio_largo_y_persistente
GOOGLE_OAUTH_CLIENT_ID=cliente_web.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=secreto_del_cliente_web
GOOGLE_OAUTH_REDIRECT_URI=http://127.0.0.1:5000/login/google/callback
GOOGLE_WORKSPACE_DOMAIN=colegiocima.edu.pe
GOOGLE_ALLOWED_TEACHER_EMAILS=docente1@colegiocima.edu.pe,docente2@colegiocima.edu.pe
GOOGLE_ALLOW_INSECURE_LOCAL_COOKIES=true
```

En producción, la redirección debe usar HTTPS, `SESSION_COOKIE_SECURE=true` y `GOOGLE_ALLOW_INSECURE_LOCAL_COOKIES=false`. El sistema verifica firma, audiencia, emisor, expiración, `state`, `nonce`, PKCE, `email_verified`, el claim `hd` del dominio Workspace y la lista exacta de docentes. Solo conserva el `sub` estable, el correo y el nombre; descarta los tokens de Google al terminar el acceso.

El dominio institucional no demuestra que una cuenta sea docente, porque también puede contener estudiantes. Por eso `GOOGLE_ALLOWED_TEACHER_EMAILS` es obligatorio. Para automatizar esa autorización en el futuro se necesita una fuente institucional de roles o grupos.

Importante: el acceso de Google autentica al docente en MAXCIM, pero el documento entregado por CIMA solo permite obtener su JWT mediante usuario/contraseña. MAXCIM no envía un token de Google a endpoints no documentados ni simula aulas. CIMA debe proporcionar un intercambio de tokens o una autorización servidor-a-servidor antes de mostrar aulas con `AUTH_PROVIDER=google`. Consulta [`docs/GOOGLE_INSTITUTIONAL_LOGIN.md`](docs/GOOGLE_INSTITUTIONAL_LOGIN.md).

Con `AUTO_CREATE_DB=true`, SQLAlchemy crea `google_identities`. En una base institucional con `AUTO_CREATE_DB=false`, crea y ejecuta primero una migración versionada equivalente.

## Arquitectura

| Capa | Ubicación |
|---|---|
| Fábrica y configuración | `maxcim/__init__.py`, `maxcim/config.py` |
| Modelos | `maxcim/models/` |
| Rutas web, autenticación y API | `maxcim/routes/` |
| IA y almacenamiento | `maxcim/services/` |
| Datos ficticios | `maxcim/demo.py` |
| Cliente oficial CIMA | `maxcim/services/cima_api.py` |
| Sesiones CIMA cifradas | `maxcim/services/cima_session.py`, `maxcim/models/cima.py` |
| Identidad institucional Google | `maxcim/services/google_identity.py`, `maxcim/models/google.py` |
| Interfaz | `templates/`, `static/` |
| Pruebas | `tests/` |

Los documentos generados se almacenan en `instance/uploads/`, fuera del directorio público. Cada consulta valida que el material pertenezca al usuario autenticado.

## Calidad

```bash
python -m pip install -r requirements-dev.txt
ruff check .
bandit -q -r maxcim app.py wsgi.py
pytest --cov=maxcim --cov-report=term-missing --cov-fail-under=75
```

La matriz de aceptación que convierte la evaluación original en una demostración verificable está en [`docs/DEMO_AUDIT.md`](docs/DEMO_AUDIT.md). La política y el checklist para operar fuera del modo demostración están en [`SECURITY.md`](SECURITY.md).

## Despliegue demostrativo

El repositorio incluye `Dockerfile`, `Procfile`, `railway.toml` y el endpoint público `/health`. Para un despliegue persistente configura `DATABASE_URL`, `SECRET_KEY`, cookies seguras y un volumen para `UPLOAD_FOLDER`.

## Alcance

Esta versión está preparada para demostrar el funcionamiento completo con datos ficticios. Antes de usarla con estudiantes reales se requiere evaluación institucional de privacidad, retención de información, consentimiento, copias de seguridad y operación del proveedor de IA.
