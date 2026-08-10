import shutil
import subprocess
from pathlib import Path

from .config import TECTONIC_BIN


def find_latex_engine() -> list[str] | None:
    if TECTONIC_BIN.exists():
        return [str(TECTONIC_BIN)]
    for name in ("tectonic", "pdflatex", "xelatex", "lualatex"):
        path = shutil.which(name)
        if path:
            return [path]
    return None


def compile_pdf(tex_path: Path, output_dir: Path | None = None) -> Path:
    """Compile LaTeX resume to PDF. Returns path to the PDF."""
    tex_path = tex_path.resolve()
    output_dir = (output_dir or tex_path.parent).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    engine = find_latex_engine()
    if not engine:
        raise RuntimeError(
            "No LaTeX engine found. Install tectonic/pdflatex or keep bin/tectonic."
        )

    binary = Path(engine[0]).name
    if binary == "tectonic":
        cmd = [
            engine[0],
            "-X",
            "compile",
            "--outdir",
            str(output_dir),
            str(tex_path),
        ]
    else:
        cmd = [
            engine[0],
            "-interaction=nonstopmode",
            f"-output-directory={output_dir}",
            str(tex_path),
        ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(output_dir),
    )
    pdf_path = output_dir / f"{tex_path.stem}.pdf"
    if result.returncode != 0 or not pdf_path.exists():
        details = (result.stdout or "")[-2000:] + "\n" + (result.stderr or "")[-2000:]
        raise RuntimeError(f"PDF compilation failed:\n{details}")
    return pdf_path
