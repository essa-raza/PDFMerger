import re
import shutil
from pathlib import Path

from pypdf import PdfReader, PdfWriter

# =========================
# CONFIG (change this path)
# =========================
ROOT_FOLDER = r"C:\Users\Admin\Pictures\pdf\3"   # <-- set your root folder here (e.g., C:\Users\Admin\Pictures\pdf\Reports)

# File naming
MAIN_SUFFIX = "_Main.pdf"
DETAIL_SUFFIX = "_Detaillering.pdf"

# Output folder name inside each subfolder
RESULTS_FOLDER_NAME = "results"

# Detect base from filenames like: <base>_Main.pdf or <base>_Detaillering.pdf
FILE_PATTERN = re.compile(r"^(?P<base>.+)_(?P<kind>Main|Detaillering)\.pdf$", re.IGNORECASE)


def merge_two_pdfs(main_path: Path, detail_path: Path, out_path: Path) -> None:
    """Merge Main first, then Detaillering."""
    writer = PdfWriter()

    main_reader = PdfReader(str(main_path))
    for page in main_reader.pages:
        writer.add_page(page)

    detail_reader = PdfReader(str(detail_path))
    for page in detail_reader.pages:
        writer.add_page(page)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        writer.write(f)


def process_one_folder(folder: Path) -> None:
    """
    Process a single subfolder:
    - Find <base>_Main.pdf and <base>_Detaillering.pdf
    - Create folder/results/
    - Output <base>.pdf:
        A) merge if both exist
        B) copy Main if only Main exists
        C) copy Detaillering if only Detaillering exists
    """
    results_dir = folder / RESULTS_FOLDER_NAME
    results_dir.mkdir(parents=True, exist_ok=True)

    # base -> {"main": Path|None, "detail": Path|None}
    pairs: dict[str, dict[str, Path | None]] = {}

    for f in folder.iterdir():
        if not f.is_file() or f.suffix.lower() != ".pdf":
            continue

        m = FILE_PATTERN.match(f.name)
        if not m:
            continue  # ignore unrelated PDFs

        base = m.group("base")
        kind = m.group("kind").lower()  # main or detaillering

        pairs.setdefault(base, {"main": None, "detail": None})
        if kind == "main":
            pairs[base]["main"] = f
        else:
            pairs[base]["detail"] = f

    merged = copied = skipped = 0
    log_lines = []
    log_lines.append(f"FOLDER: {folder}")
    log_lines.append(f"RESULTS: {results_dir}")
    log_lines.append("-" * 80)

    for base, files in sorted(pairs.items(), key=lambda kv: kv[0].lower()):
        main_path = files["main"]
        detail_path = files["detail"]
        out_path = results_dir / f"{base}.pdf"

        try:
            if main_path and detail_path:
                merge_two_pdfs(main_path, detail_path, out_path)
                merged += 1
                log_lines.append(f"[OK]   MERGED: {main_path.name} + {detail_path.name} -> {out_path.name}")

            elif main_path and not detail_path:
                shutil.copyfile(main_path, out_path)
                copied += 1
                log_lines.append(f"[WARN]   COPIED (no detail): {main_path.name} -> {out_path.name}")

            elif detail_path and not main_path:
                shutil.copyfile(detail_path, out_path)
                copied += 1
                log_lines.append(f"[WARN] ONLY detail found: {detail_path.name} -> {out_path.name}")

            else:
                skipped += 1
                log_lines.append(f"[SKIP] {base} (no files?)")

        except Exception as e:
            skipped += 1
            log_lines.append(f"[ERR]  {base}: {e}")

    log_lines.append("-" * 80)
    log_lines.append(f"Done. Merged: {merged}, Copied: {copied}, Skipped: {skipped}")

    (results_dir / "merge_log.txt").write_text("\n".join(log_lines), encoding="utf-8")
    print("\n".join(log_lines))


def main():
    root = Path(ROOT_FOLDER).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Root folder not found or not a directory: {root}")

    # Process each immediate subfolder under root
    subfolders = [p for p in root.iterdir() if p.is_dir()]

    if not subfolders:
        print(f"No subfolders found inside: {root}")
        return

    for folder in sorted(subfolders, key=lambda p: p.name.lower()):
        process_one_folder(folder)


if __name__ == "__main__":
    main()