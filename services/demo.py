from __future__ import annotations

import io
import math
import os
import re
import wave

from services.institutional import (
    AuthenticatedTeacher,
    Classroom,
    RecognizedStudent,
)


DEMO_TEACHER_ID = "DOC-DEMO-01"
DEMO_TEACHER_NAME = "Marín Reyes, Camila"
DEMO_ACCESS_TOKEN = "maxcim-demo-only-token"

DEMO_CLASSROOMS = (
    Classroom("AULA-DEMO-3A", "3RO A — Tutoría", "Tercero de primaria", "Tutoría", "2026"),
    Classroom("AULA-DEMO-2B", "2DO B — Comunicación", "Segundo de primaria", "Comunicación", "2026"),
    Classroom("AULA-DEMO-4C", "4TO C — Tutoría", "Cuarto de primaria", "Tutoría", "2026"),
    Classroom("AULA-DEMO-1A", "1RO A — Comunicación", "Primero de primaria", "Comunicación", "2026"),
    Classroom("AULA-DEMO-5B", "5TO B — Tutoría", "Quinto de primaria", "Tutoría", "2026"),
)


class DemoInstitutionalClient:
    """Isolated institutional adapter used only by the test repository.

    It implements the same interface as the real adapter so the screens and
    business flow stay identical without contacting CIMA's source database.
    """

    login_ready = True
    google_login_ready = True
    recognition_ready = True

    def authenticate(self, institutional_id: str, credential: str) -> AuthenticatedTeacher:
        teacher_id = str(institutional_id or "").strip()
        if not teacher_id or not str(credential or "").strip():
            from services.institutional import InstitutionalAuthenticationError

            raise InstitutionalAuthenticationError()
        return self._teacher(teacher_id)

    def authenticate_google(self, verified_id_token: str) -> AuthenticatedTeacher:
        return self._teacher(DEMO_TEACHER_ID)

    @staticmethod
    def _teacher(teacher_id: str = DEMO_TEACHER_ID) -> AuthenticatedTeacher:
        return AuthenticatedTeacher(
            institutional_id=teacher_id,
            display_name=DEMO_TEACHER_NAME,
            role="DOCENTE",
            access_token=DEMO_ACCESS_TOKEN,
            expires_in_seconds=8 * 60 * 60,
        )

    def list_teacher_classrooms(self, access_token: str, teacher_id: str) -> list[Classroom]:
        return list(DEMO_CLASSROOMS)

    def get_recognized_student(self, person_id: str) -> RecognizedStudent:
        normalized_id = str(person_id or "ALU-DEMO-1042").strip() or "ALU-DEMO-1042"
        names = {
            "ALU-DEMO-1042": "Valeria Mendoza",
            "ALU-DEMO-2048": "Mateo Salazar",
            "ALU-DEMO-4096": "Luciana Torres",
        }
        return RecognizedStudent(
            institutional_id=normalized_id,
            display_name=names.get(normalized_id, "Alumno de pruebas"),
            role="ALUMNO",
            active=True,
            classroom_ids=frozenset(item.institutional_id for item in DEMO_CLASSROOMS),
        )


def create_demo_story(
    *,
    character: str,
    setting: str,
    grade_level: str,
    objective: str,
    extra_details: str,
    duration_minutes: int,
    words_per_minute: int = 125,
) -> dict[str, object]:
    """Build a deterministic story-shaped fixture with the selected duration."""

    details = extra_details or "una sorpresa que el grupo descubre en conjunto"
    target_words = max(80, duration_minutes * words_per_minute)
    passages = [
        f"Había una vez {character}, que vivía una mañana especial en {setting}.",
        f"Todo comenzó cuando apareció un reto relacionado con {objective}.",
        f"Para resolverlo, recordó que también debía incluir {details}.",
        "Primero observó con calma, escuchó a quienes estaban cerca y preguntó qué necesitaban.",
        "Cada respuesta aportó una pista distinta y convirtió el problema en una oportunidad para colaborar.",
        "Aunque el camino parecía difícil, nadie se burló de las ideas de los demás.",
        "El personaje principal explicó su propuesta con palabras claras y esperó su turno para continuar.",
        "Después, el grupo probó una solución, reconoció lo que podía mejorar y volvió a intentarlo.",
        "Con paciencia descubrieron que aprender juntos era más valioso que terminar primero.",
        "Al caer la tarde, el reto estaba resuelto y todos podían contar qué habían aprendido.",
        f"La aventura mostró a estudiantes de {grade_level} que {objective} puede practicarse cada día.",
        "Desde entonces, cuando surgía una dificultad, respiraban, escuchaban y buscaban una respuesta entre todos.",
    ]
    words: list[str] = []
    passage_index = 0
    while len(words) < target_words - 1:
        words.extend(passages[passage_index % len(passages)].split())
        passage_index += 1
    words = words[: target_words - 1]
    words.append("Fin.")
    story = " ".join(words)
    title_character = re.sub(r"\s+", " ", character).strip().capitalize()
    return {
        "title": f"La aventura de {title_character}",
        "story": story,
        "summary": (
            f"{title_character} vive una aventura en {setting} y aprende, junto a sus amigos, "
            f"la importancia de {objective}."
        ),
        "target_duration_minutes": duration_minutes,
        "word_count": len(words),
    }


def create_demo_questions(text: str, counts: dict[str, int]) -> dict[str, list[dict[str, str]]]:
    first_sentence = next(
        (item.strip() for item in re.split(r"(?<=[.!?])\s+", text) if item.strip()),
        "El personaje comenzó una aventura.",
    )
    templates = {
        "literales": (
            "¿Qué ocurrió al inicio de la historia?",
            f"Se menciona explícitamente que: {first_sentence}",
        ),
        "inferenciales": (
            "¿Por qué fue importante escuchar las ideas de los demás?",
            "Porque permitió comprender el problema y encontrar una solución en equipo.",
        ),
        "criticas": (
            "¿Qué habrías hecho tú ante el mismo reto y por qué?",
            "Respuesta personal argumentada y relacionada con lo ocurrido en el cuento.",
        ),
    }
    result: dict[str, list[dict[str, str]]] = {}
    for question_type, count in counts.items():
        question, expected = templates[question_type]
        result[question_type] = [
            {
                "pregunta": question if index == 0 else f"{question[:-1]} ({index + 1})?",
                "respuesta_esperada": expected,
            }
            for index in range(count)
        ]
    return result


def process_demo_document(file_storage) -> tuple[str, str]:
    filename = os.path.basename(file_storage.filename or "cuento")
    extension = os.path.splitext(filename)[1].lower()
    raw = file_storage.read()
    decoded = raw.decode("utf-8", errors="ignore").strip() if extension == ".txt" else ""
    text = decoded if len(decoded) >= 20 else (
        f"Este es el contenido de prueba extraído de {filename}. "
        "Una niña encontró una caja de historias en la biblioteca de su colegio. "
        "Invitó a sus compañeros a escuchar, imaginar un final y compartir sus ideas con respeto. "
        "Entre todos descubrieron que cada respuesta podía enriquecer la aventura."
    )
    sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", text) if item.strip()]
    summary = " ".join(sentences[:2])[:600]
    return text, summary


def create_demo_wav(text: str, target_duration_minutes: int | None = None) -> tuple[bytes, float]:
    """Return a lightweight audible placeholder WAV with an exact test duration."""

    if target_duration_minutes is not None:
        duration_seconds = float(target_duration_minutes * 60)
    else:
        word_count = max(1, len(text.split()))
        duration_seconds = float(max(4, min(30, round(word_count / 2.2))))

    sample_rate = 8_000
    pattern_seconds = 2
    pattern = bytearray()
    tones = (523.25, 659.25, 783.99, 659.25)
    for sample in range(sample_rate * pattern_seconds):
        quarter = (sample // (sample_rate // 2)) % len(tones)
        frequency = tones[quarter]
        value = 128 + int(12 * math.sin(2 * math.pi * frequency * sample / sample_rate))
        pattern.append(max(0, min(255, value)))

    frame_count = int(duration_seconds * sample_rate)
    repeats, remainder = divmod(frame_count, len(pattern))
    frames = bytes(pattern) * repeats + bytes(pattern[:remainder])
    output = io.BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(1)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(frames)
    return output.getvalue(), duration_seconds


def create_demo_assessment(base_metrics: dict) -> dict[str, object]:
    participation = float(base_metrics.get("porcentaje_participacion") or 0)
    comprehension = float(base_metrics.get("porcentaje_comprension") or 0)
    score = round((participation + comprehension) / 2, 2)
    criteria = {
        "comunicacion_oral": {
            "nombre": "Comunicación oral",
            "puntuacion": score,
            "evidencia": "El alumno respondió con frases relacionadas con las preguntas de MAXCIM.",
        },
        "escucha_activa": {
            "nombre": "Escucha activa",
            "puntuacion": participation,
            "evidencia": "Respondió después de los turnos de pregunta registrados.",
        },
        "respeto_turnos": {
            "nombre": "Respeto de turnos",
            "puntuacion": participation,
            "evidencia": "La secuencia de conversación alternó entre MAXCIM y el alumno.",
        },
        "coherencia": {
            "nombre": "Coherencia de las respuestas",
            "puntuacion": comprehension,
            "evidencia": "Las respuestas marcadas como correctas guardan relación con la actividad.",
        },
    }
    return {
        "criterios": criteria,
        "porcentaje_interaccion_oral": score,
        "resumen": "Interacción de prueba completada y lista para la revisión de la docente.",
        "recomendacion_docente": "Revisa los porcentajes y ajusta la retroalimentación antes de aprobar.",
    }
