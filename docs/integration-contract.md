# Contrato de integración de MAXCIM App

Este contrato separa la sesión web de la docente, la identidad detectada por el sistema facial y la credencial técnica de MAXCIM. La aplicación no recibe ni almacena datos biométricos.

## 1. Autenticación docente

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

Solo `DOCENTE/TEACHER` con estado `ACTIVO/ACTIVE` puede entrar. El token se cifra en la base propia y nunca se devuelve al navegador.

### 1.1 Acceso docente con Google Workspace

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
token institucional cifrado.

## 2. Aulas asignadas

La ruta se configura mediante `INSTITUTIONAL_API_CLASSROOMS_PATH` y admite `{teacher_id}`.

```http
GET {base}/v1/teachers/{teacher_id}/classrooms
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

## 3. Validación del ID reconocido

La ruta se configura mediante `INSTITUTIONAL_API_STUDENT_PATH` y admite `{person_id}`. Esta llamada usa `INSTITUTIONAL_API_SERVICE_TOKEN`; no usa el token de una docente.

```http
GET {base}/v1/students/{person_id}
Authorization: Bearer <service_token>
```

```json
{
  "student": {
    "id": "<id_alumno>",
    "display_name": "<nombre_visible>",
    "role": "ALUMNO",
    "status": "ACTIVO",
    "classroom_ids": ["<id_aula_activa>"]
  }
}
```

La sesión oral solo se activa cuando:

- el registro corresponde a `ALUMNO/STUDENT`;
- el estado es `ACTIVO/ACTIVE`;
- `classroom_ids` contiene el aula seleccionada por la docente;
- la confianza facial alcanza `FACE_MATCH_MIN_CONFIDENCE`.

Si el contrato oficial utiliza otros nombres o una estructura distinta, se modifica únicamente el adaptador `services/institutional.py` después de recibir documentación autorizada.

## 4. Evento facial enviado a MAXCIM App

El servicio facial aporta únicamente el identificador detectado. Nombre, rol y matrícula recibidos desde el dispositivo no se consideran confiables.

```http
POST /api/integrations/face-recognition/events
X-MAXCIM-Webhook-Secret: <secreto>
Content-Type: application/json
```

```json
{
  "session_uuid": "<uuid_sesion>",
  "person_id": "<id_detectado>",
  "confidence": 0.97
}
```

Resultados: `aceptado`, `requiere_confirmacion` o `ignorado`.

## 5. Material que recibe el robot

```http
GET /api/interactions/sessions/{session_uuid}/robot-payload
X-MAXCIM-Webhook-Secret: <secreto>
```

La respuesta contiene:

- objetivo pedagógico;
- ID y nombre ya validados del alumno;
- URL del texto completo y resumen;
- URL del audio completo y audio resumen;
- duración objetivo seleccionada por la docente y duración real medida del audio;
- preguntas aprobadas, respuesta esperada, tipo y orden.

Con esta respuesta MAXCIM puede narrar el cuento generado por la miss y continuar con las preguntas revisadas.

Campos de duración incluidos dentro de `material`:

```json
{
  "target_duration_minutes": 5,
  "audio_duration_seconds": 298.42
}
```

La duración es un objetivo: Gemini controla el ritmo mediante instrucciones y la
aplicación ajusta la cantidad de palabras. El valor `audio_duration_seconds` es la
medición real del WAV que MAXCIM reproducirá completo.

## 6. Turnos orales

```http
POST /api/interactions/sessions/{session_uuid}/turns
X-MAXCIM-Webhook-Secret: <secreto>
Content-Type: application/json
```

Pregunta de MAXCIM:

```json
{
  "speaker": "MAXCIM",
  "question_id": 81,
  "transcript": "<pregunta_narrada>"
}
```

Respuesta del alumno:

```json
{
  "speaker": "ALUMNO",
  "question_id": 81,
  "transcript": "<transcripcion_real>",
  "response_time_ms": 4200,
  "is_correct": true,
  "needed_help": false,
  "audio_path": null
}
```

`is_correct` puede ser `null` en preguntas abiertas o cuando no exista evidencia suficiente.

## 7. Cierre y revisión

MAXCIM llama `POST /api/interactions/sessions/{uuid}/complete`. La aplicación calcula métricas objetivas y solicita la propuesta cualitativa a Gemini. El resultado no es definitivo hasta que la docente autenticada realiza `PATCH /api/interactions/sessions/{uuid}/evaluation`.

## 8. Requisitos antes de habilitar producción

- HTTPS válido.
- Swagger/OpenAPI o respuestas anonimizadas aprobadas por el responsable de la API.
- Secretos distintos por ambiente.
- Rotación del token técnico y del secreto del robot.
- Migraciones `001_interacciones.sql` y `002_sesiones_web.sql` aplicadas.
- Política institucional de retención para audio y transcripciones de menores.
- Auditoría y respaldo de MySQL.
