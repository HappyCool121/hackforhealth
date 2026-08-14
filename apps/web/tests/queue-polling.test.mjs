import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const queueSource = readFileSync(
  fileURLToPath(new URL("../app/clinic/queue/page.tsx", import.meta.url)),
  "utf8",
);

test("clinic queue refreshes while the page is visible", () => {
  assert.match(queueSource, /setInterval\(refreshVisibleQueue, 2000\)/);
  assert.match(queueSource, /document\.visibilityState === "visible"/);
  assert.match(queueSource, /removeEventListener\("visibilitychange"/);
});
