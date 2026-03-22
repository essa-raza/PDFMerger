"""
Generate a fake test dataset of PDFs that match your rules.

Creates:
<root>/
  2-26/
    Factuur_38_frituur-annigo_2-2026_Main.pdf
    Factuur_38_frituur-annigo_2-2026_Detaillering.pdf
    Factuur_40_frituur-xyz_2-2026_Main.pdf
  3-26/
    ...
  4-26/
    ...

Each PDF contains only a tiny random number + filename (no excessive data).
"""

import os
import random
from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4


# -------------------------
# Config you can change
# -------------------------
ROOT_FOLDER = r"C:\Users\Admin\Pictures\pdf\3"  # <-- change this
SUBFOLDERS = ["2-26", "3-26", "4-26"]  # folders inside root
TOTAL_BASES = 50                      # total "base identifiers" to generate
YEAR = 2026

# Probability of each case:
# A = both exist, B = only Main, C = only Detaillering
CASE_WEIGHTS = {"A": 0.55, "B": 0.30, "C": 0.15}


# -------------------------
# Helpers
# -------------------------
def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def write_tiny_pdf(filepath: Path, title: str) -> None:
    """Create a 1-page minimal PDF with just a couple lines."""
    ensure_dir(filepath.parent)
    c = canvas.Canvas(str(filepath), pagesize=A4)
    w, h = A4
    c.setFont("Helvetica", 12)
    c.drawString(72, h - 72, title)
    c.drawString(72, h - 96, f"Random: {random.randint(100000, 999999)}")
    c.showPage()
    c.save()

def weighted_choice(weights: dict) -> str:
    r = random.random()
    cumulative = 0.0
    for k, w in weights.items():
        cumulative += w
        if r <= cumulative:
            return k
    return list(weights.keys())[-1]


# -------------------------
# Main generation
# -------------------------
def generate():
    root = Path(ROOT_FOLDER)
    ensure_dir(root)

    # Some fake client slugs
    clients = [
        "frituur-annigo", "frituur-xyz", "bakkerij-de-smid", "pizza-luna", "snackbar-royal",
        "cafe-roma", "bistro-olive", "kebab-istanbul", "sushi-nori", "shop-alpha",
        "shop-beta", "garage-nova", "service-pro", "market-central", "food-corner"
    ]

    # Pre-create subfolders
    folder_paths = []
    for f in SUBFOLDERS:
        p = root / f
        ensure_dir(p)
        folder_paths.append(p)

    # Create 50 base identifiers, distributed across subfolders
    used_bases = set()

    for i in range(TOTAL_BASES):
        folder = random.choice(folder_paths)

        # Derive month from folder name like "2-26" -> month=2
        month = int(folder.name.split("-")[0])

        # Pick invoice number and client; ensure base uniqueness
        while True:
            inv_no = random.randint(1, 250)
            client = random.choice(clients)
            base = f"Factuur_{inv_no}_{client}_{month}-{YEAR}"
            # Uniqueness across all folders (good enough for testing)
            if (folder, base) not in used_bases:
                used_bases.add((folder, base))
                break

        case = weighted_choice(CASE_WEIGHTS)

        main_name = f"{base}_Main.pdf"
        det_name = f"{base}_Detaillering.pdf"

        if case == "A":
            write_tiny_pdf(folder / main_name, f"{base} | MAIN")
            write_tiny_pdf(folder / det_name, f"{base} | DETAILLERING")
        elif case == "B":
            write_tiny_pdf(folder / main_name, f"{base} | MAIN (only)")
        else:  # case == "C"
            write_tiny_pdf(folder / det_name, f"{base} | DETAILLERING (only)")

    print(f"✅ Done. Generated {TOTAL_BASES} base sets across {len(SUBFOLDERS)} folders.")
    print(f"📁 Root: {root}")

if __name__ == "__main__":
    generate()