"""Render the submission PDF from the scored pull. Numbers come from the scorer."""

from __future__ import annotations

import html
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_ads import has_rupee_one, score_creatives
from score_ads import parse_day

ROOT = Path(__file__).resolve().parents[1]
PULL = ROOT / "data" / "pull_2026-11-11.json"
HTML_OUT = ROOT / "submission" / "report.html"

# Readings are mine, so a reviewer can follow a language I don't expect them
# to read on a clock. The ad text above each reading is the source.
READINGS = {
    "english": {
        "name": "English, ₹1, emoji",
        "hook_reading": "Speak English fluently with the power of AI!",
        "body_reading": "Try MySivi for real progress. Start your trial now at just ₹1.",
        "headline_reading": "Start with MySivi, for just ₹1. Install now.",
    },
    "kannada": {
        "name": "Kannada, 15 minutes",
        "hook_reading": "The AI teacher teaches you English in Kannada.",
        "body_reading": "Practice on the MySivi app whenever you want, wherever you are. Practice 15 minutes a day and learn English properly.",
        "headline_reading": "Learning English is easy now. Install now.",
    },
    "bangla": {
        "name": "Bangla, 15 minutes",
        "hook_reading": "The AI teacher will explain English to you in Bangla.",
        "body_reading": "You can practice on the MySivi app anytime. Just 15 minutes a day and you can speak English easily.",
        "headline_reading": "Start English from ₹1. Install now.",
    },
    "tamil": {
        "name": "Tamil, proof and price",
        "hook_reading": "Get a strong spoken-English AI teacher for just ₹1.",
        "body_reading": "More than 40 lakh people are already learning English on MySivi. Build your spoken English by talking to real people. Download it and start.",
        "headline_reading": "₹1 is enough to learn English. Install now.",
    },
    "marathi": {
        "name": "Marathi, ₹1 trial",
        "hook_reading": "Learn it smartly, without the grind.",
        "body_reading": "Practice speaking real English with MySivi AI. Start the trial today for ₹1 and build your confidence.",
        "headline_reading": "Start with MySivi, in just ₹1. Install now.",
    },
    "telugu": {
        "name": "Telugu, ₹1 trial",
        "hook_reading": "Learning English has become this easy now.",
        "body_reading": "Speak well anytime, anywhere, with AI’s help. Try it now for ₹1.",
        "headline_reading": "Learn English with MySivi, for just ₹1. Install now.",
    },
}


def family(text: str) -> str:
    if any("\u0c80" <= ch <= "\u0cff" for ch in text):
        return "kannada"
    if any("\u0b80" <= ch <= "\u0bff" for ch in text):
        return "tamil"
    if any("\u0c00" <= ch <= "\u0c7f" for ch in text):
        return "telugu"
    if any("\u0900" <= ch <= "\u097f" for ch in text):
        return "marathi"
    if "bangla" in text.casefold():
        return "bangla"
    if "speak english fluently" in text.casefold():
        return "english"
    return "other"


def split_copy(text: str) -> tuple[str, str, str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    tags = [line for line in lines if line.startswith("#") or (line.count("#") >= 2 and len(line) < 90)]
    main = [line for line in lines if line not in tags]
    blob = " ".join(main)
    import re

    parts = re.split(r"(?<=[!?।])\s+|(?<=\.)\s+", blob, maxsplit=1)
    hook = parts[0].strip()
    body = parts[1].strip() if len(parts) > 1 else ""
    return hook, body, " ".join(tags)


def human(iso: str) -> str:
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%-d %b %Y")


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def ad_link(library_id: str) -> str:
    return f"https://www.facebook.com/ads/library/?id={library_id}"


def main() -> None:
    pull = json.loads(PULL.read_text(encoding="utf-8"))
    as_of = parse_day(pull["pulled_on"])
    ads = pull["ads"]
    creatives = score_creatives(ads, as_of)
    if len(creatives) != 6:
        raise SystemExit(f"expected 6 creatives, got {len(creatives)}")
    winner = creatives[0]
    if family(winner["primary_text"]) != "english" or winner["score"] != 85:
        raise SystemExit(f"unexpected winner {winner['representative_id']} {winner['score']}")

    by_id = {ad["library_id"]: ad for ad in ads}
    ranked = []
    for creative in creatives:
        key = family(creative["primary_text"])
        reading = READINGS[key]
        hook, body, tags = split_copy(creative["primary_text"])
        rep = by_id[creative["representative_id"]]
        oldest = by_id[creative["oldest_id"]]
        headline_ad = next(
            (by_id[library_id] for library_id in creative["library_ids"] if by_id[library_id].get("headline")),
            None,
        )
        extra = 15 if creative["headline_has_rupee"] and creative["parts"]["offer"] == 0 else 0
        ranked.append(
            {
                **creative,
                "key": key,
                "reading": reading,
                "hook": hook,
                "body": body,
                "tags": tags,
                "rep": rep,
                "oldest": oldest,
                "headline_ad": headline_ad,
                "sensitive_score": creative["score"] + extra,
            }
        )

    # Bangla is the only creative whose headline carries ₹1 while the primary text does not.
    sensitive = sorted(ranked, key=lambda row: (-row["sensitive_score"], row["best_position"]))
    if sensitive[0]["key"] != "english":
        raise SystemExit("sensitivity check changed the winner; rewrite the lead before shipping")

    HTML_OUT.write_text(render(pull, ads, ranked, sensitive), encoding="utf-8")
    print(HTML_OUT)


def render(pull: dict, ads: list[dict], ranked: list[dict], sensitive: list[dict]) -> str:
    by_id = {ad["library_id"]: ad for ad in ads}
    winner = ranked[0]
    kannada = next(row for row in ranked if row["key"] == "kannada")
    bangla = next(row for row in ranked if row["key"] == "bangla")
    tamil = next(row for row in ranked if row["key"] == "tamil")
    marathi = next(row for row in ranked if row["key"] == "marathi")
    telugu = next(row for row in ranked if row["key"] == "telugu")
    pw = next(ad for ad in ads if "pw talk" in ad["page_name"].casefold())
    pw_days = (parse_day(pull["pulled_on"]) - parse_day(pw["started_on"])).days
    kannada_newest = max((by_id[library_id] for library_id in kannada["library_ids"]), key=lambda ad: ad["started_on"])
    kannada_newest_days = (parse_day(pull["pulled_on"]) - parse_day(kannada_newest["started_on"])).days
    winner_days = (parse_day(pull["pulled_on"]) - parse_day(winner["rep"]["started_on"])).days

    def score_row(row: dict) -> str:
        parts = row["parts"]
        return (
            "<tr>"
            f"<td>{esc(row['reading']['name'])}</td>"
            f"<td class='num'>{row['score']}</td>"
            f"<td class='num'>{parts['delivery']}</td>"
            f"<td class='num'>{parts['survival']}</td>"
            f"<td class='num'>{parts['repetition']}</td>"
            f"<td class='num'>{parts['offer']}</td>"
            f"<td class='num'>{parts['specificity']}</td>"
            f"<td class='num'>{row['sensitive_score']}</td>"
            "</tr>"
        )

    cards = []
    for ad in ads:
        text = ad.get("search_card_text", ad["primary_text"]) if ad.get("text_from") == "detail_page" and not ad["primary_text"] else ad["primary_text"]
        # PW text is stored in primary_text. Family label uses page name first.
        if "pw talk" in ad["page_name"].casefold():
            label = "PW Talk, not ranked"
        else:
            label = READINGS[family(ad["primary_text"])]["name"]
        days = (parse_day(pull["pulled_on"]) - parse_day(ad["started_on"])).days
        cards.append(
            "<tr>"
            f"<td class='num'>{ad['position']}</td>"
            f"<td><a href='{esc(ad_link(ad['library_id']))}'>{esc(ad['library_id'])}</a></td>"
            f"<td>{esc(human(ad['started_on']))}</td>"
            f"<td class='num'>{days}</td>"
            f"<td>{esc(ad['page_name'])}</td>"
            f"<td>{esc(label)}</td>"
            "</tr>"
        )

    creative_blocks = "\n".join(creative_block(row, index) for index, row in enumerate(ranked, start=1))
    sensitive_line = ", ".join(f"{row['reading']['name'].split(',')[0]} {row['sensitive_score']}" for row in sensitive)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Which MySivi ad is the control</title>
<style>
  @page {{ size: A4; margin: 14mm 14mm 16mm; }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{
    font-family: "Noto Sans", "Noto Sans Devanagari", "Noto Sans Kannada", "Noto Sans Tamil", "Noto Sans Telugu", "Noto Sans Bengali", sans-serif;
    color: #1c1917;
    font-size: 10.5pt;
    line-height: 1.42;
    background: white;
  }}
  main {{ max-width: 182mm; margin: 0 auto; padding: 0; }}
  h1 {{ font-size: 20pt; line-height: 1.15; margin: 0 0 4px; letter-spacing: -0.02em; }}
  h2 {{ font-size: 13pt; margin: 18px 0 6px; letter-spacing: -0.01em; }}
  h3 {{ font-size: 11.5pt; margin: 12px 0 4px; }}
  p {{ margin: 0 0 8px; }}
  a {{ color: #1c1917; }}
  .byline {{ color: #57534e; margin-bottom: 12px; }}
  .decision {{
    border: 1.5px solid #1c1917;
    padding: 10px 12px 8px;
    margin: 8px 0 12px;
  }}
  .decision .id {{ font-size: 13pt; font-weight: 700; margin: 0 0 4px; }}
  .meta {{ color: #44403c; }}
  table {{ width: 100%; border-collapse: collapse; margin: 6px 0 10px; font-size: 9.5pt; }}
  th, td {{ text-align: left; vertical-align: top; padding: 4px 6px; border-bottom: 1px solid #e7e5e4; }}
  th {{ font-size: 8.5pt; letter-spacing: 0.03em; text-transform: uppercase; color: #57534e; font-weight: 600; }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .copy {{ white-space: pre-wrap; background: #fafaf9; padding: 8px 10px; margin: 4px 0 6px; }}
  .reading {{ color: #44403c; }}
  ol {{ margin: 4px 0 8px; padding-left: 18px; }}
  li {{ margin: 0 0 6px; }}
  .small {{ font-size: 9.5pt; color: #44403c; }}
  code {{ font-family: "Noto Sans Mono", ui-monospace, monospace; font-size: 9pt; }}
</style>
</head>
<body>
<main>
  <p class="byline">Priyansh Agarwal · MySivi growth internship · 11 Nov 2026</p>
  <h1>Which MySivi ad is the control</h1>
  <p>Active ads in India for the exact phrase “MySivi”, sorted by total impressions. Thirty cards. Six primary texts. One of them is already the ad the account is scaling, and it is not the best written ad on the page.</p>

  <div class="decision">
    <p class="id">Best ad in this list: library ID {esc(winner['representative_id'])}</p>
    <p class="meta">{esc(winner['rep']['page_name'])}. Started {esc(human(winner['rep']['started_on']))} ({winner_days} days). Video. Score {winner['score']}/100.</p>
    <p><strong>Hook.</strong> {esc(winner['hook'])}</p>
    <p><strong>Body.</strong> {esc(winner['body'])} {esc(winner['tags'])}</p>
    <p><strong>Headline.</strong> {esc(winner['headline_ad']['headline'])}</p>
    <p><strong>CTA.</strong> Install Now, to Google Play <code>{esc(pull['play_store_id'])}</code>.</p>
    <p class="small"><a href="{esc(ad_link(winner['representative_id']))}">{esc(ad_link(winner['representative_id']))}</a></p>
  </div>

  <p>Same primary text is on {winner['copies']} of the 30 cards, including library ID {esc(winner['oldest_id'])}, still running since {esc(human(winner['oldest_started_on']))} ({winner['max_days']} days). That older card is the survival evidence. The card at position 1 is the one this sort put first. I am naming the position-1 card as the best ad, and the sentence as the control.</p>

  <h2>What “best” means</h2>
  <p>Not the line I would brief next. The ad with the strongest public evidence that MySivi is already spending behind it.</p>
  <p>For a commercial ad in India, the Ad Library does not show spend, CTR, or the impression count. Meta’s own help page says you can search ads that are currently active, and that spend, funding, and demographic reach are shown for ads about issues, elections, or politics. Ads delivered in the EU carry a separate transparency total. An India query does not. The URL sorts by total impressions, and the number never arrives. Position in that sort is a rank. I treated it as a rank.</p>
  <p>Anyone who writes “this ad has 2.4 million impressions” made the number up. I did not call a model to pick the winner. The rank below is arithmetic. Gemini is in the workflow as a translator, with a score nudge capped at 8 points, and only if it quotes a phrase that is already in the ad. This PDF is the run with that nudge turned off, so you can recompute every cell.</p>

  <table>
    <thead>
      <tr>
        <th>Creative</th>
        <th class="num">Score</th>
        <th class="num">Delivery 30</th>
        <th class="num">Survival 25</th>
        <th class="num">Copies 15</th>
        <th class="num">₹1 in text 15</th>
        <th class="num">Specific 15</th>
        <th class="num">If headline ₹1 counts</th>
      </tr>
    </thead>
    <tbody>
      {''.join(score_row(row) for row in ranked)}
    </tbody>
  </table>
  <p class="small">Delivery is 30 at position 1 and 0 at position 30, linear. Survival is 25 at 180 days or more, 21 at 120, 17 at 90, 13 at 60, 8 at 30, 4 at 14, else 1. Copies are 15 at 8 or more cards, 12 at 5, 8 at 3, 4 at 2, else 1. Specificity is 6 for a “15 minutes” line, 6 for a proof number, 3 for a language other than generic English, capped at 15. The last column gives 15 extra points when the primary text has no ₹1 but a headline I opened does. Order under that check: {esc(sensitive_line)}. The winner does not move. Bangla passes Kannada and becomes the runner-up. I am not using that column as the official score, because I opened one headline per creative, not every card.</p>

  <h2>The six creatives</h2>
  <p>Thirty cards is the wrong unit. Ranking them one by one would crown the same English sentence eleven times and call it a finding. These are the sentences.</p>
  {creative_blocks}

  <h2>What I would do on Monday</h2>
  <p>Hold the English ad as the control. Do not brief another “speak English fluently with the power of AI”. The account already has {winner['copies']} live copies, and one of them has survived since April. A new adjective on that hook will not move CAC.</p>
  <ol>
    <li>Put library ID {esc(winner['representative_id'])} in the buyer’s sheet as the named control. Same headline, same Install Now, same Play listing.</li>
    <li>Brief one Kannada test, not a new concept. Kannada is the runner-up on the official score ({kannada['score']}) and the copy they are still launching: library ID {esc(kannada_newest['library_id'])} started {esc(human(kannada_newest['started_on']))}, {kannada_newest_days} days before this pull, with the same text as the {esc(human(kannada['oldest_started_on']))} ad. The primary text and the two headlines I opened never say ₹1. Give the Kannada writer this English line and let them write it, rather than shipping a machine translation: “40 lakh people already learn English on MySivi. Start today for ₹1. The teacher explains it in Kannada. 15 minutes a day.” Keep the 15 minutes and the mother tongue. Change the opening. Do not pause the {kannada_newest_days}-day-old ID. It has no read yet.</li>
    <li>On the Bangla primary text, move the headline into the first line. The 10 August card already says “₹1 theke English start korun” under the video. The primary text, which is what a lot of people read before that, does not mention the price. That is a one-line edit on a creative with {bangla['copies']} live cards and {bangla['max_days']} days of survival.</li>
    <li>Leave the Marathi ads on. Two cards, both started {esc(human(marathi['oldest_started_on']))}, best position {marathi['best_position']}. The line is specific, and the ₹1 is in the primary text as well as the headline. It does not have a 60-day read in this pull. An Airbridge teardown dated 19 October, from a 16 October library pull, said a Marathi ₹1 line was on 7 of their top 12 and that the longest ad had been live about 190 days. I do not see that older Marathi set at the top of this sort. Ask the buyer whether those ads were paused. If they were, the October note is stale and the English emoji line has taken the delivery.</li>
    <li>Open library ID {esc(pw['library_id'])} before the next scrape. It is {esc(pw['page_name'])}, running since {esc(human(pw['started_on']))} ({pw_days} days). The search card did not show a primary text. The detail view says: “{esc(pw['primary_text'])}”. There is no MySivi in that sentence, inside an exact-phrase MySivi search. Either the video names MySivi, or the match is loose. It is PhysicsWallah’s English app, at a discount. It is not a MySivi ad and it is not in the score. It is the thing I would check before I scrape this URL again.</li>
    <li>Do not transcribe all 30 videos to answer this question. Six primary texts cover the page. Transcribe the one video you are about to shoot against, when the test needs it. The workflow leaves that as a later node, not as a bill on the free tier today.</li>
  </ol>
  <p>Tamil is the best written primary text in the set and the fourth score ({tamil['score']}), because it sits at position {tamil['best_position']} with {tamil['copies']} cards and {tamil['max_days']} days. Price, then 40 lakh, then “talk to real people”, then download. That structure is what the Kannada test above is borrowing. I would not call Tamil the best ad. The sort does not support it. Telugu is one card at position {telugu['best_position']}, {telugu['max_days']} days, price in the text and in the headline. Too thin to be a control.</p>

  <h2>Every card</h2>
  <p class="small">Position is the order the library returned. Days are counted to 11 Nov 2026. All MySivi cards were videos. “Multiple versions” was on every card, so I did not score it. Platform icons did not come through as text, so I am not claiming a Facebook versus Instagram split.</p>
  <table>
    <thead>
      <tr><th class="num">#</th><th>Library ID</th><th>Started</th><th class="num">Days</th><th>Page</th><th>Creative</th></tr>
    </thead>
    <tbody>
      {''.join(cards)}
    </tbody>
  </table>
  <p class="small">The brand is not one Facebook page. Marathi is on <a href="https://www.facebook.com/my.siviai/">facebook.com/my.siviai</a>. The Tamil card I opened is on a page called MySivi AI. English, Bangla, and the older Kannada cards are on MySivi Spoken English App. A scrape of a single page URL would have dropped either the control or the Tamil script. The assignment URL, a keyword search, is the right input. Keep it.</p>

  <h2>The workflow, and what it costs</h2>
  <p>The file to import is <code>workflow/mysivi_ad_library.json</code>. It is not the public n8n template that transcribes Facebook videos into a Google Sheet. That template is a scrape. The question on the brief is which ad is best, and a sheet does not answer it. This one scores in a Code node before a model is allowed to speak.</p>
  <p>Config holds the assignment URL, how many ads to pull, the as-of date, and two paste fields: an Apify token and a Gemini key. Mode <code>sample</code> scores the 11 November pull stored in the workflow, which is this PDF. Mode <code>apify</code> runs <code>curious_coder/facebook-ads-library-scraper</code>, polls the run, and scores whatever comes back. Same function either way. The Python file and the Code node were checked against each other on this pull. They return the same six scores.</p>
  <p>If the Gemini key is still the placeholder, the model is skipped and the rank stands. If a key is present, one call to <code>gemini-2.5-flash-lite</code> translates the set and may propose a delta from −8 to +8. The code keeps the delta only when the model quotes a phrase that is already in the primary text, and it clamps anything outside that range. A confident paragraph with no quote scores zero. That is the whole point of putting the model second.</p>
  <p>I looked up the prices rather than guessing a “free stack”.</p>
  <ul>
    <li>Apify lists this actor at $0.75 per 1,000 dataset items. Twelve ads is under one US cent of actor fees. The workflow asks for 1 GB of memory, turns off EU ad-detail scraping (those fields are empty on an India query and they burn extra requests), and does not request a residential proxy. Residential proxies are where a free demo quietly stops being free. Apify’s free plan includes a monthly usage credit, currently published at $5. Check it the morning of the demo. Allowances move.</li>
    <li>Google’s Gemini pricing page, updated 30 Oct 2026, lists free input and output for Gemini 2.5 Flash-Lite on the free tier. One request covers the whole page of ads. I pinned Flash-Lite rather than Flash, because Google has said <code>gemini-2.5-flash</code> routes to <code>gemini-3.5-flash-lite</code> from 1 December 2026. A failed model call must not change the rank, and in this workflow it does not.</li>
    <li>n8n’s self-hosted edition is free to run for your own team. The nodes here are Manual Trigger, Set, IF, HTTP Request, and Code. No paid node, no Google Sheet required for the demo. <code>npx n8n</code> on a laptop is enough for the Meet. n8n Cloud’s trial works too.</li>
  </ul>
  <p>A few runs and a screen-share stay inside that. I would not turn the schedule on until the buyer has used the sample mode once and agreed the formula. A weekly run of 30 ads is still cents. A weekly run with video transcription of every card is a different product and a different bill, which is why it is not in this version.</p>

  <h2>Why I want the seat</h2>
  <p>I am Priyansh Agarwal. I study AI and data science at IIIT Raichur. The work I already like is the unglamorous part of this job: get the rows out of a page that does not want to give them to you, then refuse to pretend the rows say more than they do. SearchGPT, on my GitHub, is a small version of that. This assignment is the same muscle on your account.</p>
  <p>The brief is not “use ChatGPT”. It is six months in the HSR office, next to the people buying the media, while the company tries to go from 175 crore ARR to 500 crore. The library will not tell you the CAC of the English ad against the Kannada one. It will tell you which sentence you have been willing to keep on since April, and which sentence you copied again on 4 November without the price in it. n8n is the right home for that check because the next person to press execute should be a media buyer, not me. I want that seat, on the six-day in-office terms you wrote, not a remote version of it.</p>

  <h2>How to recompute this</h2>
  <p><code>python3 analysis/build_report.py</code> reads <code>data/pull_2026-11-11.json</code> and writes this HTML. <code>node analysis/check_score.mjs</code> fails if the n8n scoring code and the Python scoring code disagree. The pull is the assignment URL, captured 11 Nov 2026. Headlines were opened that same day on library IDs {esc(', '.join(sorted(ad['library_id'] for ad in ads if ad.get('headline'))))}. I did not open every card. Where a headline is quoted, the library ID it came from is in that creative’s block.</p>
  <p class="small">Sources. Meta Ad Library help, facebook.com/help/259468828226154. Assignment URL, in the repo README. Actor price and input, apify.com/curious_coder/facebook-ads-library-scraper. Gemini prices, ai.google.dev/gemini-api/docs/pricing, page updated 30 Oct 2026. n8n hosting, docs.n8n.io/hosting. The October comparison is Airbridge’s MySivi teardown, published 19 Oct 2026, from a library pull dated 16 Oct 2026. The Kamlesh Sawant film (Zee Business, 2 Nov 2026) is a brand story about a cop transferred to Tamil Nadu who uses Arya. It was not among these 30 active cards. I did not search inactive ads, so I am not saying the film is off. I am saying it is not what this impressions sort is delivering at the top.</p>
</main>
</body>
</html>
"""


def creative_block(row: dict, index: int) -> str:
    headline_ad = row["headline_ad"]
    headline = headline_ad["headline"] if headline_ad else "Not opened on this creative."
    headline_id = headline_ad["library_id"] if headline_ad else ""
    cta = "Install Now → Google Play com.practice.ninja_study" if headline_ad and headline_ad.get("cta_text") else "Button not opened on this creative."
    reading = row["reading"]
    pages = ", ".join(row["pages"])
    ids = ", ".join(row["library_ids"])
    parts = row["parts"]
    return f"""
  <h3>{index}. {esc(reading['name'])} · {row['score']}</h3>
  <p class="small">Best position {row['best_position']} · {row['copies']} cards · oldest {esc(human(row['oldest_started_on']))} ({row['max_days']} days) · pages: {esc(pages)}</p>
  <p class="small">Delivery {parts['delivery']} · survival {parts['survival']} · copies {parts['repetition']} · ₹1 in the primary text {parts['offer']} · specificity {parts['specificity']}</p>
  <div class="copy">{esc(row['primary_text'])}</div>
  <p><strong>Hook.</strong> {esc(row['hook'])}</p>
  <p><strong>Body.</strong> {esc(row['body'] or '—')} {esc(row['tags'])}</p>
  <p class="reading"><strong>Reading.</strong> {esc(reading['hook_reading'])} {esc(reading['body_reading'])}</p>
  <p><strong>Headline</strong> (library ID {esc(headline_id)}). {esc(headline)}</p>
  <p class="reading">{esc(reading['headline_reading'])}</p>
  <p><strong>CTA.</strong> {esc(cta)}</p>
  <p class="small">Representative card {esc(row['representative_id'])}. Oldest card {esc(row['oldest_id'])}. All cards: {esc(ids)}.</p>
"""


if __name__ == "__main__":
    main()
