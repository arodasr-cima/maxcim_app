"""Private and recoverable material-file storage helpers."""

from __future__ import annotations

import json
import logging
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BundlePaths:
    text: str
    summary: str
    questions: str
    audio: str
    summary_audio: str


def _safe_root(root: str | Path) -> Path:
    path = Path(root).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_bundle(
    root: str | Path,
    text: str,
    summary: str,
    questions: list[dict],
    audio: bytes,
    summary_audio: bytes,
    bundle_id: str | None = None,
) -> BundlePaths:
    root_path = _safe_root(root)
    directory_name = bundle_id or uuid.uuid4().hex
    directory = (root_path / directory_name).resolve()
    if root_path not in directory.parents:
        raise ValueError("Invalid storage directory")
    directory.mkdir(parents=False, exist_ok=False)
    try:
        (directory / "texto.txt").write_text(text, encoding="utf-8")
        (directory / "resumen.txt").write_text(summary, encoding="utf-8")
        (directory / "preguntas.json").write_text(
            json.dumps(questions, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (directory / "audio.wav").write_bytes(audio)
        (directory / "audio_resumen.wav").write_bytes(summary_audio)
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise

    return BundlePaths(
        text=f"{directory_name}/texto.txt",
        summary=f"{directory_name}/resumen.txt",
        questions=f"{directory_name}/preguntas.json",
        audio=f"{directory_name}/audio.wav",
        summary_audio=f"{directory_name}/audio_resumen.wav",
    )


def resolve_file(root: str | Path, relative_path: str) -> Path:
    root_path = _safe_root(root)
    candidate = (root_path / relative_path).resolve()
    if root_path not in candidate.parents or not candidate.is_file():
        raise FileNotFoundError(relative_path)
    return candidate


def delete_bundle(root: str | Path, directory_name: str) -> None:
    root_path = _safe_root(root)
    directory = (root_path / directory_name).resolve()
    if root_path not in directory.parents:
        raise ValueError("Invalid storage directory")
    if not directory.exists():
        return
    shutil.rmtree(directory, ignore_errors=True)
    if directory.exists():
        logger.warning(
            "Could not fully delete material bundle %s at %s", directory_name, directory
        )
