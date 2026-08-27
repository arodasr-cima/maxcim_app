# Contrato de integración de MAXCIM App

Este documento separa tres identidades: la sesión web de la docente, la identidad institucional reconocida por la cámara y la credencial técnica de MAXCIM. Ninguna contraseña ni dato biométrico debe llegar a la base de esta app.

## 1. Datos necesarios de la API institucional

El equipo de la base principal debe confirmar:

| Dato | Ejemplo esperado |
|---|---|
| URL base y ambientes | `https://api.colegio.example/v1` |
| Inicio de sesión | método, ruta, cuerpo y tipo de token/cookie |
| Perfil activo | ID institucional, nombres, rol, estado y sede |
| Aulas de la docente | ID canónico, nombre, grado, curso y periodo |
| Alumnos por aula | ID canónico, nombre visible y matrícula activa |
| Expiración | duración y mecanismo de renovación del token |
| Errores | códigos para credenciales, cuenta inactiva y servicio caído |

Reglas mínimas:

- Solo un perfil institucional activo con rol docente puede entrar a la consola.
- Las aulas y materiales visibles se filtran por el ID docente autenticado; nunca por un ID recibido libremente desde el navegador.
- Antes de activar la sesión se valida que el ID de alumno reconocido tenga matrícula activa en el aula seleccionada.
- Si la confianza facial es menor que `FACE_MATCH_MIN_CONFIDENCE`, la sesión queda esperando confirmación y no se asocia al alumno.

## 2. Evento del reconocimiento facial

```http
POST /api/integrations/face-recognition/events
X-MAXCIM-Webhook-Secret: <secreto>
Content-Type: application/json
```

```json
{
  "session_uuid": "2e3779c5-3f22-4d6d-899c-3e01c31f8712",
  "person_id": "ALU-1042",
  "person_type": "ALUMNO",
  "display_name": "Valeria Mendoza",
  "confidence": 0.97,
  "classroom_ids": ["AULA-3A-2026"]
}
```

Resultados posibles: `aceptado`, `requiere_confirmacion` o `ignorado`. En producción, `classroom_ids` es obligatorio y debe provenir de la matrícula institucional activa; la sesión solo comienza si contiene el aula seleccionada. El nombre es una instantánea visible; `person_id` es la referencia canónica. No se reciben imágenes ni embeddings.

## 3. Material que consume MAXCIM

```http
GET /api/interactions/sessions/{session_uuid}/robot-payload
X-MAXCIM-Webhook-Secret: <secreto>
```

La respuesta incluye el objetivo y el alumno ya asociado. Si la docente eligió una conversación libre, `material` será `null`; de lo contrario contiene las URLs del texto/audio y únicamente preguntas con estado `aprobada`. Cada pregunta contiene `id`, `statement`, `expected_answer`, `type` y `order`.

## 4. Registro de turnos orales

Pregunta de MAXCIM:

```json
{
  "speaker": "MAXCIM",
  "question_id": 81,
  "transcript": "¿Qué hizo el personaje para ayudar?"
}
```

Respuesta del alumno:

```json
{
  "speaker": "ALUMNO",
  "question_id": 81,
  "transcript": "La escuchó sin interrumpir.",
  "response_time_ms": 4200,
  "is_correct": true,
  "needed_help": false,
  "audio_path": null
}
```

`is_correct` debe provenir de la comparación entre la respuesta oral y el criterio aprobado por la docente. Puede ser `null` cuando la pregunta sea abierta o no exista evidencia suficiente.

## 5. Cierre y revisión

MAXCIM llama `POST /api/interactions/sessions/{uuid}/complete`. La app calcula participación, comprensión, promedio de respuesta e indicadores orales. El resultado queda en `pendiente_revision` o `pendiente_ia`; nunca se publica como definitivo sin el `PATCH` de aprobación de la docente.

## 6. Seguridad para producción

- HTTPS obligatorio.
- `DEMO_MODE=false`.
- Secretos diferentes por ambiente y rotación programada.
- Validación de firma o secreto para cada webhook.
- Límite de tasa y tamaño para transcripciones.
- Registro de auditoría para cambios de preguntas y evaluaciones.
- Política institucional de retención para audio y transcripciones de menores.
