import { test, expect } from "@playwright/test";
for (const condition of ["paired", "single"] as const) {
  test(`complete ${condition} round from landing, including refresh and keyboard play`, async ({ page, context }) => {
    await page.addInitScript(() => {
      Object.defineProperty(navigator, "share", {
        configurable: true, value: async () => {

        }
      });

    });
    const browserErrors: string[] = [];
    page.on("pageerror", e => browserErrors.push(e.message));
    // Retry real random assignments in the disposable DB; no test bypass ships in the app.
    await page.route("**/api/sessions", async (route) => {
      if (route.request().method() !== "POST")
        return route.continue();
      for (let i = 0; i < 20; i++) {
        const response = await route.fetch();
        expect(response.ok()).toBe(true);
        const session = await response.json();
        if (session.condition === condition)
          return route.fulfill({ response });

      }
      throw new Error("Could not obtain the randomly assigned condition after 20 attempts.");

    });
    await page.goto("/");
    await page.getByRole("link", { name: "Start the hunt" }).click();
    // Pilot status comes from the URL; the normal landing navigation is exercised first.
    await page.goto("/play?pilot=1");
    const start = page.getByRole("button", { name: "Start the hunt" });
    await expect(start).toBeDisabled();
    await page.getByRole("checkbox", { name: "I am 18 or older" }).check();
    await expect(start).toBeDisabled();
    await page.getByRole("checkbox", { name: "I agree to take part" }).check();
    await start.click();
    await expect(page.getByRole("button", { name: "Skip", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Skip", exact: true }).click();
    await expect(page.locator(".question-block h1")).toBeVisible();
    const total = Number(await page.locator("progress").getAttribute("max"));
    expect(total).toBeGreaterThan(0);
    for (let position = 1; position <= total; position++) {
      await expect(page.locator("progress")).toHaveAttribute("value", String(position));
      if (position === 2) {
        await page.reload();
        await expect(page.locator("progress")).toHaveAttribute("value", "2");

      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.keyboard.press(condition === "paired" ? "a" : "y");
      await expect(page.getByRole("heading", { name: "How confident are you?" })).toBeFocused();
      // Confidence deliberation must not extend the response time recorded at choice.
      await page.waitForTimeout(100);
      const sent = page.waitForRequest(r => r.url().endsWith("/api/guesses") && r.method() === "POST");
      await page.keyboard.press("3");
      const payload = (await sent).postDataJSON();
      expect(payload.confidence).toBe(3);
      expect(payload).not.toHaveProperty("score");
      await expect(page.locator(".reveal")).toBeVisible();
      await expect(page.locator(".reveal mark")).not.toBeEmpty();
      await page.keyboard.press("Enter");

    }
    await expect(page.getByRole("heading", { name: "Good eye, human." })).toBeVisible();
    await expect(page.getByText("A little gut check")).toBeVisible();
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await page.getByRole("button", { name: "Share your score" }).click();
    const copied = await page.evaluate(() => navigator.clipboard.readText());
    expect(copied).toMatch(/\/share\?score=\d+&total=\d+$/);
    expect(copied).not.toContain("session");
    for (const path of ["/about", "/privacy", "/leaderboard", "/share?score=8&total=10"]) {
      await page.goto(path);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);

    }
    await expect(page.locator('meta[property="og:image"]')).toHaveAttribute("content", /share\/image\?score=8&total=10/);
    const og = await page.request.get("/share/image?score=8&total=10");
    expect(og.status()).toBe(200);
    expect(og.headers()["content-type"]).toContain("image/png");
    expect(browserErrors).toEqual([]);

  });
}
