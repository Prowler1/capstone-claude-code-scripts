import { test } from "node:test";
import assert from "node:assert/strict";
import { commentVerdictOf, closeVerdictOf } from "./auto-close-duplicates.ts";

const cutoff = new Date("2026-10-10T00:00:00Z");
const issue = { number: 7, title: "t", user: { id: 1 }, created_at: "2026-10-01T00:00:00Z" };
const bot = (at: string, body = "Found 1 possible duplicate: #42") =>
  ({ id: 9, body, created_at: at, user: { type: "Bot", id: 2 } });

test("no bot comment -> skip", () => {
  assert.equal((commentVerdictOf([], cutoff) as any).kind, "skip");
});
test("recent bot comment -> skip", () => {
  assert.match((commentVerdictOf([bot("2026-10-12T00:00:00Z")], cutoff) as any).reason, /too recent/);
});
test("activity after detection -> skip", () => {
  const human = { id: 3, body: "not a dupe", created_at: "2026-10-05T00:00:00Z", user: { type: "User", id: 1 } };
  assert.match((commentVerdictOf([bot("2026-10-02T00:00:00Z"), human], cutoff) as any).reason, /activity/);
});
test("old, quiet detection returns the comment", () => {
  assert.equal((commentVerdictOf([bot("2026-10-02T00:00:00Z")], cutoff) as any).id, 9);
});
test("author thumbs-down -> skip", () => {
  assert.equal(closeVerdictOf(issue, bot("x"), [{ user: { id: 1 }, content: "-1" }]).kind, "skip");
});
test("otherwise close as duplicate of the number in the comment", () => {
  assert.deepEqual(closeVerdictOf(issue, bot("x"), []), { kind: "close", duplicateOf: 42 });
});
