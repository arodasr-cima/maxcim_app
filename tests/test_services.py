from __future__ import annotations

import pytest

from maxcim.services.ai import split_text_into_chunks
from maxcim.services.storage import delete_bundle, resolve_file, write_bundle


def test_long_tts_sentences_are_always_split():
    chunks = split_text_into_chunks("x" * 1_500, max_chars=700)
    assert len(chunks) == 3
    assert max(map(len, chunks)) <= 700


def test_storage_bundle_is_private_and_deletable(tmp_path):
    paths = write_bundle(tmp_path, "texto", "resumen", [], b"audio", b"audio", bundle_id="bundle")
    assert resolve_file(tmp_path, paths.text).read_text(encoding="utf-8") == "texto"
    delete_bundle(tmp_path, "bundle")
    assert not (tmp_path / "bundle").exists()


def test_storage_blocks_path_traversal(tmp_path):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        resolve_file(tmp_path, "../outside.txt")
