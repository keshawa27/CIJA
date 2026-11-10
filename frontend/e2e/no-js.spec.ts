import { expect, test } from "@playwright/test";

// A form submitted before its JavaScript has loaded (or with JavaScript off) must never
// put what was typed into the URL, where it would sit in the browser history.
test.use({ javaScriptEnabled: false });

test("sign-in without JavaScript keeps the password out of the URL", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("someone@example.com");
  await page.getByLabel("Password").fill("not-a-real-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForLoadState();
  expect(page.url()).not.toContain("password");
  expect(page.url()).not.toContain("someone");
});

test("intake without JavaScript keeps the client's details out of the URL", async ({ page }) => {
  await page.goto("/intake");
  await page.getByLabel("First name").fill("Private");
  await page.getByLabel("Last name").fill("Person");
  await page.getByLabel("Email", { exact: true }).fill("private.person@example.com");
  await page.getByLabel(/Staying safe online/).check();
  await page.getByLabel(/I agree to Vela collecting/).check();
  await page.getByRole("button", { name: "Send my request" }).click();
  await page.waitForLoadState();
  expect(page.url()).not.toContain("Private");
  expect(page.url()).not.toContain("private.person");
});
