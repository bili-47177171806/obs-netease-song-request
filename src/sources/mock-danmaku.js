import { EventEmitter } from "node:events";
import readline from "node:readline";

export class MockDanmakuSource extends EventEmitter {
  constructor({
    input = process.stdin,
    output = process.stdout,
    user = process.env.MOCK_DANMAKU_USER || "模拟用户",
    fanLevel = Number(process.env.MOCK_DANMAKU_FAN_LEVEL || 0),
  } = {}) {
    super();
    this.input = input;
    this.output = output;
    this.user = user;
    this.fanLevel = Number.isFinite(fanLevel) ? fanLevel : 0;
    this.reader = null;
  }

  start() {
    this.reader = readline.createInterface({
      input: this.input,
      output: this.output,
      terminal: Boolean(this.input.isTTY),
      prompt: "弹幕> ",
    });
    this.reader.on("line", (line) => {
      const fanCommand = line.trim().match(/^:fan\s+(\d+)$/u);
      if (fanCommand) {
        this.fanLevel = Number(fanCommand[1]);
        this.output.write(`[模拟弹幕] 粉丝团等级已设为 ${this.fanLevel}\n`);
        this.reader.prompt();
        return;
      }
      if (line.trim() === ":quit") {
        this.close();
        return;
      }
      this.emit("message", {
        user: this.user,
        fanLevel: this.fanLevel,
        text: line,
        receivedAt: new Date(),
      });
      this.reader.prompt();
    });
    this.reader.on("close", () => this.emit("close"));
    this.reader.prompt();
  }

  close() {
    this.reader?.close();
  }
}
