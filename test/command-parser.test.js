import test from "node:test";
import assert from "node:assert/strict";
import { parseSongCommand } from "../src/bot/command-parser.js";

test("解析方括号歌名", () => {
  assert.deepEqual(parseSongCommand("点歌[IF Else]"), {
    kind: "song",
    value: "IF Else",
    trigger: "点歌",
    searchStrategy: "first",
    payload: { song: "IF Else", searchStrategy: "first" },
  });
});

test("解析中文括号和空白", () => {
  assert.equal(parseSongCommand(" 点歌 【春を告げる】 ").value, "春を告げる");
});

test("纯数字按歌曲 ID 处理", () => {
  assert.deepEqual(parseSongCommand("点歌[3384055850]"), {
    kind: "id",
    value: "3384055850",
    trigger: "点歌",
    payload: { id: "3384055850" },
  });
});

test("支持空格分隔的简写", () => {
  assert.equal(parseSongCommand("点歌 IF Else").value, "IF Else");
});

test("支持不加空格的歌名和 ID", () => {
  assert.deepEqual(parseSongCommand("点歌IF Else"), {
    kind: "song",
    value: "IF Else",
    trigger: "点歌",
    searchStrategy: "first",
    payload: { song: "IF Else", searchStrategy: "first" },
  });
  assert.deepEqual(parseSongCommand("点歌3384055850"), {
    kind: "id",
    value: "3384055850",
    trigger: "点歌",
    payload: { id: "3384055850" },
  });
});

test("点歌和模糊点歌选择 API 第一名", () => {
  assert.equal(parseSongCommand("点歌被生命所厌恶").searchStrategy, "first");
  assert.deepEqual(parseSongCommand("模糊点歌[被生命所厌恶]").payload, {
    song: "被生命所厌恶",
    searchStrategy: "first",
  });
});

test("经典搜索使用标题文字匹配", () => {
  const command = parseSongCommand("经典搜索被生命所厌恶");
  assert.equal(command.trigger, "经典搜索");
  assert.equal(command.searchStrategy, "classic");
  assert.deepEqual(command.payload, {
    song: "被生命所厌恶",
    searchStrategy: "classic",
  });
});

test("插队指令要求粉丝团 11 级并标记优先级", () => {
  assert.deepEqual(parseSongCommand("插队[IF Else]"), {
    kind: "song",
    value: "IF Else",
    trigger: "插队",
    searchStrategy: "first",
    priority: true,
    minFanLevel: 11,
    payload: { song: "IF Else", searchStrategy: "first" },
  });
  assert.equal(parseSongCommand("插队3384055850").priority, true);
});

test("忽略普通弹幕和空指令", () => {
  assert.equal(parseSongCommand("这首歌很好听"), null);
  assert.equal(parseSongCommand("点歌[]"), null);
  assert.equal(parseSongCommand("点歌[IF Else"), null);
  assert.equal(parseSongCommand("经典搜索【被生命所厌恶"), null);
});
