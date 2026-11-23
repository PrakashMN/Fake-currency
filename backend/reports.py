"""Dependency-free PDF report generation for detection records.

The reports are intentionally simple: A4 pages, standard Helvetica fonts, and
plain text/rectangles. A tiny PDF writer is included so the project does not
need an extra third-party package just to create reports.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .config import REPORT_DIR

PAGE_WIDTH = 595
PAGE_HEIGHT = 842
MARGIN = 48
CONTENT_WIDTH = PAGE_WIDTH - (MARGIN * 2)


def report_path(detection_id: int) -> Path:
    return REPORT_DIR / f"report_{int(detection_id):04d}.pdf"


def _ascii(value) -> str:
    text = str(value) if value is not None else "-"
    return text.encode("ascii", "replace").decode("ascii")


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .replace("\r", " ")
        .replace("\n", " ")
    )


class SimplePDF:
    """Minimal single-font-family PDF writer (Helvetica / Helvetica-Bold)."""

    def __init__(self) -> None:
        self.pages: list[list[str]] = []
        self.add_page()

    def add_page(self) -> None:
        self.pages.append([])
        self.current = self.pages[-1]

    def text(
        self,
        x: float,
        top: float,
        content,
        size: float = 11,
        bold: bool = False,
        color: tuple[int, int, int] = (15, 23, 42),
    ) -> None:
        font = "F2" if bold else "F1"
        red, green, blue = color
        baseline = PAGE_HEIGHT - top - size
        self.current.append(
            f"BT /{font} {size:.2f} Tf "
            f"{red / 255:.3f} {green / 255:.3f} {blue / 255:.3f} rg "
            f"1 0 0 1 {x:.2f} {baseline:.2f} Tm "
            f"({_escape(_ascii(content))}) Tj ET"
        )

    def rect(
        self,
        x: float,
        top: float,
        width: float,
        height: float,
        color: tuple[int, int, int],
    ) -> None:
        red, green, blue = color
        bottom = PAGE_HEIGHT - top - height
        self.current.append(
            f"{red / 255:.3f} {green / 255:.3f} {blue / 255:.3f} rg "
            f"{x:.2f} {bottom:.2f} {width:.2f} {height:.2f} re f"
        )

    def line(
        self,
        x1: float,
        top1: float,
        x2: float,
        top2: float,
        color: tuple[int, int, int] = (226, 232, 240),
        width: float = 1,
    ) -> None:
        red, green, blue = color
        y1 = PAGE_HEIGHT - top1
        y2 = PAGE_HEIGHT - top2
        self.current.append(
            f"{red / 255:.3f} {green / 255:.3f} {blue / 255:.3f} RG "
            f"{width:.2f} w {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S"
        )

    @staticmethod
    def wrap(content, size: float, max_width: float) -> list[str]:
        text = " ".join(_ascii(content).split())
        if not text:
            return [""]

        approximate_char_width = size * 0.52
        max_chars = max(12, int(max_width / approximate_char_width))
        lines: list[str] = []
        current = ""

        for word in text.split():
            candidate = f"{current} {word}".strip()
            if len(candidate) <= max_chars or not current:
                current = candidate
            else:
                lines.append(current)
                current = word

        if current:
            lines.append(current)
        return lines or [""]

    def ensure(self, top: float, needed: float) -> float:
        if top + needed > PAGE_HEIGHT - 68:
            self.add_page()
            return MARGIN
        return top

    def paragraph(
        self,
        x: float,
        top: float,
        content,
        size: float = 9,
        color: tuple[int, int, int] = (71, 85, 105),
        max_width: float = CONTENT_WIDTH,
        line_height: float = 13,
    ) -> float:
        for line in self.wrap(content, size, max_width):
            top = self.ensure(top, line_height)
            self.text(x, top, line, size=size, color=color)
            top += line_height
        return top

    def to_bytes(self) -> bytes:
        page_ids: list[tuple[int, int]] = []
        next_id = 5
        for _ in self.pages:
            page_ids.append((next_id, next_id + 1))
            next_id += 2

        objects: dict[int, bytes] = {
            1: b"<< /Type /Catalog /Pages 2 0 R >>",
            3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            4: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        }

        kids = " ".join(f"{page_id} 0 R" for page_id, _ in page_ids)
        objects[2] = (
            f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>"
        ).encode("ascii")

        for (page_id, content_id), commands in zip(page_ids, self.pages):
            content = "\n".join(commands).encode("latin-1", "replace")
            objects[page_id] = (
                f"<< /Type /Page /Parent 2 0 R "
                f"/MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
                f"/Contents {content_id} 0 R >>"
            ).encode("ascii")
            objects[content_id] = (
                f"<< /Length {len(content)} >>\nstream\n".encode("ascii")
                + content
                + b"\nendstream"
            )

        max_id = max(objects)
        output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets: dict[int, int] = {}

        for object_id in range(1, max_id + 1):
            offsets[object_id] = len(output)
            output += f"{object_id} 0 obj\n".encode("ascii")
            output += objects[object_id]
            output += b"\nendobj\n"

        xref_position = len(output)
        output += f"xref\n0 {max_id + 1}\n".encode("ascii")
        output += b"0000000000 65535 f \n"
        for object_id in range(1, max_id + 1):
            output += f"{offsets[object_id]:010d} 00000 n \n".encode("ascii")

        output += (
            f"trailer\n<< /Size {max_id + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_position}\n%%EOF\n"
        ).encode("ascii")
        return bytes(output)

    def output(self, path: Path) -> None:
        path.write_bytes(self.to_bytes())


def create_report(record: dict) -> Path:
    pdf = SimplePDF()
    y = MARGIN

    pdf.text(
        MARGIN, y, "FAKE CURRENCY DETECTOR", size=9, bold=True, color=(180, 140, 40)
    )
    y += 15
    pdf.text(MARGIN, y, "Detection Report", size=22, bold=True, color=(15, 23, 42))
    y += 36

    result = str(record.get("result", "UNKNOWN")).upper()
    if result == "REAL":
        fill = (16, 185, 129)
    elif result == "FAKE":
        fill = (225, 29, 72)
    else:
        fill = (100, 116, 139)

    pdf.rect(MARGIN, y, CONTENT_WIDTH, 36, fill)
    pdf.text(MARGIN + 14, y + 10, result, size=16, bold=True, color=(255, 255, 255))
    y += 56

    confidence = float(record.get("confidence") or 0)
    denomination = record.get("denomination") or "unknown"
    denomination_text = (
        "Not specified" if denomination == "unknown" else f"INR {denomination}"
    )
    original_filename = _ascii(record.get("original_filename", "-"))
    if len(original_filename) > 64:
        original_filename = original_filename[:61] + "..."

    rows = [
        ("Report ID", f"#{int(record.get('id', 0)):04d}"),
        ("Generated", datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")),
        ("Detection time", record.get("created_at", "-")),
        ("Original file", original_filename),
        ("Denomination", denomination_text),
        ("Confidence", f"{confidence * 100:.1f}%"),
        ("Model mode", record.get("model_mode", "demo")),
    ]

    for label, value in rows:
        y = pdf.ensure(y, 24)
        pdf.text(
            MARGIN, y, label.upper(), size=8.5, bold=True, color=(100, 116, 139)
        )
        pdf.text(MARGIN + 120, y, value, size=10.5, color=(15, 23, 42))
        pdf.line(
            MARGIN,
            y + 17,
            PAGE_WIDTH - MARGIN,
            y + 17,
            color=(241, 245, 249),
        )
        y += 24

    y += 10

    mode = record.get("model_mode")
    if mode == "demo":
        warning = (
            "DEMO MODE: No trained model was found. This result is simulated "
            "for testing the application flow and is not a genuine "
            "authenticity assessment."
        )
    elif mode == "seeded":
        warning = (
            "SAMPLE DATA: This report was generated from seeded demo data for "
            "interface preview purposes. It does not represent a real scan."
        )
    else:
        warning = None

    if warning:
        lines = pdf.wrap(warning, 9, CONTENT_WIDTH - 24)
        box_height = (len(lines) * 13) + 16
        y = pdf.ensure(y, box_height + 16)
        pdf.rect(MARGIN, y, CONTENT_WIDTH, box_height, (254, 243, 199))
        text_y = y + 8
        for line in lines:
            pdf.text(MARGIN + 12, text_y, line, size=9, color=(146, 64, 14))
            text_y += 13
        y += box_height + 18

    y = pdf.ensure(y, 80)
    pdf.text(MARGIN, y, "IMPORTANT", size=9, bold=True, color=(100, 116, 139))
    y += 15
    pdf.paragraph(
        MARGIN,
        y,
        "This report is generated by an educational computer-vision project. "
        "It is not a legal or forensic verification of currency authenticity. "
        "Always refer suspected counterfeit notes to a bank or the police.",
        size=9,
        color=(71, 85, 105),
        line_height=13,
    )

    footer_top = PAGE_HEIGHT - 48
    pdf.line(
        MARGIN,
        footer_top - 10,
        PAGE_WIDTH - MARGIN,
        footer_top - 10,
        color=(226, 232, 240),
    )
    pdf.text(
        MARGIN,
        footer_top,
        "Fake Currency Detector - educational project. Not a legal verification.",
        size=8,
        color=(148, 163, 184),
    )

    path = report_path(int(record["id"]))
    pdf.output(path)
    return path
