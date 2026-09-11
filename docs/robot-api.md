# API del robot

Punto de conexión que usa el robot para consultar material y reportar
interacciones con los alumnos. Vive dentro de la misma app Flask
(`app.py`), bajo el prefijo `/api`.

## Cómo conectarse

- **Base URL**: la del despliegue de MAXCIM (ej. `https://maxcim.tuescuela.edu/`).
- **Autenticación**: header `X-MAXCIM-Webhook-Secret` con el valor exacto
  de la variable de entorno `MAXCIM_WEBHOOK_SECRET`. Sin este header (o con
  un valor incorrecto) toda ruta responde `401 {"error": "Integración no
  autorizada."}`.
- **Excepción**: si `DEMO_MODE=true`, la validación del secreto se omite
  por completo (útil para probar el robot en un entorno de pruebas).
- **Formato**: JSON en cuerpo y respuesta, salvo `POST /api/interacciones`
  (`multipart/form-data`, porque sube un archivo). No requiere cookies ni
  CSRF (el robot no es un navegador).

## Endpoints

| Método y ruta | Para qué sirve |
|---|---|
| `GET /api/materials?teacher_id={id}` (o `docente={nombre}`) | Listar materiales de una docente. Filtro opcional `tipo=cuento\|oracion\|oracion_imagen` |
| `GET /api/temas?teacher_id={id}` (o `docente={nombre}`) | Listar los temas de una docente. Filtro opcional `periodo={id}` |
| `GET /api/materials/{id}` | Obtener metadatos de un material (cuento, oración u oración con imágenes) |
| `GET /api/materials/{id}/{recurso}` | Descargar un recurso del material: `texto`, `resumen`, `audio`, `audio-resumen`, `preguntas` (cuentos) u `oraciones` (oraciones y oraciones con imágenes) |
| `GET /api/materials/{id}/imagen/{oración}/{sustantivo}` | Descargar el PNG de un sustantivo de una "oración con imágenes" (índices 0-based tal como llegan en `oraciones_detalle`) |

### Temas de una docente

`GET /api/temas?teacher_id={id}` devuelve los temas con los que la docente
organiza su material, ordenados por periodo y nombre:

```json
[
  {
    "id": 3,
    "nombre": "Animales",
    "fk_user": "1000001",
    "periodo": {"id": 2, "nombre": "II BIMESTRE", "anio": 2026},
    "materiales_count": 5
  }
]
```

Acepta `docente={nombre}` como alternativa a `teacher_id`, pero el nombre se
resuelve a partir de `material.fk_user_name`: una docente sin ningún material
no se puede ubicar solo por nombre (responde `[]`). Filtro opcional
`periodo={id}`.

Cada material de `GET /api/materials` incluye `id_periodo` e `id_tema`, así que
el robot puede agrupar la lista de materiales por tema usando este endpoint.

### Oraciones con imágenes (`tipo_material: "oracion_imagen"`)

`GET /api/materials/{id}` y `GET /api/materials/{id}/oraciones` incluyen
`oraciones` (lista de textos completos, igual que una `oracion`) y además
`oraciones_detalle`, con una entrada por oración:

```json
{
  "oracion_completa": "El niño monta en su bicicleta azul.",
  "plantilla": "El {{0}} monta en su {{1}} azul.",
  "sustantivos": [
    {"palabra": "niño",      "imagen_url": "https://.../api/materials/12/imagen/0/0"},
    {"palabra": "bicicleta", "imagen_url": "https://.../api/materials/12/imagen/0/1"}
  ]
}
```

El robot arma la pantalla sustituyendo `{{0}}` / `{{1}}` en `plantilla` por la
imagen de `sustantivos[0]` / `sustantivos[1]`. `imagen_url` es `null` si el
material se guardó sin imágenes; las URLs de imagen exigen el mismo secreto y
la identificación de la docente que el resto de la API.
| `POST /api/interacciones` | Registrar un turno de pregunta/respuesta, subiendo el audio de la respuesta |
| `GET /api/interacciones/{id}/audio` | Descargar el audio de una respuesta ya registrada |
| `GET /api/interacciones?id_material={id}&fk_alumno={id}` | Consultar historial de interacciones (se exige al menos uno de los dos filtros) |

## Registrar una interacción

A diferencia del resto de la API, esta llamada es `multipart/form-data`
porque sube el archivo de audio de la respuesta; MAXCIM lo guarda y lo sirve
después por `GET /api/interacciones/{id}/audio`.

```bash
curl -X POST https://.../api/interacciones \
  -H "X-MAXCIM-Webhook-Secret: <secreto>" \
  -F "id_material=12" \
  -F "fk_alumno=79398411" \
  -F "pregunta=..." \
  -F "respuesta=..." \
  -F "apreciacion_robot=correcta" \
  -F "rpta_correcta=true" \
  -F "audio_rpta=@respuesta.wav;type=audio/wav"
```

`id_material` es el único campo opcional (omitirlo = charla libre, sin
material asociado). `audio_rpta` debe ser un WAV válido; si falta o no lo es,
`400`.

Respuesta `201` con el registro creado, incluyendo `audio_rpta_url` (URL
autenticada al archivo que MAXCIM acaba de guardar) y `periodo` (`{"id": 2,
"nombre": "II BIMESTRE"}` o `null`).

El robot no debe enviar ningún campo nuevo: MAXCIM deriva el periodo en el
servidor desde el material, cuando se proporciona uno, o desde la fecha UTC de
`fecha_hora` en una charla libre. No hay una llamada adicional a la API
institucional de CIMA.

## Notas

- El robot resuelve por su cuenta qué alumno tiene enfrente y qué
  material está usando; MAXCIM ya no gestiona sesiones ni reconocimiento
  facial del lado del robot.
- Detalle completo de variables, request/response y ejemplos de curl:
  ver [README.md](../README.md#endpoints-del-robot).
