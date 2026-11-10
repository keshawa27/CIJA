import { defineConfig } from "@playwright/test";

// Expects the whole stack to be running already (see the README): database,
// Mailpit, the API on :8000 and this app on :3000, with the seed data loaded.
export default defineConfig({
  testDir: "e2e",
  timeout: 90_000,
  use: { baseURL: "http://localhost:3000", trace: "retain-on-failure" },
});
