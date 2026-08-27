import io
import hmac
import json
import mimetypes
import os
import re
import tempfile
import uuid
import wave
from datetime import UTC, date, datetime
from urllib.parse import quote_plus

from dotenv import load_dotenv
from flask import (
    Flask,
    Response,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from google import genai
from google.genai import types

from extensions import db
from models import (
    EventoReconocimiento,
    EvaluacionInteraccion,
    Material,
    Pregunta,
    SesionInteraccion,
    TurnoConversacion,
)
from services.evaluation import calculate_base_metrics, generate_ai_assessment

load_dotenv()

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
GEMINI_TTS_VOICE = os.environ.get("GEMINI_TTS_VOICE", "Puck")

gemini_client = genai.Client(api_key=GOOGLE_API_KEY) if GOOGLE_API_KEY else None


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def utc_now() -> datetime:
    """UTC stored without tzinfo for compatibility with MySQL DATETIME."""
    return datetime.now(UTC).replace(tzinfo=None)


MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
MYSQL_PORT = os.environ.get("MYSQL_PORT", "3306")
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "")
SQLALCHEMY_DATABASE_URI = (
    f"mysql+pymysql://{quote_plus(MYSQL_USER)}:{quote_plus(MYSQL_PASSWORD)}"
    f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4"
)

EXTRACT_PROMPT = (
    "Extrae todo el texto de este documento, tal como aparece, sin resumir, "
    "interpretar ni agregar comentarios. Responde solo con el texto extraído."
)
SUMMARY_PROMPT_TEMPLATE = (
    "Resume el siguiente texto en 2 o 3 oraciones, en español, de forma clara "
    "y concisa:\n\n{text}"
)

QUESTION_TYPES = ["literales", "inferenciales", "criticas"]
QUESTION_TYPE_DESCRIPTIONS = {
    "literales": "preguntas literales, que se responden con información explícita presente directamente en el texto",
    "inferenciales": "preguntas inferenciales, que requieren deducir información que el texto no dice explícitamente, a partir de sus pistas",
    "criticas": "preguntas críticas, que invitan a opinar, valorar o reflexionar críticamente sobre el texto",
}
QUESTIONS_PROMPT_TEMPLATE = (
    "A partir del siguiente texto, genera preguntas de comprensión lectora en "
    "español para estudiantes de nivel inicial y primaria. Genera exactamente esta cantidad "
    "de preguntas para cada tipo:\n{requirements}\n\nTexto:\n{text}\n\n"
    "Responde únicamente con un JSON de la forma "
    '{{"literales": [{{"pregunta": "...", "respuesta_esperada": "..."}}], '
    '"inferenciales": [...], "criticas": [...]}}, '
    "donde cada elemento contiene la pregunta y una respuesta esperada o criterio de evaluación. "
    "No agregues numeración, comentarios ni texto fuera del JSON."
)
MAX_QUESTIONS_PER_TYPE = 15

STORY_PROMPT_TEMPLATE = """
Crea un cuento educativo original en español para {nivel}. El personaje principal
es {personaje} y la historia ocurre en {escenario}. El objetivo pedagógico es
{objetivo}. Incorpora de forma natural estas respuestas adicionales del alumno:
{detalles}

El cuento debe ser apropiado para la edad, claro, positivo y útil para una
interacción oral posterior. No incluyas preguntas todavía. Devuelve solamente JSON:
{{"titulo": "...", "cuento": "...", "resumen": "..."}}
""".strip()

# Gemini TTS quality tends to drift (flatter tone, mumbled words) the longer a
# single generation runs. Splitting the text into short chunks — and re-stating
# the same tone instruction on every chunk — keeps each individual generation
# short enough that the voice stays consistent from start to finish.
TTS_CHUNK_MAX_CHARS = 700
TTS_STYLE_INSTRUCTION = (
    "Narra el siguiente fragmento en español latinoamericano, en voz alta, con un tono alegre, "
    "natural y propio de un cuento infantil. Mantén EXACTAMENTE la misma "
    "tonalidad, ritmo, energía, volumen y claridad de principio a fin de este "
    "fragmento, sin que la voz decaiga, se apague, acelere o pierda entonación "
    "en ningún momento:\n\n"
)
TTS_DEFAULT_SAMPLE_RATE = 24000

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
ALLOWED_UPLOAD_EXTENSIONS = {".doc", ".docx", ".pdf", ".txt"}
MAX_SOURCE_TEXT_CHARS = 120_000
MAX_SUMMARY_CHARS = 20_000
MAX_TTS_TEXT_CHARS = 30_000
MAX_TRANSCRIPT_CHARS = 20_000
MAX_OBJECTIVE_CHARS = 2_000

DIAS_ES = [
    "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo",
]
MESES_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

STAT_CARDS = [
    {"value": "5", "label": "Aulas a cargo", "color": "#2f5bcf"},
    {"value": "12", "label": "Evaluaciones pendientes", "color": "#d64545"},
    {"value": "78%", "label": "Promedio general", "color": "#1f9d55"},
    {"value": "146", "label": "Alumnos evaluados", "color": "#132a5e"},
]

AULAS = [
    {
        "id": "demo-3ro-a",
        "name": "3RO A SECONDARY — Tutoría",
        "grade": "Tercero de Secundaria",
        "tutor": "Herrera, Brigny",
        "initials": "BH",
        "avatar_bg": "#2f5bcf",
        "score": 82,
        "pendientes": 2,
        "skills": [
            {"name": "Comunicación oral", "value": 85, "color": "#2f5bcf"},
            {"name": "Escucha activa", "value": 76, "color": "#1f9d55"},
            {"name": "Trabajo en equipo", "value": 84, "color": "#e6a23c"},
        ],
    },
    {
        "id": "demo-1ro-b",
        "name": "1RO B SECONDARY — Tutoría",
        "grade": "Primero de Secundaria",
        "tutor": "Torres, Jhonatan",
        "initials": "JT",
        "avatar_bg": "#1f9d55",
        "score": 74,
        "pendientes": 4,
        "skills": [
            {"name": "Empatía", "value": 70, "color": "#2f5bcf"},
            {"name": "Comunicación oral", "value": 79, "color": "#1f9d55"},
            {"name": "Resolución de conflictos", "value": 72, "color": "#e6a23c"},
        ],
    },
    {
        "id": "demo-4to-c",
        "name": "4TO C SECONDARY — Tutoría",
        "grade": "Cuarto de Secundaria",
        "tutor": "Mendoza, Karla",
        "initials": "KM",
        "avatar_bg": "#e6a23c",
        "score": 88,
        "pendientes": 1,
        "skills": [
            {"name": "Trabajo en equipo", "value": 90, "color": "#2f5bcf"},
            {"name": "Escucha activa", "value": 86, "color": "#1f9d55"},
            {"name": "Comunicación oral", "value": 88, "color": "#e6a23c"},
        ],
    },
    {
        "id": "demo-2do-a",
        "name": "2DO A SECONDARY — Tutoría",
        "grade": "Segundo de Secundaria",
        "tutor": "Villanueva, Sofía",
        "initials": "SV",
        "avatar_bg": "#8a5fd6",
        "score": 69,
        "pendientes": 5,
        "skills": [
            {"name": "Empatía", "value": 65, "color": "#2f5bcf"},
            {"name": "Comunicación oral", "value": 71, "color": "#1f9d55"},
            {"name": "Escucha activa", "value": 70, "color": "#e6a23c"},
        ],
    },
]

MATERIAL_SKILLS = [
    "Todas las habilidades",
    "Comunicación oral",
    "Escucha activa",
    "Empatía",
    "Trabajo en equipo",
    "Resolución de conflictos",
]

UPLOAD_PREVIEW = {
    "transcribed_text": (
        "Había una vez un pequeño zorro llamado Fido que vivía en el bosque "
        "junto a sus amigos. Un día, Fido notó que su amiga la ardilla estaba "
        "triste porque nadie escuchaba sus ideas durante los juegos. Fido "
        "decidió sentarse junto a ella y prestarle toda su atención, sin "
        "interrumpir. Poco a poco, aprendió que escuchar con calma ayuda a "
        "que los demás se sientan valorados y comprendidos..."
    ),
    "summary_text": (
        "Fido, un zorro del bosque, aprende que escuchar con atención a sus "
        "amigos les ayuda a sentirse valorados."
    ),
    "questions": [
        {
            "key": "literales",
            "label": "Literales", "default": 3,
            "label_color": "#132a5e", "value_color": "#2f5bcf",
            "bg": "#eaf0fd", "border": "#c7d5f7",
        },
        {
            "key": "inferenciales",
            "label": "Inferenciales", "default": 2,
            "label_color": "#14532d", "value_color": "#1f9d55",
            "bg": "#e8f7ee", "border": "#b7e4c7",
        },
        {
            "key": "criticas",
            "label": "Críticas", "default": 1,
            "label_color": "#7c4a03", "value_color": "#b8760a",
            "bg": "#fdf3e3", "border": "#f5d99b",
        },
    ],
}


def extract_and_summarize(file_storage) -> tuple[str, str]:
    """Uploads the file to Gemini, extracts its text, then summarizes it."""
    filename = file_storage.filename or "documento"
    mime_type = file_storage.mimetype or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    suffix = os.path.splitext(filename)[1]

    tmp_path = None
    uploaded_file = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            file_storage.save(tmp)
            tmp_path = tmp.name

        uploaded_file = gemini_client.files.upload(
            file=tmp_path,
            config={"mime_type": mime_type, "display_name": filename},
        )

        extract_response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[uploaded_file, EXTRACT_PROMPT],
        )
        transcribed_text = extract_response.text.strip()

        summary_response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=SUMMARY_PROMPT_TEMPLATE.format(text=transcribed_text),
        )
        summary_text = summary_response.text.strip()

        return transcribed_text, summary_text
    finally:
        if uploaded_file is not None:
            try:
                gemini_client.files.delete(name=uploaded_file.name)
            except Exception:
                pass
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


def generate_questions(text: str, counts: dict[str, int]) -> dict[str, list[dict[str, str]]]:
    """Asks Gemini for reading-comprehension questions, grouped by type, in the
    quantities requested."""
    requirements = "\n".join(
        f"- {count} {QUESTION_TYPE_DESCRIPTIONS[qtype]}"
        for qtype, count in counts.items()
        if count > 0
    )

    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=QUESTIONS_PROMPT_TEMPLATE.format(requirements=requirements, text=text),
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    data = json.loads(response.text)

    normalized = {}
    for qtype, count in counts.items():
        questions = []
        for raw_question in data.get(qtype, [])[:count]:
            if isinstance(raw_question, dict):
                statement = str(raw_question.get("pregunta") or "").strip()
                expected = str(raw_question.get("respuesta_esperada") or "").strip()
            else:
                # Backwards compatibility with older Gemini responses.
                statement = str(raw_question).strip()
                expected = ""
            if statement:
                questions.append({
                    "pregunta": statement,
                    "respuesta_esperada": expected,
                })
        normalized[qtype] = questions

    return normalized


def generate_story(
    character: str,
    setting: str,
    grade_level: str,
    objective: str,
    extra_details: str,
) -> dict[str, str]:
    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=STORY_PROMPT_TEMPLATE.format(
            nivel=grade_level,
            personaje=character,
            escenario=setting,
            objetivo=objective,
            detalles=extra_details or "Sin detalles adicionales.",
        ),
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    data = json.loads(response.text)
    title = str(data.get("titulo") or "").strip()
    story = str(data.get("cuento") or "").strip()
    summary = str(data.get("resumen") or "").strip()
    if not title or not story or not summary:
        raise ValueError("Gemini no devolvió un cuento completo.")
    return {"title": title, "story": story, "summary": summary}


def _split_text_into_chunks(text: str, max_chars: int = TTS_CHUNK_MAX_CHARS) -> list[str]:
    """Splits text into sentence-aligned chunks no longer than max_chars."""
    sentences = re.split(r"(?<=[.!?…])\s+", text.strip())
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        if not sentence:
            continue
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) > max_chars and current:
            chunks.append(current)
            current = sentence
        else:
            current = candidate

    if current:
        chunks.append(current)

    return chunks or [text.strip()]


def generate_speech(text: str) -> bytes:
    """Converts text to speech with Gemini TTS, chunked to keep tone consistent
    across long passages, and returns a WAV file's bytes."""
    pcm_data = bytearray()
    sample_rate = TTS_DEFAULT_SAMPLE_RATE

    for chunk in _split_text_into_chunks(text):
        response = gemini_client.models.generate_content(
            model=GEMINI_TTS_MODEL,
            contents=TTS_STYLE_INSTRUCTION + chunk,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=GEMINI_TTS_VOICE
                        )
                    )
                ),
            ),
        )
        inline_data = response.candidates[0].content.parts[0].inline_data
        pcm_data.extend(inline_data.data)

        rate_match = re.search(r"rate=(\d+)", inline_data.mime_type or "")
        if rate_match:
            sample_rate = int(rate_match.group(1))

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(bytes(pcm_data))

    return buffer.getvalue()


# Placeholder until login comes from the school's API — that response will carry
# the docente's real identifier (fk_user) in place of this stub value.
USER = {"name": "Marín Reyes, Camila", "initials": "MR", "role": "DOCENTE", "fk_user": 72737674}


def format_period_label(today: date) -> str:
    return f"{DIAS_ES[today.weekday()]} {today.day}, {MESES_ES[today.month - 1]}"


def create_app(test_config: dict | None = None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev"),
        MAX_CONTENT_LENGTH=MAX_UPLOAD_BYTES,
        SQLALCHEMY_DATABASE_URI=SQLALCHEMY_DATABASE_URI,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        FACE_MATCH_MIN_CONFIDENCE=float(os.environ.get("FACE_MATCH_MIN_CONFIDENCE", "0.85")),
        MAXCIM_WEBHOOK_SECRET=os.environ.get("MAXCIM_WEBHOOK_SECRET", ""),
        DEMO_MODE=env_bool("DEMO_MODE", False),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=env_bool("SESSION_COOKIE_SECURE", False),
    )
    if test_config:
        app.config.update(test_config)
    db.init_app(app)

    def webhook_authorized() -> bool:
        if app.config.get("TESTING"):
            return True
        expected = app.config.get("MAXCIM_WEBHOOK_SECRET", "")
        received = request.headers.get("X-MAXCIM-Webhook-Secret", "")
        return bool(expected and received and hmac.compare_digest(expected, received))

    def teacher_actions_available() -> bool:
        # Replaced by a validated institutional session when the API contract
        # is provided. Until then, teacher data/actions are demo/test only.
        return bool(app.config.get("DEMO_MODE") or app.config.get("TESTING"))

    def trusted_robot_request() -> bool:
        return teacher_actions_available() or webhook_authorized()

    def institutional_auth_pending_response():
        return jsonify({
            "error": "La autenticación institucional aún no está configurada. Activa DEMO_MODE solo para desarrollo."
        }), 503

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if request.path.startswith("/api/") or request.path in {
            "/dashboard", "/material", "/sesiones",
        }:
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.route("/service-worker.js")
    def service_worker():
        response = send_from_directory(app.static_folder, "service-worker.js")
        response.headers["Service-Worker-Allowed"] = "/"
        response.headers["Cache-Control"] = "no-cache"
        return response

    @app.route("/")
    def index():
        return redirect(url_for("dashboard"))

    @app.route("/dashboard")
    def dashboard():
        if not teacher_actions_available():
            return institutional_auth_pending_response()
        return render_template(
            "dashboard.html",
            active_nav="tablon",
            user=USER,
            stat_cards=STAT_CARDS,
            aulas=AULAS,
            today_label=format_period_label(date.today()),
            periodo_range="22/06/2026 – 22/07/2026",
        )

    @app.route("/material")
    def material():
        if not teacher_actions_available():
            return institutional_auth_pending_response()
        materials = (
            Material.query.filter_by(fk_user=str(USER["fk_user"]))
            .order_by(Material.fecha_subido.desc(), Material.id.desc())
            .all()
        )
        return render_template(
            "material.html",
            active_nav="material",
            user=USER,
            materials=materials,
            skills=MATERIAL_SKILLS,
            upload_preview=UPLOAD_PREVIEW,
        )

    @app.route("/sesiones")
    def sesiones():
        if not teacher_actions_available():
            return institutional_auth_pending_response()
        recent_sessions = (
            SesionInteraccion.query
            .filter_by(id_docente_institucional=str(USER["fk_user"]))
            .order_by(SesionInteraccion.creada_en.desc())
            .limit(20)
            .all()
        )
        materials = (
            Material.query.filter_by(fk_user=str(USER["fk_user"]))
            .order_by(Material.fecha_subido.desc(), Material.id.desc())
            .all()
        )
        return render_template(
            "sesiones.html",
            active_nav="sesiones",
            user=USER,
            aulas=AULAS,
            materials=materials,
            sessions=recent_sessions,
            demo_mode=app.config["DEMO_MODE"],
        )

    @app.route("/api/material/process", methods=["POST"])
    def process_material():
        if not teacher_actions_available():
            return institutional_auth_pending_response()
        uploaded = request.files.get("file")
        if not uploaded or not uploaded.filename:
            return jsonify({"error": "No se recibió ningún archivo."}), 400
        extension = os.path.splitext(uploaded.filename)[1].lower()
        if extension not in ALLOWED_UPLOAD_EXTENSIONS:
            return jsonify({"error": "El archivo debe ser DOC, DOCX, PDF o TXT."}), 400
        if not gemini_client:
            return jsonify({"error": "GOOGLE_API_KEY no está configurada en el servidor."}), 503

        try:
            transcribed_text, summary_text = extract_and_summarize(uploaded)
        except Exception:
            app.logger.exception("No se pudo procesar el documento con Gemini")
            return jsonify({"error": "No se pudo procesar el documento con Gemini."}), 502

        return jsonify({
            "transcribed_text": transcribed_text,
            "summary_text": summary_text,
        })

    @app.route("/api/material/tts", methods=["POST"])
    def material_tts():
        if not teacher_actions_available():
            return institutional_auth_pending_response()
        payload = request.get_json(silent=True) or {}
        text = (payload.get("text") or "").strip()
        if not text:
            return jsonify({"error": "No hay texto para convertir a audio."}), 400
        if len(text) > MAX_TTS_TEXT_CHARS:
            return jsonify({"error": "El texto es demasiado largo para generar audio."}), 413
        if not gemini_client:
            return jsonify({"error": "GOOGLE_API_KEY no está configurada en el servidor."}), 503

        try:
            audio_bytes = generate_speech(text)
        except Exception:
            app.logger.exception("No se pudo generar el audio con Gemini")
            return jsonify({"error": "No se pudo generar el audio con Gemini."}), 502

        return Response(audio_bytes, mimetype="audio/wav")

    @app.route("/api/material/questions", methods=["POST"])
    def material_questions():
        if not teacher_actions_available():
            return institutional_auth_pending_response()
        payload = request.get_json(silent=True) or {}
        text = (payload.get("text") or "").strip()
        counts_payload = payload.get("counts") or {}

        if not text:
            return jsonify({"error": "No hay texto para generar preguntas."}), 400
        if len(text) > MAX_SOURCE_TEXT_CHARS:
            return jsonify({"error": "El texto es demasiado largo para generar preguntas."}), 413

        counts = {}
        for qtype in QUESTION_TYPES:
            try:
                count = int(counts_payload.get(qtype, 0))
            except (TypeError, ValueError):
                count = 0
            counts[qtype] = max(0, min(count, MAX_QUESTIONS_PER_TYPE))

        if not any(counts.values()):
            return jsonify({"error": "Indica al menos una pregunta para generar."}), 400
        if not gemini_client:
            return jsonify({"error": "GOOGLE_API_KEY no está configurada en el servidor."}), 503

        try:
            questions = generate_questions(text, counts)
        except Exception:
            app.logger.exception("No se pudieron generar las preguntas con Gemini")
            return jsonify({"error": "No se pudieron generar las preguntas con Gemini."}), 502

        return jsonify({"questions": questions})

    @app.route("/api/story/generate", methods=["POST"])
    def story_generate():
        if not teacher_actions_available():
            return institutional_auth_pending_response()
        payload = request.get_json(silent=True) or {}
        character = str(payload.get("character") or "").strip()
        setting = str(payload.get("setting") or "").strip()
        grade_level = str(payload.get("grade_level") or "").strip()
        objective = str(payload.get("objective") or "").strip()
        extra_details = str(payload.get("extra_details") or "").strip()

        missing = [
            label
            for label, value in (
                ("personaje principal", character),
                ("lugar de la historia", setting),
                ("nivel del aula", grade_level),
                ("objetivo pedagógico", objective),
            )
            if not value
        ]
        if missing:
            return jsonify({"error": f"Falta indicar: {', '.join(missing)}."}), 400
        field_limits = {
            "personaje principal": (character, 120),
            "lugar de la historia": (setting, 160),
            "nivel del aula": (grade_level, 100),
            "objetivo pedagógico": (objective, 240),
            "detalles adicionales": (extra_details, 1_000),
        }
        too_long = [label for label, (value, limit) in field_limits.items() if len(value) > limit]
        if too_long:
            return jsonify({"error": f"Excede el límite permitido: {', '.join(too_long)}."}), 413
        if not gemini_client:
            return jsonify({"error": "GOOGLE_API_KEY no está configurada en el servidor."}), 503

        try:
            story = generate_story(
                character=character,
                setting=setting,
                grade_level=grade_level,
                objective=objective,
                extra_details=extra_details,
            )
        except Exception:
            app.logger.exception("No se pudo crear el cuento con Gemini")
            return jsonify({"error": "No se pudo crear el cuento con Gemini."}), 502

        return jsonify(story)

    @app.route("/api/material/save", methods=["POST"])
    def save_material():
        if not teacher_actions_available():
            return institutional_auth_pending_response()
        title = (request.form.get("title") or "").strip() or "Material sin título"
        transcribed_text = (request.form.get("transcribed_text") or "").strip()
        summary_text = (request.form.get("summary_text") or "").strip()
        questions_json_raw = (request.form.get("questions_json") or "").strip()
        audio_full = request.files.get("audio_full")
        audio_summary = request.files.get("audio_summary")

        if not transcribed_text or not summary_text:
            return jsonify({"error": "Falta el texto completo o el resumen."}), 400
        if len(title) > 255 or len(transcribed_text) > MAX_SOURCE_TEXT_CHARS or len(summary_text) > MAX_SUMMARY_CHARS:
            return jsonify({"error": "El título, texto o resumen excede el límite permitido."}), 413
        if not questions_json_raw:
            return jsonify({"error": "Falta generar las preguntas."}), 400
        try:
            questions_data = json.loads(questions_json_raw)
        except json.JSONDecodeError:
            return jsonify({"error": "Las preguntas no tienen un formato JSON válido."}), 400
        if not isinstance(questions_data, list) or not questions_data:
            return jsonify({"error": "Falta generar las preguntas."}), 400
        if len(questions_data) > len(QUESTION_TYPES) * MAX_QUESTIONS_PER_TYPE:
            return jsonify({"error": "Hay demasiadas preguntas en el material."}), 413
        invalid_questions = [
            question
            for question in questions_data
            if not isinstance(question, dict)
            or not str(question.get("pregunta") or question.get("enunciado") or "").strip()
            or not str(question.get("respuesta_esperada") or "").strip()
        ]
        if invalid_questions:
            return jsonify({
                "error": "Cada pregunta debe incluir un enunciado y una respuesta esperada revisados por la docente."
            }), 400
        if not audio_full or not audio_summary:
            return jsonify({"error": "Falta generar el audio completo o el audio resumen."}), 400

        material_dir_name = uuid.uuid4().hex
        material_dir = os.path.join(app.static_folder, "uploads", material_dir_name)
        os.makedirs(material_dir, exist_ok=True)

        text_files = {
            "texto.txt": transcribed_text.encode("utf-8"),
            "resumen.txt": summary_text.encode("utf-8"),
            "preguntas.json": json.dumps(questions_data, ensure_ascii=False, indent=2).encode("utf-8"),
        }
        for filename, content in text_files.items():
            with open(os.path.join(material_dir, filename), "wb") as f:
                f.write(content)

        audio_full.save(os.path.join(material_dir, "audio.wav"))
        audio_summary.save(os.path.join(material_dir, "audio_resumen.wav"))

        material = Material(
            nombre_material=title,
            path_texto=f"uploads/{material_dir_name}/texto.txt",
            path_texto_resumen=f"uploads/{material_dir_name}/resumen.txt",
            path_preguntas=f"uploads/{material_dir_name}/preguntas.json",
            path_audio=f"uploads/{material_dir_name}/audio.wav",
            path_audio_resumen=f"uploads/{material_dir_name}/audio_resumen.wav",
            fk_user=str(USER["fk_user"]),
        )
        db.session.add(material)
        db.session.flush()

        approved_at = utc_now()
        for order, question_data in enumerate(questions_data, start=1):
            if not isinstance(question_data, dict):
                continue
            statement = str(
                question_data.get("pregunta") or question_data.get("enunciado") or ""
            ).strip()
            if not statement:
                continue
            db.session.add(Pregunta(
                id_material=material.id,
                tipo=str(question_data.get("tipo") or "general")[:30],
                enunciado=statement,
                respuesta_esperada=str(question_data.get("respuesta_esperada") or "").strip() or None,
                orden=order,
                generada_por_ia=True,
                editada_por_docente=bool(question_data.get("editada_por_docente", False)),
                estado="aprobada",
                aprobada_por=str(USER["fk_user"]),
                aprobada_en=approved_at,
            ))
        db.session.commit()

        return jsonify({"material_id": material.id})

    def serialize_material(material):
        return {
            "id": material.id,
            "titulo": material.nombre_material,
            "fecha_subido": material.fecha_subido.isoformat() if material.fecha_subido else None,
            "fk_user": material.fk_user,
            "texto_completo_url": url_for("static", filename=material.path_texto, _external=True),
            "texto_resumen_url": url_for("static", filename=material.path_texto_resumen, _external=True),
            "audio_completo_url": url_for("static", filename=material.path_audio, _external=True),
            "audio_resumen_url": url_for("static", filename=material.path_audio_resumen, _external=True),
            "preguntas_url": url_for("static", filename=material.path_preguntas, _external=True),
            "preguntas": [
                {
                    "id": question.id,
                    "tipo": question.tipo,
                    "pregunta": question.enunciado,
                    "respuesta_esperada": question.respuesta_esperada,
                    "estado": question.estado,
                }
                for question in material.preguntas
            ],
        }

    # Temporary compatibility endpoint for the robot-side prototype. It is
    # available only in demo/test until institutional authentication replaces it.
    @app.route("/api/materials", methods=["GET"])
    def list_materials():
        if not teacher_actions_available():
            return institutional_auth_pending_response()
        dni = request.args.get("dni", "").strip()
        if not dni:
            return jsonify({"error": "Falta el parámetro dni."}), 400

        materials = (
            Material.query.filter_by(fk_user=dni)
            .order_by(Material.fecha_subido.desc(), Material.id.desc())
            .all()
        )
        return jsonify([serialize_material(m) for m in materials])

    @app.route("/api/materials/<int:material_id>", methods=["GET"])
    def get_material(material_id):
        if not teacher_actions_available():
            return institutional_auth_pending_response()
        material = db.session.get(Material, material_id)
        if not material:
            return jsonify({"error": "Material no encontrado."}), 404
        return jsonify(serialize_material(material))

    def decimal_value(value):
        return float(value) if value is not None else None

    def parse_optional_bool(value):
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "si", "sí"}:
                return True
            if normalized in {"false", "0", "no"}:
                return False
        raise ValueError("El valor booleano no es válido.")

    def serialize_turn(turn):
        return {
            "id": turn.id,
            "order": turn.orden,
            "speaker": turn.emisor,
            "transcript": turn.texto_transcrito,
            "question_id": turn.id_pregunta,
            "audio_path": turn.path_audio,
            "response_time_ms": turn.tiempo_respuesta_ms,
            "is_correct": turn.respuesta_correcta,
            "needed_help": turn.necesito_ayuda,
            "created_at": turn.creada_en.isoformat() if turn.creada_en else None,
        }

    def serialize_evaluation(evaluation):
        if evaluation is None:
            return None
        try:
            criteria = json.loads(evaluation.criterios_json) if evaluation.criterios_json else {}
        except json.JSONDecodeError:
            criteria = {}
        return {
            "id": evaluation.id,
            "questions_asked": evaluation.preguntas_realizadas,
            "answers_recorded": evaluation.respuestas_registradas,
            "correct_answers": evaluation.respuestas_correctas,
            "average_response_ms": evaluation.promedio_respuesta_ms,
            "participation_percentage": decimal_value(evaluation.porcentaje_participacion),
            "comprehension_percentage": decimal_value(evaluation.porcentaje_comprension),
            "oral_interaction_percentage": decimal_value(evaluation.porcentaje_interaccion_oral),
            "overall_percentage": decimal_value(evaluation.porcentaje_general),
            "criteria": criteria,
            "ai_summary": evaluation.resumen_ia,
            "status": evaluation.estado,
            "teacher_feedback": evaluation.retroalimentacion_docente,
            "reviewed_by": evaluation.revisada_por,
            "reviewed_at": evaluation.revisada_en.isoformat() if evaluation.revisada_en else None,
        }

    def serialize_session(session, include_turns: bool = False):
        payload = {
            "id": session.id,
            "uuid": session.uuid,
            "status": session.estado,
            "teacher_id": session.id_docente_institucional,
            "student_id": session.id_alumno_institucional,
            "student_name": session.alumno_nombre,
            "classroom_id": session.id_aula_institucional,
            "material_id": session.id_material,
            "material_title": session.material.nombre_material if session.material else None,
            "objective": session.objetivo,
            "recognition_confidence": decimal_value(session.confianza_reconocimiento),
            "created_at": session.creada_en.isoformat() if session.creada_en else None,
            "started_at": session.iniciada_en.isoformat() if session.iniciada_en else None,
            "finished_at": session.finalizada_en.isoformat() if session.finalizada_en else None,
            "teacher_reviewed": session.revisada_por_docente,
            "teacher_notes": session.observaciones_docente,
            "evaluation": serialize_evaluation(session.evaluacion),
        }
        if include_turns:
            payload["turns"] = [serialize_turn(turn) for turn in session.turnos]
        return payload

    @app.route("/api/interactions/sessions", methods=["GET"])
    def list_interaction_sessions():
        if not teacher_actions_available():
            return institutional_auth_pending_response()
        sessions = (
            SesionInteraccion.query
            .filter_by(id_docente_institucional=str(USER["fk_user"]))
            .order_by(SesionInteraccion.creada_en.desc())
            .limit(100)
            .all()
        )
        return jsonify([serialize_session(session) for session in sessions])

    @app.route("/api/interactions/sessions", methods=["POST"])
    def create_interaction_session():
        if not teacher_actions_available():
            return institutional_auth_pending_response()

        payload = request.get_json(silent=True) or {}
        classroom_id = str(payload.get("classroom_id") or "").strip()
        objective = str(payload.get("objective") or "").strip()
        material_id = payload.get("material_id")

        if not classroom_id:
            return jsonify({"error": "Selecciona un aula."}), 400
        if not objective:
            return jsonify({"error": "Indica el objetivo de la interacción."}), 400
        if len(classroom_id) > 50 or len(objective) > MAX_OBJECTIVE_CHARS:
            return jsonify({"error": "El aula o el objetivo excede el límite permitido."}), 413

        material = None
        if material_id not in (None, ""):
            try:
                material = db.session.get(Material, int(material_id))
            except (TypeError, ValueError):
                material = None
            if not material or str(material.fk_user) != str(USER["fk_user"]):
                return jsonify({"error": "El material no pertenece a la docente activa."}), 404

        session = SesionInteraccion(
            uuid=str(uuid.uuid4()),
            id_docente_institucional=str(USER["fk_user"]),
            id_aula_institucional=classroom_id,
            id_material=material.id if material else None,
            objetivo=objective,
            estado="esperando_identificacion",
        )
        db.session.add(session)
        db.session.commit()
        return jsonify(serialize_session(session, include_turns=True)), 201

    @app.route("/api/interactions/sessions/<string:session_uuid>", methods=["GET"])
    def get_interaction_session(session_uuid):
        if not teacher_actions_available():
            return institutional_auth_pending_response()
        session = SesionInteraccion.query.filter_by(uuid=session_uuid).first()
        if not session:
            return jsonify({"error": "Sesión no encontrada."}), 404
        return jsonify(serialize_session(session, include_turns=True))

    @app.route("/api/integrations/face-recognition/events", methods=["POST"])
    def face_recognition_event():
        if not trusted_robot_request():
            return jsonify({"error": "Integración no autorizada."}), 401

        payload = request.get_json(silent=True) or {}
        session_uuid = str(payload.get("session_uuid") or "").strip()
        person_id = str(payload.get("person_id") or "").strip()
        person_type = str(payload.get("person_type") or "").strip().upper()
        display_name = str(payload.get("display_name") or "").strip()
        classroom_ids_payload = payload.get("classroom_ids")
        classroom_ids = {
            str(classroom_id).strip()
            for classroom_id in classroom_ids_payload
            if str(classroom_id).strip()
        } if isinstance(classroom_ids_payload, list) else set()
        try:
            confidence = float(payload.get("confidence"))
        except (TypeError, ValueError):
            return jsonify({"error": "La confianza de reconocimiento no es válida."}), 400

        if not session_uuid or not person_id or not person_type:
            return jsonify({"error": "Faltan session_uuid, person_id o person_type."}), 400
        if len(person_id) > 50 or len(person_type) > 30 or len(display_name) > 255:
            return jsonify({"error": "Los datos de identidad exceden el límite permitido."}), 413
        if confidence < 0 or confidence > 1:
            return jsonify({"error": "La confianza debe estar entre 0 y 1."}), 400

        session = SesionInteraccion.query.filter_by(uuid=session_uuid).first()
        if not session:
            return jsonify({"error": "Sesión no encontrada."}), 404

        event_status = "aceptado"
        reason = None
        if session.estado != "esperando_identificacion":
            event_status = "ignorado"
            reason = "La sesión ya no espera identificación."
        elif person_type not in {"ALUMNO", "STUDENT"}:
            event_status = "ignorado"
            reason = "La persona reconocida no es un alumno."
        elif not teacher_actions_available() and not classroom_ids:
            event_status = "ignorado"
            reason = "El servicio institucional no confirmó las aulas activas del alumno."
        elif classroom_ids and session.id_aula_institucional not in classroom_ids:
            event_status = "ignorado"
            reason = "El alumno no pertenece al aula seleccionada para la sesión."
        elif confidence < app.config["FACE_MATCH_MIN_CONFIDENCE"]:
            event_status = "requiere_confirmacion"
            reason = "La confianza facial está por debajo del mínimo configurado."

        event = EventoReconocimiento(
            id_sesion=session.id,
            id_persona_institucional=person_id,
            tipo_persona=person_type,
            nombre_persona=display_name or None,
            confianza=confidence,
            estado=event_status,
            motivo=reason,
        )
        db.session.add(event)

        if event_status == "aceptado":
            session.id_alumno_institucional = person_id
            session.alumno_nombre = display_name or f"Alumno {person_id}"
            session.confianza_reconocimiento = confidence
            session.estado = "activa"
            session.iniciada_en = utc_now()

        db.session.commit()
        status_code = 200 if event_status in {"aceptado", "ignorado"} else 202
        return jsonify({
            "event_status": event_status,
            "reason": reason,
            "session": serialize_session(session, include_turns=True),
        }), status_code

    @app.route("/api/interactions/sessions/<string:session_uuid>/turns", methods=["POST"])
    def add_conversation_turn(session_uuid):
        if not trusted_robot_request():
            return jsonify({"error": "Integración no autorizada."}), 401

        session = SesionInteraccion.query.filter_by(uuid=session_uuid).first()
        if not session:
            return jsonify({"error": "Sesión no encontrada."}), 404
        if session.estado != "activa":
            return jsonify({"error": "La sesión no está activa."}), 409

        payload = request.get_json(silent=True) or {}
        speaker = str(payload.get("speaker") or "").strip().upper()
        transcript = str(payload.get("transcript") or "").strip()
        if speaker not in {"MAXCIM", "ALUMNO"}:
            return jsonify({"error": "El emisor debe ser MAXCIM o ALUMNO."}), 400
        if not transcript:
            return jsonify({"error": "La transcripción está vacía."}), 400
        if len(transcript) > MAX_TRANSCRIPT_CHARS:
            return jsonify({"error": "La transcripción excede el límite permitido."}), 413

        question = None
        question_id = payload.get("question_id")
        if question_id not in (None, ""):
            try:
                question = db.session.get(Pregunta, int(question_id))
            except (TypeError, ValueError):
                question = None
            if not question or question.id_material != session.id_material:
                return jsonify({"error": "La pregunta no pertenece al material de la sesión."}), 400

        try:
            correct = parse_optional_bool(payload.get("is_correct"))
            needed_help = parse_optional_bool(payload.get("needed_help")) or False
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        response_time = payload.get("response_time_ms")
        if response_time not in (None, ""):
            try:
                response_time = max(0, int(response_time))
            except (TypeError, ValueError):
                return jsonify({"error": "El tiempo de respuesta no es válido."}), 400
        else:
            response_time = None

        max_order = (
            db.session.query(db.func.max(TurnoConversacion.orden))
            .filter_by(id_sesion=session.id)
            .scalar()
            or 0
        )
        turn = TurnoConversacion(
            id_sesion=session.id,
            id_pregunta=question.id if question else None,
            orden=max_order + 1,
            emisor=speaker,
            texto_transcrito=transcript,
            path_audio=str(payload.get("audio_path") or "").strip()[:500] or None,
            tiempo_respuesta_ms=response_time,
            respuesta_correcta=correct,
            necesito_ayuda=needed_help,
        )
        db.session.add(turn)
        db.session.commit()
        return jsonify(serialize_turn(turn)), 201

    @app.route("/api/interactions/sessions/<string:session_uuid>/complete", methods=["POST"])
    def complete_interaction_session(session_uuid):
        if not trusted_robot_request():
            return jsonify({"error": "Integración no autorizada."}), 401

        session = SesionInteraccion.query.filter_by(uuid=session_uuid).first()
        if not session:
            return jsonify({"error": "Sesión no encontrada."}), 404
        if session.evaluacion and session.estado in {"finalizada", "evaluacion_aprobada"}:
            return jsonify(serialize_session(session, include_turns=True))
        if session.estado != "activa":
            return jsonify({"error": "La sesión no está activa."}), 409

        metrics = calculate_base_metrics(session.turnos)
        assessment = None
        assessment_error = None
        try:
            assessment = generate_ai_assessment(
                gemini_client,
                GEMINI_MODEL,
                session.turnos,
                metrics,
            )
        except Exception:
            app.logger.exception("No se pudo generar la evaluación cualitativa con Gemini")
            assessment_error = "No se pudo obtener la propuesta cualitativa de Gemini."

        oral_percentage = assessment.get("porcentaje_interaccion_oral") if assessment else None
        scores = [metrics["porcentaje_participacion"]]
        if metrics["respuestas_calificadas"]:
            scores.append(metrics["porcentaje_comprension"])
        if oral_percentage is not None:
            scores.append(oral_percentage)
        overall = round(sum(scores) / len(scores), 2) if scores else None

        evaluation = EvaluacionInteraccion(
            id_sesion=session.id,
            preguntas_realizadas=metrics["preguntas_realizadas"],
            respuestas_registradas=metrics["respuestas_registradas"],
            respuestas_correctas=metrics["respuestas_correctas"],
            promedio_respuesta_ms=metrics["promedio_respuesta_ms"],
            porcentaje_participacion=metrics["porcentaje_participacion"],
            porcentaje_comprension=metrics["porcentaje_comprension"],
            porcentaje_interaccion_oral=oral_percentage,
            porcentaje_general=overall,
            criterios_json=json.dumps(
                {
                    "criterios": assessment.get("criterios", {}) if assessment else {},
                    "recomendacion_docente": assessment.get("recomendacion_docente", "") if assessment else "",
                    "error_ia": assessment_error,
                },
                ensure_ascii=False,
            ),
            resumen_ia=assessment.get("resumen") if assessment else None,
            estado="pendiente_revision" if assessment else "pendiente_ia",
        )
        db.session.add(evaluation)
        session.estado = "finalizada"
        session.finalizada_en = utc_now()
        db.session.commit()
        return jsonify(serialize_session(session, include_turns=True))

    @app.route("/api/interactions/sessions/<string:session_uuid>/evaluation", methods=["PATCH"])
    def review_interaction_evaluation(session_uuid):
        if not teacher_actions_available():
            return jsonify({"error": "La sesión institucional no está disponible."}), 503

        session = SesionInteraccion.query.filter_by(uuid=session_uuid).first()
        if not session or not session.evaluacion:
            return jsonify({"error": "Evaluación no encontrada."}), 404

        payload = request.get_json(silent=True) or {}
        evaluation = session.evaluacion
        for field, attribute in (
            ("participation_percentage", "porcentaje_participacion"),
            ("comprehension_percentage", "porcentaje_comprension"),
            ("oral_interaction_percentage", "porcentaje_interaccion_oral"),
            ("overall_percentage", "porcentaje_general"),
        ):
            if field in payload and payload[field] is not None:
                try:
                    value = max(0, min(float(payload[field]), 100))
                except (TypeError, ValueError):
                    return jsonify({"error": f"{field} no es válido."}), 400
                setattr(evaluation, attribute, value)

        evaluation.retroalimentacion_docente = str(
            payload.get("teacher_feedback") or ""
        ).strip() or None
        evaluation.estado = "aprobada"
        evaluation.revisada_por = str(USER["fk_user"])
        evaluation.revisada_en = utc_now()
        session.revisada_por_docente = True
        session.observaciones_docente = evaluation.retroalimentacion_docente
        session.estado = "evaluacion_aprobada"
        db.session.commit()
        return jsonify(serialize_session(session, include_turns=True))

    @app.route("/api/interactions/sessions/<string:session_uuid>/robot-payload", methods=["GET"])
    def robot_session_payload(session_uuid):
        if not trusted_robot_request():
            return jsonify({"error": "Integración no autorizada."}), 401

        session = SesionInteraccion.query.filter_by(uuid=session_uuid).first()
        if not session:
            return jsonify({"error": "Sesión no encontrada."}), 404

        base_payload = {
            "session_uuid": session.uuid,
            "student": {
                "institutional_id": session.id_alumno_institucional,
                "display_name": session.alumno_nombre,
            },
            "objective": session.objetivo,
        }
        if not session.material:
            return jsonify({**base_payload, "material": None})

        material = session.material
        approved_questions = [
            question
            for question in material.preguntas
            if question.estado == "aprobada"
        ]
        return jsonify({
            **base_payload,
            "material": {
                "id": material.id,
                "title": material.nombre_material,
                "full_text_url": url_for("static", filename=material.path_texto, _external=True),
                "summary_url": url_for("static", filename=material.path_texto_resumen, _external=True),
                "full_audio_url": url_for("static", filename=material.path_audio, _external=True),
                "summary_audio_url": url_for("static", filename=material.path_audio_resumen, _external=True),
                "questions": [
                    {
                        "id": question.id,
                        "type": question.tipo,
                        "statement": question.enunciado,
                        "expected_answer": question.respuesta_esperada,
                        "order": question.orden,
                    }
                    for question in approved_questions
                ],
            },
        })

    return app


app = create_app()

if __name__ == "__main__":
    app.run(
        host=os.environ.get("FLASK_HOST", "0.0.0.0"),
        port=int(os.environ.get("FLASK_PORT", "5000")),
        debug=env_bool("FLASK_DEBUG", False),
    )
