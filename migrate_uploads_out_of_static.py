"""Migración única: mueve los archivos de materiales de `static/uploads/` a
`UPLOADS_ROOT` (por defecto `<instance>/uploads/`).

Desde este cambio, los archivos de los materiales ya no viven bajo `static/`
para que Flask no los sirva sin autenticación. Las rutas guardadas en la BD
(`uploads/<id>/archivo`) no cambian: solo se reinterpretan como relativas a
`UPLOADS_ROOT`. Este script copia el árbol existente a la nueva ubicación.

Uso:  python migrate_uploads_out_of_static.py [--delete-source]
"""

import os
import shutil
import sys

from app import app

LEGACY_ROOT = os.path.join(app.static_folder, "uploads")


def main() -> int:
    delete_source = "--delete-source" in sys.argv[1:]
    target_root = app.config["UPLOADS_ROOT"]

    if os.path.normpath(LEGACY_ROOT) == os.path.normpath(target_root):
        print("UPLOADS_ROOT sigue siendo static/uploads; nada que migrar.")
        return 0
    if not os.path.isdir(LEGACY_ROOT):
        print(f"No existe {LEGACY_ROOT}; nada que migrar.")
        return 0

    os.makedirs(target_root, exist_ok=True)
    moved = skipped = 0
    for name in sorted(os.listdir(LEGACY_ROOT)):
        src = os.path.join(LEGACY_ROOT, name)
        dst = os.path.join(target_root, name)
        if os.path.exists(dst):
            print(f"  = ya existe en destino, se omite: {name}")
            skipped += 1
            continue
        shutil.copytree(src, dst) if os.path.isdir(src) else shutil.copy2(src, dst)
        print(f"  + copiado: {name}")
        moved += 1

    print(f"\nListo: {moved} copiados, {skipped} omitidos -> {target_root}")

    if delete_source:
        shutil.rmtree(LEGACY_ROOT, ignore_errors=True)
        print(f"Origen eliminado: {LEGACY_ROOT}")
    else:
        print(
            "El origen se conservó. Verifica la app y luego borra "
            f"{LEGACY_ROOT} (o repite con --delete-source)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
