import { expect, test } from "vitest";
import { createLimiter } from "@/lib/rate-limit";
import { body, endpoint } from "@/lib/http";
import { sessionSchema } from "@/lib/schemas";
test("limits isolate keys, expire without timers, and bound memory", () => {
  const limit = createLimiter(2);
  limit("a", 1, 1000, 0);
  expect(() => limit("a", 1, 1000, 1)).toThrow("Too many");
  limit("b", 1, 1000, 0);
  expect(() => limit("c", 1, 1000, 0)).toThrow("busy");
  expect(() => limit("a", 1, 1000, 1001)).not.toThrow();
});
test("API errors are JSON without stack traces", async () => {
  for (const request of [new Request("http://local", { method: "POST", body: "{" }), new Request("http://local", { method: "POST", body: JSON.stringify({ consent: false, ageConfirmed: true }) })]) {
    const response = await endpoint(async () => Response.json(await body(request, sessionSchema)));
    expect(response.status).toBe(400);
    expect(Object.keys(await response.json())).toEqual(["error"]);
  }
  const response = await endpoint(async () => {
    throw new Error("private secret");

  });
  expect(response.status).toBe(500);
  expect(JSON.stringify(await response.json())).not.toContain("private secret");
});
test("body size is enforced even without a Content-Length header", async () => {
  const response = await endpoint(async () => Response.json(await body(new Request("http://local", { method: "POST", body: "x".repeat(9000) }), sessionSchema)));
  expect(response.status).toBe(413);
});
