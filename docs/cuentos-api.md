# Qué expone hoy la API del robot para los "cuentos"

Resumen enfocado en `tipo_material: "cuento"`. Para el resto de tipos
(`oracion`, `oracion_imagen`, `bits`) y el detalle exacto de cada endpoint
(auth, query params, códigos de error), ver la referencia completa en
[`robot-api-reference.md`](robot-api-reference.md).

## 1. Forma del material

`GET /api/materials?teacher_id=...&tipo=cuento` o `GET /api/materials/{id}`
devuelven, para un cuento:

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

  "texto_completo_url": "https://.../api/materials/12/texto",
  "texto_resumen_url":  "https://.../api/materials/12/resumen",
  "audio_completo_url": "https://.../api/materials/12/audio",
  "preguntas_url":      "https://.../api/materials/12/preguntas",
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

No hay ningún campo de audio para el **resumen** — el resumen solo existe
como texto (`texto_resumen_url` → `resumen.txt`). El audio resumen se quitó
de todo el programa (UI, servidor, modelo, API del robot); solo queda el
endpoint `audio` para la narración completa.

## 2. El cuento se reproduce por escenas

Desde el cambio reciente, **todo** cuento se guarda con escenas: cada escena
es un fragmento del texto con su propia imagen y su propio audio. La consola
exige escenas al guardar, así que `escenas` viene vacío (`[]`) solo en
cuentos guardados antes de esta función — ahí el robot debe usar
`audio_completo_url` como único recurso.

**Cómo reproducirlo:** por cada elemento de `escenas`, en orden, descargar
`imagen_url` y `audio_url`, mostrar la imagen mientras suena el audio y pasar
a la siguiente escena cuando el audio termina. No hay timestamps que
sincronizar — cada audio narra exactamente el texto de su propia imagen, y el
fin real de una escena es el fin de su audio (`duracion_s` es solo
orientativo, para precargar o mostrar una barra de progreso).

- Los `texto` de todas las escenas, unidos con un espacio, son el mismo
  contenido que `texto_completo_url`.
- `audio_completo_url` es la unión, en orden, de los `audio_url` de todas las
  escenas (MAXCIM la arma al guardar el cuento) — la misma narración de
  corrido, sin cortes de imagen. Se deja como respaldo; lo esperado es que el
  robot use `escenas`.

## 3. Endpoints involucrados

| Endpoint | Devuelve |
|---|---|
| `GET /api/materials/{id}/texto` | texto completo del cuento (`text/plain`) |
| `GET /api/materials/{id}/resumen` | resumen en texto (`text/plain`) |
| `GET /api/materials/{id}/audio` | narración completa (`audio/wav`) |
| `GET /api/materials/{id}/preguntas` | `[{pregunta, respuesta_esperada}]` |
| `GET /api/materials/{id}/escena-imagen/{i}` | imagen PNG de la escena `i` (0-based) |
| `GET /api/materials/{id}/escena-audio/{i}` | audio WAV de la escena `i` (0-based) |

Todos requieren el header del secreto compartido y `?teacher_id=` (o
`?docente=`) — igual que el resto de la API del robot. En la práctica no hace
falta construir estas URLs a mano: los `*_url` de la respuesta ya vienen
absolutos, listos para descargar agregándoles esos dos requisitos.

## 4. Qué cambió respecto a antes

- Antes existía la posibilidad de un cuento sin escenas, reproducido solo con
  `audio_completo_url` generado a mano. Ahora las escenas son obligatorias al
  guardar; ese camino solo sigue vivo para cuentos antiguos.
- El audio resumen (un audio corto aparte de la narración completa)
  desapareció del todo. Si algún cliente viejo todavía lo esperaba, ya no
  existe ese campo ni ese endpoint.
