import { expect, test } from "@playwright/test";

test("Member cannot discover lead or PM actions and backend denies overview", async ({ page, request }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Project Assistant" })).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to main content" })).toBeFocused();
  await expect(page.getByRole("main")).toBeVisible();
  await expect(page.getByRole("button", { name: "Daily update", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Team overview", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Team weekly", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Team settings", exact: true })).toHaveCount(0);

  const response = await request.get(`/api/v1/teams/team-ops/overview`, {
    headers: { "X-Dev-User-ID": "user-member-1" },
  });
  expect(response.status()).toBe(403);
  await expect(response.json()).resolves.toMatchObject({ code: "FORBIDDEN" });
});
