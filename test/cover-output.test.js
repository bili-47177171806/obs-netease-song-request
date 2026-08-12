import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { once } from "node:events";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import sharp from "sharp";
import { CoverOutput } from "../src/outputs/cover-output.js";

test("writes the current cover image to the configured output path", async (t) => {
  const expected = Buffer.from([0xff, 0xd8, 0xff, 0xdb, 0x00, 0x43]);
  const server = http.createServer((_request, response) => {
    response.writeHead(200, { "Content-Type": "image/jpeg" });
    response.end(expected);
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  t.after(() => server.close());

  const directory = await mkdtemp(path.join(os.tmpdir(), "cloudmusic-cover-"));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const outputPath = path.join(directory, "nested", "cover.jpg");
  const address = server.address();
  const output = new CoverOutput({ outputPath, circlePath: null });

  const result = await output.update({
    coverUrl: `http://127.0.0.1:${address.port}/cover.jpg`,
  });

  assert.deepEqual(result, {
    written: true,
    path: path.resolve(outputPath),
    bytes: expected.length,
  });
  assert.deepEqual(await readFile(outputPath), expected);
});

test("creates a square cover variant at the player hole size without distortion", async (t) => {
  const source = await sharp({
    create: { width: 40, height: 20, channels: 3, background: { r: 230, g: 120, b: 80 } },
  }).jpeg().toBuffer();
  const directory = await mkdtemp(path.join(os.tmpdir(), "cloudmusic-cover-circle-"));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const output = new CoverOutput({
    outputPath: path.join(directory, "cover.jpg"),
    circlePath: path.join(directory, "cover-circle.jpg"),
    circleSize: 288,
    fetchImpl: async () => new Response(source, { status: 200 }),
  });

  const result = await output.update({ coverUrl: "https://example.test/cover.jpg" });
  const metadata = await sharp(result.circle.path).metadata();
  assert.equal(result.circle.written, true);
  assert.equal(metadata.width, 288);
  assert.equal(metadata.height, 288);
});

test("does nothing when the current track has no cover", async () => {
  const output = new CoverOutput({ outputPath: path.join(os.tmpdir(), "unused-cover.jpg") });
  assert.deepEqual(await output.update({ songId: "123" }), {
    written: false,
    reason: "no-cover",
  });
});
