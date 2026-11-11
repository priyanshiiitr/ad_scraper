/**
 * Same scoring rules as analysis/score_ads.py.
 * Kept in JS because the n8n Code node runs this, not Python.
 */

const REGIONAL = /[\u0900-\u0D7F]/;
const NAMED_LANGUAGE = /\b(bangla|kannada|tamil|telugu|marathi|hindi)\b/i;
const RUPEE_ONE = /(?:₹|rs\.?)\s*1(?!\d)/i;
const TIME_15 = /15\s*(?:minute|min|ನಿಮಿಷ)/i;
const PROOF_LAKH = /லட்ச|lakh/i;

function parseDay(value) {
  return new Date(`${String(value).slice(0, 10)}T00:00:00Z`);
}

function daysLive(startedOn, asOf) {
  const ms = parseDay(asOf) - parseDay(startedOn);
  return Math.round(ms / 86400000);
}

function normalizeCopy(text) {
  let out = "";
  for (const ch of text || "") {
    if (ch === "\uFE0F" || ch === "\u200D") continue;
    const code = ch.codePointAt(0);
    // Emoji and other symbols. Letters, including Indic, stay.
    if (
      (code >= 0x1f000 && code <= 0x1faff) ||
      (code >= 0x2600 && code <= 0x27bf) ||
      (code >= 0x2300 && code <= 0x23ff) ||
      code === 0xfe0f ||
      code === 0x200d
    ) {
      continue;
    }
    out += ch;
  }
  return out.replace(/\s+/g, " ").trim().toLowerCase();
}

function isCompetitor(ad) {
  const name = (ad.page_name || "").toLowerCase();
  const text = (ad.primary_text || "").toLowerCase();
  return name.includes("pw talk") || text.includes("physicswallah");
}

function hasRupeeOne(text) {
  return RUPEE_ONE.test(text || "");
}

function specificity(text) {
  let score = 0;
  if (TIME_15.test(text || "")) score += 6;
  if (PROOF_LAKH.test(text || "") && /40/.test(text || "")) score += 6;
  if (REGIONAL.test(text || "") || NAMED_LANGUAGE.test(text || "")) score += 3;
  return Math.min(15, score);
}

function survivalPoints(days) {
  if (days >= 180) return 25;
  if (days >= 120) return 21;
  if (days >= 90) return 17;
  if (days >= 60) return 13;
  if (days >= 30) return 8;
  if (days >= 14) return 4;
  return 1;
}

function repetitionPoints(count) {
  if (count >= 8) return 15;
  if (count >= 5) return 12;
  if (count >= 3) return 8;
  if (count >= 2) return 4;
  return 1;
}

function deliveryPoints(bestPosition, nCards) {
  if (nCards <= 1) return 30;
  const raw = Math.round((30 * (nCards - bestPosition)) / (nCards - 1));
  return Math.max(0, raw);
}

function rankSpan(ads, declared) {
  let span = Math.max(ads.length, Number(declared) || 0, 1);
  ads.forEach((ad, index) => {
    const position = Number(ad.position) || index + 1;
    if (position > span) span = position;
  });
  return span;
}

function repetitionCount(members) {
  const rows = members.length;
  const coll = members.reduce((max, member) => {
    const value = Number(member.collation_count) || 0;
    return value > max ? value : max;
  }, 0);
  return Math.max(rows, coll);
}

export function scoreCreatives(ads, asOf, rankSpanOverride) {
  const nCards = rankSpan(ads, rankSpanOverride);
  const groups = new Map();
  ads.forEach((ad, index) => {
    if (isCompetitor(ad) || !(ad.primary_text || "").trim()) return;
    const positioned = ad.position ? ad : { ...ad, position: index + 1 };
    const key = normalizeCopy(positioned.primary_text);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(positioned);
  });

  const creatives = [];
  for (const [key, members] of groups) {
    const rep = members.reduce((a, b) => (a.position < b.position ? a : b));
    const oldest = members.reduce((a, b) => {
      if (a.started_on !== b.started_on) return a.started_on < b.started_on ? a : b;
      return a.position <= b.position ? a : b;
    });
    const text = rep.primary_text;
    const maxDays = Math.max(...members.map((m) => daysLive(m.started_on, asOf)));
    const copies = repetitionCount(members);
    const parts = {
      delivery: deliveryPoints(rep.position, nCards),
      survival: survivalPoints(maxDays),
      repetition: repetitionPoints(copies),
      offer: hasRupeeOne(text) ? 15 : 0,
      specificity: specificity(text),
    };
    creatives.push({
      copy_key: key,
      primary_text: text,
      score: Object.values(parts).reduce((sum, n) => sum + n, 0),
      parts,
      best_position: rep.position,
      representative_id: String(rep.library_id),
      oldest_id: String(oldest.library_id),
      oldest_started_on: oldest.started_on,
      max_days: maxDays,
      copies,
      library_ids: members
        .slice()
        .sort((a, b) => a.position - b.position)
        .map((m) => String(m.library_id)),
      pages: [...new Set(members.map((m) => m.page_name || ""))].sort(),
      headline_has_rupee: members.some((m) => hasRupeeOne(m.headline || "")),
    });
  }
  creatives.sort((a, b) => b.score - a.score || a.best_position - b.best_position || b.max_days - a.max_days);
  return creatives;
}

export function applyDeltas(creatives, deltas) {
  const byId = new Map();
  for (const item of deltas || []) {
    if (item.creative_id) byId.set(String(item.creative_id), item);
  }
  const adjusted = creatives.map((creative) => {
    const proposal = byId.get(creative.representative_id) || byId.get(creative.copy_key) || {};
    let raw = Number.parseInt(proposal.score_delta, 10);
    if (Number.isNaN(raw)) raw = 0;
    const quote = String(proposal.quote || "").trim();
    const quoted = quote && creative.primary_text.toLowerCase().includes(quote.toLowerCase());
    const delta = quoted ? Math.max(-8, Math.min(8, raw)) : 0;
    return {
      ...creative,
      hook_en: typeof proposal.hook_en === "string" ? proposal.hook_en : creative.hook_en || "",
      body_en: typeof proposal.body_en === "string" ? proposal.body_en : creative.body_en || "",
      angle: typeof proposal.angle === "string" ? proposal.angle : creative.angle || "",
      model_delta: delta,
      model_reason: delta ? proposal.delta_reason || "" : "",
      final_score: Math.max(0, Math.min(100, creative.score + delta)),
    };
  });
  adjusted.sort(
    (a, b) => b.final_score - a.final_score || a.best_position - b.best_position || b.max_days - a.max_days,
  );
  return adjusted;
}

export function parseModelPayload(text) {
  const cleaned = String(text || "")
    .trim()
    .replace(/^```(?:json)?\s*/i, "")
    .replace(/\s*```$/, "");
  if (!cleaned) return [];
  const parsed = JSON.parse(cleaned);
  if (Array.isArray(parsed)) return parsed;
  if (parsed && Array.isArray(parsed.creatives)) return parsed.creatives;
  if (parsed && Array.isArray(parsed.deltas)) return parsed.deltas;
  return [];
}

export function splitCopy(text) {
  const lines = String(text || "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  const tags = lines.filter((line) => line.startsWith("#") || (line.split("#").length - 1 >= 2 && line.length < 90));
  const main = lines.filter((line) => !tags.includes(line));
  const blob = main.join(" ");
  const parts = blob.split(/(?<=[!?।])\s+|(?<=\.)\s+/);
  return {
    hook: (parts[0] || "").trim(),
    body: parts.slice(1).join(" ").trim(),
    hashtags: tags.join(" "),
  };
}

export function normalizeApifyItem(raw, index) {
  const snap = raw.snapshot || {};
  const bodyObj = snap.body;
  let body = "";
  if (typeof bodyObj === "string") body = bodyObj;
  else if (bodyObj && typeof bodyObj.text === "string") body = bodyObj.text;
  const cards = Array.isArray(snap.cards) ? snap.cards : [];
  const card = cards[0] || {};
  if (!body && card.body) body = card.body;
  let started = raw.start_date_formatted || raw.started_on || null;
  if (!started && typeof raw.start_date === "number") {
    started = new Date(raw.start_date * 1000).toISOString().slice(0, 10);
  }
  const videos = snap.videos || card.video_hd_url || card.video_sd_url;
  return {
    library_id: String(raw.ad_archive_id || raw.adArchiveID || raw.library_id || ""),
    position: Number(raw.position) || index + 1,
    started_on: started ? String(started).slice(0, 10) : null,
    page_name: raw.page_name || snap.page_name || card.title || "",
    primary_text: String(body || "").trim(),
    headline: snap.title || card.title || raw.headline || "",
    cta_text: snap.cta_text || card.cta_text || raw.cta_text || "",
    cta_type: snap.cta_type || card.cta_type || "",
    link_url: snap.link_url || card.link_url || "",
    is_video: String(snap.display_format || "").toUpperCase() === "VIDEO" || Boolean(videos),
    collation_count: raw.collation_count || raw.collationCount || null,
    is_active: raw.is_active !== false,
  };
}
