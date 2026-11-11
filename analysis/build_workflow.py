"""Assemble the importable n8n workflow from the shared scoring code."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = (ROOT / "analysis" / "score_ads.mjs").read_text(encoding="utf-8")
LIB = LIB.replace("export function ", "function ")
PULL = json.loads((ROOT / "data" / "pull_2026-11-11.json").read_text(encoding="utf-8"))
ADS_JSON = json.dumps(PULL["ads"], ensure_ascii=False, separators=(",", ":"))

AD_URL = PULL["source_url"]

SCORE_JS = (
    LIB
    + """

const config = $('Config').first().json;
const incoming = $input.all().map((item) => item.json);
let ads;
if (incoming.length === 1 && Array.isArray(incoming[0].ads)) {
  ads = incoming[0].ads;
} else {
  ads = incoming.map((raw, index) => normalizeApifyItem(raw, index));
}
ads = ads.filter((ad) => ad && ad.primary_text && ad.started_on);
const rankSpanOverride = incoming.length === 1 ? incoming[0].rankSpan : undefined;
const creatives = scoreCreatives(ads, config.asOf, rankSpanOverride).map((creative) => {
  const rep = ads.find((ad) => String(ad.library_id) === String(creative.representative_id)) || {};
  const split = splitCopy(creative.primary_text);
  return {
    ...creative,
    hook: split.hook,
    body: split.body,
    hashtags: split.hashtags,
    headline: rep.headline || '',
    cta_text: rep.cta_text || '',
    link_url: rep.link_url || '',
    model_delta: 0,
    model_reason: '',
    final_score: creative.score,
  };
});
const winner = creatives[0] || null;
return [{
  json: {
    as_of: config.asOf,
    mode: config.mode,
    geminiKey: config.geminiKey,
    geminiModel: config.geminiModel,
    ad_count: ads.length,
    model_used: false,
    winner_id: winner ? winner.representative_id : null,
    winner_score: winner ? winner.final_score : null,
    creatives,
    ads,
  },
}];
"""
)

SHAPE_JS = (
    LIB
    + """

const items = $input.all().map((item) => item.json);
let rows = items;
if (items.length === 1 && Array.isArray(items[0])) rows = items[0];
else if (items.length === 1 && Array.isArray(items[0].items)) rows = items[0].items;
const shaped = rows.map((raw, index) => normalizeApifyItem(raw, index));
const rankSpan = shaped.reduce((span, ad) => Math.max(span, Number(ad.position) || 0), shaped.length);
const ads = shaped.filter((ad) => ad.primary_text && ad.started_on);
if (!ads.length) {
  throw new Error('Apify returned no ads with a primary text and a start date. Check the run, or switch Config mode to sample.');
}
return [{ json: { ads, rankSpan } }];
"""
)

PROMPT_JS = r"""
const base = $input.first().json;
const packed = base.creatives.map((creative) => ({
  creative_id: creative.representative_id,
  primary_text: creative.primary_text,
  deterministic_score: creative.score,
}));
const instructions = [
  'You are reading MySivi ads for a media buyer. Do not pick a winner.',
  'Do not invent impressions, spend, CTR, or CAC. India commercial ads do not show those here.',
  'For each creative return creative_id unchanged, hook_en, body_en, angle, score_delta, quote, delta_reason.',
  'hook_en and body_en are an English reading of the primary text. If it is already English, copy it.',
  'angle is one of: generic_ai, mother_tongue, price, social_proof, time_bound.',
  'score_delta is an integer from -8 to 8. Use 0 unless a phrase in the primary text changes the read in a way the numbers missed.',
  'quote must be copied from primary_text. If you cannot quote, score_delta must be 0.',
  'delta_reason is one sentence.',
  'Return one JSON object and nothing else. The object has a single key, creatives, whose value is the array. Do not return a bare array.',
].join(' ');
return [{
  json: {
    ...base,
    geminiBody: {
      contents: [{ role: 'user', parts: [{ text: instructions + '\n\n' + JSON.stringify(packed) }] }],
      generationConfig: {
        temperature: 0.2,
        responseMimeType: 'application/json',
      },
    },
  },
}];
"""

APPLY_JS = (
    LIB
    + """

const base = $('Score the pull').first().json;
const payload = $json || {};
let deltas = [];
let modelError = '';
const httpError = payload.error;
if (httpError) {
  modelError = typeof httpError === 'string' ? httpError : (httpError.message || JSON.stringify(httpError));
} else {
  try {
    const parts = payload.candidates?.[0]?.content?.parts || [];
    const text = parts.map((part) => part.text || '').join('');
    if (!text.trim()) {
      modelError = 'Gemini returned no text. Rank left on the arithmetic.';
    } else {
      deltas = parseModelPayload(text);
    }
  } catch (error) {
    modelError = error.message || String(error);
  }
}
const creatives = applyDeltas(base.creatives, deltas).map((creative) => {
  const previous = base.creatives.find((item) => item.representative_id === creative.representative_id) || {};
  return { ...previous, ...creative };
});
const winner = creatives[0] || null;
return [{
  json: {
    ...base,
    creatives,
    winner_id: winner ? winner.representative_id : null,
    winner_score: winner ? winner.final_score : null,
    model_used: !modelError,
    model_error: modelError,
  },
}];
"""
)

REPORT_JS = r"""
const row = $input.first().json;
const lines = [];
lines.push('# MySivi ad rank, as of ' + row.as_of);
lines.push('Mode: ' + row.mode + '. Ads scored: ' + row.ad_count + '.');
lines.push('Winner: library ID ' + row.winner_id + ' at ' + row.winner_score + '.');
lines.push('Model used: ' + (row.model_used ? 'yes' : 'no') + '.');
if (row.model_error) lines.push('Model error (rank left on the arithmetic): ' + row.model_error);
lines.push('');
lines.push('This rank is the arithmetic in the Code node. A model delta is applied only when the quote is copied from the ad, and only inside -8 to +8.');
lines.push('');
for (const creative of row.creatives) {
  lines.push('## ' + creative.final_score + ' (base ' + creative.score + ', delta ' + creative.model_delta + ')');
  lines.push('Library ID ' + creative.representative_id + ', position ' + creative.best_position + ', ' + creative.copies + ' copies, ' + creative.max_days + ' days.');
  lines.push('Hook: ' + (creative.hook || ''));
  if (creative.hook_en) lines.push('Hook in English: ' + creative.hook_en);
  lines.push('Body: ' + (creative.body || ''));
  if (creative.body_en) lines.push('Body in English: ' + creative.body_en);
  if (creative.headline) lines.push('Headline: ' + creative.headline);
  if (creative.cta_text) lines.push('CTA: ' + creative.cta_text);
  if (creative.model_reason) lines.push('Delta reason: ' + creative.model_reason);
  lines.push('');
}
return [{ json: { ...row, report_markdown: lines.join('\n') } }];
"""

LOAD_JS = "const ads = " + ADS_JSON + ";\nreturn [{ json: { ads } }];\n"

FAIL_JS = """
const status = $json.data && $json.data.status ? $json.data.status : 'UNKNOWN';
return [{
  json: {
    error: 'Apify run ended as ' + status + '. Open the run in the Apify console. Config mode sample still scores the 11 Nov pull with no token.',
    status,
  },
}];
"""


def node(name, type_, version, x, y, parameters, notes="", on_error=""):
    item = {
        "id": name.lower().replace(" ", "-").replace("?", "").replace("'", "")[:48],
        "name": name,
        "type": type_,
        "typeVersion": version,
        "position": [x, y],
        "parameters": parameters,
    }
    if on_error:
        item["onError"] = on_error
    if notes:
        item["notes"] = notes
        item["notesInFlow"] = True
    return item


def main() -> None:
    nodes = [
        node("When clicking Execute workflow", "n8n-nodes-base.manualTrigger", 1, -900, 200, {}),
        node(
            "Config",
            "n8n-nodes-base.set",
            3.4,
            -680,
            200,
            {
                "options": {},
                "assignments": {
                    "assignments": [
                        {"id": "mode", "name": "mode", "type": "string", "value": "sample"},
                        {"id": "url", "name": "adLibraryUrl", "type": "string", "value": AD_URL},
                        {"id": "max", "name": "maxAds", "type": "number", "value": 12},
                        {"id": "asof", "name": "asOf", "type": "string", "value": "2026-11-11"},
                        {"id": "apify", "name": "apifyToken", "type": "string", "value": "PASTE_APIFY_TOKEN"},
                        {"id": "gemini", "name": "geminiKey", "type": "string", "value": "PASTE_GEMINI_KEY"},
                        {"id": "model", "name": "geminiModel", "type": "string", "value": "gemini-2.5-flash-lite"},
                    ]
                },
            },
            "mode sample scores the saved 11 Nov pull and spends nothing. mode apify runs a live scrape. Set asOf to the day you run a live pull. Leave the Gemini placeholder to skip the model.",
        ),
        node(
            "Sample or live?",
            "n8n-nodes-base.if",
            2,
            -460,
            200,
            {
                "options": {},
                "conditions": {
                    "options": {"leftValue": "", "caseSensitive": True, "typeValidation": "loose"},
                    "combinator": "and",
                    "conditions": [
                        {
                            "id": "mode-apify",
                            "leftValue": "={{ $json.mode }}",
                            "rightValue": "apify",
                            "operator": {"type": "string", "operation": "equals"},
                        }
                    ],
                },
            },
        ),
        node(
            "Load 11 Nov pull",
            "n8n-nodes-base.code",
            2,
            -220,
            420,
            {"jsCode": LOAD_JS},
            "The pull behind the PDF. No token, no model.",
        ),
        node(
            "Start Apify run",
            "n8n-nodes-base.httpRequest",
            4.2,
            -220,
            40,
            {
                "method": "POST",
                "url": "=https://api.apify.com/v2/acts/curious_coder~facebook-ads-library-scraper/runs?waitForFinish=60&memory=1024&timeout=300&token={{ $('Config').first().json.apifyToken }}",
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": "={{ JSON.stringify({ urls: [{ url: $('Config').first().json.adLibraryUrl }], count: Number($('Config').first().json.maxAds), limitPerSource: Number($('Config').first().json.maxAds), scrapeAdDetails: false }) }}",
                "options": {"timeout": 120000},
            },
            "1 GB, no EU detail scrape, no residential proxy. Twelve ads is under one cent of the actor's published per-item price.",
        ),
        node(
            "Run succeeded?",
            "n8n-nodes-base.if",
            2,
            20,
            40,
            {
                "options": {},
                "conditions": {
                    "options": {"leftValue": "", "caseSensitive": True, "typeValidation": "loose"},
                    "combinator": "and",
                    "conditions": [
                        {
                            "id": "status-ok",
                            "leftValue": "={{ $json.data.status }}",
                            "rightValue": "SUCCEEDED",
                            "operator": {"type": "string", "operation": "equals"},
                        }
                    ],
                },
            },
        ),
        node(
            "Run died?",
            "n8n-nodes-base.if",
            2,
            20,
            260,
            {
                "options": {},
                "conditions": {
                    "options": {"leftValue": "", "caseSensitive": True, "typeValidation": "loose"},
                    "combinator": "and",
                    "conditions": [
                        {
                            "id": "status-dead",
                            "leftValue": "={{ ['FAILED', 'ABORTED', 'TIMED-OUT'].includes($json.data.status) }}",
                            "rightValue": True,
                            "operator": {"type": "boolean", "operation": "true", "singleValue": True},
                        }
                    ],
                },
            },
        ),
        node(
            "Poll Apify run",
            "n8n-nodes-base.httpRequest",
            4.2,
            260,
            420,
            {
                "url": "=https://api.apify.com/v2/actor-runs/{{ $json.data.id }}?waitForFinish=60&token={{ $('Config').first().json.apifyToken }}",
                "options": {"timeout": 120000},
            },
        ),
        node("Run failed", "n8n-nodes-base.code", 2, 260, 260, {"jsCode": FAIL_JS}),
        node(
            "Fetch dataset items",
            "n8n-nodes-base.httpRequest",
            4.2,
            260,
            40,
            {
                "url": "=https://api.apify.com/v2/datasets/{{ $json.data.defaultDatasetId }}/items?clean=true&token={{ $('Config').first().json.apifyToken }}",
                "options": {"timeout": 60000},
            },
        ),
        node("Shape Apify rows", "n8n-nodes-base.code", 2, 500, 40, {"jsCode": SHAPE_JS}),
        node(
            "Score the pull",
            "n8n-nodes-base.code",
            2,
            740,
            200,
            {"jsCode": SCORE_JS},
            "Same rules as analysis/score_ads.py. The model does not run inside this node.",
        ),
        node(
            "Gemini key set?",
            "n8n-nodes-base.if",
            2,
            980,
            200,
            {
                "options": {},
                "conditions": {
                    "options": {"leftValue": "", "caseSensitive": True, "typeValidation": "loose"},
                    "combinator": "and",
                    "conditions": [
                        {
                            "id": "has-key",
                            "leftValue": "={{ $json.geminiKey && $json.geminiKey !== 'PASTE_GEMINI_KEY' }}",
                            "rightValue": True,
                            "operator": {"type": "boolean", "operation": "true", "singleValue": True},
                        }
                    ],
                },
            },
        ),
        node("Build Gemini body", "n8n-nodes-base.code", 2, 1200, 40, {"jsCode": PROMPT_JS}),
        node(
            "Ask Gemini",
            "n8n-nodes-base.httpRequest",
            4.2,
            1420,
            40,
            {
                "method": "POST",
                "url": "=https://generativelanguage.googleapis.com/v1beta/models/{{ $('Config').first().json.geminiModel }}:generateContent",
                "sendHeaders": True,
                "headerParameters": {
                    "parameters": [
                        {"name": "x-goog-api-key", "value": "={{ $('Config').first().json.geminiKey }}"},
                    ]
                },
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": "={{ JSON.stringify($json.geminiBody) }}",
                "options": {"timeout": 60000, "response": {"neverError": True}},
            },
            "One call for the whole set. A bad key, a timeout, or a 4xx still continues into the read, on the arithmetic score.",
            "continueRegularOutput",
        ),
        node("Apply the model delta", "n8n-nodes-base.code", 2, 1640, 40, {"jsCode": APPLY_JS}),
        node(
            "Build the read",
            "n8n-nodes-base.code",
            2,
            1640,
            280,
            {"jsCode": REPORT_JS},
            "Open report_markdown on this item. The PDF in submission/ is the written version of the sample run.",
        ),
        node(
            "How to read this",
            "n8n-nodes-base.stickyNote",
            1,
            -900,
            -160,
            {
                "width": 640,
                "height": 300,
                "content": (
                    "## MySivi Ad Library, control finder\n\n"
                    "Sample mode scores the 11 Nov 2026 pull and spends nothing. "
                    "That run is the PDF.\n\n"
                    "Live mode: paste an Apify token, set mode to apify, set asOf to today, "
                    "leave maxAds at 12. No residential proxy. scrapeAdDetails is off.\n\n"
                    "Paste a Gemini key only if you want a translation and a clamped nudge. "
                    "A quote that is not in the ad scores 0. The rank does not come from the model.\n\n"
                    "Best ad in the saved pull: library ID 1112422725088441, score 85."
                ),
            },
        ),
    ]

    def link(src, dest, output=0):
        return src, dest, output

    links = [
        ("When clicking Execute workflow", "Config", 0),
        ("Config", "Sample or live?", 0),
        ("Sample or live?", "Start Apify run", 0),
        ("Sample or live?", "Load 11 Nov pull", 1),
        ("Load 11 Nov pull", "Score the pull", 0),
        ("Start Apify run", "Run succeeded?", 0),
        ("Run succeeded?", "Fetch dataset items", 0),
        ("Run succeeded?", "Run died?", 1),
        ("Run died?", "Run failed", 0),
        ("Run died?", "Poll Apify run", 1),
        ("Poll Apify run", "Run succeeded?", 0),
        ("Fetch dataset items", "Shape Apify rows", 0),
        ("Shape Apify rows", "Score the pull", 0),
        ("Score the pull", "Gemini key set?", 0),
        ("Gemini key set?", "Build Gemini body", 0),
        ("Gemini key set?", "Build the read", 1),
        ("Build Gemini body", "Ask Gemini", 0),
        ("Ask Gemini", "Apply the model delta", 0),
        ("Apply the model delta", "Build the read", 0),
    ]
    connections = {}
    for src, dest, output in links:
        connections.setdefault(src, {"main": []})
        while len(connections[src]["main"]) <= output:
            connections[src]["main"].append([])
        connections[src]["main"][output].append({"node": dest, "type": "main", "index": 0})

    workflow = {
        "name": "MySivi Ad Library — which ad is the control",
        "nodes": nodes,
        "connections": connections,
        "pinData": {},
        "settings": {"executionOrder": "v1"},
        "staticData": None,
        "meta": {"templateCredsSetupCompleted": True},
        "tags": [],
    }
    dest = ROOT / "workflow" / "mysivi_ad_library.json"
    dest.write_text(json.dumps(workflow, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(dest, "bytes", dest.stat().st_size)


if __name__ == "__main__":
    main()
