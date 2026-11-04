import test from "node:test";
import assert from "node:assert/strict";
import { TRANSLATIONS, translate, translateText } from "../src/lib/translations.ts";

const LANGS = ["en", "mr", "hi"];
const placeholders = (s) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();

test("every language defines exactly the same keys as English", () => {
  const enKeys = Object.keys(TRANSLATIONS.en).sort();
  for (const lang of ["mr", "hi"]) {
    const keys = Object.keys(TRANSLATIONS[lang]).sort();
    const missing = enKeys.filter((k) => !keys.includes(k));
    const extra = keys.filter((k) => !enKeys.includes(k));
    assert.deepEqual({ missing, extra }, { missing: [], extra: [] }, `key mismatch in "${lang}"`);
  }
});

test("no translation is empty", () => {
  for (const lang of LANGS) {
    for (const [key, value] of Object.entries(TRANSLATIONS[lang])) {
      assert.ok(value.trim().length > 0, `${lang}.${key} is empty`);
    }
  }
});

test("translations keep the same {placeholders} as English", () => {
  for (const [key, en] of Object.entries(TRANSLATIONS.en)) {
    for (const lang of ["mr", "hi"]) {
      const other = TRANSLATIONS[lang][key];
      if (other === undefined) continue;
      assert.deepEqual(placeholders(other), placeholders(en), `${lang}.${key} placeholders differ`);
    }
  }
});

test("translate returns the string for the requested language", () => {
  const key = Object.keys(TRANSLATIONS.en)[0];
  for (const lang of LANGS) {
    assert.equal(translate(lang, key), TRANSLATIONS[lang][key]);
  }
});

test("translate falls back to the key when it is unknown", () => {
  assert.equal(translate("mr", "no_such_key_123"), "no_such_key_123");
});

test("translate falls back to English when the language is unknown", () => {
  const key = Object.keys(TRANSLATIONS.en)[0];
  assert.equal(translate("fr", key), TRANSLATIONS.en[key]);
});

test("translate substitutes every occurrence of each parameter", () => {
  const key = Object.keys(TRANSLATIONS.en).find((k) => placeholders(TRANSLATIONS.en[k]).length);
  assert.ok(key, "expected at least one parameterised string");
  const params = Object.fromEntries(placeholders(TRANSLATIONS.en[key]).map((p) => [p, "X"]));
  const out = translate("en", key, params);
  assert.doesNotMatch(out, /\{\w+\}/);
});

test("translateText returns empty input unchanged", () => {
  assert.equal(translateText(""), "");
});

test("translateText replaces known phrases", () => {
  assert.equal(translateText("सह्याद्री हॉस्पिटल"), "Sahyadri Hospital");
  assert.equal(translateText("वजन ७२ किलो"), "Weight 72 kg");
});

test("translateText labels text it cannot translate", () => {
  assert.equal(translateText("नमस्कार"), '[Translated summary]: "नमस्कार"');
});

// Known bug: shorter keys are replaced first, so a longer phrase that contains them
// never matches. Remove `todo` once translateText tries longer keys first.
test("translateText prefers the longest matching phrase", { todo: "shorter keys win over longer ones" }, () => {
  assert.equal(translateText("लाईट बिल १५०० रुपये"), "Electricity bill ₹1500");
  assert.equal(translateText("१० नोव्हेंबरपर्यंत"), "Before 10th November");
});
