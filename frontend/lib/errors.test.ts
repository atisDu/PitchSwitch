import assert from "node:assert/strict";
import { test } from "node:test";

import { ApiError } from "./api.ts";
import { describeError } from "./errors.ts";

test("raw Cala 422 for a bad ID reads as 'not found', raw text kept", () => {
  const raw = 'data source unavailable: Cala POST /entities/not-a-real-id failed (422): {"response_type":"ERROR"}';
  const e = describeError(new ApiError(raw, 502));
  assert.equal(e.notFound, true);
  assert.equal(e.message, "That link doesn't point to a company or investor in Cala.");
  assert.equal(e.detail, raw);
});

test("upstream failures say Cala didn't answer; plain messages pass through", () => {
  assert.match(describeError(new ApiError("data source unavailable: timeout", 502)).message, /Cala, our data source/);
  assert.equal(describeError(new ApiError("Pick a company first.", 400)).message, "Pick a company first.");
  assert.equal(describeError(new ApiError("No company with that ID.", 404)).notFound, true);
  assert.match(describeError(new ApiError("x", 0)).message, /Can't reach/);
  assert.equal(describeError(new Error("boom")).message, "Something went wrong.");
  assert.equal(describeError(new ApiError("CACHE_ONLY is on and GET /entities is not cached", 502)).notFound, true);
});
