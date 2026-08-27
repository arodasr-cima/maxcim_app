import io
import hmac
import json
import mimetypes
import os
import re
import secrets
import shutil
import tempfile
import uuid
import wave
from datetime import UTC, date, datetime, timedelta
from functools import wraps
from urllib.parse import quote_plus

from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv
from flask import (
    Flask,
    Response,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session as browser_session,
    url_for,
)
from google import genai
from google.genai import types

from extensions import db
from models import Interaccion, Material
from services.demo import (
    DemoInstitutionalClient,
    create_demo_questions,
    create_demo_story,
    create_demo_wav,
    process_demo_document,
)
from services.google_oauth import GoogleOIDCClient, GoogleOIDCError
from services.institutional import (
    InstitutionalAPIError,
    InstitutionalClient,
    InstitutionalConfigurationError,
)

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


# This repository is intentionally the isolated test environment. The real
# repository keeps DEMO_MODE disabled and never imports this adapter.
DEFAULT_DEMO_MODE = env_bool("DEMO_MODE", True)


def utc_now() -> datetime:
    """UTC stored without tzinfo for compatibility with MySQL DATETIME."""
    return datetime.now(UTC).replace(tzinfo=None)


MYSQL_HOST = os.environ.get("MYSQL_HOST") or os.environ.get("MYSQLHOST", "localhost")
MYSQL_PORT = os.environ.get("MYSQL_PORT") or os.environ.get("MYSQLPORT", "3306")
MYSQL_USER = os.environ.get("MYSQL_USER") or os.environ.get("MYSQLUSER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD") or os.environ.get("MYSQLPASSWORD", "")
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE") or os.environ.get("MYSQLDATABASE", "")
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("MYSQL_URL", "")
if DATABASE_URL.startswith("mysql://"):
    DATABASE_URL = DATABASE_URL.replace("mysql://", "mysql+pymysql://", 1)
if DATABASE_URL:
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
elif DEFAULT_DEMO_MODE:
    SQLALCHEMY_DATABASE_URI = os.environ.get("DEMO_DATABASE_URL", "sqlite:///maxcim_demo.db")
else:
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
interacción oral posterior. La narración completa debe durar aproximadamente
{duracion_minutos} minuto(s), considerando un ritmo infantil claro de
{palabras_por_minuto} palabras por minuto. El campo "cuento" debe contener entre
{palabras_minimas} y {palabras_maximas} palabras, idealmente {palabras_objetivo};
respeta este rango. No incluyas preguntas todavía. Devuelve solamente JSON:
{{"titulo": "...", "cuento": "...", "resumen": "..."}}
""".strip()

STORY_LENGTH_CORRECTION_TEMPLATE = """
Reescribe el siguiente cuento educativo sin cambiar su personaje, escenario,
objetivo pedagógico ni hechos principales. El campo "cuento" debe quedar entre
{palabras_minimas} y {palabras_maximas} palabras para aproximarse a una narración
de {duracion_minutos} minuto(s). Conserva un resumen breve y devuelve solamente JSON:
{{"titulo": "...", "cuento": "...", "resumen": "..."}}

Cuento actual:
{cuento_actual}
""".strip()

STORY_DURATION_MINUTES_MIN = 1
STORY_DURATION_MINUTES_MAX = 15
STORY_NARRATION_WORDS_PER_MINUTE = 125
STORY_WORD_COUNT_TOLERANCE = 0.08
TTS_MIN_WORDS_PER_MINUTE = 90
TTS_MAX_WORDS_PER_MINUTE = 170

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
    "en ningún momento. No resumas, no omitas y no agregues palabras."
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

MATERIAL_SKILLS = [
    "Todas las habilidades",
    "Comunicación oral",
    "Escucha activa",
    "Empatía",
    "Trabajo en equipo",
    "Resolución de conflictos",
]

QUESTION_CONFIGURATION = [
    {"key": "literales", "label": "Literales", "default": 3},
    {"key": "inferenciales", "label": "Inferenciales", "default": 2},
    {"key": "criticas", "label": "Críticas", "default": 1},
]


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
    duration_minutes: int,
) -> dict[str, object]:
    target_words, min_words, max_words = _story_word_limits(duration_minutes)
    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=STORY_PROMPT_TEMPLATE.format(
            nivel=grade_level,
            personaje=character,
            escenario=setting,
            objetivo=objective,
            detalles=extra_details or "Sin detalles adicionales.",
            duracion_minutos=duration_minutes,
            palabras_por_minuto=STORY_NARRATION_WORDS_PER_MINUTE,
            palabras_minimas=min_words,
            palabras_maximas=max_words,
            palabras_objetivo=target_words,
        ),
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )

    data = _parse_story_response(response.text)
    word_count = _count_words(data["story"])

    # Gemini follows a target range better than an exact token count. If the
    # first draft falls outside the range, one focused rewrite keeps the user
    # flow reliable without looping indefinitely or multiplying API costs.
    if not min_words <= word_count <= max_words:
        correction = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=STORY_LENGTH_CORRECTION_TEMPLATE.format(
                palabras_minimas=min_words,
                palabras_maximas=max_words,
                duracion_minutos=duration_minutes,
                cuento_actual=json.dumps({
                    "titulo": data["title"],
                    "cuento": data["story"],
                    "resumen": data["summary"],
                }, ensure_ascii=False),
            ),
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        corrected = _parse_story_response(correction.text)
        corrected_word_count = _count_words(corrected["story"])
        if abs(corrected_word_count - target_words) < abs(word_count - target_words):
            data = corrected
            word_count = corrected_word_count

    data.update({
        "target_duration_minutes": duration_minutes,
        "word_count": word_count,
        "estimated_duration_seconds": round(
            word_count / STORY_NARRATION_WORDS_PER_MINUTE * 60
        ),
    })
    return data


def _parse_story_response(response_text: str) -> dict[str, str]:
    data = json.loads(response_text)
    title = str(data.get("titulo") or "").strip()
    story = str(data.get("cuento") or "").strip()
    summary = str(data.get("resumen") or "").strip()
    if not title or not story or not summary:
        raise ValueError("Gemini no devolvió un cuento completo.")
    return {"title": title, "story": story, "summary": summary}


def _parse_duration_minutes(value) -> int:
    if isinstance(value, bool) or value is None:
        raise ValueError(
            f"La duración debe ser un número entero entre {STORY_DURATION_MINUTES_MIN} "
            f"y {STORY_DURATION_MINUTES_MAX} minutos."
        )
    try:
        duration = int(value)
    except (TypeError, ValueError):
        duration = 0
    if str(value).strip() not in {str(duration), f"{duration}.0"}:
        duration = 0
    if not STORY_DURATION_MINUTES_MIN <= duration <= STORY_DURATION_MINUTES_MAX:
        raise ValueError(
            f"La duración debe estar entre {STORY_DURATION_MINUTES_MIN} "
            f"y {STORY_DURATION_MINUTES_MAX} minutos."
        )
    return duration


def _count_words(text: str) -> int:
    return len(re.findall(r"\b\w+(?:[’'-]\w+)*\b", text, flags=re.UNICODE))


def _story_word_limits(duration_minutes: int) -> tuple[int, int, int]:
    target = duration_minutes * STORY_NARRATION_WORDS_PER_MINUTE
    tolerance = max(10, round(target * STORY_WORD_COUNT_TOLERANCE))
    return target, target - tolerance, target + tolerance


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


def _target_narration_pace(text: str, target_duration_minutes: int) -> float:
    word_count = _count_words(text)
    if not word_count:
        raise ValueError("El texto no contiene palabras que se puedan narrar.")
    words_per_minute = word_count / target_duration_minutes
    if not TTS_MIN_WORDS_PER_MINUTE <= words_per_minute <= TTS_MAX_WORDS_PER_MINUTE:
        min_words = target_duration_minutes * TTS_MIN_WORDS_PER_MINUTE
        max_words = target_duration_minutes * TTS_MAX_WORDS_PER_MINUTE
        raise ValueError(
            "La cantidad de texto no corresponde a la duración elegida. "
            f"Para {target_duration_minutes} minuto(s), usa entre "
            f"{min_words} y {max_words} palabras."
        )
    return words_per_minute


def _tts_prompt(chunk: str, words_per_minute: float | None) -> str:
    pace_instruction = ""
    if words_per_minute is not None:
        pace_instruction = (
            f" Mantén un ritmo cercano a {round(words_per_minute)} palabras por minuto "
            "para respetar la duración elegida por la docente."
        )
    return f"{TTS_STYLE_INSTRUCTION}{pace_instruction}\n\nTexto que debes narrar:\n{chunk}"


def generate_speech(
    text: str,
    target_duration_minutes: int | None = None,
) -> tuple[bytes, float]:
    """Converts text to speech with Gemini TTS, chunked to keep tone consistent
    across long passages. Returns the WAV bytes and its measured duration."""
    pcm_data = bytearray()
    sample_rate = None
    elapsed_seconds = 0.0
    chunks = _split_text_into_chunks(text)
    chunk_word_counts = [_count_words(chunk) for chunk in chunks]

    if target_duration_minutes is not None:
        _target_narration_pace(text, target_duration_minutes)

    for index, chunk in enumerate(chunks):
        target_pace = None
        if target_duration_minutes is not None:
            remaining_words = sum(chunk_word_counts[index:])
            remaining_seconds = max(
                target_duration_minutes * 60 - elapsed_seconds,
                1,
            )
            target_pace = remaining_words / (remaining_seconds / 60)
            target_pace = max(
                TTS_MIN_WORDS_PER_MINUTE,
                min(target_pace, TTS_MAX_WORDS_PER_MINUTE),
            )

        response = gemini_client.models.generate_content(
            model=GEMINI_TTS_MODEL,
            contents=_tts_prompt(chunk, target_pace),
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
        chunk_sample_rate = (
            int(rate_match.group(1)) if rate_match else TTS_DEFAULT_SAMPLE_RATE
        )
        if sample_rate is None:
            sample_rate = chunk_sample_rate
        elif sample_rate != chunk_sample_rate:
            raise ValueError("Gemini devolvió fragmentos de audio con frecuencias incompatibles.")
        elapsed_seconds += len(inline_data.data) / (sample_rate * 2)

    sample_rate = sample_rate or TTS_DEFAULT_SAMPLE_RATE

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(bytes(pcm_data))

    duration_seconds = len(pcm_data) / (sample_rate * 2)
    return buffer.getvalue(), round(duration_seconds, 2)


def _wav_duration_seconds(path: str) -> float:
    with wave.open(path, "rb") as wav_file:
        frame_rate = wav_file.getframerate()
        if frame_rate <= 0:
            raise wave.Error("Frecuencia de audio inválida.")
        return wav_file.getnframes() / frame_rate


def format_period_label(today: date) -> str:
    return f"{DIAS_ES[today.weekday()]} {today.day}, {MESES_ES[today.month - 1]}"


def create_app(test_config: dict | None = None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", ""),
        MAX_CONTENT_LENGTH=MAX_UPLOAD_BYTES,
        SQLALCHEMY_DATABASE_URI=SQLALCHEMY_DATABASE_URI,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAXCIM_WEBHOOK_SECRET=os.environ.get("MAXCIM_WEBHOOK_SECRET", ""),
        SESSION_TOKEN_ENCRYPTION_KEY=os.environ.get("SESSION_TOKEN_ENCRYPTION_KEY", ""),
        INSTITUTIONAL_API_BASE_URL=os.environ.get("INSTITUTIONAL_API_BASE_URL", ""),
        INSTITUTIONAL_API_LOGIN_PATH=os.environ.get("INSTITUTIONAL_API_LOGIN_PATH", ""),
        INSTITUTIONAL_API_GOOGLE_LOGIN_PATH=os.environ.get(
            "INSTITUTIONAL_API_GOOGLE_LOGIN_PATH", ""
        ),
        INSTITUTIONAL_API_CLASSROOMS_PATH=os.environ.get("INSTITUTIONAL_API_CLASSROOMS_PATH", ""),
        INSTITUTIONAL_API_STUDENTS_PATH=os.environ.get("INSTITUTIONAL_API_STUDENTS_PATH", ""),
        INSTITUTIONAL_API_STUDENT_PATH=os.environ.get("INSTITUTIONAL_API_STUDENT_PATH", ""),
        INSTITUTIONAL_API_SERVICE_TOKEN=os.environ.get("INSTITUTIONAL_API_SERVICE_TOKEN", ""),
        INSTITUTIONAL_API_TIMEOUT_SECONDS=float(os.environ.get("INSTITUTIONAL_API_TIMEOUT_SECONDS", "8")),
        INSTITUTIONAL_API_VERIFY_TLS=env_bool("INSTITUTIONAL_API_VERIFY_TLS", True),
        GOOGLE_OAUTH_CLIENT_ID=os.environ.get("GOOGLE_OAUTH_CLIENT_ID", ""),
        GOOGLE_OAUTH_CLIENT_SECRET=os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", ""),
        GOOGLE_OAUTH_ALLOWED_DOMAINS=os.environ.get("GOOGLE_OAUTH_ALLOWED_DOMAINS", ""),
        GOOGLE_OAUTH_REDIRECT_URI=os.environ.get("GOOGLE_OAUTH_REDIRECT_URI", ""),
        GOOGLE_OAUTH_TIMEOUT_SECONDS=float(os.environ.get("GOOGLE_OAUTH_TIMEOUT_SECONDS", "8")),
        DEMO_MODE=DEFAULT_DEMO_MODE,
        SESSION_COOKIE_NAME="maxcim_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=env_bool("SESSION_COOKIE_SECURE", not DEFAULT_DEMO_MODE),
    )
    if test_config:
        app.config.update(test_config)

    if app.config.get("DEMO_MODE"):
        os.makedirs(app.instance_path, exist_ok=True)
        if not app.config.get("SECRET_KEY"):
            app.config["SECRET_KEY"] = secrets.token_hex(32)
        if not app.config.get("SESSION_TOKEN_ENCRYPTION_KEY"):
            app.config["SESSION_TOKEN_ENCRYPTION_KEY"] = Fernet.generate_key().decode("ascii")
        if not app.config.get("MAXCIM_WEBHOOK_SECRET"):
            app.config["MAXCIM_WEBHOOK_SECRET"] = "maxcim-demo-isolated-webhook"
    db.init_app(app)

    institutional_client = app.config.get("INSTITUTIONAL_CLIENT")
    if institutional_client is None:
        institutional_client = (
            DemoInstitutionalClient()
            if app.config.get("DEMO_MODE")
            else InstitutionalClient.from_config(app.config)
        )
    app.extensions["institutional_client"] = institutional_client
    google_oidc_client = app.config.get("GOOGLE_OIDC_CLIENT") or GoogleOIDCClient.from_config(
        app.config
    )
    app.extensions["google_oidc_client"] = google_oidc_client

    def token_cipher() -> Fernet:
        key = str(app.config.get("SESSION_TOKEN_ENCRYPTION_KEY") or "").strip()
        if not key:
            raise InstitutionalConfigurationError(
                "Falta configurar SESSION_TOKEN_ENCRYPTION_KEY en el servidor."
            )
        try:
            return Fernet(key.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as exc:
            raise InstitutionalConfigurationError(
                "SESSION_TOKEN_ENCRYPTION_KEY no tiene un formato Fernet válido."
            ) from exc

    def safe_next_path(value: str | None) -> str:
        candidate = str(value or "")
        return (
            candidate
            if candidate.startswith("/") and not candidate.startswith("//")
            else url_for("dashboard")
        )

    def complete_teacher_login(authenticated, next_path: str | None = None):
        # No hay tabla `sesion_web_docente` en este esquema: la sesión del
        # docente vive solo en la cookie firmada de Flask. El access token
        # institucional va cifrado dentro de la cookie (no en claro) porque
        # es un bearer token hacia la API institucional.
        cipher = token_cipher()
        destination = safe_next_path(next_path)
        browser_session.clear()
        browser_session["teacher_id"] = authenticated.institutional_id
        browser_session["teacher_name"] = authenticated.display_name
        browser_session["teacher_role"] = authenticated.role
        browser_session["teacher_token"] = cipher.encrypt(
            authenticated.access_token.encode("utf-8")
        ).decode("ascii")
        browser_session["teacher_expires_at"] = (
            utc_now() + timedelta(seconds=authenticated.expires_in_seconds)
        ).isoformat()
        browser_session.permanent = True
        return redirect(destination)

    def login_readiness() -> dict[str, bool]:
        if app.config.get("DEMO_MODE"):
            return {"password_ready": True, "google_ready": True, "any_ready": True}
        secure_session_ready = bool(
            app.config.get("SECRET_KEY")
            and app.config.get("SESSION_TOKEN_ENCRYPTION_KEY")
        )
        password_ready = bool(
            secure_session_ready and getattr(institutional_client, "login_ready", False)
        )
        google_ready = bool(
            secure_session_ready
            and getattr(institutional_client, "google_login_ready", False)
            and getattr(google_oidc_client, "ready", False)
        )
        return {
            "password_ready": password_ready,
            "google_ready": google_ready,
            "any_ready": password_ready or google_ready,
        }

    def render_login_page(error: str | None = None, status_code: int = 200):
        if not error and app.config.get("SECRET_KEY"):
            error = browser_session.pop("google_login_error", None)
        readiness = login_readiness()
        return render_template(
            "login.html",
            error=error,
            api_ready=readiness["any_ready"],
            password_ready=readiness["password_ready"],
            google_ready=readiness["google_ready"],
            demo_mode=bool(app.config.get("DEMO_MODE")),
        ), status_code

    def google_redirect_uri() -> str:
        configured = str(app.config.get("GOOGLE_OAUTH_REDIRECT_URI") or "").strip()
        if configured:
            return configured
        scheme = "https" if app.config.get("SESSION_COOKIE_SECURE") else request.scheme
        return url_for("google_callback", _external=True, _scheme=scheme)

    def google_error_redirect(message: str):
        browser_session["google_login_error"] = message
        return redirect(url_for("login"))

    def current_teacher() -> dict | None:
        cached = getattr(g, "maxcim_teacher", None)
        if cached is not None:
            return cached

        if app.config.get("TESTING") and app.config.get("TEST_TEACHER"):
            teacher = dict(app.config["TEST_TEACHER"])
            g.maxcim_teacher = teacher
            return teacher

        token_blob = browser_session.get("teacher_token")
        expires_at_raw = browser_session.get("teacher_expires_at")
        if not token_blob or not expires_at_raw:
            return None
        try:
            expires_at = datetime.fromisoformat(expires_at_raw)
        except ValueError:
            browser_session.clear()
            return None
        if expires_at <= utc_now():
            browser_session.clear()
            return None
        try:
            access_token = token_cipher().decrypt(token_blob.encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError):
            browser_session.clear()
            return None

        name_parts = [
            part for part in str(browser_session.get("teacher_name") or "").split() if part
        ]
        teacher = {
            "id": browser_session.get("teacher_id"),
            "name": browser_session.get("teacher_name"),
            "initials": "".join(part[0].upper() for part in name_parts[:2]) or "DC",
            "role": browser_session.get("teacher_role"),
            "access_token": access_token,
        }
        g.maxcim_teacher = teacher
        return teacher

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if current_teacher() is None:
                if request.path.startswith("/api/"):
                    return jsonify({"error": "La sesión institucional no es válida o expiró."}), 401
                return redirect(url_for("login", next=request.path))
            return view(*args, **kwargs)

        return wrapped

    def csrf_token() -> str:
        if not app.config.get("SECRET_KEY"):
            return ""
        token = browser_session.get("csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            browser_session["csrf_token"] = token
        return token

    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.context_processor
    def inject_environment():
        return {"demo_mode": bool(app.config.get("DEMO_MODE"))}

    def webhook_authorized() -> bool:
        if app.config.get("DEMO_MODE"):
            return True
        if app.config.get("TESTING") and app.config.get("TEST_WEBHOOK_AUTHORIZED", True):
            return True
        expected = app.config.get("MAXCIM_WEBHOOK_SECRET", "")
        received = request.headers.get("X-MAXCIM-Webhook-Secret", "")
        return bool(expected and received and hmac.compare_digest(expected, received))

    @app.before_request
    def enforce_csrf():
        if request.method in {"GET", "HEAD", "OPTIONS"} or app.config.get("TESTING"):
            return None
        if request.path == "/api/interacciones":
            # Endpoint robot-side: no es un formulario de navegador, así que
            # no lleva token CSRF. Su propia autorización (el secreto
            # compartido, vía webhook_authorized()) decide con un 401 claro
            # en vez de un 403 genérico de CSRF.
            return None
        if webhook_authorized():
            return None
        expected = str(browser_session.get("csrf_token") or "")
        received = str(
            request.headers.get("X-CSRF-Token")
            or request.form.get("csrf_token")
            or ""
        )
        if not expected or not received or not hmac.compare_digest(expected, received):
            if request.path.startswith("/api/"):
                return jsonify({"error": "La solicitud no superó la validación de seguridad."}), 403
            return render_login_page("La sesión del formulario expiró.", 403)
        return None

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if (
            request.path.startswith("/api/")
            or request.path.startswith("/auth/")
            or request.path.startswith("/login")
            or request.path in {
            "/dashboard", "/material", "/sesiones",
            }
        ):
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
        return redirect(url_for("dashboard" if current_teacher() else "login"))

    @app.route("/health")
    def health():
        payload = {"status": "ok"}
        if app.config.get("DEMO_MODE"):
            payload["environment"] = "test"
        return jsonify(payload)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_teacher():
            return redirect(url_for("dashboard"))

        error = None
        status_code = 200
        if request.method == "POST":
            institutional_id = str(request.form.get("institutional_id") or "").strip()
            credential = str(request.form.get("credential") or "")
            if not institutional_id or not credential:
                error = "Ingresa tu ID y credencial institucional."
                status_code = 400
            else:
                try:
                    authenticated = institutional_client.authenticate(institutional_id, credential)
                    return complete_teacher_login(
                        authenticated,
                        request.args.get("next"),
                    )
                except InstitutionalAPIError as exc:
                    error = str(exc)
                    status_code = exc.status_code

        return render_login_page(error, status_code)

    @app.route("/login/google")
    def google_login():
        if current_teacher():
            return redirect(url_for("dashboard"))
        if app.config.get("DEMO_MODE"):
            authenticated = institutional_client.authenticate_google("demo-google-login")
            return complete_teacher_login(authenticated, request.args.get("next"))
        if not login_readiness()["google_ready"]:
            return render_login_page(
                "El acceso institucional con Google todavía no está configurado.",
                503,
            )

        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        code_verifier, code_challenge = google_oidc_client.create_pkce_pair()
        browser_session["google_oauth_state"] = state
        browser_session["google_oauth_nonce"] = nonce
        browser_session["google_oauth_code_verifier"] = code_verifier
        browser_session["google_oauth_next"] = safe_next_path(request.args.get("next"))
        authorization_url = google_oidc_client.authorization_url(
            redirect_uri=google_redirect_uri(),
            state=state,
            nonce=nonce,
            code_challenge=code_challenge,
        )
        return redirect(authorization_url)

    @app.route("/auth/google/callback")
    def google_callback():
        expected_state = str(browser_session.pop("google_oauth_state", ""))
        nonce = str(browser_session.pop("google_oauth_nonce", ""))
        code_verifier = str(browser_session.pop("google_oauth_code_verifier", ""))
        next_path = str(browser_session.pop("google_oauth_next", ""))

        if request.args.get("error"):
            return google_error_redirect("El acceso con Google fue cancelado.")
        received_state = str(request.args.get("state") or "")
        code = str(request.args.get("code") or "")
        if (
            not expected_state
            or not received_state
            or not hmac.compare_digest(expected_state, received_state)
            or not nonce
            or not code_verifier
            or not code
        ):
            return google_error_redirect(
                "La respuesta de Google no corresponde a esta sesión de acceso."
            )

        try:
            identity = google_oidc_client.exchange_and_verify(
                code=code,
                redirect_uri=google_redirect_uri(),
                nonce=nonce,
                code_verifier=code_verifier,
            )
            authenticated = institutional_client.authenticate_google(identity.id_token)
            return complete_teacher_login(authenticated, next_path)
        except (GoogleOIDCError, InstitutionalAPIError) as exc:
            return google_error_redirect(str(exc))

    @app.route("/logout", methods=["POST"])
    def logout():
        # Sin sesion_web_docente no hay nada que revocar del lado del
        # servidor: cerrar sesión es simplemente borrar la cookie.
        browser_session.clear()
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        teacher = current_teacher()
        try:
            institutional_classrooms = institutional_client.list_teacher_classrooms(
                teacher["access_token"], teacher["id"]
            )
        except InstitutionalAPIError as exc:
            return render_template(
                "integration_error.html",
                user=teacher,
                active_nav="tablon",
                message=str(exc),
            ), exc.status_code

        teacher_materials = Material.query.filter_by(fk_user=str(teacher["id"])).all()
        material_ids = [material.id for material in teacher_materials]
        interactions = (
            Interaccion.query.filter(Interaccion.id_material.in_(material_ids)).all()
            if material_ids
            else []
        )
        correct_count = sum(1 for item in interactions if item.rpta_correcta)
        average_score = (
            round(correct_count / len(interactions) * 100) if interactions else None
        )
        participating_students = {item.fk_alumno for item in interactions}

        stat_cards = [
            {"value": len(institutional_classrooms), "label": "Aulas a cargo", "color": "#2f5bcf"},
            {"value": len(interactions), "label": "Interacciones registradas", "color": "#d64545"},
            {"value": f"{average_score}%" if average_score is not None else "—", "label": "Promedio de aciertos", "color": "#1f9d55"},
            {"value": len(participating_students), "label": "Alumnos participantes", "color": "#132a5e"},
        ]

        # `interaccion` no guarda el aula (ver bd_app.sql: solo id_material y
        # fk_alumno), así que ya no se puede desglosar el desempeño por aula
        # con datos locales. Se muestra solo lo que informa la API
        # institucional.
        aulas = []
        for classroom in institutional_classrooms:
            words = [word for word in classroom.name.split() if word]
            aulas.append({
                "id": classroom.institutional_id,
                "name": classroom.name,
                "grade": classroom.grade,
                "course": classroom.course,
                "period": classroom.period,
                "initials": "".join(word[0].upper() for word in words[:2]) or "AU",
                "score": None,
                "pending": 0,
                "interactions": 0,
            })

        periods = sorted({classroom.period for classroom in institutional_classrooms if classroom.period})
        return render_template(
            "dashboard.html",
            active_nav="tablon",
            user=teacher,
            stat_cards=stat_cards,
            aulas=aulas,
            today_label=format_period_label(date.today()),
            periodo_label=" · ".join(periods) if periods else "Periodo institucional activo",
        )

    @app.route("/material")
    @login_required
    def material():
        teacher = current_teacher()
        materials = (
            Material.query.filter_by(fk_user=str(teacher["id"]))
            .order_by(Material.fecha_subido.desc(), Material.id.desc())
            .all()
        )
        return render_template(
            "material.html",
            active_nav="material",
            user=teacher,
            materials=materials,
            skills=MATERIAL_SKILLS,
            question_configuration=QUESTION_CONFIGURATION,
        )

    @app.route("/sesiones")
    @login_required
    def sesiones():
        teacher = current_teacher()
        try:
            classrooms = institutional_client.list_teacher_classrooms(
                teacher["access_token"], teacher["id"]
            )
        except InstitutionalAPIError as exc:
            return render_template(
                "integration_error.html",
                user=teacher,
                active_nav="sesiones",
                message=str(exc),
            ), exc.status_code
        materials = (
            Material.query.filter_by(fk_user=str(teacher["id"]))
            .order_by(Material.fecha_subido.desc(), Material.id.desc())
            .all()
        )
        return render_template(
            "sesiones.html",
            active_nav="sesiones",
            user=teacher,
            aulas=[{"id": item.institutional_id, "name": item.name} for item in classrooms],
            materials=materials,
            # El flujo de sesión en vivo (reconocimiento facial + evaluación
            # por turnos) ya no tiene tablas que lo respalden — ver
            # models.py / bd_app.sql. Queda un log plano en `interaccion`
            # que el frontend todavía no consume; por eso el historial se
            # sirve vacío hasta que se rediseñe esta pantalla.
            sessions=[],
            recognition_ready=bool(app.config.get("MAXCIM_WEBHOOK_SECRET")),
            demo_mode=bool(app.config.get("DEMO_MODE")),
        )

    @app.route("/api/material/process", methods=["POST"])
    @login_required
    def process_material():
        uploaded = request.files.get("file")
        if not uploaded or not uploaded.filename:
            return jsonify({"error": "No se recibió ningún archivo."}), 400
        extension = os.path.splitext(uploaded.filename)[1].lower()
        if extension not in ALLOWED_UPLOAD_EXTENSIONS:
            return jsonify({"error": "El archivo debe ser DOC, DOCX, PDF o TXT."}), 400
        if not gemini_client and app.config.get("DEMO_MODE"):
            transcribed_text, summary_text = process_demo_document(uploaded)
            return jsonify({
                "transcribed_text": transcribed_text,
                "summary_text": summary_text,
            })
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
    @login_required
    def material_tts():
        payload = request.get_json(silent=True) or {}
        text = (payload.get("text") or "").strip()
        target_duration_minutes = None
        if payload.get("target_duration_minutes") not in (None, ""):
            try:
                target_duration_minutes = _parse_duration_minutes(
                    payload.get("target_duration_minutes")
                )
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
        if not text:
            return jsonify({"error": "No hay texto para convertir a audio."}), 400
        if len(text) > MAX_TTS_TEXT_CHARS:
            return jsonify({"error": "El texto es demasiado largo para generar audio."}), 413
        if not gemini_client and app.config.get("DEMO_MODE"):
            audio_bytes, duration_seconds = create_demo_wav(text, target_duration_minutes)
            response = Response(audio_bytes, mimetype="audio/wav")
            response.headers["X-MAXCIM-Audio-Duration-Seconds"] = f"{duration_seconds:.2f}"
            response.headers["X-MAXCIM-Demo-Audio"] = "true"
            if target_duration_minutes is not None:
                response.headers["X-MAXCIM-Target-Duration-Minutes"] = str(
                    target_duration_minutes
                )
            return response
        if not gemini_client:
            return jsonify({"error": "GOOGLE_API_KEY no está configurada en el servidor."}), 503

        try:
            audio_bytes, duration_seconds = generate_speech(
                text,
                target_duration_minutes=target_duration_minutes,
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception:
            app.logger.exception("No se pudo generar el audio con Gemini")
            return jsonify({"error": "No se pudo generar el audio con Gemini."}), 502

        response = Response(audio_bytes, mimetype="audio/wav")
        response.headers["X-MAXCIM-Audio-Duration-Seconds"] = f"{duration_seconds:.2f}"
        if target_duration_minutes is not None:
            response.headers["X-MAXCIM-Target-Duration-Minutes"] = str(
                target_duration_minutes
            )
        return response

    @app.route("/api/material/questions", methods=["POST"])
    @login_required
    def material_questions():
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
        if not gemini_client and app.config.get("DEMO_MODE"):
            return jsonify({"questions": create_demo_questions(text, counts)})
        if not gemini_client:
            return jsonify({"error": "GOOGLE_API_KEY no está configurada en el servidor."}), 503

        try:
            questions = generate_questions(text, counts)
        except Exception:
            app.logger.exception("No se pudieron generar las preguntas con Gemini")
            return jsonify({"error": "No se pudieron generar las preguntas con Gemini."}), 502

        return jsonify({"questions": questions})

    @app.route("/api/story/generate", methods=["POST"])
    @login_required
    def story_generate():
        payload = request.get_json(silent=True) or {}
        character = str(payload.get("character") or "").strip()
        setting = str(payload.get("setting") or "").strip()
        grade_level = str(payload.get("grade_level") or "").strip()
        objective = str(payload.get("objective") or "").strip()
        extra_details = str(payload.get("extra_details") or "").strip()
        duration_value = payload.get("duration_minutes")

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
        if duration_value in (None, ""):
            missing.append("duración del cuento")
        if missing:
            return jsonify({"error": f"Falta indicar: {', '.join(missing)}."}), 400
        try:
            duration_minutes = _parse_duration_minutes(duration_value)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
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
        if not gemini_client and app.config.get("DEMO_MODE"):
            return jsonify(create_demo_story(
                character=character,
                setting=setting,
                grade_level=grade_level,
                objective=objective,
                extra_details=extra_details,
                duration_minutes=duration_minutes,
                words_per_minute=STORY_NARRATION_WORDS_PER_MINUTE,
            ))
        if not gemini_client:
            return jsonify({"error": "GOOGLE_API_KEY no está configurada en el servidor."}), 503

        try:
            story = generate_story(
                character=character,
                setting=setting,
                grade_level=grade_level,
                objective=objective,
                extra_details=extra_details,
                duration_minutes=duration_minutes,
            )
        except Exception:
            app.logger.exception("No se pudo crear el cuento con Gemini")
            return jsonify({"error": "No se pudo crear el cuento con Gemini."}), 502

        return jsonify(story)

    @app.route("/api/material/save", methods=["POST"])
    @login_required
    def save_material():
        teacher = current_teacher()
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

        full_audio_path = os.path.join(material_dir, "audio.wav")
        audio_full.save(full_audio_path)
        audio_summary.save(os.path.join(material_dir, "audio_resumen.wav"))

        try:
            _wav_duration_seconds(full_audio_path)
        except (EOFError, OSError, wave.Error):
            shutil.rmtree(material_dir, ignore_errors=True)
            return jsonify({"error": "El audio completo no es un WAV válido."}), 400

        material = Material(
            nombre_material=title,
            # El frontend todavía no informa si el material vino de un
            # documento subido o de un cuento generado con IA (material.js
            # no envía ese dato a este endpoint), así que se guarda un tipo
            # genérico hasta que se actualice ese formulario.
            tipo_material="general",
            path_texto=f"uploads/{material_dir_name}/texto.txt",
            path_texto_resumen=f"uploads/{material_dir_name}/resumen.txt",
            path_preguntas=f"uploads/{material_dir_name}/preguntas.json",
            path_audio=f"uploads/{material_dir_name}/audio.wav",
            path_audio_resumen=f"uploads/{material_dir_name}/audio_resumen.wav",
            fk_user=str(teacher["id"]),
        )
        db.session.add(material)
        db.session.commit()

        return jsonify({"material_id": material.id})

    def serialize_material(material):
        preguntas_path = os.path.join(app.static_folder, material.path_preguntas)
        try:
            with open(preguntas_path, "r", encoding="utf-8") as f:
                preguntas = json.load(f)
        except (OSError, json.JSONDecodeError):
            preguntas = []
        return {
            "id": material.id,
            "titulo": material.nombre_material,
            "tipo_material": material.tipo_material,
            "fecha_subido": material.fecha_subido.isoformat() if material.fecha_subido else None,
            "fk_user": material.fk_user,
            "texto_completo_url": url_for("static", filename=material.path_texto, _external=True),
            "texto_resumen_url": url_for("static", filename=material.path_texto_resumen, _external=True),
            "audio_completo_url": url_for("static", filename=material.path_audio, _external=True),
            "audio_resumen_url": url_for("static", filename=material.path_audio_resumen, _external=True),
            "preguntas_url": url_for("static", filename=material.path_preguntas, _external=True),
            "preguntas": preguntas,
        }

    # Robot-side endpoint. Every request must use the shared MAXCIM secret.
    @app.route("/api/materials", methods=["GET"])
    def list_materials():
        if not webhook_authorized():
            return jsonify({"error": "Integración no autorizada."}), 401
        teacher_id = (request.args.get("teacher_id") or request.args.get("dni") or "").strip()
        if not teacher_id:
            return jsonify({"error": "Falta el ID institucional de la docente."}), 400

        materials = (
            Material.query.filter_by(fk_user=teacher_id)
            .order_by(Material.fecha_subido.desc(), Material.id.desc())
            .all()
        )
        return jsonify([serialize_material(m) for m in materials])

    @app.route("/api/materials/<int:material_id>", methods=["GET"])
    def get_material(material_id):
        if not webhook_authorized():
            return jsonify({"error": "Integración no autorizada."}), 401
        material = db.session.get(Material, material_id)
        if not material:
            return jsonify({"error": "Material no encontrado."}), 404
        return jsonify(serialize_material(material))

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

    def serialize_interaccion(interaccion):
        return {
            "id": interaccion.id,
            "id_material": interaccion.id_material,
            "fk_alumno": interaccion.fk_alumno,
            "fecha_hora": interaccion.fecha_hora.isoformat() if interaccion.fecha_hora else None,
            "pregunta": interaccion.pregunta,
            "respuesta": interaccion.respuesta,
            "path_audio_rpta": url_for("static", filename=interaccion.path_audio_rpta, _external=True),
            "apreciacion_robot": interaccion.apreciacion_robot,
            "rpta_correcta": interaccion.rpta_correcta,
        }

    # Robot-side endpoint. MAXCIM ya no gestiona sesiones ni reconocimiento
    # facial: el robot resuelve por su cuenta qué alumno tiene enfrente y qué
    # material está usando, y reporta cada turno de pregunta/respuesta con
    # una sola llamada.
    @app.route("/api/interacciones", methods=["POST"])
    def registrar_interaccion():
        if not webhook_authorized():
            return jsonify({"error": "Integración no autorizada."}), 401

        payload = request.get_json(silent=True) or {}
        fk_alumno = str(payload.get("fk_alumno") or "").strip()
        pregunta = str(payload.get("pregunta") or "").strip()
        respuesta = str(payload.get("respuesta") or "").strip()
        path_audio_rpta = str(payload.get("path_audio_rpta") or "").strip()
        apreciacion_robot = str(payload.get("apreciacion_robot") or "").strip()

        try:
            material_id = int(payload.get("id_material"))
        except (TypeError, ValueError):
            return jsonify({"error": "id_material no es válido."}), 400
        try:
            rpta_correcta = parse_optional_bool(payload.get("rpta_correcta"))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        missing = [
            label
            for label, value in (
                ("fk_alumno", fk_alumno),
                ("pregunta", pregunta),
                ("respuesta", respuesta),
                ("path_audio_rpta", path_audio_rpta),
                ("apreciacion_robot", apreciacion_robot),
            )
            if not value
        ]
        if rpta_correcta is None:
            missing.append("rpta_correcta")
        if missing:
            return jsonify({"error": f"Faltan campos obligatorios: {', '.join(missing)}."}), 400
        if len(fk_alumno) > 50:
            return jsonify({"error": "fk_alumno excede el límite permitido."}), 413
        if len(path_audio_rpta) > 500:
            return jsonify({"error": "path_audio_rpta excede el límite permitido."}), 413
        if len(pregunta) > MAX_TRANSCRIPT_CHARS or len(respuesta) > MAX_TRANSCRIPT_CHARS:
            return jsonify({"error": "La pregunta o la respuesta exceden el límite permitido."}), 413

        material = db.session.get(Material, material_id)
        if not material:
            return jsonify({"error": "Material no encontrado."}), 404

        interaccion = Interaccion(
            id_material=material.id,
            fk_alumno=fk_alumno,
            pregunta=pregunta,
            respuesta=respuesta,
            path_audio_rpta=path_audio_rpta,
            apreciacion_robot=apreciacion_robot,
            rpta_correcta=rpta_correcta,
        )
        db.session.add(interaccion)
        db.session.commit()
        return jsonify(serialize_interaccion(interaccion)), 201

    # Robot-side endpoint: consulta el historial (por material y/o alumno).
    @app.route("/api/interacciones", methods=["GET"])
    def list_interacciones():
        if not webhook_authorized():
            return jsonify({"error": "Integración no autorizada."}), 401
        query = Interaccion.query
        material_id = request.args.get("id_material")
        if material_id:
            try:
                query = query.filter_by(id_material=int(material_id))
            except ValueError:
                return jsonify({"error": "id_material no es válido."}), 400
        fk_alumno = request.args.get("fk_alumno")
        if fk_alumno:
            query = query.filter_by(fk_alumno=fk_alumno.strip())
        interacciones = query.order_by(Interaccion.fecha_hora.desc()).limit(200).all()
        return jsonify([serialize_interaccion(item) for item in interacciones])

    return app


app = create_app()

if __name__ == "__main__":
    app.run(
        host=os.environ.get("FLASK_HOST", "0.0.0.0"),
        port=int(os.environ.get("FLASK_PORT", "5000")),
        debug=env_bool("FLASK_DEBUG", False),
    )
