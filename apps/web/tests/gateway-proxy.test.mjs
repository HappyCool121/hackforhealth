import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const route = readFileSync(new URL("../app/api/[...path]/route.ts", import.meta.url), "utf8");
const nextConfig = readFileSync(new URL("../next.config.ts", import.meta.url), "utf8");

test("same-origin API route injects the private backend gateway secret", () => {
  assert.match(route, /process\.env\.BACKEND_GATEWAY_SECRET/);
  assert.match(route, /headers\.set\("x-clinicpass-gateway", gatewaySecret\)/);
  assert.match(route, /request\.arrayBuffer\(\)/);
  assert.doesNotMatch(nextConfig, /rewrites\(\)/);
});

test("gateway proxy preserves every API method used by the application", () => {
  for (const method of ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]) {
    assert.match(route, new RegExp(`export const ${method} = proxyRequest`));
  }
});
