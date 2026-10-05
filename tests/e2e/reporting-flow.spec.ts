import { expect, test, type APIRequestContext } from "@playwright/test";

const today = (() => {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
})();
const currentMonday = (() => {
  const value = new Date(`${today}T12:00:00Z`);
  const day = value.getUTCDay() || 7;
  value.setUTCDate(value.getUTCDate() - day + 1);
  return value.toISOString().slice(0, 10);
})();

function headers(userId: string, action: string): Record<string, string> {
  return { "X-Dev-User-ID": userId, "Idempotency-Key": `e2e:${action}:${Date.now()}` };
}

async function createDailyIfNeeded(request: APIRequestContext, userId: string, teamId: string) {
  const history = await request.get(`/api/v1/daily-reports/history?teamId=${teamId}&dateFrom=${today}&dateTo=${today}`, { headers: headers(userId, "history") });
  expect(history.ok()).toBeTruthy();
  const used = new Set((await history.json() as Array<{ workItemId: string }>).map((report) => report.workItemId));
  const optionsResponse = await request.get(`/api/v1/daily-reports/options?teamId=${teamId}`, { headers: headers(userId, "options") });
  expect(optionsResponse.ok()).toBeTruthy();
  const options = await optionsResponse.json() as { workItems: Array<{ id: string; projectId: string }> };
  const item = options.workItems.find((candidate) => !used.has(candidate.id));
  expect(item, `an unused work item in ${teamId}`).toBeTruthy();
  const response = await request.post("/api/v1/daily-reports", {
    headers: headers(userId, `daily:${teamId}`),
    data: { teamId, projectId: item!.projectId, workItemId: item!.id, reportDate: today, status: "IN_PROGRESS", workSummary: `E2E evidence for ${teamId}`, blocker: null, nextAction: "Continue E2E verification" },
  });
  expect(response.ok()).toBeTruthy();
}

async function generateAndConfirm(request: APIRequestContext, userId: string, scope: "MEMBER" | "TEAM", teamId: string) {
  const generated = await request.post("/api/v1/weekly-reports/generate", { headers: headers(userId, `generate:${scope}:${teamId}`), data: { scope, teamId, teamIds: [], weekStart: currentMonday, subjectUserId: null } });
  expect(generated.ok()).toBeTruthy();
  const report = await generated.json() as { id: string };
  const confirmed = await request.post(`/api/v1/weekly-reports/${report.id}/confirm?teamId=${teamId}`, { headers: headers(userId, `confirm:${scope}:${teamId}`) });
  expect(confirmed.ok()).toBeTruthy();
}

test.describe.serial("standalone structured reporting", () => {
  test("Member records Daily evidence, sees exact History date, and confirms weekly", async ({ page, request }) => {
    const history = await request.get(`/api/v1/daily-reports/history?teamId=team-ops&dateFrom=${today}&dateTo=${today}`, { headers: headers("user-member-1", "find-daily") });
    const used = new Set((await history.json() as Array<{ workItemId: string }>).map((report) => report.workItemId));
    const options = await (await request.get("/api/v1/daily-reports/options?teamId=team-ops", { headers: headers("user-member-1", "options-ui") })).json() as { workItems: Array<{ id: string; projectId: string }> };
    const item = options.workItems.find((candidate) => !used.has(candidate.id));
    expect(item).toBeTruthy();

    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Project Assistant" })).toBeVisible();
    await page.locator('select[name="projectId"]').selectOption(item!.projectId);
    await page.locator('select[name="workItemId"]').selectOption(item!.id);
    await page.getByLabel("Work summary").fill("Implemented the E2E reporting path");
    await page.getByLabel("Next action").fill("Review the weekly evidence");
    await page.getByRole("button", { name: "Save daily update" }).click();
    await expect(page.getByText(`Saved ${item!.id} for ${today}.`)).toBeVisible();

    await page.getByRole("button", { name: "History" }).click();
    await expect(page.getByText(today).first()).toBeVisible();
    await expect(
      page.getByRole("listitem").filter({ hasText: item!.id }).getByText("Implemented the E2E reporting path"),
    ).toBeVisible();

    await page.getByRole("button", { name: "My weekly" }).click();
    await page.getByRole("button", { name: "Generate draft" }).click();
    await expect(page.getByRole("button", { name: "Confirm report" })).toBeVisible();
    await page.getByRole("button", { name: "Confirm report" }).click();
    await expect(page.getByRole("button", { name: "Create revision" })).toBeVisible();
  });

  test("Tech Lead reviews Team overview and confirms Team weekly", async ({ page }) => {
    await page.goto("/");
    await page.getByLabel("Demo identity").selectOption("user-lead");
    await page.getByRole("button", { name: "Team overview", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Team overview" })).toBeVisible();
    await page.getByRole("button", { name: "Team weekly", exact: true }).click();
    await page.getByRole("button", { name: "Generate draft" }).click();
    await page.getByRole("button", { name: "Confirm report" }).click();
    await expect(page.getByRole("button", { name: "Create revision" })).toBeVisible();
  });

  test("PM generates multi-Team report and explicitly approves publication", async ({ page, request }) => {
    await createDailyIfNeeded(request, "user-member-1", "team-platform");
    await generateAndConfirm(request, "user-member-1", "MEMBER", "team-platform");
    await generateAndConfirm(request, "user-lead", "TEAM", "team-platform");

    await page.goto("/");
    await page.getByLabel("Demo identity").selectOption("user-pm");
    await page.getByRole("button", { name: "Multi-team weekly" }).click();
    await page.getByRole("checkbox", { name: "Mock Ops Team" }).check();
    await page.getByRole("checkbox", { name: "Mock Platform Team" }).check();
    await page.getByRole("button", { name: "Generate multi-team draft" }).click();
    await page.getByRole("button", { name: "Confirm report" }).click();
    const publish = page.getByRole("button", { name: "Publish confirmed report" });
    await expect(publish).toBeDisabled();
    await page.getByPlaceholder("Captured Teams conversation ID").fill("e2e-personal-conversation");
    await page.getByRole("checkbox", { name: /I confirm this report/ }).check();
    await expect(publish).toBeEnabled();
    await publish.click();
    await expect(page.getByText(/^Published at/)).toBeVisible();
  });
});
