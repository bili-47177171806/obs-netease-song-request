import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { once } from "node:events";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("模拟弹幕端到端触发点歌请求", { timeout: 10_000 }, async (t) => {
  const requests = [];
  const server = http.createServer((request, response) => {
    response.setHeader("Content-Type", "application/json; charset=utf-8");
    if (request.method === "GET") {
      response.end(JSON.stringify({ ok: true, service: "cloudmusic-cdp" }));
      return;
    }

    let raw = "";
    request.setEncoding("utf8");
    request.on("data", (chunk) => { raw += chunk; });
    request.on("end", () => {
      requests.push(JSON.parse(raw));
      response.end(JSON.stringify({ ok: true, songId: "123", name: "Test Song" }));
    });
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  t.after(() => server.close());

  const address = server.address();
  const child = spawn(process.execPath, ["src/index.js"], {
    cwd: PROJECT_ROOT,
    env: {
      ...process.env,
      CLOUDMUSIC_API_URL: `http://127.0.0.1:${address.port}`,
      CLOUDMUSIC_AUTO_START: "false",
      CLOUDMUSIC_TOAST: "false",
      DANMAKU_SOURCE: "mock",
    },
    stdio: ["pipe", "pipe", "pipe"],
  });
  let output = "";
  child.stdout.setEncoding("utf8");
  child.stderr.setEncoding("utf8");
  child.stdout.on("data", (chunk) => { output += chunk; });
  child.stderr.on("data", (chunk) => { output += chunk; });

  child.stdin.end("普通弹幕\n点歌[123]\n:quit\n");
  const [exitCode] = await once(child, "close");

  assert.equal(exitCode, 0, output);
  assert.deepEqual(requests, [{ id: "123" }]);
  assert.match(output, /已连接注入服务/u);
  assert.match(output, /成功：Test Song/u);
});
