import test from "node:test";
import assert from "node:assert/strict";
import {
  emptyReply,
  reduceReply,
  containRect,
  visiblePoint,
} from "../src/services/classroomInteraction.js";

test("thinking to real deltas to queued; stale and cancelled streams ignored", () => {
  let r = reduceReply(emptyReply(), {
    type: "generation_started",
    generation_id: "one",
  });
  assert.equal(r.phase, "thinking");
  assert.equal(r.studentId, undefined);
  r = reduceReply(r, {
    type: "generation_student",
    generation_id: "one",
    student_id: "ming",
  });
  r = reduceReply(r, {
    type: "reply_delta",
    generation_id: "one",
    student_id: "ming",
    delta: "平均",
  });
  assert.equal(r.text, "平均");
  assert.equal(r.phase, "generating");
  assert.equal(
    reduceReply(r, { type: "reply_delta", generation_id: "old", delta: "BAD" }),
    r,
  );
  r = reduceReply(r, {
    type: "generation_completed",
    generation_id: "one",
    student_id: "ming",
    text: "平均分。",
  });
  assert.equal(r.phase, "queued");
  assert.equal(
    reduceReply(r, {
      type: "reply_delta",
      generation_id: "one",
      student_id: "ming",
      delta: "late",
    }),
    r,
  );
  r = reduceReply(r, { type: "cancel" });
  assert.deepEqual(r, emptyReply());
  assert.equal(
    reduceReply(r, {
      type: "reply_delta",
      generation_id: "one",
      delta: "late",
    }),
    r,
  );
});

test("failure removes unvalidated draft; disconnect clears state", () => {
  let r = reduceReply(emptyReply(), {
    type: "generation_started",
    generation_id: "one",
    student_id: "ming",
  });
  r = reduceReply(r, {
    type: "generation_failed",
    generation_id: "one",
    message: "连接中断",
  });
  assert.equal(r.phase, "failed");
  assert.equal(r.text, "");
  assert.deepEqual(reduceReply(r, { type: "disconnected" }), emptyReply());
});

test("skeleton mapping preserves letterboxing at portrait and landscape sizes", () => {
  const rect = containRect(1000, 500, 640, 480);
  assert.ok(
    Math.abs(rect.x - 500 / 3) < 1e-8 &&
      Math.abs(rect.y) < 1e-8 &&
      Math.abs(rect.height - 500) < 1e-8,
  );
  assert.deepEqual(containRect(320, 600, 640, 480), {
    x: 0,
    y: 180,
    width: 320,
    height: 240,
  });
  assert.equal(containRect(320, 600, 0, 0).width, 0);
  assert.equal(visiblePoint({ x: 0.5, y: 0.5, visibility: 0.2 }, true), false);
  assert.equal(visiblePoint({ x: 0.5, y: 0.5 }, false), true);
  assert.equal(visiblePoint({ x: NaN, y: 0.5 }), false);
});
