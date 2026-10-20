import test from "node:test";
import assert from "node:assert/strict";
import { CHANNELS, channelLabel, guessLanguage, languageLabel, normalizeFeedback } from "./feedback.js";
import { mockFeedback } from "../data/mockFeedback.js";

test("every offline inbox item has the API fields and a known channel", () => {
  assert.ok(mockFeedback.length >= 8);
  const channels = new Set(CHANNELS.map((channel) => channel.id));
  mockFeedback.forEach((item) => {
    ["feedback_id", "channel", "author", "received_at", "text", "metadata"].forEach((key) => assert.ok(key in item, `${item.feedback_id} ${key}`));
    assert.ok(channels.has(item.channel), item.channel);
    assert.ok(item.text.length >= 10);
  });
  assert.equal(new Set(mockFeedback.map((item) => item.feedback_id)).size, mockFeedback.length);
});

test("the inbox mixes Indonesian and English and contains a duplicate pair", () => {
  const languages = mockFeedback.map((item) => normalizeFeedback(item).language);
  assert.ok(languages.includes("id"));
  assert.ok(languages.includes("en"));
  const flashSale = mockFeedback.filter((item) => /flash sale/i.test(item.text) && /(Bayar|Pay)\b/.test(item.text));
  assert.ok(flashSale.length >= 2, "two messages about the same flash-sale crash");
});

test("labels fall back gracefully", () => {
  assert.equal(channelLabel("cs_chat"), "Customer-service chat");
  assert.equal(channelLabel("carrier_pigeon"), "Carrier pigeon");
  assert.equal(channelLabel(undefined), "Other channel");
  assert.equal(languageLabel("id"), "Bahasa Indonesia");
  assert.equal(guessLanguage("Tombol Simpan di halaman profil tidak berfungsi"), "id");
  assert.equal(guessLanguage("Order history takes ten seconds to open"), "en");
  assert.equal(normalizeFeedback({ body: "hello there friend" }).text, "hello there friend");
});
