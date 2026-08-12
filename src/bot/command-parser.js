const BRACKET_VALUE = /^(?:\[([^\]]+)\]|【([^】]+)】)$/u;
const COMMANDS = [
  { trigger: "插队", searchStrategy: "first", priority: true, minFanLevel: 11 },
  { trigger: "模糊点歌", searchStrategy: "first" },
  { trigger: "经典搜索", searchStrategy: "classic" },
  { trigger: "点歌", searchStrategy: "first" },
];

/**
 * 由歌名/ID 直接拼一条点歌指令，供管理面板手动加歌使用。
 * 与弹幕解析共用同一套 ID 判定和载荷格式。
 */
export function buildSongCommand({ value, priority = false, searchStrategy = "first" } = {}) {
  const text = String(value ?? "").trim();
  if (!text) return null;

  const strategy = searchStrategy === "classic" ? "classic" : "first";
  const trigger = priority ? "插队" : "点歌";
  const priorityFields = priority ? { priority: true, minFanLevel: 0 } : {};

  if (/^\d+$/.test(text)) {
    return { kind: "id", value: text, trigger, ...priorityFields, payload: { id: text } };
  }

  return {
    kind: "song",
    value: text,
    trigger,
    searchStrategy: strategy,
    ...priorityFields,
    payload: { song: text, searchStrategy: strategy },
  };
}

export function parseSongCommand(text) {
  if (typeof text !== "string") return null;

  const input = text.trim();
  const command = COMMANDS.find(({ trigger }) => input.startsWith(trigger));
  if (!command) return null;

  const rest = input.slice(command.trigger.length).trim();
  const match = rest.match(BRACKET_VALUE);
  let value;

  if (match) {
    value = (match[1] || match[2] || "").trim();
  } else {
    value = rest;
    // 括号开头却未匹配完整格式，视为无效指令。
    if (value.startsWith("[") || value.startsWith("【")) return null;
  }

  if (!value) return null;

  if (/^\d+$/.test(value)) {
    return {
      kind: "id",
      value,
      trigger: command.trigger,
      ...(command.priority ? { priority: true, minFanLevel: command.minFanLevel } : {}),
      payload: { id: value },
    };
  }

  return {
    kind: "song",
    value,
    trigger: command.trigger,
    searchStrategy: command.searchStrategy,
    ...(command.priority ? { priority: true, minFanLevel: command.minFanLevel } : {}),
    payload: { song: value, searchStrategy: command.searchStrategy },
  };
}
