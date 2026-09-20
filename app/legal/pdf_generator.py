"""
pdf_generator.py – Jinja2 + WeasyPrint PDF renderer for FIRs and legal notices.
"""
from __future__ import annotations

from pathlib import Path
from uuid import UUID

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR = Path("/tmp/chainsleuth/pdfs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


async def render_pdf(template_name: str, context: dict, output_filename: str) -> Path:
    """
    Render *template_name* with *context* and write a PDF to disk.

    Returns the path to the generated PDF file.
    """
    try:
        from weasyprint import HTML
    except ImportError as exc:
        raise RuntimeError("WeasyPrint is not installed. Add it to requirements.txt.") from exc

    template = _jinja_env.get_template(template_name)
    html_content = template.render(**context)

    output_path = OUTPUT_DIR / output_filename
    HTML(string=html_content).write_pdf(str(output_path))
    return output_path


async def generate_fir_pdf(fir_data: dict, fir_id: UUID) -> Path:
    """Generate a FIR PDF and return its path."""
    return await render_pdf(
        template_name="fir.html",
        context=fir_data,
        output_filename=f"FIR_{fir_id}.pdf",
    )


async def generate_notice_pdf(notice_data: dict, notice_id: UUID) -> Path:
    """Generate a legal notice PDF and return its path."""
    return await render_pdf(
        template_name="notice.html",
        context=notice_data,
        output_filename=f"NOTICE_{notice_id}.pdf",
    )
