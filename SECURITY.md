# Seguridad de MAXCIM

## Alcance de la demostración

La cuenta `docente@maxcim.demo` y su contraseña visible son exclusivamente ficticias. El modo demostración no debe almacenar información de estudiantes reales ni exponerse como un servicio institucional.

## Controles incluidos

- Contraseñas con hash seguro y sesiones `HttpOnly`/`SameSite`.
- CSRF en formularios y solicitudes JavaScript.
- Límites de frecuencia para acceso, IA y operaciones de escritura.
- Validación de extensión, tamaño, texto, preguntas y encabezado WAV.
- Archivos fuera de `static/`, con autorización por propietario y bloqueo de traversal.
- CSP, anti-framing, `nosniff`, políticas de origen, no-cache privado y HSTS al activar HTTPS.
- Datos iniciales ficticios solo cuando el modo demostración está activo.
- Análisis Bandit, pruebas y actualizaciones de dependencias en GitHub.
- El JWT de CIMA se cifra con una clave Fernet independiente y se guarda del lado servidor; nunca se guarda la contraseña ni el token en la cookie.
- Cada consulta de alumnos vuelve a comprobar que el aula pertenece al docente autenticado.
- La vista de alumnos descarta DNI, correo y fotografía recibidos desde CIMA.
- El acceso Google usa Authorization Code, PKCE, `state`, `nonce` y validación del ID token en el servidor.
- Google se restringe por el claim Workspace `hd` y por una lista exacta de correos docentes; los tokens no se persisten.

## Antes de un uso institucional

1. Configura `DEMO_MODE=false`, `SEED_DEMO_DATA=false` y una `SECRET_KEY` aleatoria persistente.
2. Activa `SESSION_COOKIE_SECURE=true` y termina TLS en un proxy confiable.
3. Usa PostgreSQL o MySQL administrado, migraciones versionadas y copias de seguridad probadas.
4. Configura almacenamiento privado persistente y un backend compartido para `RATELIMIT_STORAGE_URI`.
5. Define retención, consentimiento, acceso, auditoría e incident response para datos educativos.
6. Ejecuta revisión de dependencias, DAST, restauración y carga antes de aceptar usuarios reales.
7. Confirma con CIMA el claim exacto de `idDocente`, la semántica de `identifier`, la duración del JWT y el contrato de errores.
8. Mantén `CIMA_API_VERIFY_TLS=true`; no uses una cuenta personal compartida ni guardes credenciales en `.env`.
9. Confirma que el claim docente sea estable y único antes de asociarlo a materiales o sesiones privadas.
10. Ejecuta una migración versionada de las tablas CIMA antes de desactivar `AUTO_CREATE_DB`.
11. En Google OAuth registra una URI exacta por entorno, usa HTTPS y conserva el secreto únicamente en variables protegidas.
12. Mantén una fuente autorizada para la lista docente; no trates la pertenencia al dominio como prueba del rol.
13. Ejecuta una migración versionada para `google_identities` antes de desactivar `AUTO_CREATE_DB`.

El SQL heredado fue retirado del árbol actual. Si alguna revisión confirma que sus versiones históricas contenían datos reales, habrá que purgar el historial Git y coordinar una nueva clonación; este cambio no reescribe historia automáticamente.

Reporta vulnerabilidades de forma privada al responsable del repositorio; no publiques datos sensibles en un issue.
