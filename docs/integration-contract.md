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
  "oraciones": ["La luna brilla.", "El río canta."],
  "oraciones_url": "https://<maxcim>/static/uploads/.../oraciones.json",
  "texto_completo_url": null,
  "texto_resumen_url": null,
  "audio_completo_url": null,
  "audio_resumen_url": null,
  "preguntas_url": null,
  "preguntas": []
}
```

`oraciones` es una lista, una entrada por oración, en el mismo orden en que la
docente las cargó. Al subir el archivo, Gemini identifica cada oración
individual (la docente las revisa y corrige antes de aprobar) y MAXCIM las
guarda como `uploads/<id>/oraciones.json`, igual que `preguntas.json` de un
cuento; `path_preguntas` apunta a ese archivo y `oraciones_url` lo expone.
`path_texto`, `path_texto_resumen`, `path_audio` y `path_audio_resumen` quedan
en `NULL`.

Compatibilidad: registros antiguos guardan el texto plano directamente en
`path_preguntas`. Para esos, `oraciones` se divide en oraciones al vuelo
(por saltos de línea y puntuación final) y `oraciones_url` es `null`.

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

### 3.1 Inicio de sesión con usuario y contraseña — confirmado contra la API real

A diferencia del resto de esta sección, este endpoint ya fue verificado contra
la API real de CIMA (ver [probar_conexion.py](../probar_conexion.py)), no es
un contrato provisional.

Ruta configurable mediante `INSTITUTIONAL_API_LOGIN_PATH` (valor real:
`/api/v2/authentication/with/user`), sobre `INSTITUTIONAL_API_BASE_URL`
(valor real: `https://apicima.colegiocima.edu.pe:8086`):

```http
POST {INSTITUTIONAL_API_BASE_URL}{INSTITUTIONAL_API_LOGIN_PATH}
Content-Type: application/json
Accept: application/json
```

```json
{
  "username": "<usuario_institucional>",
  "password": "<credencial_institucional>",
  "idSystem": 21,
  "identifier": "Sin IP"
}
```

`idSystem` (config `INSTITUTIONAL_API_ID_SYSTEM`) identifica a MAXCIM como
sistema consumidor frente a CIMA; otros sistemas que comparten la misma API
usan otros valores. `identifier` esperaría en teoría la IP de quien llama,
pero el tráfico real observado de otro sistema que ya consume esta API envía
el valor literal `"Sin IP"` en vez de una IP; MAXCIM hace lo mismo mientras
no se confirme lo contrario.

Respuesta observada en un login válido:

```json
{
  "content": {
    "token": "Bearer <jwt>"
  }
}
```

A diferencia de un contrato REST típico, no hay un sobre `teacher` aparte: la
identidad viaja como claims sin firmar dentro del propio JWT. Payload
decodificado de ejemplo:

```json
{
  "idPersona": "70385",
  "sub": "orodasr",
  "nombres": "RODAS ROSALES OSCAR ALEXIS",
  "grupoPersonal": "DOCENTE COLEGIO",
  "idGrupoPersonal": "5",
  "correoInstitucional": "oscar.rodas@colegiocima.edu.pe",
  "rutaFoto": "https://drive.google.com/...",
  "idLogueo": "9716",
  "idSistema": "21",
  "aula": "",
  "iat": 1788103877,
  "exp": 1788121877
}
```

`InstitutionalClient._parse_jwt_teacher` decodifica el JWT **sin verificar su
firma** — es seguro porque el token se obtiene directamente de CIMA por HTTPS
dentro de esta misma solicitud del servidor, nunca lo entrega el navegador de
la docente. Mapeo de campos:

| Campo MAXCIM | Claim del JWT | Notas |
|---|---|---|
| `institutional_id` | `idPersona` | Identificador único y estable de la persona |
| `display_name` | `nombres` | Apellidos y nombres juntos, en MAYÚSCULAS (ej. `RODAS ROSALES OSCAR ALEXIS`); MAXCIM solo normaliza la capitalización, no los separa |
| `role` | `grupoPersonal` | Se acepta el login solo si el texto contiene `DOCENTE` (insensible a mayúsculas); de lo contrario se rechaza como si la credencial fuera inválida |
| `expires_in_seconds` | `exp` − `iat` | Si faltan o no son válidos, usa 3600 segundos por defecto |
| `access_token` | el JWT completo (sin el prefijo `Bearer`) | Se cifra dentro de la cookie firmada de Flask; no existe una tabla local de sesiones |
| `photo_url` | `rutaFoto` | Opcional. Enlace de Google Drive; si se puede extraer el id del archivo se reescribe a `https://drive.google.com/thumbnail?id=<id>&sz=w160` para incrustarlo en el avatar del docente. Cualquier otra URL http(s) se deja igual; si falta o no es http(s) se usa el avatar con iniciales. Se guarda en claro en la cookie firmada de Flask |

CIMA no parece usar un sobre de error dedicado para credenciales inválidas en
este endpoint: una respuesta `200` sin `content.token` se trata como
credenciales inválidas. `idPersona`, `nombres` y `grupoPersonal` son
obligatorios; su ausencia se trata como una respuesta institucional no
válida.

**Pendiente de confirmar:** si `/login/google` (`INSTITUTIONAL_API_GOOGLE_LOGIN_PATH`,
sección 3.2) responde con el mismo sobre `{"content": {"token": "<jwt>"}}`.
MAXCIM lo asume por ahora, pero no se ha verificado contra la API real como sí
se hizo con este endpoint.

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

### 3.3 Aulas de la docente — confirmado contra la API real

Igual que la sección 3.1, este endpoint ya fue verificado contra la API real
(ver [probar_conexion_aulas.py](../probar_conexion_aulas.py)), no es un
contrato provisional.

Ruta configurable mediante `INSTITUTIONAL_API_CLASSROOMS_PATH` (valor real:
`/api/v2/gradesection/list/group/user/{login_id}`):

```http
GET {INSTITUTIONAL_API_BASE_URL}{INSTITUTIONAL_API_CLASSROOMS_PATH}
Authorization: Bearer <token_institucional_de_la_docente>
Accept: application/json
```

El path param **no** es `idPersona` (el ID estable de la persona, usado en
todo el resto de MAXCIM como `institutional_id`/`fk_user`): es `idLogueo`,
un claim distinto del mismo JWT, aparentemente ligado a la sesión de login.
`InstitutionalClient.list_teacher_classrooms` decodifica el propio
`access_token` para extraerlo — no depende del `teacher_id` que le pasa el
caller (ver `app.py`), que se mantiene en la firma solo por compatibilidad
con `DemoInstitutionalClient`.

Respuesta observada — una lista JSON desnuda, sin sobre:

```json
[
  {
    "id": 2331,
    "type": "N",
    "status": false,
    "description": "5TH - D PRIM. GRAU MAÑANA"
  }
]
```

Mapeo actual en `Classroom`:

| Campo MAXCIM | Campo CIMA | Notas |
|---|---|---|
| `institutional_id` | `id` | |
| `name` | `description` | CIMA no separa grado, sección, sede ni turno: vienen todos juntos en un solo string. Se usa tal cual; no se intenta partirlo con heurísticas. |
| `grade`, `course`, `period` | — | Sin mapear todavía; siempre `None`. No hay campos separados en la respuesta real para llenarlos. |

`status` llega en la respuesta pero **no se usa**: su significado no está
confirmado y fue `false` en las 31 aulas observadas para la cuenta de
prueba, lo que no calza con una lectura obvia de "aula activa". Antes de
filtrar o mostrar algo basado en él hay que confirmar su significado con la
persona responsable de la API institucional.

`type` sí se usa, pero no para mostrar nada: se guarda en
`Classroom.section_type` porque el endpoint de alumnos por aula (sección
3.4) lo vuelve a pedir como parte de su URL.

### 3.4 Alumnos de un aula — confirmado contra la API real

Igual que 3.1 y 3.3, este endpoint ya fue verificado contra la API real (ver
[probar_conexion_alumnos.py](../probar_conexion_alumnos.py)), no es un
contrato provisional.

Ruta configurable mediante `INSTITUTIONAL_API_STUDENTS_PATH` (valor real:
`/api/v2/studentschool/list/gradesectiongroup/{classroom_id}/type/{section_type}/order/{order}`):

```http
GET {INSTITUTIONAL_API_BASE_URL}{INSTITUTIONAL_API_STUDENTS_PATH}
Authorization: Bearer <token_institucional_de_la_docente>
Accept: application/json
```

- `{classroom_id}`: el `id` del aula (viene de la sección 3.3, `Classroom.institutional_id`).
- `{section_type}`: el `type` que trajo esa misma aula en la sección 3.3 (`Classroom.section_type`; `"N"` es el único valor observado hasta ahora). `InstitutionalClient.list_classroom_students` lo recibe como parámetro en vez de volver a pedirlo a la API.
- `{order}`: `A` (ascendente) o `N` (descendente). MAXCIM siempre envía `A`; no hay control en la UI para cambiarlo todavía.

Respuesta observada — una lista JSON desnuda, sin sobre:

```json
[
  {
    "idStudentSchool": 79398411,
    "firstName": "CIELITO ABIGAIL",
    "lastName": "CABRERA BURGA",
    "idPerson": 66696,
    "photoRoute": "https://drive.google.com/file/d/.../view?usp=drivesdk",
    "institutionalEmail": "79398411@colegiocima.edu.pe",
    "studentSchool": "CABRERA BURGA CIELITO ABIGAIL"
  }
]
```

Mapeo en `ClassroomStudent` (`InstitutionalClient._map_classroom_student`):

| Campo MAXCIM | Campo CIMA | Notas |
|---|---|---|
| `institutional_id` | `idStudentSchool` | Coincide con el prefijo de `institutionalEmail` (ej. `79398411` en `79398411@colegiocima.edu.pe`); es el ID institucional estable del alumno. **No** `idPerson`, que es otro ID interno de CIMA (paralelo a `idPersona` para docentes). |
| `apellidos` | `lastName` | |
| `nombres` | `firstName` | |

`idPerson`, `photoRoute`, `institutionalEmail` y `studentSchool` (nombre
completo ya combinado, `apellidos + nombres`) llegan en la respuesta pero no
se usan todavía. Cualquiera de los tres primeros ausente o vacío se trata
como una respuesta institucional inválida.

## 4. Cómo se deriva el avance por aula

`interaccion` no almacena el aula. Solo relaciona un `fk_alumno` institucional con un `id_material`; a su vez, `material.fk_user` identifica a la docente dueña.

Por eso `/aulas/<classroom_id>/avance` se construye en tiempo de consulta:

1. MAXCIM obtiene de la API institucional la matrícula vigente del aula.
2. Obtiene las interacciones cuyos `fk_alumno` aparecen en esa matrícula.
3. Limita esas interacciones a materiales cuyo `fk_user` sea la docente autenticada.
4. Calcula por alumno la secuencia de aciertos y errores y el total correcto/realizado.

La misma restricción de matrícula y propiedad de materiales protege `/aulas/<classroom_id>/alumnos/<student_id>`. Como no existe un ID de aula histórico en `interaccion`, si un alumno pertenece a varias aulas de la misma docente no se puede atribuir una interacción a una de ellas con mayor precisión.

## 5. Confirmaciones pendientes antes de producción

- Confirmar si `identifier: "Sin IP"` es realmente el valor esperado para todo `idSystem`, o si CIMA sí espera una IP real en algún ambiente; hoy se copia de un caso observado en otro sistema, no de documentación oficial.
- Confirmar el significado real de `status` y `type` en la respuesta de aulas (sección 3.3) antes de usarlos para filtrar o mostrar algo.
- Confirmar si conviene separar grado, sección, sede y turno de `description` en la respuesta de aulas, y con qué formato son estables esas piezas.
- Confirmar si el endpoint de Google (sección 3.2) responde con el mismo sobre `{"content": {"token": "<jwt>"}}` que el login con usuario y contraseña.
- Confirmar si conviene usar `photoRoute` (foto del alumno) en alguna pantalla; hoy se ignora.
- Definir cómo se transfiere al servidor el archivo indicado por `path_audio_rpta`.
- Usar HTTPS y secretos distintos por ambiente, con rotación periódica.
- Definir la política institucional de retención de audios y transcripciones de menores.
- Aplicar `bd_app.sql` y las migraciones pendientes sobre MySQL, y configurar auditoría y respaldo.
