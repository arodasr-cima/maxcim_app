import io
import json
import mimetypes
import os
import re
import tempfile
import uuid
import wave
from datetime import date
from urllib.parse import quote_plus

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy
from google import genai
from google.genai import types

load_dotenv()

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
GEMINI_TTS_VOICE = os.environ.get("GEMINI_TTS_VOICE", "Puck")

gemini_client = genai.Client(api_key=GOOGLE_API_KEY) if GOOGLE_API_KEY else None

MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
MYSQL_PORT = os.environ.get("MYSQL_PORT", "3306")
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "")
SQLALCHEMY_DATABASE_URI = (
    f"mysql+pymysql://{quote_plus(MYSQL_USER)}:{quote_plus(MYSQL_PASSWORD)}"
    f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4"
)

db = SQLAlchemy()


class Material(db.Model):
    """Maps to the pre-existing `material` table — audio/text are stored as
    files on disk, this row only holds their paths."""

    __tablename__ = "material"

    id = db.Column(db.Integer, primary_key=True)
    nombre_material = db.Column(db.String(255), nullable=False)
    path_audio = db.Column(db.String(500), nullable=False)
    path_texto = db.Column(db.String(500), nullable=False)
    path_audio_resumen = db.Column(db.String(500), nullable=False)
    path_texto_resumen = db.Column(db.String(500), nullable=False)
    path_preguntas = db.Column(db.String(500), nullable=False)
    fecha_subido = db.Column(db.Date, server_default=db.func.curdate())
    # No `usuario` table exists yet, so this isn't a real FK — just the
    # placeholder identifier from USER until one does (see the
    # docente_seccion design we're deferring).
    fk_user = db.Column(db.String(50), nullable=True)

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
    '{{"literales": [...], "inferenciales": [...], "criticas": [...]}}, '
    "donde cada elemento de las listas es el enunciado de una pregunta. "
    "No agregues numeración, comentarios ni texto fuera del JSON."
)
MAX_QUESTIONS_PER_TYPE = 15

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


def generate_questions(text: str, counts: dict[str, int]) -> dict[str, list[str]]:
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

    return {
        qtype: [str(q).strip() for q in data.get(qtype, [])][:count]
        for qtype, count in counts.items()
    }


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


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev")
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
    app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
    db.init_app(app)

    @app.route("/")
    def index():
        return redirect(url_for("dashboard"))

    @app.route("/dashboard")
    def dashboard():
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
        return render_template(
            "sesiones.html",
            active_nav="sesiones",
            user=USER,
        )

    @app.route("/api/material/process", methods=["POST"])
    def process_material():
        if not gemini_client:
            return jsonify({"error": "GOOGLE_API_KEY no está configurada en el servidor."}), 500

        uploaded = request.files.get("file")
        if not uploaded or not uploaded.filename:
            return jsonify({"error": "No se recibió ningún archivo."}), 400

        try:
            transcribed_text, summary_text = extract_and_summarize(uploaded)
        except Exception as exc:
            return jsonify({"error": f"No se pudo procesar el documento: {exc}"}), 502

        return jsonify({
            "transcribed_text": transcribed_text,
            "summary_text": summary_text,
        })

    @app.route("/api/material/tts", methods=["POST"])
    def material_tts():
        if not gemini_client:
            return jsonify({"error": "GOOGLE_API_KEY no está configurada en el servidor."}), 500

        payload = request.get_json(silent=True) or {}
        text = (payload.get("text") or "").strip()
        if not text:
            return jsonify({"error": "No hay texto para convertir a audio."}), 400

        try:
            audio_bytes = generate_speech(text)
        except Exception as exc:
            return jsonify({"error": f"No se pudo generar el audio: {exc}"}), 502

        return Response(audio_bytes, mimetype="audio/wav")

    @app.route("/api/material/questions", methods=["POST"])
    def material_questions():
        if not gemini_client:
            return jsonify({"error": "GOOGLE_API_KEY no está configurada en el servidor."}), 500

        payload = request.get_json(silent=True) or {}
        text = (payload.get("text") or "").strip()
        counts_payload = payload.get("counts") or {}

        if not text:
            return jsonify({"error": "No hay texto para generar preguntas."}), 400

        counts = {}
        for qtype in QUESTION_TYPES:
            try:
                count = int(counts_payload.get(qtype, 0))
            except (TypeError, ValueError):
                count = 0
            counts[qtype] = max(0, min(count, MAX_QUESTIONS_PER_TYPE))

        if not any(counts.values()):
            return jsonify({"error": "Indica al menos una pregunta para generar."}), 400

        try:
            questions = generate_questions(text, counts)
        except Exception as exc:
            return jsonify({"error": f"No se pudieron generar las preguntas: {exc}"}), 502

        return jsonify({"questions": questions})

    @app.route("/api/material/save", methods=["POST"])
    def save_material():
        title = (request.form.get("title") or "").strip() or "Material sin título"
        transcribed_text = (request.form.get("transcribed_text") or "").strip()
        summary_text = (request.form.get("summary_text") or "").strip()
        questions_json_raw = (request.form.get("questions_json") or "").strip()
        audio_full = request.files.get("audio_full")
        audio_summary = request.files.get("audio_summary")

        if not transcribed_text or not summary_text:
            return jsonify({"error": "Falta el texto completo o el resumen."}), 400
        if not questions_json_raw:
            return jsonify({"error": "Falta generar las preguntas."}), 400
        try:
            questions_data = json.loads(questions_json_raw)
        except json.JSONDecodeError:
            return jsonify({"error": "Las preguntas no tienen un formato JSON válido."}), 400
        if not isinstance(questions_data, list) or not questions_data:
            return jsonify({"error": "Falta generar las preguntas."}), 400
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
            fk_user=USER["fk_user"],
        )
        db.session.add(material)
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
        }

    # No auth yet — for testing only, per explicit request. Do not expose this
    # publicly as-is; add an API key check before anything but local use.
    @app.route("/api/materials", methods=["GET"])
    def list_materials():
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
        material = db.session.get(Material, material_id)
        if not material:
            return jsonify({"error": "Material no encontrado."}), 404
        return jsonify(serialize_material(material))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
