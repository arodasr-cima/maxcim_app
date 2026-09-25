# MAXCIM · API del robot — referencia de implementación

Documento para implementar el **cliente del robot**. Cubre solo los endpoints
que consume el robot (los que exigen el secreto compartido). Los endpoints de
la consola web de la docente (subida de material, generación con IA, etc.) no
están aquí y no los usa el robot.

---

## 1. Conexión

| | |
|---|---|
| **Base URL** | La del despliegue de MAXCIM, p. ej. `https://maxcim.tu-dominio.edu.pe` (sin `/` final). Todas las rutas de abajo cuelgan de ahí. |
| **Formato** | JSON en todas las respuestas, salvo las descargas de archivo (audio WAV, imagen PNG), que devuelven bytes binarios. |
| **Codificación** | UTF-8. Los textos llevan tildes y `«»`; no los escapes. |

### Autenticación

**Toda** petición lleva este header:

```
X-MAXCIM-Webhook-Secret: <MAXCIM_WEBHOOK_SECRET>
```

`MAXCIM_WEBHOOK_SECRET` es un valor compartido (≥ 32 caracteres) que entrega el
equipo de MAXCIM. Sin header válido → `401 {"error": "Integración no autorizada."}`.

- No hay OAuth, ni tokens por usuario, ni cookies. Es un único secreto de servicio.
- No se envía token CSRF (el robot no es un navegador).
- En un entorno con `DEMO_MODE=true` la validación del secreto se omite; en
  producción es obligatoria. Implementa el cliente **siempre** mandando el header.

### Identificar a la docente

Casi todos los GET necesitan saber **de qué docente** son los datos. Se pasa por
query string, de una de estas dos formas (elige una):

| Query param | Qué es | Notas |
|---|---|---|
| `teacher_id` | `idPersona` de CIMA, p. ej. `1000001` | Forma preferida, es única. `dni` se acepta como alias histórico. |
| `docente` | Nombre tal cual lo envía CIMA, p. ej. `Perez Flores, Ana` | Se compara sin distinguir mayúsculas ni acentos. **No es único**: dos docentes con el mismo nombre devuelven datos de ambas. Se resuelve a partir de los materiales existentes, así que una docente sin ningún material no se encuentra por nombre. |

Falta el identificador → `400 {"error": "Falta identificar a la docente (docente o teacher_id)."}`.

---

## 2. Índice de endpoints

| Método y ruta | Para qué |
|---|---|
| `GET /api/temas` | Temas (unidades) de una docente |
| `GET /api/materials` | Lista de materiales de una docente |
| `GET /api/materials/{id}` | Metadatos de un material |
| `GET /api/materials/{id}/{recurso}` | Descargar un recurso del material (texto/audio/preguntas/oraciones/bits) |
| `GET /api/materials/{id}/imagen/{oracion}/{sustantivo}` | PNG de un sustantivo de una "oración con imágenes" |
| `GET /api/materials/{id}/bit-imagen/{i}` | PNG de la palabra de un "bit" |
| `GET /api/materials/{id}/escena-imagen/{i}` | Imagen de una escena de un cuento |
| `GET /api/materials/{id}/escena-audio/{i}` | Audio (WAV) de la narración de una escena de un cuento |
| `POST /api/interacciones` | Registrar un turno pregunta/respuesta (sube el audio) |
| `GET /api/interacciones` | Historial de turnos (por material y/o alumno) |
| `GET /api/interacciones/{id}/audio` | Descargar el audio de un turno ya registrado |

---

## 3. `GET /api/temas`

Temas con los que la docente organiza su material (p. ej. "Animales", "La familia").
Un tema pertenece a **una** docente y a **un** periodo (bimestre).

### Query params

| Param | Obligatorio | Descripción |
|---|---|---|
| `teacher_id` **o** `docente` | Sí | Ver §1. |
| `periodo` | No | ID de periodo; filtra a los temas de ese bimestre. |

### Respuesta `200`

Array ordenado por periodo y luego por nombre:

```json
[
  {
    "id": 3,
    "nombre": "Animales",
    "fk_user": "1000001",
    "periodo": { "id": 2, "nombre": "II BIMESTRE", "anio": 2026 },
    "materiales_count": 5
  }
]
```

| Campo | Tipo | Notas |
|---|---|---|
| `id` | int | ID del tema. Cruza con `id_tema` de cada material. |
| `nombre` | string | |
| `fk_user` | string | `idPersona` de la docente dueña. |
| `periodo` | objeto \| null | Bimestre del tema. |
| `materiales_count` | int | Cuántos materiales usan este tema. |

Docente sin temas (o nombre desconocido) → `200 []` (no es error).

### Ejemplo

```bash
curl -H "X-MAXCIM-Webhook-Secret: $SECRET" \
  "$BASE/api/temas?teacher_id=1000001&periodo=2"
```

---

## 4. `GET /api/materials`

Lista los materiales de una docente, del más reciente al más antiguo.

### Query params

| Param | Obligatorio | Descripción |
|---|---|---|
| `teacher_id` **o** `docente` | Sí | Ver §1. |
| `tipo` | No | `cuento`, `oracion`, `oracion_imagen` o `bits`. Filtra por tipo. Valor no válido → `400`. |

### Respuesta `200`

Array de objetos material. La forma depende de `tipo_material`.

#### Campos comunes a todos los tipos

| Campo | Tipo | Notas |
|---|---|---|
| `id` | int | ID del material. |
| `titulo` | string | |
| `tipo_material` | string | `cuento` \| `oracion` \| `oracion_imagen` \| `bits`. |
| `fecha_subido` | string (YYYY-MM-DD) \| null | |
| `fk_user` | string | `idPersona` de la docente dueña. |
| `docente` | string \| null | Nombre de la docente al crear el material (copia). |
| `id_periodo` | int \| null | Bimestre. |
| `id_tema` | int \| null | Tema. Cruza con `GET /api/temas`. |
| `periodo` | objeto `{id, nombre}` \| null | |
| `tema` | objeto `{id, nombre}` \| null | |

#### `tipo_material: "cuento"`

```json
{
  "id": 12,
  "titulo": "El bosque que escucha",
  "tipo_material": "cuento",
  "fecha_subido": "2026-09-01",
  "fk_user": "1000001",
  "docente": "Perez Flores, Ana",
  "id_periodo": 3, "id_tema": 7,
  "periodo": { "id": 3, "nombre": "III BIMESTRE" },
  "tema": { "id": 7, "nombre": "Convivencia" },

  "texto_completo_url":  "https://.../api/materials/12/texto",
  "texto_resumen_url":   "https://.../api/materials/12/resumen",
  "audio_completo_url":  "https://.../api/materials/12/audio",
  "preguntas_url":       "https://.../api/materials/12/preguntas",
  "preguntas": [
    { "pregunta": "¿Quién es el personaje?", "respuesta_esperada": "Una zorrita llamada Luna" }
  ],
  "escenas": [
    {
      "indice": 0,
      "texto": "Luna salió al bosque.",
      "duracion_s": 2.9,
      "imagen_url": "https://.../api/materials/12/escena-imagen/0",
      "audio_url":  "https://.../api/materials/12/escena-audio/0"
    },
    {
      "indice": 1,
      "texto": "Encontró a un búho. Juntos regresaron a casa.",
      "duracion_s": 5.4,
      "imagen_url": "https://.../api/materials/12/escena-imagen/1",
      "audio_url":  "https://.../api/materials/12/escena-audio/1"
    }
  ]
}
```

- Los `*_url` **ya vienen absolutos** y apuntan a `GET /api/materials/{id}/{recurso}`.
  Para descargarlos hay que volver a mandar el header del secreto **y** el
  identificador de la docente como query (`?teacher_id=...`).
- `preguntas` viene embebido además de `preguntas_url` (mismo contenido).
- Un `*_url` es `null` si ese recurso no existe.
- `escenas` es la lista, **en orden de lectura**, de las escenas ilustradas y
  narradas del cuento. La consola las exige al guardar un cuento, así que solo
  es `[]` en los cuentos guardados antes de esta función: en ese caso el robot
  usa `audio_completo_url` como siempre.

**Cómo reproduce el robot un cuento con `escenas`** — por cada elemento, en
orden: descarga `imagen_url` y `audio_url`, muestra la imagen mientras suena el
audio y, cuando el audio termina, pasa a la siguiente escena. No hay tiempos que
sincronizar: cada audio ya narra exactamente el fragmento de su imagen. Los
`texto` de todas las escenas, unidos con un espacio, reproducen el cuento
completo (`texto_completo_url`, con los saltos de línea reducidos a espacios),
por lo que sirven también como subtítulo.
`duracion_s` (segundos) permite precargar o mostrar una barra de progreso, pero
el fin real de cada escena es el fin de su audio. En un cuento con escenas,
`audio_completo_url` es simplemente la unión, en orden, de los `audio_url` de
todas las escenas (MAXCIM la arma al guardar): la misma narración de corrido,
sin cortes de imagen. Lo esperado es que el robot use `escenas` y deje
`audio_completo_url` solo para cuentos que no las tengan.

#### `tipo_material: "oracion"`

```json
{
  "id": 20,
  "titulo": "Oraciones de práctica",
  "tipo_material": "oracion",
  "fecha_subido": "2026-09-05",
  "fk_user": "1000001", "docente": "Perez Flores, Ana",
  "id_periodo": 3, "id_tema": 7,
  "periodo": { "id": 3, "nombre": "III BIMESTRE" },
  "tema": { "id": 7, "nombre": "Convivencia" },

  "oraciones": ["La luna brilla.", "El río canta."],
  "oraciones_url": "https://.../api/materials/20/oraciones",

  "texto_completo_url": null, "texto_resumen_url": null,
  "audio_completo_url": null,
  "preguntas_url": null, "preguntas": []
}
```

- `oraciones` = lista de frases completas para leer en voz alta.
- `oraciones_url` es `null` en registros antiguos que guardaban las oraciones
  como texto plano; en ese caso usa el campo `oraciones` directamente.

#### `tipo_material: "oracion_imagen"`

Igual que `oracion` **más** el campo `oraciones_detalle`. Cada oración lleva dos
sustantivos concretos que se muestran como imágenes en los huecos.

```json
{
  "id": 31,
  "titulo": "Oraciones con imágenes",
  "tipo_material": "oracion_imagen",
  "fecha_subido": "2026-09-10",
  "fk_user": "1000001", "docente": "Perez Flores, Ana",
  "id_periodo": 3, "id_tema": 9,
  "periodo": { "id": 3, "nombre": "III BIMESTRE" },
  "tema": { "id": 9, "nombre": "Mi día" },

  "oraciones": ["El niño monta en su bicicleta azul."],
  "oraciones_url": "https://.../api/materials/31/oraciones",
  "oraciones_detalle": [
    {
      "oracion_completa": "El niño monta en su bicicleta azul.",
      "plantilla": "El {{0}} monta en su {{1}} azul.",
      "sustantivos": [
        { "palabra": "niño",      "imagen_url": "https://.../api/materials/31/imagen/0/0" },
        { "palabra": "bicicleta", "imagen_url": "https://.../api/materials/31/imagen/0/1" }
      ]
    }
  ],

  "texto_completo_url": null, "texto_resumen_url": null,
  "audio_completo_url": null,
  "preguntas_url": null, "preguntas": []
}
```

**Cómo arma el robot la pantalla de una `oracion_imagen`** — por cada elemento de
`oraciones_detalle`:

1. Toma `plantilla` y pártela por los marcadores `{{0}}` y `{{1}}`.
2. Renderiza los trozos de texto tal cual (fuente escolar cursiva; la consola
   usa "Massallera", el robot puede usar la suya).
3. Sustituye `{{0}}` por la imagen de `sustantivos[0]` y `{{1}}` por la de
   `sustantivos[1]`, descargándolas de `imagen_url`.
4. Las imágenes deben verse grandes, alineadas con el texto (alto ≈ 2–3 líneas).

- `imagen_url` es `null` si el material se guardó sin imágenes: en ese caso
  muestra `oracion_completa` como texto plano.
- `plantilla` siempre tiene exactamente los marcadores `{{0}}` y `{{1}}`, en el
  orden en que aparecen los sustantivos en la frase. Si `plantilla` faltara,
  usa `oracion_completa`.

#### `tipo_material: "bits"`

"Bits" (bits de inteligencia): tarjetas de una sola palabra con su imagen, para
practicar fonética. A diferencia de `oracion_imagen` no hay una oración que
armar: cada elemento de `bits` es autosuficiente (palabra + imagen). Un bit
**siempre** tiene imagen — a diferencia de `oracion_imagen`, MAXCIM no permite
guardar un bit sin ella.

```json
{
  "id": 40,
  "titulo": "Bits: sílabas ma, me",
  "tipo_material": "bits",
  "fecha_subido": "2026-09-15",
  "fk_user": "1000001", "docente": "Perez Flores, Ana",
  "id_periodo": 3, "id_tema": 9,
  "periodo": { "id": 3, "nombre": "III BIMESTRE" },
  "tema": { "id": 9, "nombre": "Fonética" },

  "bits": [
    { "palabra": "feliz", "pregunta": "El sol está…",
      "imagen_url": "https://.../api/materials/40/bit-imagen/0" },
    { "palabra": "familia", "pregunta": "Esto es una…",
      "imagen_url": "https://.../api/materials/40/bit-imagen/1" }
  ],
  "consonante": "M",

  "texto_completo_url": null, "texto_resumen_url": null,
  "audio_completo_url": null,
  "preguntas_url": null, "preguntas": []
}
```

**Cómo arma el robot la pantalla de un bit** — por cada elemento de `bits`:
muestra la imagen (descargada de `imagen_url`) y dice/muestra la `pregunta`. La
`palabra` es **la respuesta que debe dar el niño**, no un texto para leer en
voz alta junto a la imagen: la `pregunta` es el comienzo de una frase que esa
palabra completa (`"El sol está…"` → «feliz», `"Esto es una…"` → «familia»).
Por eso el robot no debe anteponer un `"Esto es…"` genérico: «Esto es feliz»
no tiene sentido. MAXCIM no evalúa la respuesta — eso lo resuelve el robot por
su cuenta (igual que en `oracion_imagen`).

- `pregunta` la sugiere la IA al diseñar el material (mirando la imagen) y la
  docente puede editarla; **nunca contiene la propia `palabra`**. Es
  `string` de hasta 200 caracteres, o `null` si el bit se guardó sin pregunta
  (bits anteriores a este campo, o material armado a mano sin escribirla): en
  ese caso el robot usa su frase por defecto. El saludo o la transición («muy
  bien, vamos con la siguiente») los agrega el robot, no vienen en la pregunta.

- `consonante` es la letra inicial que comparten **todas** las palabras del
  material (p. ej. `"M"` si son "mano", "mapa", "mesa"…), en mayúscula. Es
  `null` si las palabras no comparten una consonante inicial -por ejemplo un
  `bits` armado a mano con palabras sueltas, o con sílabas de varias
  consonantes distintas-. MAXCIM la calcula a partir de las palabras
  guardadas, la docente no la escribe en ningún lado.

### Ejemplo

```bash
curl -H "X-MAXCIM-Webhook-Secret: $SECRET" \
  "$BASE/api/materials?teacher_id=1000001&tipo=oracion_imagen"

curl -H "X-MAXCIM-Webhook-Secret: $SECRET" \
  "$BASE/api/materials?teacher_id=1000001&tipo=bits"
```

---

## 5. `GET /api/materials/{id}`

Un solo material. **Requiere** el identificador de la docente y que el material
le pertenezca.

### Query params

| Param | Obligatorio | Descripción |
|---|---|---|
| `teacher_id` **o** `docente` | Sí | |

### Respuestas

- `200` — el mismo objeto que un elemento de `GET /api/materials` (§4).
- `400` — falta el identificador de la docente.
- `404` — no existe un material con ese `id`.
- `403` — el material existe pero no es de esa docente.

---

## 6. `GET /api/materials/{id}/{recurso}`

Descarga un recurso concreto de un material. **Requiere** identificador de la
docente y propiedad (400 / 404 / 403 como en §5).

### `recurso` según el tipo de material

| `recurso` | Para | Content-Type | Devuelve |
|---|---|---|---|
| `texto` | cuento | `text/plain; charset=utf-8` | archivo del texto completo |
| `resumen` | cuento | `text/plain; charset=utf-8` | archivo del resumen |
| `audio` | cuento | `audio/wav` | narración del texto completo |
| `preguntas` | cuento | `application/json` | array `[{pregunta, respuesta_esperada}]` |
| `oraciones` | oracion / oracion_imagen | `application/json` | ver abajo |
| `bits` | bits | `application/json` | ver abajo |

Las descargas de archivo llegan con `Content-Disposition: attachment`.

- Pedir `texto`/`audio`/… a una `oracion`, `oracion_imagen` o `bits` → `404`
  (`"solo expone 'oraciones'"` / `"solo expone 'bits'"`, según el tipo).
- Pedir `oraciones` a un `bits` (o `bits` a una `oracion`/`oracion_imagen`) → `404`.
- Pedir `oraciones` a un `cuento` → `404`.
- `recurso` desconocido → `404`.
- El material no tiene ese recurso guardado → `404`.

### `recurso = oraciones`

```jsonc
// oracion:
{ "oraciones": ["La luna brilla.", "El río canta."] }

// oracion_imagen: además de "oraciones", el mismo "oraciones_detalle" de §4
{
  "oraciones": ["El niño monta en su bicicleta azul."],
  "oraciones_detalle": [ { "oracion_completa": "...", "plantilla": "...", "sustantivos": [ ... ] } ]
}
```

### `recurso = bits`

```json
{
  "bits": [ { "palabra": "feliz", "pregunta": "El sol está…", "imagen_url": "https://.../api/materials/40/bit-imagen/0" } ],
  "consonante": "M"
}
```

Mismo contenido que los campos `bits` y `consonante` de §4.

### Ejemplo

```bash
curl -H "X-MAXCIM-Webhook-Secret: $SECRET" \
  "$BASE/api/materials/12/audio?teacher_id=1000001" -o cuento.wav
```

---

## 7. `GET /api/materials/{id}/imagen/{oracion}/{sustantivo}`

PNG del sustantivo de una "oración con imágenes". `{oracion}` y `{sustantivo}`
son **índices 0-based**, tal cual llegan en `oraciones_detalle`
(`oraciones_detalle[oracion].sustantivos[sustantivo]`).

### Query params

| Param | Obligatorio | Descripción |
|---|---|---|
| `teacher_id` **o** `docente` | Sí | |

### Respuestas

- `200` — bytes PNG (`Content-Type: image/png`, `attachment`).
- `400` / `403` / `404` — como en §5, y también `404` si el material no es
  `oracion_imagen`, si los índices están fuera de rango, o si esa oración se
  guardó sin imágenes.

La forma cómoda es usar directamente el campo `imagen_url` que ya viene en
`oraciones_detalle` (es esta misma ruta, absoluta); solo hay que añadirle el
header del secreto y el `?teacher_id=`.

```bash
curl -H "X-MAXCIM-Webhook-Secret: $SECRET" \
  "$BASE/api/materials/31/imagen/0/1?teacher_id=1000001" -o bicicleta.png
```

---

## 8. `GET /api/materials/{id}/bit-imagen/{i}`

PNG de la palabra de un "bit". `{i}` es un **índice 0-based**, tal cual llega
en `bits` (`bits[i]`).

### Query params

| Param | Obligatorio | Descripción |
|---|---|---|
| `teacher_id` **o** `docente` | Sí | |

### Respuestas

- `200` — bytes PNG (`Content-Type: image/png`, `attachment`).
- `400` / `403` / `404` — como en §5, y también `404` si el material no es
  `bits`, si el índice está fuera de rango, o si ese bit se guardó sin imagen
  (no debería pasar: MAXCIM exige imagen para guardar un bit).

La forma cómoda es usar directamente el campo `imagen_url` que ya viene en
`bits` (es esta misma ruta, absoluta); solo hay que añadirle el header del
secreto y el `?teacher_id=`.

```bash
curl -H "X-MAXCIM-Webhook-Secret: $SECRET" \
  "$BASE/api/materials/40/bit-imagen/0?teacher_id=1000001" -o mama.png
```

---

## 8.1. `GET /api/materials/{id}/escena-imagen/{i}`

Imagen de una escena de un `cuento`. `{i}` es un **índice 0-based**, tal cual
llega en `escenas` (`escenas[i].indice`).

### Query params

| Param | Obligatorio | Descripción |
|---|---|---|
| `teacher_id` **o** `docente` | Sí | |

### Respuestas

- `200` — bytes de la imagen (`attachment`). El `Content-Type` es `image/png`
  en la práctica, pero puede ser `image/jpeg` o `image/webp`: usa el header, no
  la extensión.
- `400` / `401` / `403` / `404` — como en §5, y también `404` si el material no
  es un cuento con escenas o si el índice está fuera de rango.

La forma cómoda es usar directamente `imagen_url` de `escenas` (es esta misma
ruta, absoluta) añadiéndole el header del secreto y el `?teacher_id=`.

```bash
curl -H "X-MAXCIM-Webhook-Secret: $SECRET" \
  "$BASE/api/materials/12/escena-imagen/0?teacher_id=1000001" -o escena_0.png
```

---

## 8.2. `GET /api/materials/{id}/escena-audio/{i}`

Narración de una escena de un `cuento`, en WAV. Mismos parámetros y códigos de
error que §8.1.

- `200` — bytes WAV (`Content-Type: audio/wav`, `attachment`).

```bash
curl -H "X-MAXCIM-Webhook-Secret: $SECRET" \
  "$BASE/api/materials/12/escena-audio/0?teacher_id=1000001" -o escena_0.wav
```

---

## 9. `POST /api/interacciones`

Registra **un turno** de pregunta/respuesta ya resuelto por el robot. El robot
decide por su cuenta qué alumno tiene enfrente y qué material está usando; MAXCIM
no gestiona sesiones ni reconocimiento facial.

### Formato

`multipart/form-data` (no JSON) — porque sube el archivo de audio de la respuesta.

### Campos

| Campo | Obligatorio | Tipo | Descripción |
|---|---|---|---|
| `fk_alumno` | Sí | texto (≤ 50) | `idPersona` del alumno en CIMA. |
| `pregunta` | Sí | texto (≤ 20 000) | Lo que preguntó MAXCIM. |
| `respuesta` | Sí | texto (≤ 20 000) | Lo que respondió el alumno (transcripción). |
| `apreciacion_robot` | Sí | texto | Comentario/crítica del robot sobre la respuesta. |
| `rpta_correcta` | Sí | bool | `true`/`false` (también `1`/`0`, `yes`/`no`, `si`/`sí`). |
| `audio_rpta` | Sí | archivo | WAV de la respuesta del alumno. Debe ser un WAV válido. |
| `id_material` | No | int | Material de la actividad. **Omitir** (o vacío) = conversación libre, sin material. |

### Respuestas

- `201` — objeto interacción creado (ver forma en §10).
- `400` — faltan campos (`"Faltan campos obligatorios: ..."`), `id_material` /
  `rpta_correcta` mal formados, o el `audio_rpta` no es un WAV válido.
- `404` — `id_material` no existe.
- `413` — algún texto excede el límite.

MAXCIM deriva el periodo (bimestre) en el servidor: del material si se envía uno,
o de la fecha UTC si es conversación libre. **El robot no manda el periodo.**

### Ejemplo

```bash
curl -X POST "$BASE/api/interacciones" \
  -H "X-MAXCIM-Webhook-Secret: $SECRET" \
  -F "id_material=31" \
  -F "fk_alumno=79398411" \
  -F "pregunta=¿De qué color es la bicicleta?" \
  -F "respuesta=Azul" \
  -F "apreciacion_robot=Respondió con una sola palabra, correcta." \
  -F "rpta_correcta=true" \
  -F "audio_rpta=@respuesta.wav;type=audio/wav"
```

Mismo formato para un bit (`pregunta`/`respuesta` los arma y evalúa el robot,
igual que en `oracion_imagen` — MAXCIM no sabe qué palabra "correcta" espera):

```bash
curl -X POST "$BASE/api/interacciones" \
  -H "X-MAXCIM-Webhook-Secret: $SECRET" \
  -F "id_material=40" \
  -F "fk_alumno=79398411" \
  -F "pregunta=¿Qué palabra es esta?" \
  -F "respuesta=mamá" \
  -F "apreciacion_robot=Leyó la palabra completa, correcta." \
  -F "rpta_correcta=true" \
  -F "audio_rpta=@respuesta.wav;type=audio/wav"
```

---

## 10. `GET /api/interacciones`

Historial de turnos. **Requiere** identificador de la docente **y** al menos uno
de `id_material` / `fk_alumno`. Solo devuelve interacciones de materiales de esa
docente (las conversaciones libres, sin material, no salen por aquí). Máximo 200,
de la más reciente a la más antigua.

### Query params

| Param | Obligatorio | Descripción |
|---|---|---|
| `teacher_id` **o** `docente` | Sí | |
| `id_material` | Uno de los dos | Filtra por material. |
| `fk_alumno` | Uno de los dos | Filtra por alumno (`idPersona`). |

### Respuesta `200`

```json
[
  {
    "id": 501,
    "id_material": 31,
    "fk_alumno": "79398411",
    "fecha_hora": "2026-09-10T14:03:11",
    "pregunta": "¿De qué color es la bicicleta?",
    "respuesta": "Azul",
    "audio_rpta_url": "https://.../api/interacciones/501/audio",
    "apreciacion_robot": "Respondió con una sola palabra, correcta.",
    "rpta_correcta": true,
    "periodo": { "id": 3, "nombre": "III BIMESTRE" }
  }
]
```

| Campo | Tipo | Notas |
|---|---|---|
| `fecha_hora` | string ISO **en UTC** (sin zona) | Conviértela a hora local para mostrar. |
| `audio_rpta_url` | string | Absoluta; apunta a §11. |
| `periodo` | objeto \| null | `null` si la fecha cae fuera de todos los bimestres. |

Sin `id_material` ni `fk_alumno` → `400`.

---

## 11. `GET /api/interacciones/{id}/audio`

Descarga el WAV que MAXCIM guardó al registrar el turno. **Requiere**
identificador de la docente y que el material del turno le pertenezca.

- `200` — bytes WAV (`audio/wav`, `attachment`).
- `400` — falta el identificador de la docente.
- `404` — no existe la interacción, o el archivo no está.
- `403` — el turno es de otra docente, o es una conversación libre (sin material).

---

## 12. Resumen de códigos de error

| Código | Significado | Cuerpo |
|---|---|---|
| `400` | Falta un parámetro obligatorio o un valor es inválido | `{"error": "..."}` |
| `401` | Falta o es incorrecto `X-MAXCIM-Webhook-Secret` | `{"error": "Integración no autorizada."}` |
| `403` | El recurso pertenece a otra docente | `{"error": "..."}` |
| `404` | No existe el material / interacción / recurso | `{"error": "..."}` |
| `413` | Un texto supera el límite permitido | `{"error": "..."}` |
| `502` | Fallo al hablar con Gemini (solo endpoints de la consola, no del robot) | `{"error": "..."}` |

Todo error trae un objeto `{"error": "<mensaje en español>"}` apto para registrar
en logs (no necesariamente para mostrar al alumno).

---

## 13. Glosario

| Término | Qué es |
|---|---|
| **docente** | Profesora/profesor. Se identifica por `teacher_id` (`idPersona` de CIMA) o por `docente` (nombre). MAXCIM no guarda la tabla de docentes; viene de CIMA. |
| **alumno** | Estudiante. Se identifica por `fk_alumno` (`idPersona` de CIMA). Tampoco se persiste en MAXCIM. |
| **periodo** | Bimestre académico (I–IV). MAXCIM lo asigna solo; el robot nunca lo envía. |
| **tema** | Unidad temática de una docente dentro de un periodo. Cada material tiene `id_tema`. |
| **material** | Contenido preparado por la docente: `cuento`, `oracion`, `oracion_imagen` o `bits`. |
| **interacción** | Un turno pregunta→respuesta entre un alumno y MAXCIM. |
| **plantilla** | Frase de una `oracion_imagen` con `{{0}}` / `{{1}}` donde van las imágenes. |
| **bit** | Elemento de un material `bits`: una palabra con su imagen, para practicar fonética con sílabas. |
