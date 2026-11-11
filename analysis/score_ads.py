"""Score MySivi Ad Library cards without inventing spend or CTR.

"Best" is the creative with the strongest public evidence that the account
is already scaling it. The library, for a commercial ad in India, does not
show impressions, spend, or CTR. It does show sort order, start date, and
repeated primary text. Those are the only inputs to the score.

Points, out of 100:

- delivery, max 30: best (lowest) position in this impressions-sorted page
- survival, max 25: most days any live copy of that text has been running
- repetition, max 15: how many cards in the pull share the text
  (or collation_count, when the scraper provides it, whichever is larger)
- offer, max 15: the primary text contains a ₹1 price
- specificity, max 15: a daily time, a proof number, or a named language

A model is not allowed to choose the winner. A later step may add a delta
between -8 and +8, and only if its reason quotes the primary text.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime

REGIONAL = re.compile(r"[\u0900-\u0D7F]")
NAMED_LANGUAGE = re.compile(r"\b(bangla|kannada|tamil|telugu|marathi|hindi)\b", re.I)
RUPEE_ONE = re.compile(r"(?:₹|rs\.?)\s*1(?!\d)", re.I)
TIME_15 = re.compile(r"15\s*(?:minute|min|ನಿಮಿಷ)", re.I)
PROOF_40 = re.compile(r"40")
PROOF_LAKH = re.compile(r"லட்ச|lakh", re.I)


def parse_day(value: str) -> date:
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def days_live(started_on: str, as_of: date) -> int:
    return (as_of - parse_day(started_on)).days


def normalize_copy(text: str) -> str:
    kept = []
    for ch in text or "":
        if ch in {"\ufe0f", "\u200d"}:
            continue
        if unicodedata.category(ch) in {"So", "Sk", "Cn"}:
            continue
        kept.append(ch)
    return re.sub(r"\s+", " ", "".join(kept)).strip().casefold()


def is_competitor(ad: dict) -> bool:
    name = (ad.get("page_name") or "").casefold()
    text = (ad.get("primary_text") or "").casefold()
    return "pw talk" in name or "physicswallah" in text


def has_rupee_one(text: str) -> bool:
    return RUPEE_ONE.search(text or "") is not None


def specificity(text: str) -> int:
    score = 0
    if TIME_15.search(text or ""):
        score += 6
    if PROOF_40.search(text or "") and PROOF_LAKH.search(text or ""):
        score += 6
    if REGIONAL.search(text or "") or NAMED_LANGUAGE.search(text or ""):
        score += 3
    return min(15, score)


def survival_points(days: int) -> int:
    if days >= 180:
        return 25
    if days >= 120:
        return 21
    if days >= 90:
        return 17
    if days >= 60:
        return 13
    if days >= 30:
        return 8
    if days >= 14:
        return 4
    return 1


def repetition_points(count: int) -> int:
    if count >= 8:
        return 15
    if count >= 5:
        return 12
    if count >= 3:
        return 8
    if count >= 2:
        return 4
    return 1


def delivery_points(best_position: int, n_cards: int) -> int:
    if n_cards <= 1:
        return 30
    raw = round(30 * (n_cards - best_position) / (n_cards - 1))
    return max(0, raw)


def rank_span(ads: list[dict], declared: int | None = None) -> int:
    """Scale delivery against the original sort, not the rows left after a filter.

    A live scrape can drop a card with no text and keep a later position.
    Using the filtered length as the denominator makes that position negative.
    """
    positions = []
    for index, ad in enumerate(ads, start=1):
        position = ad.get("position")
        positions.append(int(position) if position else index)
    return max([len(ads), declared or 0, *positions, 1])


def repetition_count(members: list[dict]) -> int:
    rows = len(members)
    collations = [int(m["collation_count"]) for m in members if m.get("collation_count")]
    coll = max(collations) if collations else 0
    return max(rows, coll)


def score_creatives(ads: list[dict], as_of: date, rank_span_override: int | None = None) -> list[dict]:
    n_cards = rank_span(ads, rank_span_override)
    groups: dict[str, list[dict]] = defaultdict(list)
    for index, ad in enumerate(ads, start=1):
        if is_competitor(ad) or not (ad.get("primary_text") or "").strip():
            continue
        if not ad.get("position"):
            ad = {**ad, "position": index}
        groups[normalize_copy(ad["primary_text"])].append(ad)

    creatives = []
    for key, members in groups.items():
        rep = min(members, key=lambda m: m["position"])
        oldest = min(members, key=lambda m: (m["started_on"], m["position"]))
        text = rep["primary_text"]
        max_days = max(days_live(m["started_on"], as_of) for m in members)
        copies = repetition_count(members)
        parts = {
            "delivery": delivery_points(rep["position"], n_cards),
            "survival": survival_points(max_days),
            "repetition": repetition_points(copies),
            "offer": 15 if has_rupee_one(text) else 0,
            "specificity": specificity(text),
        }
        creatives.append(
            {
                "copy_key": key,
                "primary_text": text,
                "score": sum(parts.values()),
                "parts": parts,
                "best_position": rep["position"],
                "representative_id": rep["library_id"],
                "oldest_id": oldest["library_id"],
                "oldest_started_on": oldest["started_on"],
                "max_days": max_days,
                "copies": copies,
                "library_ids": [m["library_id"] for m in sorted(members, key=lambda m: m["position"])],
                "pages": sorted({m.get("page_name") or "" for m in members}),
                "headline_has_rupee": any(has_rupee_one(m.get("headline") or "") for m in members),
            }
        )
    creatives.sort(key=lambda c: (-c["score"], c["best_position"], -c["max_days"]))
    return creatives


def apply_deltas(creatives: list[dict], deltas: list[dict]) -> list[dict]:
    """Clamp a model delta. A reason that does not quote the ad scores 0."""
    by_id = {item.get("creative_id"): item for item in deltas}
    adjusted = []
    for creative in creatives:
        proposal = by_id.get(creative["representative_id"]) or by_id.get(creative["copy_key"]) or {}
        try:
            raw = int(proposal.get("score_delta", 0))
        except (TypeError, ValueError):
            raw = 0
        quote = (proposal.get("quote") or "").strip()
        quoted = bool(quote) and quote.casefold() in creative["primary_text"].casefold()
        delta = max(-8, min(8, raw)) if quoted else 0
        adjusted.append(
            {
                **creative,
                "model_delta": delta,
                "model_reason": (proposal.get("delta_reason") or "") if delta else "",
                "final_score": max(0, min(100, creative["score"] + delta)),
            }
        )
    adjusted.sort(key=lambda c: (-c["final_score"], c["best_position"], -c["max_days"]))
    return adjusted
