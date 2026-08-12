import test from "node:test";
import assert from "node:assert/strict";
import { canUseCommand, getFanLevel } from "../src/bot/access-control.js";

const priorityCommand = { priority: true, minFanLevel: 11 };

test("插队仅允许粉丝团 11 级及以上", () => {
  assert.equal(canUseCommand(priorityCommand, { fanLevel: 10 }), false);
  assert.equal(canUseCommand(priorityCommand, { fanLevel: 11 }), true);
  assert.equal(canUseCommand(priorityCommand, { fanLevel: 20 }), true);
});

test("普通点歌不限制粉丝团等级", () => {
  assert.equal(canUseCommand({ priority: false }, { fanLevel: 0 }), true);
  assert.equal(getFanLevel({ fanLevel: "12" }), 12);
  assert.equal(getFanLevel({ fanLevel: "invalid" }), 0);
});
