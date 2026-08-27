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

## Arquitectura

| Capa | Ubicación |
|---|---|
| Fábrica y configuración | `maxcim/__init__.py`, `maxcim/config.py` |
| Modelos | `maxcim/models/` |
| Rutas web, autenticación y API | `maxcim/routes/` |
| IA y almacenamiento | `maxcim/services/` |
| Datos ficticios | `maxcim/demo.py` |
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
