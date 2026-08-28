# Acceso institucional de Google en MAXCIM

## Alcance implementado

El proveedor `AUTH_PROVIDER=google` usa OpenID Connect mediante Authorization Code. La aplicación:

1. genera `state`, `nonce` y un verificador PKCE;
2. redirige al cliente OAuth web de Google;
3. intercambia el código exclusivamente desde el servidor;
4. valida la firma, audiencia, emisor y expiración del ID token;
5. exige `email_verified=true`, el claim `hd=colegiocima.edu.pe` y un correo incluido en `GOOGLE_ALLOWED_TEACHER_EMAILS`;
6. vincula el `sub` inmutable de Google a un usuario docente local;
7. descarta el ID token y los tokens OAuth después del acceso.

El intercambio de código y la descarga de certificados públicos para validar el
ID token tienen un tiempo máximo configurable mediante
`GOOGLE_OAUTH_TIMEOUT_SECONDS` (10 segundos por defecto). Así no quedan procesos
ocupados indefinidamente cuando Google o la red no responden.

## Configuración de Google Cloud

- Tipo de cliente: **Aplicación web**.
- En **Google Auth Platform → Audience**, usa **Internal** para limitar el acceso al Workspace de CIMA. Si la organización obliga a usar **External**, registra primero los usuarios de prueba y completa la publicación/verificación exigida por Google antes del despliegue.
- En **Branding**, configura el nombre, dominio y contactos institucionales; no uses una marca o correo personal.
- Desarrollo local: `http://127.0.0.1:5000/login/google/callback`.
- Producción: `https://<dominio-oficial>/login/google/callback`.
- Scopes solicitados: `openid`, `email` y `profile`.
- La URI configurada en Google Cloud y `GOOGLE_OAUTH_REDIRECT_URI` deben coincidir exactamente.

No guardes el JSON descargado del cliente OAuth, secretos ni credenciales personales en Git.

## Autorización de docentes

El claim `hd` demuestra que la cuenta pertenece al Workspace, pero no contiene el rol docente. MAXCIM exige una lista exacta y explícita de correos para impedir el acceso de estudiantes u otras cuentas institucionales. Una sustitución futura puede consultar un directorio o grupo administrado, siempre que CIMA autorice ese origen de roles.

## Límite actual con la API CIMA

La API documentada obtiene su Bearer JWT únicamente mediante contraseña. Google no entrega esa contraseña y su ID token no debe enviarse como sustituto. En modo Google, MAXCIM permite el acceso docente y las funciones locales privadas, pero presenta las aulas como pendientes de integración y nunca usa datos ficticios como reemplazo.

Para completar el acceso a aulas y alumnos, CIMA debe documentar una de estas capacidades:

- intercambio de un ID token de Google por un JWT CIMA;
- endpoint de sesión federada;
- credencial servidor-a-servidor con autorización por docente.

La respuesta debe definir audiencia, emisor, claim de `idDocente`, expiración, revocación y errores. Hasta entonces, ambos proveedores (`cima` y `google`) permanecen separados.
