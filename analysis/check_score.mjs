import { readFileSync } from "fs";
import { scoreCreatives, applyDeltas, splitCopy } from "./score_ads.mjs";

const pull = JSON.parse(readFileSync(new URL("../data/pull_2026-11-11.json", import.meta.url), "utf8"));
const creatives = scoreCreatives(pull.ads, pull.pulled_on);
const expected = [
  ["1112422725088441", 85, 11, 217],
  ["1843111363320189", 70, 7, 163],
  ["2823814924671305", 63, 5, 93],
  ["1109916984937035", 58, 3, 81],
  ["2966208700429750", 52, 2, 18],
  ["1461355659421928", 41, 1, 19],
];
if (creatives.length !== expected.length) {
  throw new Error(`expected 6 creatives, got ${creatives.length}`);
}
expected.forEach(([id, score, copies, days], index) => {
  const row = creatives[index];
  if (row.representative_id !== id || row.score !== score || row.copies !== copies || row.max_days !== days) {
    throw new Error(`row ${index} ${JSON.stringify(row)} != ${id} ${score} ${copies} ${days}`);
  }
});
const english = splitCopy(creatives[0].primary_text);
if (!english.hook.includes("Speak English fluently")) {
  throw new Error(`hook split failed: ${english.hook}`);
}
const abused = applyDeltas(creatives, [
  { creative_id: "1112422725088441", score_delta: 40, quote: "not in the ad" },
]);
if (abused[0].model_delta !== 0) throw new Error("unquoted delta was kept");
const clamped = applyDeltas(creatives, [
  { creative_id: "1112422725088441", score_delta: 40, quote: "₹1" },
]);
if (clamped[0].model_delta !== 8 || clamped[0].final_score !== 93) {
  throw new Error(`clamp failed ${clamped[0].model_delta} ${clamped[0].final_score}`);
}
console.log("score check ok", creatives[0].representative_id, creatives[0].score);
