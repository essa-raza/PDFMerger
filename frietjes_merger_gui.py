import sys
import re
import shutil
from pathlib import Path
from datetime import datetime
from PySide6.QtGui import QIcon

from pypdf import PdfReader, PdfWriter

from PySide6.QtCore import QObject, Signal, QThread
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QTextEdit, QProgressBar,
    QMessageBox, QCheckBox, QGroupBox, QDialog, QDialogButtonBox
)

# =========================
# Core merge rules
# =========================
FILE_PATTERN = re.compile(r"^(?P<base>.+)_(?P<kind>Main|Detaillering)\.pdf$", re.IGNORECASE)
RESULTS_FOLDER_NAME = "results"


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


def process_pdf_folder(target_folder: Path, overwrite: bool, log_cb=None, progress_cb=None) -> None:
    """
    Process ONE folder:
    - Find <base>_Main.pdf and <base>_Detaillering.pdf
    - Create results/
    - Output <base>.pdf:
        A) merge if both exist
        B) copy Main if only Main exists
        C) copy Detaillering if only Detaillering exists (warn)
    - Write merge_log.txt in results/
    """
    target_folder = target_folder.resolve()
    results_dir = target_folder / RESULTS_FOLDER_NAME
    results_dir.mkdir(parents=True, exist_ok=True)

    def log(msg: str):
        if log_cb:
            log_cb(msg)

    # base -> {"main": Path|None, "detail": Path|None}
    pairs: dict[str, dict[str, Path | None]] = {}

    pdf_files = [p for p in target_folder.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"]
    for f in pdf_files:
        m = FILE_PATTERN.match(f.name)
        if not m:
            continue
        base = m.group("base")
        kind = m.group("kind").lower()

        pairs.setdefault(base, {"main": None, "detail": None})
        if kind == "main":
            pairs[base]["main"] = f
        else:
            pairs[base]["detail"] = f

    bases = sorted(pairs.keys(), key=lambda s: s.lower())

    merged = copied = skipped = 0
    log_lines = []
    log_lines.append(f"FOLDER : {target_folder}")
    log_lines.append(f"RESULTS: {results_dir}")
    log_lines.append(f"TIME   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_lines.append("-" * 90)

    total = len(bases) if bases else 1
    done = 0

    for base in bases:
        done += 1
        if progress_cb:
            progress_cb(int(done * 100 / total))

        files = pairs[base]
        main_path = files["main"]
        detail_path = files["detail"]
        out_path = results_dir / f"{base}.pdf"

        if out_path.exists() and not overwrite:
            skipped += 1
            msg = f"[SKIP] {out_path.name} (already exists)"
            log(msg)
            log_lines.append(msg)
            continue

        try:
            if main_path and detail_path:
                merge_two_pdfs(main_path, detail_path, out_path)
                merged += 1
                msg = f"[OK]   MERGED: {main_path.name} + {detail_path.name} -> {out_path.name}"
                log(msg)
                log_lines.append(msg)

            elif main_path and not detail_path:
                shutil.copyfile(main_path, out_path)
                copied += 1
                msg = f"[OK]   COPIED (no detail): {main_path.name} -> {out_path.name}"
                log(msg)
                log_lines.append(msg)

            elif detail_path and not main_path:
                shutil.copyfile(detail_path, out_path)
                copied += 1
                msg = f"[WARN] ONLY detail found: {detail_path.name} -> {out_path.name}"
                log(msg)
                log_lines.append(msg)

            else:
                skipped += 1
                msg = f"[SKIP] {base} (no files?)"
                log(msg)
                log_lines.append(msg)

        except Exception as e:
            skipped += 1
            msg = f"[ERR]  {base}: {e}"
            log(msg)
            log_lines.append(msg)

    if progress_cb:
        progress_cb(100)

    log_lines.append("-" * 90)
    log_lines.append(f"Done. Merged: {merged}, Copied: {copied}, Skipped: {skipped}")

    (results_dir / "merge_log.txt").write_text("\n".join(log_lines), encoding="utf-8")


def process_root_subfolders(root: Path, overwrite: bool, log_cb=None, progress_cb=None) -> None:
    """
    Process each immediate subfolder of root:
      root/
        2-26/
        3-26/
    Each gets its own results/ folder.
    """
    root = root.resolve()
    subfolders = sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.name.lower())
    total = len(subfolders) if subfolders else 1
    done = 0

    def log(msg: str):
        if log_cb:
            log_cb(msg)

    for sf in subfolders:
        done += 1
        if progress_cb:
            progress_cb(int(done * 100 / total))

        log("")
        log(f"=== Processing folder: {sf} ===")
        process_pdf_folder(sf, overwrite=overwrite, log_cb=log_cb, progress_cb=None)

    if progress_cb:
        progress_cb(100)


# =========================
# Rules Dialog
# =========================
class RulesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Rules")
        self.resize(560, 380)

        layout = QVBoxLayout(self)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml("""
        <h2>PDF Merger Rules</h2>
        <ul>
          <li>Pairs files by name: <b>&lt;base&gt;_Main.pdf</b> and <b>&lt;base&gt;_Detaillering.pdf</b></li>
          <li>Creates output: <b>&lt;base&gt;.pdf</b></li>
          <li>Merge order: <b>Main first</b>, then <b>Detaillering</b></li>
          <li>If a sibling is missing, the existing file is kept as <b>&lt;base&gt;.pdf</b></li>
          <li>All outputs are saved in a folder named <b>results</b></li>
          <li>A log file <b>merge_log.txt</b> is written inside the results folder</li>
        </ul>
        """)
        layout.addWidget(text)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


# =========================
# Worker thread (keeps UI responsive)
# =========================
class Worker(QObject):
    log_signal = Signal(str)
    progress_signal = Signal(int)
    done_signal = Signal(bool, str)

    def __init__(self, mode: str, path: Path, overwrite: bool):
        super().__init__()
        self.mode = mode
        self.path = path
        self.overwrite = overwrite

    def run(self):
        try:
            self.progress_signal.emit(0)

            if self.mode in ("current", "pick_folder"):
                process_pdf_folder(
                    self.path,
                    overwrite=self.overwrite,
                    log_cb=lambda s: self.log_signal.emit(s),
                    progress_cb=lambda p: self.progress_signal.emit(p),
                )

            elif self.mode == "subfolders":
                process_root_subfolders(
                    self.path,
                    overwrite=self.overwrite,
                    log_cb=lambda s: self.log_signal.emit(s),
                    progress_cb=lambda p: self.progress_signal.emit(p),
                )
            else:
                raise ValueError("Unknown mode")

            self.done_signal.emit(True, "Completed successfully.")
        except Exception as e:
            self.done_signal.emit(False, str(e))


# =========================
# GUI App
# =========================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon("pdf_merger.ico"))
        self.setWindowTitle("PDF Merger")
        self.resize(920, 620)

        self.thread = None
        self.worker = None

        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)

        # Header row: title left, Rules button right
        header_row = QHBoxLayout()
        title = QLabel("PDF Merger")
        title.setStyleSheet("font-size: 22px; font-weight: 600;")
        header_row.addWidget(title)
        header_row.addStretch(1)

        self.btn_rules = QPushButton("Rules")
        self.btn_rules.setFixedHeight(30)
        header_row.addWidget(self.btn_rules)
        layout.addLayout(header_row)

        # Small subtitle


        opts_box = QGroupBox("Options")
        opts_layout = QHBoxLayout(opts_box)
        self.overwrite_chk = QCheckBox("Overwrite existing output PDFs")
        opts_layout.addWidget(self.overwrite_chk)
        opts_layout.addStretch(1)
        layout.addWidget(opts_box)

        btn_row = QHBoxLayout()

        self.btn_current = QPushButton("Process Current Folder (EXE Location)")
        self.btn_pick = QPushButton("Choose Folder…")
        self.btn_subfolders = QPushButton("Choose Root Folder (Process Subfolders)…")

        for b in (self.btn_current, self.btn_pick, self.btn_subfolders):
            b.setMinimumHeight(38)

        btn_row.addWidget(self.btn_current)
        btn_row.addWidget(self.btn_pick)
        btn_row.addWidget(self.btn_subfolders)
        layout.addLayout(btn_row)

        self.path_label = QLabel("Selected path: (none)")
        self.path_label.setStyleSheet("color: #555;")
        layout.addWidget(self.path_label)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        layout.addWidget(self.progress)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Logs will appear here…")
        layout.addWidget(self.log, stretch=1)

        # Signals
        self.btn_rules.clicked.connect(self.show_rules)
        self.btn_current.clicked.connect(self.on_current)
        self.btn_pick.clicked.connect(self.on_pick_folder)
        self.btn_subfolders.clicked.connect(self.on_pick_root)

        # Light modern styling
        self.setStyleSheet("""
            QGroupBox { font-weight: 600; }
            QPushButton { padding: 6px 10px; }
            QTextEdit { background: #ffffff; }
        """)

    def show_rules(self):
        dlg = RulesDialog(self)
        dlg.exec()

    def append_log(self, msg: str):
        self.log.append(msg)

    def set_busy(self, busy: bool):
        self.btn_current.setEnabled(not busy)
        self.btn_pick.setEnabled(not busy)
        self.btn_subfolders.setEnabled(not busy)

    def run_job(self, mode: str, path: Path):
        if not path.exists():
            QMessageBox.critical(self, "Error", f"Path not found:\n{path}")
            return

        self.log.clear()
        self.progress.setValue(0)
        self.path_label.setText(f"Selected path: {path}")

        overwrite = self.overwrite_chk.isChecked()

        self.thread = QThread()
        self.worker = Worker(mode=mode, path=path, overwrite=overwrite)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.log_signal.connect(self.append_log)
        self.worker.progress_signal.connect(self.progress.setValue)
        self.worker.done_signal.connect(self.on_done)

        self.worker.done_signal.connect(self.thread.quit)
        self.worker.done_signal.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.set_busy(True)
        self.thread.start()

    def on_done(self, ok: bool, msg: str):
        self.set_busy(False)
        if ok:
            QMessageBox.information(self, "Done", msg)
        else:
            QMessageBox.critical(self, "Error", msg)

    def on_current(self):
        # Folder where the script/exe is located
        exe_dir = Path(sys.argv[0]).resolve().parent
        self.run_job("current", exe_dir)

    def on_pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose folder containing PDFs")
        if folder:
            self.run_job("pick_folder", Path(folder))

    def on_pick_root(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose ROOT folder (will process each subfolder)")
        if folder:
            self.run_job("subfolders", Path(folder))


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()