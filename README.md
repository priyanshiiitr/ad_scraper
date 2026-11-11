# MySivi Ad Library — which ad is the control

Growth internship assignment for MySivi. Active Facebook ads in India for the exact phrase “MySivi”, scored from public library evidence only.

**Best ad in the 11 Nov 2026 pull: library ID [1112422725088441](https://www.facebook.com/ads/library/?id=1112422725088441). Score 85/100.**

It is the first card in the impressions sort. The primary text (“Speak English fluently with the power of AI… Start your trial now at just ₹1”) is on 11 of the 30 cards, including one still running since 8 Apr 2026. The CTA on the card I opened is **Install Now**, to Google Play `com.practice.ninja_study`. The headline is “MySivi Se Shuru Karo – Sirf ₹1 Mein Install Now”.

That is the control. It is not the best written ad. The written recommendation, and the full table, is in [`submission/MySivi_Ad_Library_Analysis.pdf`](submission/MySivi_Ad_Library_Analysis.pdf).

The assignment URL:

<https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=IN&is_targeted_country=false&media_type=all&q=%22MySivi%22&search_type=keyword_exact_phrase&sort_data[direction]=desc&sort_data[mode]=total_impressions>

## What to submit

| Piece | Where |
| --- | --- |
| PDF | `submission/MySivi_Ad_Library_Analysis.pdf` |
| n8n workflow | `workflow/mysivi_ad_library.json` |
| Loom | Record it from `submission/LOOM_SCRIPT.md`. It has to be your voice. |

## Run the workflow

1. Self-host n8n (`npx n8n`) or use the cloud trial. Import `workflow/mysivi_ad_library.json`.
2. Leave **mode** as `sample` and execute. That scores the saved 11 Nov pull, spends nothing, and writes `report_markdown` on the last node. It should name library ID `1112422725088441` at 85.
3. For a live run, paste an Apify token into **apifyToken**, set **mode** to `apify`, and set **asOf** to today. `maxAds` is 12. The actor is `curious_coder/facebook-ads-library-scraper` at its published $0.75 per 1,000 ads. The run asks for 1 GB, does not scrape EU ad details, and does not request a residential proxy.
4. Paste a Gemini key only if you want a translation. The model is `gemini-2.5-flash-lite`. A score nudge is kept only when the model quotes the ad, and only inside −8 to +8. A bad key, a timeout, or a bare JSON array does not drop the read: the arithmetic rank still comes out, with the English reading attached when the model actually returned one. Leave the placeholder and the rank stays arithmetic.

## Rebuild the PDF

```bash
python3 analysis/build_report.py
google-chrome --headless --disable-gpu --no-sandbox --no-pdf-header-footer \
  --print-to-pdf=submission/MySivi_Ad_Library_Analysis.pdf \
  submission/report.html
python3 -m unittest tests/test_score.py
node analysis/check_score.mjs
```

`analysis/score_ads.py` and `analysis/score_ads.mjs` are the same rules. The test fails if they disagree.
