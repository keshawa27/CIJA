import { expect, type Page, test } from "@playwright/test";

// The demo script from imp_plan.md section 14, as one test.
// Needs the seeded staff accounts; adds one synthetic intake per run.

const PASSWORD = process.env.SEED_PASSWORD ?? "demo-password-123";
const MAILPIT = "http://127.0.0.1:8025";

async function signIn(page: Page, email: string) {
  await page.context().clearCookies();
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
}

test("a client's request travels from the form to a closed case", async ({ page, request }) => {
  const clientEmail = `e2e-${Date.now()}@example.com`;

  // 1. A client in danger submits the form.
  await page.goto("/");
  await expect(page.getByRole("button", { name: /Quick exit/ })).toBeVisible();
  await page.getByRole("link", { name: "Start the form" }).click();
  await page.getByLabel("First name").fill("Eden");
  await page.getByLabel("Last name").fill("Testcase");
  await page.getByLabel("Email", { exact: true }).fill(clientEmail);
  await page.getByLabel("Staying safe online and with technology").check();
  await page.getByLabel("I am worried about my safety right now").check();
  await page.getByLabel(/I agree to Vela collecting/).check();
  await page.getByRole("button", { name: "Send my request" }).click();
  const reference = (await page.locator("p.font-mono").innerText()).trim();
  expect(reference).toMatch(/^VELA-[A-Z0-9]{8}$/);

  // 2. They get a confirmation email that gives nothing away.
  await expect
    .poll(async () => {
      const found = await request.get(`${MAILPIT}/api/v1/search`, { params: { query: `to:${clientEmail}` } });
      return (await found.json()).messages[0]?.Subject;
    })
    .toBe(`We have received your request ${reference}`);

  // ...and can check on it with the code alone.
  await page.goto("/status");
  await page.getByLabel("Reference code").fill(reference);
  await page.getByRole("button", { name: "Check" }).click();
  await expect(page.getByRole("status")).toContainText("Received");

  // 3. The team lead sees it already triaged as urgent, with the reason, and assigned.
  await signIn(page, "lead@example.com");
  await page.getByRole("link", { name: new RegExp(reference) }).click();
  await expect(page.getByRole("heading", { name: "Eden Testcase" })).toBeVisible();
  await expect(page.getByText("Client reported an immediate safety concern")).toBeVisible();
  await expect(page.locator("#priority")).toHaveValue("urgent");
  const caseUrl = page.url();
  const assignedTo = (await page.getByText(/Assigned to/).innerText()).match(/Assigned to (\w+)/)![1];
  const caseworker = `${assignedTo.toLowerCase()}@example.com`;
  const otherCaseworker = ["casey", "jordan", "riley"].find((name) => !caseworker.startsWith(name)) + "@example.com";

  // 4. The caseworker works through every step. They cannot skip one.
  await signIn(page, caseworker);
  await page.goto(caseUrl);
  await expect(page.getByRole("button", { name: "Mark done" }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Skip…" })).toHaveCount(0);
  const closed = page.getByText("All steps finished. This case is closed.");
  while (!(await closed.isVisible())) {
    const done = page.waitForResponse((r) => r.url().includes("/complete") && r.ok());
    await page.getByRole("button", { name: "Mark done" }).first().click();
    await done;
    await expect(page.getByRole("button", { name: "Mark done" }).first().or(closed)).toBeEnabled();
  }
  await expect(page.getByText("Step completed: Book Digital Safety session")).toBeVisible();

  // 5. Another caseworker cannot open the case, even with the link.
  await signIn(page, otherCaseworker);
  await page.goto(caseUrl);
  await expect(page.locator("p.error")).toHaveText("Case not found");

  // 6. A manager sees the numbers and reference codes, but no names and no way in.
  await signIn(page, "manager@example.com");
  await page.getByLabel("Show closed").check();
  await expect(page.getByText(reference)).toBeVisible();
  await expect(page.getByText("Eden Testcase")).toHaveCount(0);
  await expect(page.getByRole("link", { name: new RegExp(reference) })).toHaveCount(0);

  // 7. Everything that happened is in the audit log.
  await signIn(page, "admin@example.com");
  await page.getByRole("link", { name: "Audit log" }).click();
  await page.getByLabel("Action").selectOption("stage.changed");
  await expect(page.getByText("to=closed").first()).toBeVisible();
});
