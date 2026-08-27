"""Authenticated JSON API for MAXCIM material workflows."""

from __future__ import annotations

import json

from flask import Blueprint, Response, current_app, jsonify, request, send_file, url_for
from flask_login import current_user, login_required

from ..demo import MATERIAL_SKILLS
from ..extensions import db, limiter
from ..models import Material
from ..services.ai import (
    AIServiceError,
    allowed_document,
    generate_questions,
    generate_speech,
    process_document,
)
from ..services.storage import delete_bundle, resolve_file, write_bundle

api_bp = Blueprint("api", __name__)
QUESTION_TYPES = ("literales", "inferenciales", "criticas")
QUESTION_STORAGE_TYPES = {"literal", "inferencial", "critica"}


def _json_error(message: str, status: int):
    return jsonify({"error": message}), status


def _valid_wav(upload) -> bool:
    if not upload:
        return False
    position = upload.stream.tell()
    header = upload.stream.read(12)
    upload.stream.seek(position)
    return len(header) == 12 and header[:4] == b"RIFF" and header[8:] == b"WAVE"


def _validated_questions(raw: str) -> list[dict]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Las preguntas no tienen un formato JSON válido.") from exc
    if not isinstance(data, list) or not data or len(data) > 45:
        raise ValueError("Genera entre 1 y 45 preguntas.")
    cleaned = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("El formato de las preguntas no es válido.")
        qtype = str(item.get("tipo", "")).strip().lower()
        question = str(item.get("pregunta", "")).strip()
        if qtype not in QUESTION_STORAGE_TYPES or not question or len(question) > 400:
            raise ValueError("Cada pregunta debe tener un tipo y un enunciado válidos.")
        cleaned.append({"tipo": qtype, "pregunta": question})
    return cleaned


def _serialize_material(material: Material) -> dict:
    return {
        "id": material.id,
        "titulo": material.nombre_material,
        "habilidad": material.skill,
        "fecha_subido": material.fecha_subido.isoformat(),
        "texto_completo_url": url_for("api.material_file", material_id=material.id, kind="texto"),
        "texto_resumen_url": url_for("api.material_file", material_id=material.id, kind="resumen"),
        "audio_completo_url": url_for("api.material_file", material_id=material.id, kind="audio"),
        "audio_resumen_url": url_for("api.material_file", material_id=material.id, kind="audio-resumen"),
        "preguntas_url": url_for("api.material_file", material_id=material.id, kind="preguntas"),
    }


@api_bp.post("/api/material/process")
@login_required
@limiter.limit("10 per minute")
def process_material():
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return _json_error("No se recibió ningún archivo.", 400)
    if not allowed_document(uploaded.filename, current_app.config):
        return _json_error("Usa un archivo TXT, PDF o DOCX.", 415)
    try:
        text, summary, demo_mode = process_document(uploaded, current_app.config)
    except AIServiceError as exc:
        return _json_error(str(exc), 400)
    except Exception:
        current_app.logger.exception("Unexpected document processing error")
        return _json_error("No se pudo procesar el documento.", 502)
    return jsonify({"transcribed_text": text, "summary_text": summary, "demo_mode": demo_mode})


@api_bp.post("/api/material/tts")
@login_required
@limiter.limit("10 per minute")
def material_tts():
    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()
    if not text:
        return _json_error("No hay texto para convertir a audio.", 400)
    if len(text) > current_app.config["MAX_TEXT_CHARS"]:
        return _json_error("El texto supera el límite permitido.", 400)
    try:
        audio_bytes, demo_mode = generate_speech(text, current_app.config)
    except AIServiceError as exc:
        return _json_error(str(exc), 502)
    response = Response(audio_bytes, mimetype="audio/wav")
    response.headers["X-MAXCIM-AI-Mode"] = "demo" if demo_mode else "gemini"
    return response


@api_bp.post("/api/material/questions")
@login_required
@limiter.limit("15 per minute")
def material_questions():
    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()
    if not text or len(text) > current_app.config["MAX_TEXT_CHARS"]:
        return _json_error("El texto está vacío o supera el límite permitido.", 400)
    counts_payload = payload.get("counts") or {}
    counts = {}
    for qtype in QUESTION_TYPES:
        try:
            value = int(counts_payload.get(qtype, 0))
        except (TypeError, ValueError):
            value = 0
        counts[qtype] = max(0, min(value, current_app.config["MAX_QUESTIONS_PER_TYPE"]))
    if not any(counts.values()):
        return _json_error("Indica al menos una pregunta para generar.", 400)
    try:
        questions, demo_mode = generate_questions(text, counts, current_app.config)
    except AIServiceError as exc:
        return _json_error(str(exc), 502)
    return jsonify({"questions": questions, "demo_mode": demo_mode})


@api_bp.post("/api/material/save")
@login_required
@limiter.limit("20 per hour")
def save_material():
    title = (request.form.get("title") or "").strip()
    skill = (request.form.get("skill") or "").strip()
    text = (request.form.get("transcribed_text") or "").strip()
    summary = (request.form.get("summary_text") or "").strip()
    audio_full = request.files.get("audio_full")
    audio_summary = request.files.get("audio_summary")
    if not title or len(title) > 120:
        return _json_error("Escribe un título de hasta 120 caracteres.", 400)
    if skill not in set(MATERIAL_SKILLS[1:]):
        return _json_error("Selecciona una habilidad válida.", 400)
    if not text or not summary or len(text) > current_app.config["MAX_TEXT_CHARS"]:
        return _json_error("El texto está vacío o supera el límite permitido.", 400)
    if not _valid_wav(audio_full) or not _valid_wav(audio_summary):
        return _json_error("Los audios deben estar en formato WAV válido.", 400)
    try:
        questions = _validated_questions(request.form.get("questions_json") or "")
    except ValueError as exc:
        return _json_error(str(exc), 400)

    paths = None
    try:
        paths = write_bundle(
            current_app.config["UPLOAD_FOLDER"],
            text,
            summary,
            questions,
            audio_full.read(),
            audio_summary.read(),
        )
        material = Material(
            nombre_material=title,
            skill=skill,
            path_audio=paths.audio,
            path_texto=paths.text,
            path_audio_resumen=paths.summary_audio,
            path_texto_resumen=paths.summary,
            path_preguntas=paths.questions,
            owner_id=current_user.id,
        )
        db.session.add(material)
        db.session.commit()
    except Exception:
        db.session.rollback()
        if paths:
            delete_bundle(current_app.config["UPLOAD_FOLDER"], paths.text.split("/", 1)[0])
        current_app.logger.exception("Material save failed")
        return _json_error("No se pudo guardar el material.", 500)
    return jsonify({"material": _serialize_material(material)}), 201


@api_bp.get("/api/materials")
@login_required
def list_materials():
    materials = (
        Material.query.filter_by(owner_id=current_user.id)
        .order_by(Material.fecha_subido.desc(), Material.id.desc())
        .all()
    )
    return jsonify([_serialize_material(item) for item in materials])


@api_bp.get("/api/materials/<int:material_id>")
@login_required
def get_material(material_id: int):
    material = Material.query.filter_by(id=material_id, owner_id=current_user.id).first_or_404()
    return jsonify(_serialize_material(material))


@api_bp.delete("/api/materials/<int:material_id>")
@login_required
@limiter.limit("20 per hour")
def delete_material(material_id: int):
    material = Material.query.filter_by(id=material_id, owner_id=current_user.id).first_or_404()
    directory = material.storage_directory
    db.session.delete(material)
    db.session.commit()
    delete_bundle(current_app.config["UPLOAD_FOLDER"], directory)
    return "", 204


@api_bp.get("/media/materials/<int:material_id>/<kind>")
@login_required
def material_file(material_id: int, kind: str):
    material = Material.query.filter_by(id=material_id, owner_id=current_user.id).first_or_404()
    file_map = {
        "texto": (material.path_texto, "text/plain; charset=utf-8", True),
        "resumen": (material.path_texto_resumen, "text/plain; charset=utf-8", True),
        "preguntas": (material.path_preguntas, "application/json", True),
        "audio": (material.path_audio, "audio/wav", False),
        "audio-resumen": (material.path_audio_resumen, "audio/wav", False),
    }
    if kind not in file_map:
        return _json_error("Archivo no encontrado.", 404)
    relative_path, mimetype, as_attachment = file_map[kind]
    try:
        path = resolve_file(current_app.config["UPLOAD_FOLDER"], relative_path)
    except FileNotFoundError:
        return _json_error("Archivo no encontrado.", 404)
    return send_file(path, mimetype=mimetype, as_attachment=as_attachment, download_name=path.name)
