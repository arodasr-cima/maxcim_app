# Contrato de integración de MAXCIM App

Este contrato cubre dos cosas separadas:

1. Cómo inicia sesión la docente (usuario/credencial o Google), contra la API institucional.
2. Cómo lee y escribe el robot en las dos tablas propias de MAXCIM: `material` e `interaccion` (ver [bd_app.sql](../bd_app.sql)).

MAXCIM no hace reconocimiento facial ni gestiona sesiones de interacción: el robot resuelve por su cuenta qué alumno tiene enfrente y qué material está usando, y solo reporta el resultado de cada turno.

## 1. Autenticación docente (usuario/credencial)

La ruta se configura mediante `INSTITUTIONAL_API_LOGIN_PATH`.

```http
POST {INSTITUTIONAL_API_BASE_URL}{INSTITUTIONAL_API_LOGIN_PATH}
Content-Type: application/json
```

```json
{
  "institutional_id": "<id_docente>",
  "credential": "<credencial_institucional>"
}
```

Respuesta canónica que consume el adaptador actual:

```json
{
  "access_token": "<token>",
  "expires_in": 3600,
  "teacher": {
    "id": "<id_docente>",
    "display_name": "<nombre_visible>",
    "role": "DOCENTE",
    "status": "ACTIVO"
  }
}
```

Solo `DOCENTE/TEACHER` con estado `ACTIVO/ACTIVE` puede entrar. El `access_token` se cifra y se guarda dentro de la propia cookie de sesión del navegador (no hay tabla de sesiones en el servidor) y nunca se devuelve al frontend en texto plano.

Con `DEMO_MODE=true` (el valor por defecto en este repositorio) esta llamada no ocurre: `DemoInstitutionalClient.authenticate()` fabrica una docente de prueba fija en memoria.

### 1.1 Acceso docente con Google

La aplicación realiza OpenID Connect con Google mediante autorización de
servidor, `state`, `nonce` y PKCE. Valida la firma, audiencia, expiración, correo
verificado y el dominio Workspace permitido. Después envía el ID token a la API
institucional; no crea una docente usando únicamente los datos de Google.

La ruta se configura mediante `INSTITUTIONAL_API_GOOGLE_LOGIN_PATH`.

```http
POST {INSTITUTIONAL_API_BASE_URL}{INSTITUTIONAL_API_GOOGLE_LOGIN_PATH}
Content-Type: application/json
```

```json
{
  "id_token": "<id_token_firmado_por_google>"
}
```

La API institucional debe volver a validar el ID token, asociar `sub` o el correo
con un registro docente activo y devolver la misma respuesta canónica de la
sección 1. Una cuenta Google no asociada debe responder `401` o `403`.

El callback público que se registra exactamente en Google Cloud es:

```text
https://<dominio-maxcim>/auth/google/callback
```

MAXCIM descarta los tokens de Google después del canje y conserva únicamente el
token institucional, cifrado dentro de la cookie de sesión.

Con `DEMO_MODE=true`, el botón "Continuar con Google" también entra directo con la docente de prueba, sin contactar a Google ni a la API institucional.

## 2. Aulas asignadas

Usada por `/dashboard` y `/sesiones` para listar las aulas de la docente autenticada. La ruta se configura mediante `INSTITUTIONAL_API_CLASSROOMS_PATH` y admite `{teacher_id}`.

```http
GET {base}{INSTITUTIONAL_API_CLASSROOMS_PATH}
Authorization: Bearer <token_docente>
```

```json
{
  "classrooms": [
    {
      "id": "<id_aula>",
      "name": "<nombre_aula>",
      "grade": "<grado_o_nivel>",
      "course": "<curso_o_area>",
      "period": "<periodo_activo>"
    }
  ]
}
```

`id` y `name` son obligatorios. Los demás campos pueden ser `null` o cadena vacía.

Nota: la tabla `interaccion` no guarda a qué aula pertenece cada turno (ver `bd_app.sql`), así que el dashboard no puede desglosar el desempeño por aula con datos propios; solo muestra el listado que devuelve esta llamada.

## 3. Materiales que consulta el robot (`material`)

Rutas robot-side. Requieren el header `X-MAXCIM-Webhook-Secret` con el valor de `MAXCIM_WEBHOOK_SECRET` (se omite mientras `DEMO_MODE=true`).

```http
GET /api/materials?teacher_id=<id_docente>
X-MAXCIM-Webhook-Secret: <secreto>
```

```http
GET /api/materials/{id}
X-MAXCIM-Webhook-Secret: <secreto>
```

Respuesta por material:

```json
{
  "id": 12,
  "titulo": "<nombre_material>",
  "tipo_material": "<tipo_material>",
  "fecha_subido": "2026-08-27",
  "fk_user": "<id_docente>",
  "texto_completo_url": "https://.../texto.txt",
  "texto_resumen_url": "https://.../resumen.txt",
  "audio_completo_url": "https://.../audio.wav",
  "audio_resumen_url": "https://.../audio_resumen.wav",
  "preguntas_url": "https://.../preguntas.json",
  "preguntas": [
    {"pregunta": "<enunciado>", "respuesta_esperada": "<respuesta_esperada>"}
  ]
}
```

`preguntas` se lee en el momento desde el archivo JSON guardado junto al material (tal como lo aprobó la docente); no vive en una tabla propia.

## 4. Interacciones que registra el robot (`interaccion`)

El robot ya identificó al alumno y decidió qué material está usando. Reporta cada turno de pregunta/respuesta con una sola llamada:

```http
POST /api/interacciones
X-MAXCIM-Webhook-Secret: <secreto>
Content-Type: application/json
```

```json
{
  "id_material": 12,
  "fk_alumno": "<id_alumno_institucional>",
  "pregunta": "<pregunta_narrada_por_maxcim>",
  "respuesta": "<transcripcion_de_la_respuesta>",
  "path_audio_rpta": "uploads/<ruta_relativa_al_audio_de_la_respuesta>",
  "apreciacion_robot": "<comentario_o_critica_del_robot>",
  "rpta_correcta": true
}
```

Todos los campos son obligatorios. `id_material` debe existir en `material`; `fk_alumno` no se valida contra la API institucional (el robot es responsable de esa identificación). Respuesta `201` con el registro creado.

> **Pendiente de definir:** `path_audio_rpta` se recibe como una ruta ya resuelta bajo `static/`, no como un archivo subido en esta misma llamada. Falta acordar cómo llega ese archivo de audio al servidor (¿el robot lo sube por otro medio? ¿se agrega un endpoint de subida?) antes de integrar un robot real.

Consulta de historial:

```http
GET /api/interacciones?id_material=<id>&fk_alumno=<id_alumno>
X-MAXCIM-Webhook-Secret: <secreto>
```

Ambos parámetros son opcionales y se pueden combinar; devuelve hasta 200 registros, más reciente primero.

## 5. Requisitos antes de habilitar producción

- HTTPS válido.
- Swagger/OpenAPI o respuestas anonimizadas aprobadas por el responsable de la API institucional.
- Secretos distintos por ambiente (`MAXCIM_WEBHOOK_SECRET`, `SESSION_TOKEN_ENCRYPTION_KEY`, `SECRET_KEY`).
- Rotación periódica de esos secretos.
- Esquema `bd_app.sql` aplicado en la base de destino (`material` + `interaccion`).
- Definir cómo llega al servidor el audio de cada interacción (ver nota de la sección 4).
- Política institucional de retención para audio y transcripciones de interacciones con menores.
- Auditoría y respaldo de MySQL.
