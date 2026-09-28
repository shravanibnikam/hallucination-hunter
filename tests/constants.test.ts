import { expect, test } from "vitest";
import { ROUND_LENGTH, TOO_FAST_MS } from "@/lib/constants";
test("study defaults are explicit", () => { expect(ROUND_LENGTH).toBe(10); expect(TOO_FAST_MS).toBe(1500); });
