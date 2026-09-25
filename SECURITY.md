# Seguridad de MAXCIM

## Alcance del modo demostración

`DEMO_MODE=true` es un bypass de autenticación (acepta cualquier credencial, omite CSRF y autoriza toda llamada del robot). Solo funciona sobre SQLite aislada: el arranque falla si coexiste con una base remota. Nunca debe exponerse como servicio institucional ni almacenar datos de estudiantes reales.

## Controles incluidos

- Acceso docente por la API institucional de CIMA (usuario y contraseña o Google). Google usa Authorization Code, PKCE, `state`, `nonce`, validación del ID token en el servidor y restricción por dominio Workspace.
- El JWT de CIMA se guarda cifrado con Fernet dentro de la cookie de sesión firmada (`HttpOnly`, `SameSite=Lax`, `Secure` fuera de demo); nunca se guardan contraseñas.
- CSRF en todas las peticiones de escritura del navegador; la API del robot se autentica con un secreto compartido (`X-MAXCIM-Webhook-Secret`, comparación en tiempo constante).
- Bloqueo de intentos fallidos de login por IP y usuario, y un tope adicional por IP.
- Archivos de materiales fuera de `static/`, entregados con URLs firmadas y ligadas a la docente; bloqueo de traversal y enlaces simbólicos.
- Aulas y alumnos se revalidan contra CIMA en cada consulta; los identificadores en las URLs son tokens firmados.
- Validación de extensión y tamaño de los documentos, re-codificación de imágenes subidas (con tope de píxeles) y comprobación del WAV.
- Cabeceras: CSP (`script-src 'self'`), `nosniff`, anti-framing, `Referrer-Policy`, `no-store` en rutas sensibles y HSTS fuera de demo.
- El arranque falla con `DEMO_MODE=false` si `SECRET_KEY` o `MAXCIM_WEBHOOK_SECRET` son débiles, si la API institucional no usa HTTPS o si se desactiva la verificación TLS.
- Análisis Bandit, pruebas y actualizaciones de dependencias en GitHub.

## Antes de un uso institucional

1. `DEMO_MODE=false`, `SECRET_KEY` y `SESSION_TOKEN_ENCRYPTION_KEY` aleatorias y persistentes, y un `MAXCIM_WEBHOOK_SECRET` propio de al menos 32 caracteres.
2. TLS en un proxy confiable delante de Gunicorn, sin publicar el puerto HTTP de la aplicación.
3. Base MySQL con un usuario limitado al esquema (no `root`) y copias de seguridad probadas.
4. El bloqueo de login es en memoria: si se usa más de un worker, mover los contadores a un almacén compartido.
5. Definir retención, consentimiento y acceso a los datos educativos (documentos enviados a Gemini, audios e interacciones).
6. Rotar cualquier credencial que haya estado alguna vez en el historial de Git y purgarlo (ver `docs/security-remediation.md`).

Reporta vulnerabilidades de forma privada al responsable del repositorio; no publiques datos sensibles en un issue.
