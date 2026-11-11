"""Turn a saved Meta Ad Library text dump into ad records.

The dump is the public library page for the assignment URL, read on
11 Nov 2026. Image CDN links are dropped on purpose: they carry expiring
tokens and are not needed to score copy.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

MONTHS = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}


def parse_started(text: str) -> str | None:
    match = re.search(r"Started running on ([A-Z][a-z]{2}) (\d{1,2}), (\d{4})", text)
    if not match:
        return None
    month, day, year = match.group(1), int(match.group(2)), int(match.group(3))
    return f"{year:04d}-{MONTHS[month]:02d}-{day:02d}"


def parse_dump(markdown: str) -> list[dict]:
    parts = re.split(r"Library ID:\s*", markdown)
    ads = []
    for part in parts[1:]:
        id_match = re.match(r"(\d+)", part)
        if not id_match:
            continue
        library_id = id_match.group(1)
        alt = re.search(r"!\[[^\]]*?:\s*([^\]]+)\]\([^)]+\)", part)
        page_name = alt.group(1).strip() if alt else ""
        # Primary text sits between the page image and the video-error line,
        # or, for a still ad, between the image and the next library card.
        after_image = re.split(r"!\[[^\]]+\]\([^)]+\)", part, maxsplit=1)
        body_zone = after_image[1] if len(after_image) > 1 else ""
        body_zone = body_zone.split("Sorry, we're having trouble playing this video.")[0]
        body_zone = re.split(r"\n\s*Active\s*\n", body_zone)[0]
        lines = []
        for line in body_zone.splitlines():
            stripped = line.strip()
            if not stripped or stripped == "​":
                continue
            if stripped.startswith("![") or stripped.startswith("http"):
                continue
            if stripped in {"*", "**Sponsored**"}:
                continue
            lines.append(stripped)
        primary = "\n".join(lines).strip()
        ads.append(
            {
                "library_id": library_id,
                "position": len(ads) + 1,
                "started_on": parse_started(part),
                "page_name": page_name,
                "primary_text": primary,
                "is_video": "trouble playing this video" in part,
                "multiple_versions": "This ad has multiple versions" in part,
                "is_active": True,
            }
        )
    return ads


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("markdown")
    parser.add_argument("out")
    args = parser.parse_args()
    ads = parse_dump(Path(args.markdown).read_text(encoding="utf-8"))
    payload = {
        "pulled_on": "2026-11-11",
        "source_url": (
            "https://www.facebook.com/ads/library/?active_status=active&ad_type=all"
            "&country=IN&is_targeted_country=false&media_type=all&q=%22MySivi%22"
            "&search_type=keyword_exact_phrase&sort_data[direction]=desc"
            "&sort_data[mode]=total_impressions"
        ),
        "note": (
            "First page of the assignment URL, active ads in India, exact phrase "
            "MySivi, sorted by total impressions descending. Order is the order "
            "the library returned. Impression counts are not shown for these ads."
        ),
        "ads": ads,
    }
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(ads)} ads")


if __name__ == "__main__":
    main()
