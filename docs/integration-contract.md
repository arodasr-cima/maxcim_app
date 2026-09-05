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

Los archivos de los materiales (texto, resumen, audio, preguntas, oraciones) **no** se sirven como archivos estáticos públicos. Se descargan solo por los endpoints autenticados de la sección 2.5 (`GET /api/materials/{id}/{recurso}`), que exigen el secreto y el identificador de la docente. Los campos `*_url` del cuerpo de respuesta apuntan a esos endpoints, no a `/static/`.

## 2. Endpoints que MAXCIM expone al robot

### 2.0 Cómo se identifica a la docente

Los endpoints de materiales aceptan dos formas de identificar a la docente (con
enviar una basta):

| Parámetro | Se compara con | Notas |
|---|---|---|
| `docente` | `material.fk_user_name` | Nombre de la docente tal como MAXCIM lo guarda al crear el material (`nombres` de CIMA normalizado, p.ej. `Rodas Rosales Oscar Alexis`). Comparación **sin distinguir mayúsculas** (y sin acentos en MySQL). El nombre **no es único**: si dos docentes se llaman igual, la consulta devuelve los materiales de ambas. Vacío en materiales creados antes de esta columna. |
| `teacher_id` (alias `dni`) | `material.fk_user` | `idPersona` de CIMA (p.ej. `70385`), el mismo valor que va en `fk_user` del cuerpo de respuesta. |

MAXCIM **no tiene tabla de docentes** y no conoce el DNI real (el JWT de login
—sección 3.1— no lo trae). El nombre y el `idPersona` se copian en cada material
al crearlo; el robot obtiene ambos autenticando a la docente contra CIMA, igual
que la consola.

### 2.1 Listar los materiales de una docente

```http
GET /api/materials?docente=<nombre>&tipo=<cuento|oracion>
X-MAXCIM-Webhook-Secret: <secreto>
Accept: application/json
```

Hay que enviar `docente` **o** `teacher_id` (ver 2.0); si faltan ambos, `400`.
`tipo` es opcional: si se envía debe ser `cuento` u `oracion` (cualquier otro
valor devuelve `400`) y filtra la lista a ese tipo. La respuesta `200` es una
lista JSON, ordenada por fecha e ID descendentes. Cada elemento tiene la misma
forma que `GET /api/materials/{id}`. Si la docente no tiene materiales, devuelve
`[]`.

### 2.2 Obtener un material

```http
GET /api/materials/{id}?docente=<nombre>
X-MAXCIM-Webhook-Secret: <secreto>
Accept: application/json
```

El identificador (`docente` o `teacher_id`) es **opcional** en este endpoint por
compatibilidad; si se envía y no coincide con el dueño del material, la
respuesta es `403`. Las descargas por archivo de la sección 2.5 sí lo exigen. La
respuesta incluye `"docente"` (el `fk_user_name` del material, o `null` en los
materiales anteriores a esa columna).

Un `cuento` devuelve `200` con esta forma:

```json
{
  "id": 12,
  "titulo": "El bosque que escucha",
  "tipo_material": "cuento",
  "fecha_subido": "2026-08-27",
  "fk_user": "<idPersona_de_cima>",
  "docente": "<nombre_de_la_docente_o_null>",
  "texto_completo_url": "https://<maxcim>/api/materials/12/texto",
  "texto_resumen_url": "https://<maxcim>/api/materials/12/resumen",
  "audio_completo_url": "https://<maxcim>/api/materials/12/audio",
  "audio_resumen_url": "https://<maxcim>/api/materials/12/audio-resumen",
  "preguntas_url": "https://<maxcim>/api/materials/12/preguntas",
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
  "fk_user": "<idPersona_de_cima>",
  "docente": "<nombre_de_la_docente_o_null>",
  "oraciones": ["La luna brilla.", "El río canta."],
  "oraciones_url": "https://<maxcim>/api/materials/13/oraciones",
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

El robot ya debe haber identificado al alumno, elegido el material y evaluado la respuesta antes de llamar a MAXCIM. A diferencia del resto de la API del robot, esta llamada es `multipart/form-data` (no JSON) porque **sube el archivo de audio de la respuesta**; MAXCIM lo guarda y lo sirve después por un endpoint autenticado (ver 2.3.1).

```http
POST /api/interacciones
X-MAXCIM-Webhook-Secret: <secreto>
Content-Type: multipart/form-data
```

| Campo (form field) | Obligatorio | Descripción |
|---|---|---|
| `id_material` | no | Si se omite o llega vacío, el turno se guarda como **conversación libre** (`id_material` queda `NULL`). Si se envía, debe identificar un registro existente (`404` si no) |
| `fk_alumno` | sí | ID institucional del alumno. No se vuelve a validar contra la API institucional |
| `pregunta` / `respuesta` | sí | Texto transcrito del turno |
| `apreciacion_robot` | sí | Evaluación cualitativa del robot |
| `rpta_correcta` | sí | Booleano; admite `true/false`, `1/0`, `yes/no`, `si/sí` |
| `audio_rpta` | sí | **Archivo WAV** con el audio de la respuesta del alumno |

Ejemplo con `curl`:

```bash
curl -X POST https://.../api/interacciones \
  -H "X-MAXCIM-Webhook-Secret: <secreto>" \
  -F "id_material=12" \
  -F "fk_alumno=<id_alumno_institucional>" \
  -F "pregunta=¿Qué hizo Luna para ayudar?" \
  -F "respuesta=Escuchó a sus amigos." \
  -F "apreciacion_robot=Respuesta clara y completa." \
  -F "rpta_correcta=true" \
  -F "audio_rpta=@respuesta.wav;type=audio/wav"
```

Un `audio_rpta` ausente o que no sea un WAV válido devuelve `400`. El archivo se guarda en `UPLOADS_ROOT` igual que el audio de un material (no bajo `/static/`).

En las vistas de la docente, una interacción con `id_material` en `NULL` se rotula **"Conversación"** en lugar del nombre del material.

La respuesta `201` contiene el registro creado:

```json
{
  "id": 41,
  "id_material": 12,
  "fk_alumno": "<id_alumno_institucional>",
  "fecha_hora": "2026-08-27T17:30:00",
  "pregunta": "¿Qué hizo Luna para ayudar?",
  "respuesta": "Escuchó a sus amigos.",
  "audio_rpta_url": "https://.../api/interacciones/41/audio",
  "apreciacion_robot": "Respuesta clara y completa.",
  "rpta_correcta": true
}
```

`audio_rpta_url` es un endpoint autenticado (mismo secreto compartido), no una ruta interna ni una URL bajo `/static/`.

#### 2.3.1 Descargar el audio de una respuesta

```http
GET /api/interacciones/{id}/audio
X-MAXCIM-Webhook-Secret: <secreto>
```

Devuelve el archivo WAV subido en 2.3 (`audio/wav`). `404` si la interacción no existe o si el archivo no está disponible.

### 2.4 Consultar interacciones

```http
GET /api/interacciones?id_material=<id_material>&fk_alumno=<id_alumno_institucional>
X-MAXCIM-Webhook-Secret: <secreto>
Accept: application/json
```

Hay que enviar **al menos uno** de los dos filtros (`id_material` o `fk_alumno`); se pueden combinar. Sin ninguno, `400` (este endpoint no vuelca el historial completo). La respuesta `200` es una lista de hasta 200 registros con la misma forma de la respuesta del `POST`, ordenados desde el más reciente. Un `id_material` no numérico devuelve `400`.

### 2.5 Descargar un archivo de un material

El robot descarga los archivos exactos de un material del docente para tenerlos
en local. Un endpoint por recurso; el robot pide solo lo que necesita.

```http
GET /api/materials/{id}/{recurso}?docente=<nombre>
X-MAXCIM-Webhook-Secret: <secreto>
```

El identificador de la docente (`docente` o `teacher_id`, ver 2.0) es
**obligatorio** y debe coincidir con el dueño del material; si faltan ambos
devuelve `400` y si no coincide devuelve `403`. Un `id` inexistente devuelve
`404`.

Para un `cuento`, `{recurso}` puede ser:

| `{recurso}` | Content-Type | Archivo | Columna |
|---|---|---|---|
| `texto` | `text/plain; charset=utf-8` | `texto.txt` | `path_texto` |
| `resumen` | `text/plain; charset=utf-8` | `resumen.txt` | `path_texto_resumen` |
| `audio` | `audio/wav` | `audio.wav` | `path_audio` |
| `audio-resumen` | `audio/wav` | `audio_resumen.wav` | `path_audio_resumen` |
| `preguntas` | `application/json` | `preguntas.json` | `path_preguntas` |

La respuesta `200` es el archivo con `Content-Disposition: attachment` y el
nombre sugerido de la tabla. Si la columna está vacía o el archivo no existe en
disco, devuelve `404`.

Para una `oracion`, el único recurso es `oraciones`, que devuelve `200` con
`{"oraciones": ["La luna brilla.", "El río canta."]}` (funciona también con los
registros antiguos que guardan el texto plano en `path_preguntas`). Pedir
`texto`, `audio`, etc. a una `oracion` devuelve `404`, y pedir `oraciones` a un
`cuento` también.

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
| `role` | (constante `"DOCENTE"`) | No se filtra por categoría de personal (docente, administrativo, etc.); se acepta el login salvo que `grupoPersonal` contenga `ALUMNO` (insensible a mayúsculas), caso en el que se rechaza como si la credencial fuera inválida |
| `expires_in_seconds` | `exp` − `iat` | Si faltan o no son válidos, usa 3600 segundos por defecto |
| `access_token` | el JWT completo (sin el prefijo `Bearer`) | Se cifra dentro de la cookie firmada de Flask; no existe una tabla local de sesiones |
| `photo_url` | `rutaFoto` | Opcional. Enlace de Google Drive; si se puede extraer el id del archivo se reescribe a `https://drive.google.com/thumbnail?id=<id>&sz=w160` para incrustarlo en el avatar del docente. Cualquier otra URL http(s) se deja igual; si falta o no es http(s) se usa el avatar con iniciales. Se guarda en claro en la cookie firmada de Flask |

El `display_name` resultante también se copia en `material.fk_user_name` al
crear un material, para que la API del robot pueda listar y mostrar los
materiales por nombre de docente (`?docente=`, ver 2.0) sin volver a consultar a
CIMA.

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

`interaccion` no almacena el aula. Solo relaciona un `fk_alumno` institucional con un `id_material` (que puede ser `NULL`); a su vez, `material.fk_user` identifica a la docente dueña.

Por eso `/aulas/<ref>/avance` se construye en tiempo de consulta (`<ref>` es un
token firmado —tipo + `classroom_id` + `id` de la docente— con caducidad de 24 h;
el `classroom_id` no viaja en texto plano y el token no sirve en la sesión de
otra docente ni en una ruta de otro tipo):

1. MAXCIM obtiene de la API institucional la matrícula vigente del aula.
2. Obtiene las interacciones cuyos `fk_alumno` aparecen en esa matrícula.
3. Limita esas interacciones a materiales cuyo `fk_user` sea la docente autenticada. Las conversaciones libres (`id_material` en `NULL`) no tienen material dueño, así que se atribuyen a la docente únicamente por la matrícula del paso 1.
4. Calcula por alumno la secuencia de aciertos y errores y el total correcto/realizado.

La misma restricción de matrícula y propiedad de materiales protege `/aulas/alumno/<ref>`. Como no existe un ID de aula histórico en `interaccion`, si un alumno pertenece a varias aulas de la misma docente no se puede atribuir una interacción a una de ellas con mayor precisión.

## 5. Confirmaciones pendientes antes de producción

- Confirmar si `identifier: "Sin IP"` es realmente el valor esperado para todo `idSystem`, o si CIMA sí espera una IP real en algún ambiente; hoy se copia de un caso observado en otro sistema, no de documentación oficial.
- Confirmar el significado real de `status` y `type` en la respuesta de aulas (sección 3.3) antes de usarlos para filtrar o mostrar algo.
- Confirmar si conviene separar grado, sección, sede y turno de `description` en la respuesta de aulas, y con qué formato son estables esas piezas.
- Confirmar si el endpoint de Google (sección 3.2) responde con el mismo sobre `{"content": {"token": "<jwt>"}}` que el login con usuario y contraseña.
- Confirmar si conviene usar `photoRoute` (foto del alumno) en alguna pantalla; hoy se ignora.
- Usar HTTPS y secretos distintos por ambiente, con rotación periódica.
- Definir la política institucional de retención de audios y transcripciones de menores.
- Aplicar `bd_app.sql` y las migraciones pendientes sobre MySQL, y configurar auditoría y respaldo.
