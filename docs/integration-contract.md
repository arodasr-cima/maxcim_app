# Contrato de integración de MAXCIM App

Este documento describe el contrato vigente entre tres participantes:

1. La consola docente de MAXCIM, que consume identidad y matrícula desde la API institucional.
2. El robot, que consulta materiales y registra o consulta interacciones mediante la API de MAXCIM.
3. La base propia de MAXCIM, que contiene únicamente `material` e `interaccion` (ver [bd_app.sql](../bd_app.sql)).

MAXCIM no realiza reconocimiento facial ni gestiona sesiones de interacción. Docentes, aulas y alumnos nunca se persisten localmente.

## 1. Autenticación de la API del robot

Los cuatro endpoints del robot requieren este header:

```http
X-MAXCIM-Webhook-Secret: <valor de MAXCIM_WEBHOOK_SECRET>
```

En producción, un secreto ausente o incorrecto devuelve `401`. Con `DEMO_MODE=true`, MAXCIM omite esta validación para permitir el uso del simulador aislado.

## 2. Endpoints que MAXCIM expone al robot

### 2.1 Listar los materiales de una docente

```http
GET /api/materials?teacher_id=<id_docente_institucional>
X-MAXCIM-Webhook-Secret: <secreto>
Accept: application/json
```

`teacher_id` es obligatorio. La respuesta `200` es una lista JSON, ordenada por fecha e ID descendentes. Cada elemento tiene la misma forma que `GET /api/materials/{id}`. Si la docente no tiene materiales, devuelve `[]`.

### 2.2 Obtener un material

```http
GET /api/materials/{id}
X-MAXCIM-Webhook-Secret: <secreto>
Accept: application/json
```

Un `cuento` devuelve `200` con esta forma:

```json
{
  "id": 12,
  "titulo": "El bosque que escucha",
  "tipo_material": "cuento",
  "fecha_subido": "2026-08-27",
  "fk_user": "<id_docente_institucional>",
  "texto_completo_url": "https://<maxcim>/static/uploads/.../texto.txt",
  "texto_resumen_url": "https://<maxcim>/static/uploads/.../resumen.txt",
  "audio_completo_url": "https://<maxcim>/static/uploads/.../audio.wav",
  "audio_resumen_url": "https://<maxcim>/static/uploads/.../audio_resumen.wav",
  "preguntas_url": "https://<maxcim>/static/uploads/.../preguntas.json",
  "preguntas": [
    {
      "pregunta": "¿Quién es el personaje?",
      "respuesta_esperada": "Luna"
    }
  ]
}
```

En la tabla `material`, el cuento llena `path_texto`, `path_texto_resumen`, `path_audio`, `path_audio_resumen` y `path_preguntas` con rutas relativas. `preguntas` se lee del JSON apuntado por `path_preguntas`; si el archivo no existe o su JSON no es válido, la API devuelve una lista vacía.

Una `oracion` devuelve `200` con esta forma:

```json
{
  "id": 13,
  "titulo": "Oraciones de práctica",
  "tipo_material": "oracion",
  "fecha_subido": "2026-08-27",
  "fk_user": "<id_docente_institucional>",
  "oraciones": "La luna brilla.\nEl río canta.",
  "texto_completo_url": null,
  "texto_resumen_url": null,
  "audio_completo_url": null,
  "audio_resumen_url": null,
  "preguntas_url": null,
  "preguntas": []
}
```

En la tabla `material`, la oración guarda el texto plano completo en `path_preguntas` y deja `path_texto`, `path_texto_resumen`, `path_audio` y `path_audio_resumen` en `NULL`.

Un ID inexistente devuelve `404`.

### 2.3 Registrar una interacción

El robot ya debe haber identificado al alumno, elegido el material y evaluado la respuesta antes de llamar a MAXCIM.

```http
POST /api/interacciones
X-MAXCIM-Webhook-Secret: <secreto>
Content-Type: application/json
```

```json
{
  "id_material": 12,
  "fk_alumno": "<id_alumno_institucional>",
  "pregunta": "¿Qué hizo Luna para ayudar?",
  "respuesta": "Escuchó a sus amigos.",
  "path_audio_rpta": "uploads/respuestas/respuesta.wav",
  "apreciacion_robot": "Respuesta clara y completa.",
  "rpta_correcta": true
}
```

Todos los campos son obligatorios. `id_material` debe identificar un registro existente; `fk_alumno` se almacena como ID institucional, pero este endpoint no vuelve a validarlo con la API institucional. `rpta_correcta` admite un booleano y las representaciones textuales aceptadas por el adaptador (`true/false`, `1/0`, `yes/no`, `si/sí`).

La respuesta `201` contiene el registro creado:

```json
{
  "id": 41,
  "id_material": 12,
  "fk_alumno": "<id_alumno_institucional>",
  "fecha_hora": "2026-08-27T17:30:00",
  "pregunta": "¿Qué hizo Luna para ayudar?",
  "respuesta": "Escuchó a sus amigos.",
  "path_audio_rpta": "https://<maxcim>/static/uploads/respuestas/respuesta.wav",
  "apreciacion_robot": "Respuesta clara y completa.",
  "rpta_correcta": true
}
```

`path_audio_rpta` se recibe hoy como una ruta relativa ya resuelta bajo `static/`; esta llamada no sube el archivo. Antes de integrar el robot real se debe acordar cómo llegará ese audio al servidor.

### 2.4 Consultar interacciones

```http
GET /api/interacciones?id_material=<id_material>&fk_alumno=<id_alumno_institucional>
X-MAXCIM-Webhook-Secret: <secreto>
Accept: application/json
```

Los dos filtros son opcionales y se pueden combinar. La respuesta `200` es una lista de hasta 200 registros con la misma forma de la respuesta del `POST`, ordenados desde el más reciente. Un `id_material` no numérico devuelve `400`.

## 3. Endpoints institucionales que MAXCIM consume

Las rutas se resuelven contra `INSTITUTIONAL_API_BASE_URL`. Las consultas de aulas y alumnos usan el token institucional de la docente como `Authorization: Bearer`; no usan el secreto del robot.

Con `DEMO_MODE=true`, estas llamadas se reemplazan por datos aislados en memoria y no contactan a la API institucional.

### 3.1 Inicio de sesión con ID y credencial

Ruta configurable mediante `INSTITUTIONAL_API_LOGIN_PATH`:

```http
POST {INSTITUTIONAL_API_BASE_URL}{INSTITUTIONAL_API_LOGIN_PATH}
Content-Type: application/json
Accept: application/json
```

```json
{
  "institutional_id": "<id_docente>",
  "credential": "<credencial_institucional>"
}
```

Respuesta esperada:

```json
{
  "access_token": "<token_institucional>",
  "expires_in": 3600,
  "teacher": {
    "id": "<id_docente>",
    "display_name": "<nombre_visible>",
    "role": "DOCENTE",
    "status": "ACTIVO"
  }
}
```

`access_token`, `teacher.id`, `teacher.display_name`, `teacher.role` y `teacher.status` son obligatorios. El adaptador acepta `DOCENTE` o `TEACHER`, y `ACTIVO` o `ACTIVE`. `expires_in` es opcional, usa 3600 segundos por defecto y nunca se interpreta como menos de 300 segundos. El token se cifra dentro de la cookie firmada de Flask; no existe una tabla local de sesiones.

### 3.2 Canje del acceso con Google

MAXCIM completa OpenID Connect con Google y valida firma, audiencia, expiración, correo verificado, dominio, `state`, `nonce` y PKCE. Luego envía el ID token verificado a la ruta configurada por `INSTITUTIONAL_API_GOOGLE_LOGIN_PATH`:

```http
POST {INSTITUTIONAL_API_BASE_URL}{INSTITUTIONAL_API_GOOGLE_LOGIN_PATH}
Content-Type: application/json
Accept: application/json
```

```json
{
  "id_token": "<id_token_firmado_por_google>"
}
```

La API institucional debe volver a validar el token, asociarlo con una docente activa y devolver exactamente la misma forma de respuesta de la sección 3.1. Una cuenta no asociada debe responder `401` o `403`. MAXCIM descarta los tokens de Google después del canje y conserva solo el token institucional cifrado.

### 3.3 Aulas de la docente

Ruta configurable mediante `INSTITUTIONAL_API_CLASSROOMS_PATH`, que admite `{teacher_id}`:

```http
GET {INSTITUTIONAL_API_BASE_URL}{INSTITUTIONAL_API_CLASSROOMS_PATH}
Authorization: Bearer <token_institucional_de_la_docente>
Accept: application/json
```

Respuesta esperada:

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

El sobre `classrooms` debe ser una lista. `id` y `name` son obligatorios; `grade`, `course` y `period` pueden faltar, ser `null` o ser cadenas vacías.

### 3.4 Alumnos de un aula — contrato provisional

Ruta configurable mediante `INSTITUTIONAL_API_STUDENTS_PATH`, que admite `{classroom_id}`:

```http
GET {INSTITUTIONAL_API_BASE_URL}{INSTITUTIONAL_API_STUDENTS_PATH}
Authorization: Bearer <token_institucional_de_la_docente>
Accept: application/json
```

La forma canónica propuesta es:

```json
{
  "students": [
    {
      "id": "<id_alumno_institucional>",
      "apellidos": "Pérez Rojas",
      "nombres": "Ana Lucía"
    }
  ]
}
```

**Los nombres exactos de los campos y del sobre todavía no han sido confirmados por el cliente. Este contrato es provisional y debe fijarse con la persona responsable de la API institucional antes de producción.**

Mientras se confirma, `InstitutionalClient.list_classroom_students` acepta una lista JSON desnuda o una lista contenida en cualquiera de estos sobres: `students`, `alumnos`, `data`, `items`.

Para cada alumno, `_map_classroom_student` acepta estas variantes:

| Dato | Campos aceptados, en orden de preferencia |
|---|---|
| ID institucional | `id`, `institutional_id`, `student_id`, `id_alumno`, `alumno_id` |
| Apellidos juntos | `apellidos`, `last_name`, `last_names`, `surname`, `surnames` |
| Nombres | `nombres`, `first_name`, `given_name`, `given_names`, `nombre` |
| Apellido paterno separado | `apellido_paterno`, `paternal_surname` |
| Apellido materno separado | `apellido_materno`, `maternal_surname` |
| Nombre completo combinado | `full_name`, `display_name`, `nombre_completo`, `name` |

Si llegan apellidos paterno y materno por separado, el adaptador los concatena. Si faltan nombres o apellidos separados, usa el campo de nombre completo:

- Con coma, interpreta `Apellidos, Nombres`.
- Sin coma, toma las dos últimas palabras como apellidos cuando hay tres palabras o más; con dos palabras toma solo la última como apellido. El resto se considera nombres.

Este fallback presupone dos apellidos y es una limitación conocida: puede separar incorrectamente nombres compuestos, personas con uno o más de dos apellidos, partículas o convenciones de nombre distintas. La API definitiva debe entregar ID, nombres y apellidos en campos separados para eliminar la heurística.

## 4. Cómo se deriva el avance por aula

`interaccion` no almacena el aula. Solo relaciona un `fk_alumno` institucional con un `id_material`; a su vez, `material.fk_user` identifica a la docente dueña.

Por eso `/aulas/<classroom_id>/avance` se construye en tiempo de consulta:

1. MAXCIM obtiene de la API institucional la matrícula vigente del aula.
2. Obtiene las interacciones cuyos `fk_alumno` aparecen en esa matrícula.
3. Limita esas interacciones a materiales cuyo `fk_user` sea la docente autenticada.
4. Calcula por alumno la secuencia de aciertos y errores y el total correcto/realizado.

La misma restricción de matrícula y propiedad de materiales protege `/aulas/<classroom_id>/alumnos/<student_id>`. Como no existe un ID de aula histórico en `interaccion`, si un alumno pertenece a varias aulas de la misma docente no se puede atribuir una interacción a una de ellas con mayor precisión.

## 5. Confirmaciones pendientes antes de producción

- Fijar con la persona responsable de la API institucional el path real, el sobre y los nombres exactos de campos del endpoint de alumnos por aula.
- Eliminar las variantes provisionales y el fallback de nombre completo una vez publicado ese contrato.
- Definir cómo se transfiere al servidor el archivo indicado por `path_audio_rpta`.
- Usar HTTPS y secretos distintos por ambiente, con rotación periódica.
- Definir la política institucional de retención de audios y transcripciones de menores.
- Aplicar `bd_app.sql` y las migraciones pendientes sobre MySQL, y configurar auditoría y respaldo.
