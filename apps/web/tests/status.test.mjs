import test from "node:test";
import assert from "node:assert/strict";

function prettyStatus(status) {
  return status.toLowerCase().split("_").map((part) => part[0].toUpperCase() + part.slice(1)).join(" ");
}

test("renders machine status for people", () => {
  assert.equal(prettyStatus("APPROVED_FOR_CHECK_IN"), "Approved For Check In");
});

