"""Siembra interacciones falsas en la tabla `interaccion` para previsualizar
las pantallas docentes (avance del aula, detalle del alumno, tarjetas del
tablón) sin depender del robot.

Cada fila sembrada lleva un marcador reconocible en `path_audio_rpta`
(prefijo ``seed/``), así que `--undo` borra exactamente lo que este script
creó y nada más.

Uso:
    # Sembrar ~14 interacciones para un alumno, repartidas en 12 días,
    # usando todos los materiales del docente 70385. Por defecto ~1 de cada 4
    # se siembra como conversación libre con MAXCIM (id_material NULL), que las
    # pantallas docentes rotulan "Conversación":
    python seed_interacciones.py --alumno 79398411

    # Elegir materiales y cantidad:
    python seed_interacciones.py --alumno 79398411 --material 11 --material 12 --n 20

    # Ajustar la proporción de conversaciones libres (0 = ninguna, 1 = todas;
    # con 1 no hace falta ningún material):
    python seed_interacciones.py --alumno 79398411 --conversacion-rate 0.5
    python seed_interacciones.py --alumno 79398411 --conversacion-rate 0

    # Borrar lo sembrado (todo, o filtrando por alumno/material):
    python seed_interacciones.py --undo
    python seed_interacciones.py --undo --alumno 79398411

IMPORTANTE: el alumno solo aparece en /aulas/<aula>/avance y en su detalle si
su ID coincide con un alumno del roster que devuelve la API de CIMA. Un ID
inventado igual cuenta en las tarjetas del tablón y en GET /api/interacciones,
pero no en las pantallas por aula.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import uuid
from datetime import datetime, time, timedelta

from app import app
from extensions import db
from models import TIPO_ORACION, Interaccion, Material

SEED_MARKER = "seed/"
DEFAULT_TEACHER = "70385"

# Respuestas plausibles de un alumno de inicial/primaria cuando acierta una
# pregunta abierta (crítica o inferencial) del cuento del búho.
CORRECT_OPEN_ANSWERS = [
    "Me parece bien, porque el búho escuchó a todos con calma y no se enojó.",
    "Sí es importante ayudar rápido, porque los amigos se apoyan entre ellos.",
    "A veces cuesta esperar mi turno, pero hay que respetar al que está hablando.",
    "Escuchar sin interrumpir ayuda a entender mejor y a no pelear.",
    "Yo respiraría y esperaría mi turno, como hizo el zorro.",
    "Sí serviría en mi salón para resolver los problemas hablando por turnos.",
    "Está bien que no se pelearan; buscaron una solución todos juntos.",
    "Me gustó que el búho agradeciera a todos por haberlo ayudado.",
    "Es mejor trabajar en equipo, porque cada uno tenía una pista distinta.",
    "La enseñanza es escuchar y respetar turnos; lo haría con mis amigos.",
]

# Respuestas típicas cuando el alumno falla.
WRONG_ANSWERS = [
    "No me acuerdo muy bien.",
    "Mmm... creo que no sé.",
    "Porque sí.",
    "¿El lobo? No estoy seguro.",
    "Que se pelearon y se fueron.",
    "Nada, no pasó nada.",
    "Creo que era de noche y ya.",
    "Que el búho se fue volando y perdió todo.",
]

ROBOT_OK_STORY = [
    "Respuesta clara y bien fundamentada.",
    "Comprendió la idea principal y la explicó con sus palabras.",
    "Buena argumentación; conectó el cuento con su experiencia.",
    "Identificó correctamente el dato del texto.",
    "Respondió con seguridad y buen vocabulario.",
]
ROBOT_FAIL_STORY = [
    "La respuesta no corresponde a lo que dice el cuento.",
    "Respondió de forma vaga; conviene volver a leer ese pasaje.",
    "Confundió a los personajes de la historia.",
    "No logró inferir la razón; se sugiere reforzar la comprensión.",
    "Se quedó sin ideas; necesita apoyo para organizar la respuesta.",
]
ROBOT_OK_SENTENCE = [
    "Leyó la oración completa con buena pronunciación.",
    "Lectura fluida y sin errores.",
    "Pronunció cada palabra con claridad.",
    "Respetó los signos y el ritmo de la oración.",
]
ROBOT_FAIL_SENTENCE = [
    "Omitió una palabra al leer; conviene repasar la oración.",
    "Cambió el orden de las palabras.",
    "Se trabó en una palabra y no volvió a intentarlo.",
    "Leyó muy rápido y se saltó parte de la oración.",
]

# Conversación libre del alumno con MAXCIM: no hay material de por medio, así
# que la fila se guarda con id_material = NULL y las pantallas docentes la
# rotulan "Conversación".
CONVERSATION_PROMPTS = [
    "¿Qué fue lo mejor de tu día en el colegio?",
    "Cuéntame algo nuevo que hayas aprendido esta semana.",
    "¿A qué te gusta jugar en el recreo?",
    "Si pudieras tener una mascota, ¿cuál elegirías y por qué?",
    "¿Cómo te sentiste hoy en clase?",
    "Cuéntame sobre tu familia o tus amigos.",
    "¿Qué te gustaría ser cuando seas grande?",
    "¿Hay algo que te preocupe y quieras contarme?",
]
CONVERSATION_OK_ANSWERS = [
    "Hoy jugué con mis amigas y también aprendí a sumar con decenas.",
    "Me gusta jugar a las escondidas y correr en el patio con mis compañeros.",
    "Elegiría un perro, porque podría pasearlo y cuidarlo todos los días.",
    "Me sentí contento porque entendí la lectura y participé en clase.",
    "Tengo un hermano menor y a veces le enseño a leer sus cuentos.",
    "Quiero ser bombero para ayudar a las personas cuando lo necesitan.",
    "Me pongo nervioso en las exposiciones, pero practico en casa con mi mamá.",
    "Aprendí que hay que escuchar a los demás antes de dar mi opinión.",
]
CONVERSATION_WRONG_ANSWERS = [
    "No sé.",
    "No quiero hablar de eso.",
    "Mmm... nada.",
    "No me acuerdo.",
]
ROBOT_OK_CONVERSATION = [
    "Conversación fluida; respondió con oraciones completas y claras.",
    "Se mantuvo en el tema y aportó detalles propios.",
    "Buen intercambio: escuchó, respondió y hasta preguntó de vuelta.",
    "Se expresó con confianza y buen vocabulario para su edad.",
]
ROBOT_FAIL_CONVERSATION = [
    "Respuestas muy cortas; conviene animarlo a desarrollar sus ideas.",
    "Le costó sostener el tema de la conversación.",
    "Participó poco; se sugiere reforzar la expresión oral.",
    "Evitó responder; necesita más confianza para conversar.",
]


def load_material_items(material: Material) -> list[dict]:
    """Devuelve una lista de 'items' de práctica del material. Para un cuento
    son las preguntas de preguntas.json; para una oración, cada oración."""
    raw = material.path_preguntas or ""
    path = (
        os.path.join(app.config["UPLOADS_ROOT"], raw[len("uploads/"):])
        if raw.startswith("uploads/")
        else None
    )

    if material.tipo_material == TIPO_ORACION:
        sentences: list[str] = []
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                sentences = [str(s).strip() for s in data if str(s).strip()]
            except (OSError, json.JSONDecodeError):
                sentences = []
        if not sentences:
            # Registro antiguo: texto plano en la columna.
            sentences = [s.strip() for s in raw.splitlines() if s.strip()]
        return [{"kind": "sentence", "text": s} for s in sentences]

    questions: list[dict] = []
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for q in data:
                if isinstance(q, dict) and (q.get("pregunta") or q.get("enunciado")):
                    questions.append({
                        "kind": "question",
                        "text": str(q.get("pregunta") or q.get("enunciado")).strip(),
                        "expected": str(q.get("respuesta_esperada") or "").strip(),
                    })
        except (OSError, json.JSONDecodeError):
            pass
    return questions


def misread(sentence: str, rng: random.Random) -> str:
    words = sentence.rstrip(".").split()
    if len(words) < 3:
        return sentence.rstrip(".") + "..."
    choice = rng.choice(("drop", "swap", "trail"))
    if choice == "drop":
        del words[rng.randrange(len(words))]
    elif choice == "swap":
        i = rng.randrange(len(words) - 1)
        words[i], words[i + 1] = words[i + 1], words[i]
    else:
        cut = rng.randrange(1, len(words))
        words = words[:cut] + ["..."]
    return " ".join(words)


def build_row(item: dict, correct: bool, rng: random.Random) -> tuple[str, str, str]:
    """Devuelve (pregunta, respuesta, apreciacion_robot) para un item."""
    if item["kind"] == "sentence":
        pregunta = f'Lee en voz alta: "{item["text"]}"'
        if correct:
            return pregunta, item["text"], rng.choice(ROBOT_OK_SENTENCE)
        return pregunta, misread(item["text"], rng), rng.choice(ROBOT_FAIL_SENTENCE)

    pregunta = item["text"]
    expected = item.get("expected", "")
    if not correct:
        return pregunta, rng.choice(WRONG_ANSWERS), rng.choice(ROBOT_FAIL_STORY)
    if expected and not expected.lower().startswith("el estudiante"):
        # Respuesta concreta del texto: el alumno la dice, quizá recortada.
        answer = expected.split(". ")[0].rstrip(".") + "."
    else:
        answer = rng.choice(CORRECT_OPEN_ANSWERS)
    return pregunta, answer, rng.choice(ROBOT_OK_STORY)


def build_conversation_row(correct: bool, rng: random.Random) -> tuple[str, str, str]:
    """Devuelve (pregunta, respuesta, apreciacion_robot) para una conversación
    libre del alumno con MAXCIM, sin material asociado."""
    pregunta = rng.choice(CONVERSATION_PROMPTS)
    if correct:
        return pregunta, rng.choice(CONVERSATION_OK_ANSWERS), rng.choice(ROBOT_OK_CONVERSATION)
    return pregunta, rng.choice(CONVERSATION_WRONG_ANSWERS), rng.choice(ROBOT_FAIL_CONVERSATION)


def correctness_pattern(n: int, rate: float, rng: random.Random) -> list[bool]:
    """Reparte n aciertos/fallos con forma de progreso: arranca flojo y termina
    con una racha buena, para que la fila de 'resultados por material' se vea
    como un avance real."""
    third = max(1, n // 3)
    weights = [0.35] * third + [0.65] * (n - 2 * third) + [0.9] * third
    weights = weights[:n] + [0.7] * (n - len(weights))
    flags = [rng.random() < w for w in weights]
    # Ajuste suave hacia la tasa global pedida.
    target = round(rate * n)
    while sum(flags) > target and False in flags:
        flags[flags.index(True)] = False
    while sum(flags) < target and False in flags:
        # convierte el último fallo en acierto (favorece la racha final)
        for i in range(n - 1, -1, -1):
            if not flags[i]:
                flags[i] = True
                break
    return flags


def spread_timestamps(n: int, days: int, rng: random.Random) -> list[datetime]:
    now = datetime.now()
    start = now - timedelta(days=days)
    span = (now - start).total_seconds()
    stamps = []
    for _ in range(n):
        offset = rng.random() * span
        d = start + timedelta(seconds=offset)
        # Hora de clase: 08:00–13:00.
        d = datetime.combine(
            d.date(),
            time(hour=rng.randint(8, 12), minute=rng.choice((0, 10, 15, 20, 30, 40, 45, 50))),
        )
        stamps.append(d)
    stamps.sort()
    return stamps


def do_seed(args) -> int:
    rng = random.Random(args.seed)

    conversacion_rate = min(1.0, max(0.0, args.conversacion_rate))
    # Redondeo aritmético (no el "half to even" de round()): con una tasa > 0
    # siempre se siembra al menos 1 conversación, para que aparezcan aunque n
    # sea pequeño.
    n_conversaciones = math.floor(conversacion_rate * args.n + 0.5)
    if conversacion_rate > 0 and n_conversaciones == 0 and args.n > 0:
        n_conversaciones = 1
    n_material = args.n - n_conversaciones

    pools = []
    if n_material > 0:
        if args.material:
            materials = Material.query.filter(Material.id.in_(args.material)).all()
            found = {m.id for m in materials}
            missing = [mid for mid in args.material if mid not in found]
            if missing:
                print(f"Materiales inexistentes: {missing}", file=sys.stderr)
                return 2
        else:
            materials = Material.query.filter_by(fk_user=args.teacher).order_by(Material.id).all()
            if not materials:
                print(f"El docente {args.teacher} no tiene materiales.", file=sys.stderr)
                return 2

        for m in materials:
            items = load_material_items(m)
            if items:
                pools.append((m, items))
            else:
                print(f"  (aviso) el material {m.id} '{m.nombre_material}' no tiene items; se omite.")
        if not pools:
            print("Ningún material utilizable.", file=sys.stderr)
            return 2

    flags = correctness_pattern(args.n, args.correct_rate, rng)
    stamps = spread_timestamps(args.n, args.days, rng)
    # Posiciones que serán conversaciones libres (id_material NULL).
    conversacion_idx = (
        set(rng.sample(range(args.n), n_conversaciones)) if n_conversaciones else set()
    )

    print(f"Sembrando {args.n} interacciones para el alumno {args.alumno}")
    if pools:
        print(f"Materiales: {', '.join(f'{m.id} ({m.nombre_material})' for m, _ in pools)}")
    if n_conversaciones:
        print(f"Conversaciones libres sin material: {n_conversaciones}/{args.n}")
    print(f"Aciertos: {sum(flags)}/{args.n}  ·  Rango: "
          f"{stamps[0].strftime('%d/%m/%Y')} – {stamps[-1].strftime('%d/%m/%Y')}")
    if not args.yes:
        if input("¿Continuar? [s/N] ").strip().lower() not in ("s", "si", "sí", "y"):
            print("Cancelado.")
            return 1

    rows = []
    for i in range(args.n):
        if i in conversacion_idx:
            pregunta, respuesta, apreciacion = build_conversation_row(flags[i], rng)
            material_id = None
        else:
            material, items = rng.choice(pools)
            item = rng.choice(items)
            pregunta, respuesta, apreciacion = build_row(item, flags[i], rng)
            material_id = material.id
        rows.append(Interaccion(
            id_material=material_id,
            fk_alumno=args.alumno,
            fecha_hora=stamps[i],
            pregunta=pregunta,
            respuesta=respuesta,
            path_audio_rpta=f"{SEED_MARKER}{args.alumno}/{uuid.uuid4().hex}.wav",
            apreciacion_robot=apreciacion,
            rpta_correcta=bool(flags[i]),
        ))
    db.session.add_all(rows)
    db.session.commit()
    print(f"Listo: {len(rows)} filas insertadas.")
    print("Abre el tablón, entra al aula del alumno y pulsa «Ver avance».")
    return 0


def do_undo(args) -> int:
    q = Interaccion.query.filter(Interaccion.path_audio_rpta.like(f"{SEED_MARKER}%"))
    if args.alumno:
        q = q.filter(Interaccion.fk_alumno == args.alumno)
    if args.material:
        q = q.filter(Interaccion.id_material.in_(args.material))
    total = q.count()
    if not total:
        print("No hay interacciones sembradas que coincidan.")
        return 0
    if not args.yes:
        if input(f"Se borrarán {total} interacciones sembradas. ¿Continuar? [s/N] ").strip().lower() not in ("s", "si", "sí", "y"):
            print("Cancelado.")
            return 1
    q.delete(synchronize_session=False)
    db.session.commit()
    print(f"Borradas {total} filas.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Siembra o borra interacciones falsas de prueba.")
    parser.add_argument("-a", "--alumno", help="ID institucional del alumno (fk_alumno).")
    parser.add_argument("-t", "--teacher", default=DEFAULT_TEACHER,
                        help=f"ID institucional del docente (default {DEFAULT_TEACHER}).")
    parser.add_argument("-m", "--material", type=int, action="append",
                        help="ID de material a usar; repetible. Default: todos los del docente.")
    parser.add_argument("-n", type=int, default=14, dest="n", help="Cantidad de interacciones (default 14).")
    parser.add_argument("--days", type=int, default=12, help="Repartir en los últimos N días (default 12).")
    parser.add_argument("--correct-rate", type=float, default=0.7, help="Fracción aproximada de aciertos (default 0.7).")
    parser.add_argument("--conversacion-rate", type=float, default=0.25,
                        help="Fracción de interacciones que serán conversaciones libres con MAXCIM, "
                             "sin material (id_material NULL). Default 0.25; 0 desactiva, 1.0 hace que "
                             "todas lo sean (y no hace falta ningún material).")
    parser.add_argument("--seed", type=int, default=42, help="Semilla del generador (default 42).")
    parser.add_argument("--undo", action="store_true", help="Borra las interacciones sembradas (marcador seed/).")
    parser.add_argument("-y", "--yes", action="store_true", help="No pedir confirmación.")
    args = parser.parse_args()

    if not args.undo and not args.alumno:
        parser.error("hace falta --alumno (o usa --undo).")

    with app.app_context():
        return do_undo(args) if args.undo else do_seed(args)


if __name__ == "__main__":
    raise SystemExit(main())
