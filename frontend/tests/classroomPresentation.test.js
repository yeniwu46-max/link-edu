import test from "node:test";
import assert from "node:assert/strict";
import {
  connectionSummary,
  budgetNotice,
  isTechnicalEvent,
  eventText,
} from "../src/services/classroomStatus.js";

const configured = {
  configured: true,
  pricing_confirmed: true,
  status: "unverified",
};
test("configured services stay pending until explicitly checked", () => {
  assert.equal(
    connectionSummary({ asr: configured, tts: configured }, ["asr", "tts"])
      .label,
    "待检查",
  );
  assert.equal(
    connectionSummary(
      { asr: { ...configured, status: "available" }, tts: configured },
      ["asr", "tts"],
    ).tone,
    "pending",
  );
  assert.equal(connectionSummary(null, ["dialogue"]).label, "读取中…");
});
test("failed or unconfigured services remain actionable in the summary", () => {
  assert.equal(
    connectionSummary(
      { asr: configured, tts: { ...configured, status: "failed" } },
      ["asr", "tts"],
    ).tone,
    "failed",
  );
  assert.equal(
    connectionSummary(
      { dialogue: { ...configured, pricing_confirmed: false } },
      ["dialogue"],
    ).tone,
    "warning",
  );
});
test("a depleted optional account is visible even when the overall budget is not stopped", () => {
  assert.match(
    budgetNotice({
      stopped: false,
      credits: { accounts: { vision: { label: "视觉", stopped: true } } },
    }),
    /视觉.*停止线/,
  );
  assert.equal(budgetNotice({ stopped: false, warning: false }), "");
  assert.match(budgetNotice({ warning: true }), /即将/);
});
test("technical records stay classifiable and unknown pose is never described as absent", () => {
  assert.equal(isTechnicalEvent({ type: "playback" }), true);
  assert.equal(isTechnicalEvent({ type: "vision" }), false);
  assert.equal(isTechnicalEvent({ type: "error" }), false);
  assert.equal(
    eventText({ type: "pose", data: { present: null } }),
    "画面暂不清晰",
  );
  assert.equal(
    eventText({ type: "playback", data: { status: "playback_completed" } }),
    "播放完成",
  );
});
