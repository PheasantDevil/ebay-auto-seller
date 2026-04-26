/**
 * Capture Research UI screenshots for docs (requires `apps/web` dev server, e.g. `npm run dev`).
 *
 * Usage:
 *   cd docs/scripts && npm install && node capture-research-screenshots.mjs
 *
 * Env: WEB_BASE_URL (default http://localhost:3001), CHROME_PATH, DEMO_TENANT_ID
 */
import { mkdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer-core";

const CHROME =
  process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const BASE = process.env.WEB_BASE_URL ?? "http://localhost:3001";
const OUT_DIR = join(dirname(fileURLToPath(import.meta.url)), "../images");

const tenant =
  process.env.DEMO_TENANT_ID ?? "11111111-1111-1111-1111-111111111111";

await mkdir(OUT_DIR, { recursive: true });

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  args: ["--no-sandbox", "--window-size=1280,900"],
});
const page = await browser.newPage();
await page.setViewport({ width: 1280, height: 900 });

await page.goto(`${BASE}/research?tenant_id=${encodeURIComponent(tenant)}`, {
  waitUntil: "domcontentloaded",
  timeout: 60000,
});
await page.waitForSelector("button.button", { timeout: 30000 });
await page.screenshot({
  path: join(OUT_DIR, "research-tenant-entered.png"),
  fullPage: true,
});

await page.click("button.button");
await Promise.race([
  page.waitForResponse((r) => r.url().includes("candidates"), { timeout: 20000 }),
  page.waitForSelector("p.error", { timeout: 20000 }),
  page.waitForSelector(".list .card", { timeout: 20000 }),
  new Promise((r) => setTimeout(r, 20000)),
]).catch(() => {});
await new Promise((r) => setTimeout(r, 600));
await page.screenshot({
  path: join(OUT_DIR, "research-after-load.png"),
  fullPage: true,
});

await browser.close();
console.log(
  "Wrote:",
  join(OUT_DIR, "research-tenant-entered.png"),
  join(OUT_DIR, "research-after-load.png"),
);
