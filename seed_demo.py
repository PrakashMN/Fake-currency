"""Seed the database with sample detections for an instant UI demo.

Run once after installing requirements:

    python seed_demo.py

The generated records are clearly marked as sample data. They exist only to
preview the dashboard/history/report flow.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw, ImageFont

from backend import database, reports
from backend.config import UPLOAD_DIR

SAMPLES = [
    ("500", "FAKE", 0.94, 0),
    ("2000", "REAL", 0.88, 1),
    ("100", "REAL", 0.82, 2),
    ("200", "FAKE", 0.77, 3),
    ("50", "REAL", 0.91, 5),
    ("20", "FAKE", 0.69, 6),
    ("10", "REAL", 0.85, 8),
]

PALETTES = {
    "10": ((120, 74, 42), (236, 214, 178)),
    "20": ((176, 58, 46), (250, 218, 197)),
    "50": ((84, 52, 110), (232, 218, 244)),
    "100": ((58, 84, 122), (219, 232, 246)),
    "200": ((180, 126, 26), (252, 239, 200)),
    "500": ((88, 60, 110), (235, 222, 244)),
    "2000": ((130, 40, 70), (248, 214, 224)),
}


def _font(size: int):
    for name in ("arial.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _make_sample_image(
    filename: str, denomination: str, result: str, index: int
) -> None:
    background, ink = PALETTES.get(denomination, ((60, 72, 100), (235, 240, 250)))
    width, height = 960, 420
    image = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        (24, 24, width - 24, height - 24), radius=26, outline=ink, width=5
    )
    draw.ellipse((60, 70, 330, 340), outline=ink, width=3)
    draw.ellipse((90, 100, 300, 310), outline=ink, width=2)

    draw.text((70, 52), "RESERVE BANK OF INDIA", font=_font(22), fill=ink)
    draw.text((360, 120), f"INR {denomination}", font=_font(82), fill=ink)
    draw.text((360, 235), "DEMO SAMPLE", font=_font(30), fill=ink)
    draw.text((360, 285), "PREVIEW DATA ONLY", font=_font(24), fill=ink)
    draw.text((70, 360), f"Sample image #{index + 1}", font=_font(18), fill=ink)

    image.save(UPLOAD_DIR / filename, "JPEG", quality=88)


def main() -> None:
    database.init_db()

    existing, _ = database.list_detections(limit=1000)
    if any(item["model_mode"] == "seeded" for item in existing):
        print("Sample data is already present. Nothing to do.")
        return

    now = datetime.now(timezone.utc)

    for index, (denomination, result, confidence, days_ago) in enumerate(SAMPLES):
        filename = f"sample_{denomination}_{index + 1}.jpg"
        _make_sample_image(filename, denomination, result, index)
        created_at = (
            now - timedelta(days=days_ago, hours=index * 3)
        ).isoformat(timespec="seconds")

        record = database.insert_detection(
            original_filename=f"sample_note_{denomination}.jpg",
            image_filename=filename,
            result=result,
            confidence=confidence,
            denomination=denomination,
            model_mode="seeded",
            created_at=created_at,
        )
        reports.create_report(record)
        print(
            f"Added sample #{record['id']:04d}: INR {denomination} "
            f"{result} ({confidence * 100:.0f}%)"
        )

    print(f"\nSeeded {len(SAMPLES)} sample detections and PDF reports.")


if __name__ == "__main__":
    main()
