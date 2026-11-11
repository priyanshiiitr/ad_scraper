"""Build the checked-in pull from a saved Ad Library text dump."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_library_markdown import parse_dump

OPENS = {
    "1112422725088441": {
        "headline": "MySivi Se Shuru Karo – Sirf ₹1 Mein Install Now",
        "cta_text": "Install Now",
        "link_url": "https://play.google.com/store/apps/details?id=com.practice.ninja_study",
        "page_url": "https://www.facebook.com/61584601834661/",
    },
    "1109916984937035": {
        "headline": "English கத்துக்க ₹1 இருந்தா போதும் Install Now",
        "cta_text": "Install Now",
        "link_url": "https://play.google.com/store/apps/details?id=com.practice.ninja_study",
        "page_url": "https://www.facebook.com/61590073214459/",
    },
    "2966208700429750": {
        "headline": "MySivi सोबत सुरुवात करा – केवळ ₹1 मध्ये Install Now",
        "cta_text": "Install Now",
        "link_url": "https://play.google.com/store/apps/details?id=com.practice.ninja_study",
        "page_url": "https://www.facebook.com/my.siviai/",
    },
    "1440471367921700": {
        "headline": "₹1 theke English start korun Install Now",
        "cta_text": "Install Now",
        "link_url": "https://play.google.com/store/apps/details?id=com.practice.ninja_study",
        "page_url": "https://www.facebook.com/61584601834661/",
    },
    "1022434796890840": {
        "headline": "English ಕಲಿಯುವುದು ಈಗ ಸುಲಭ Install Now",
        "cta_text": "Install Now",
        "link_url": "https://play.google.com/store/apps/details?id=com.practice.ninja_study",
    },
    "1843111363320189": {
        "headline": "English ಕಲಿಯುವುದು ಈಗ ಸುಲಭ Install Now",
        "cta_text": "Install Now",
        "link_url": "https://play.google.com/store/apps/details?id=com.practice.ninja_study",
    },
    "1461355659421928": {
        "headline": "MySivi తో ఇంగ్లీష్ నేర్చుకోండి - కేవలం ₹1 కి Install Now",
        "cta_text": "Install Now",
        "link_url": "https://play.google.com/store/apps/details?id=com.practice.ninja_study",
    },
}

PW_ID = "1800149651432201"
PW_TEXT = "PhysicsWallah’s PW Talk brings 24x7 English learning at a special price. Get 80% off"
PW_PAGE = "https://www.facebook.com/61591451905204/"

SOURCE_URL = (
    "https://www.facebook.com/ads/library/?active_status=active&ad_type=all"
    "&country=IN&is_targeted_country=false&media_type=all&q=%22MySivi%22"
    "&search_type=keyword_exact_phrase&sort_data[direction]=desc"
    "&sort_data[mode]=total_impressions"
)


def build(markdown_path: Path) -> dict:
    ads = parse_dump(markdown_path.read_text(encoding="utf-8"))
    for ad in ads:
        opened = OPENS.get(ad["library_id"])
        if opened:
            ad.update(opened)
            ad["text_from"] = "search_card"
            ad["headline_from"] = "detail_page"
        if ad["library_id"] == PW_ID:
            ad["search_card_text"] = ad["primary_text"]
            ad["primary_text"] = PW_TEXT
            ad["text_from"] = "detail_page"
            ad["page_url"] = PW_PAGE
        ad.setdefault("text_from", "search_card")
    return {
        "pulled_on": "2026-11-11",
        "country": "IN",
        "active_status": "active",
        "query": '"MySivi"',
        "search_type": "keyword_exact_phrase",
        "sort": "total_impressions_desc",
        "source_url": SOURCE_URL,
        "play_store_id": "com.practice.ninja_study",
        "note": (
            "Thirty cards from the first view of the assignment URL. "
            "Order is the order the library returned under that sort. "
            "The impression number itself is not shown for these ads. "
            "Headlines and the Install Now button were read on the detail "
            "view of the cards listed in headline_from, not on every card."
        ),
        "ads": ads,
    }


def main() -> None:
    src = Path(sys.argv[1])
    dest = Path(sys.argv[2])
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(build(src), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(dest, "ads", len(json.loads(dest.read_text())["ads"]))


if __name__ == "__main__":
    main()
