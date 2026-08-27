"""Document, question and speech services with a key-free demo fallback."""

from __future__ import annotations

import io
import json
import logging
import math
import mimetypes
import re
import struct
import tempfile
import wave
from pathlib import Path

from docx import Document
from google import genai
from google.genai import types
from pypdf import PdfReader

logger = logging.getLogger(__name__)


class AIServiceError(RuntimeError):
    """Raised when a document or AI response cannot be processed safely."""


EXTRACT_PROMPT = (
    "Extrae todo el texto de este documento sin resumir, interpretar ni agregar "
    "comentarios. Responde únicamente con el texto extraído."
)
SUMMARY_PROMPT = "Resume el siguiente texto en 2 o 3 oraciones claras en español:\n\n{text}"
QUESTION_DESCRIPTIONS = {
    "literales": "preguntas literales basadas en información explícita",
    "inferenciales": "preguntas inferenciales que requieran deducir información",
    "criticas": "preguntas críticas que inviten a valorar o reflexionar",
}
QUESTIONS_PROMPT = (
    "A partir del texto, genera preguntas de comprensión lectora en español.\n"
    "Cantidades exactas:\n{requirements}\n\nTexto:\n{text}\n\n"
    "Responde solamente con JSON: "
    '{{"literales": [...], "inferenciales": [...], "criticas": [...]}}.'
)
TTS_STYLE = (
    "Narra en español latinoamericano con un tono alegre, natural, claro y apropiado "
    "para un cuento educativo. Conserva el mismo ritmo y energía:\n\n"
)
TTS_CHUNK_MAX_CHARS = 700
TTS_SAMPLE_RATE = 24_000


def is_demo_mode(config) -> bool:
    return bool(config.get("DEMO_MODE") or not config.get("GOOGLE_API_KEY"))


def allowed_document(filename: str, config) -> bool:
    return Path(filename or "").suffix.lower() in config["ALLOWED_DOCUMENT_EXTENSIONS"]


def _normalize_text(text: str) -> str:
    return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", text)).strip()


def _read_document_locally(file_storage) -> str:
    suffix = Path(file_storage.filename or "").suffix.lower()
    file_storage.stream.seek(0)
    try:
        if suffix == ".txt":
            raw = file_storage.stream.read()
            text = raw.decode("utf-8-sig", errors="replace")
        elif suffix == ".pdf":
            reader = PdfReader(file_storage.stream)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        elif suffix == ".docx":
            document = Document(file_storage.stream)
            text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        else:
            raise AIServiceError("Formato de documento no permitido.")
    except AIServiceError:
        raise
    except Exception as exc:
        raise AIServiceError("No se pudo leer el documento seleccionado.") from exc
    finally:
        file_storage.stream.seek(0)

    text = _normalize_text(text)
    if not text:
        raise AIServiceError("El documento no contiene texto legible.")
    return text


def _demo_summary(text: str) -> str:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?…])\s+", text) if part.strip()]
    summary = " ".join(sentences[:3]) if sentences else text
    if len(summary) > 420:
        summary = summary[:417].rsplit(" ", 1)[0] + "..."
    return summary


def _gemini_client(config):
    key = config.get("GOOGLE_API_KEY")
    if not key:
        raise AIServiceError("La integración con Gemini no está configurada.")
    return genai.Client(api_key=key)


def _process_with_gemini(file_storage, config) -> tuple[str, str]:
    client = _gemini_client(config)
    filename = file_storage.filename or "documento"
    mime_type = file_storage.mimetype or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    suffix = Path(filename).suffix
    tmp_path = None
    uploaded_file = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            file_storage.save(tmp)
            tmp_path = tmp.name
        uploaded_file = client.files.upload(
            file=tmp_path,
            config={"mime_type": mime_type, "display_name": filename},
        )
        extracted = client.models.generate_content(
            model=config["GEMINI_MODEL"],
            contents=[uploaded_file, EXTRACT_PROMPT],
        ).text
        text = _normalize_text(extracted or "")
        if not text:
            raise AIServiceError("Gemini no encontró texto legible en el documento.")
        summary = client.models.generate_content(
            model=config["GEMINI_MODEL"],
            contents=SUMMARY_PROMPT.format(text=text),
        ).text
        return text, _normalize_text(summary or "")
    except AIServiceError:
        raise
    except Exception as exc:
        raise AIServiceError("El servicio de IA no pudo procesar el documento.") from exc
    finally:
        if uploaded_file is not None:
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception:
                logger.warning("Could not delete the temporary Gemini upload", exc_info=True)
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


def process_document(file_storage, config) -> tuple[str, str, bool]:
    if is_demo_mode(config):
        text = _read_document_locally(file_storage)
        return text, _demo_summary(text), True
    text, summary = _process_with_gemini(file_storage, config)
    return text, summary, False


def _demo_questions(text: str, counts: dict[str, int]) -> dict[str, list[str]]:
    first_sentence = re.split(r"(?<=[.!?…])\s+", text.strip())[0][:180]
    stems = {
        "literales": [
            f"¿Qué sucede en este fragmento: «{first_sentence}»?",
            "¿Quiénes participan en los hechos principales del texto?",
            "¿Dónde se desarrolla la historia o situación presentada?",
            "¿Cuál es el acontecimiento principal del texto?",
        ],
        "inferenciales": [
            "¿Qué se puede deducir sobre las emociones del personaje principal?",
            "¿Por qué crees que ocurrió el acontecimiento principal?",
            "¿Qué podría suceder después y qué pista del texto lo sugiere?",
            "¿Qué enseñanza implícita puede obtenerse de la lectura?",
        ],
        "criticas": [
            "¿Estás de acuerdo con las decisiones de los personajes? Explica tu respuesta.",
            "¿Qué habrías hecho de manera diferente en esa situación?",
            "¿Qué valor sociocomunicativo consideras más importante en el texto y por qué?",
            "¿Cómo aplicarías la enseñanza de la lectura en tu aula o comunidad?",
        ],
    }
    result = {}
    for qtype, count in counts.items():
        base = stems[qtype]
        result[qtype] = [base[index % len(base)] for index in range(count)]
    return result


def generate_questions(text: str, counts: dict[str, int], config) -> tuple[dict[str, list[str]], bool]:
    if is_demo_mode(config):
        return _demo_questions(text, counts), True

    requirements = "\n".join(
        f"- {count} {QUESTION_DESCRIPTIONS[qtype]}" for qtype, count in counts.items() if count
    )
    try:
        response = _gemini_client(config).models.generate_content(
            model=config["GEMINI_MODEL"],
            contents=QUESTIONS_PROMPT.format(requirements=requirements, text=text),
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        data = json.loads(response.text)
    except Exception as exc:
        raise AIServiceError("La IA no pudo generar preguntas válidas.") from exc
    result = {
        qtype: [str(question).strip() for question in data.get(qtype, [])][:count]
        for qtype, count in counts.items()
    }
    return result, False


def split_text_into_chunks(text: str, max_chars: int = TTS_CHUNK_MAX_CHARS) -> list[str]:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?…])\s+", text.strip()) if part.strip()]
    pieces: list[str] = []
    for sentence in sentences or [text.strip()]:
        while len(sentence) > max_chars:
            cut = sentence.rfind(" ", 0, max_chars + 1)
            cut = cut if cut > max_chars // 2 else max_chars
            pieces.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if sentence:
            pieces.append(sentence)

    chunks: list[str] = []
    current = ""
    for piece in pieces:
        candidate = f"{current} {piece}".strip()
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = piece
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def demo_wav(text: str) -> bytes:
    sample_rate = 16_000
    duration = min(3.0, max(1.4, len(text) / 180))
    frames = bytearray()
    frequencies = (440.0, 554.37, 659.25)
    for index in range(int(sample_rate * duration)):
        phase = index / sample_rate
        frequency = frequencies[int(phase / 0.35) % len(frequencies)]
        envelope = min(1.0, phase * 8, (duration - phase) * 8)
        value = int(4_000 * envelope * math.sin(2 * math.pi * frequency * phase))
        frames.extend(struct.pack("<h", value))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(bytes(frames))
    return buffer.getvalue()


def generate_speech(text: str, config) -> tuple[bytes, bool]:
    if is_demo_mode(config):
        return demo_wav(text), True

    pcm_data = bytearray()
    sample_rate = TTS_SAMPLE_RATE
    try:
        client = _gemini_client(config)
        for chunk in split_text_into_chunks(text):
            response = client.models.generate_content(
                model=config["GEMINI_TTS_MODEL"],
                contents=TTS_STYLE + chunk,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=config["GEMINI_TTS_VOICE"]
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
    except Exception as exc:
        raise AIServiceError("La IA no pudo generar el audio.") from exc

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(bytes(pcm_data))
    return buffer.getvalue(), False
