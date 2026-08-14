import { expect, test } from "@playwright/test";

test("patient journey labels simulation and in-person boundaries", async ({ page }) => {
  await page.goto("/patient/start");
  await expect(page.getByRole("heading", { name: "Let's get your details" })).toBeVisible();
  await expect(page.getByText("Simulation only", { exact: true })).toBeVisible();
  await expect(page.getByText(/original identity document.*checked.*in person/i)).toBeVisible();
  await page.getByRole("button", { name: /Continue with Singpass demo/ }).click();
  await expect(page.getByText("NOT REAL", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Simulate Singpass approval" }).click();
  await expect(page.getByRole("heading", { name: "Share synthetic details?" })).toBeVisible();
});
