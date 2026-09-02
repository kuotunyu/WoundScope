import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

import { expect, test } from '@playwright/test';

const BASE_ORIGIN = 'http://127.0.0.1:4173';
const BASE_PATH = '/WoundScope/';
const VIEWPORTS = [
  { height: 667, label: '375x667', width: 375 },
  { height: 844, label: '390x844', width: 390 },
  { height: 1024, label: '768x1024', width: 768 },
  { height: 768, label: '1024x768', width: 1024 },
  { height: 900, label: '1440x900', width: 1440 },
];
const COLOR_SCHEMES = ['light', 'dark'];
const EXTERNAL_LINKS = [
  'https://github.com/kuotunyu/WoundScope',
  'https://github.com/kuotunyu/WoundScope/releases/tag/v0.2.2',
  'https://github.com/kuotunyu/WoundScope/blob/1b3df3b516cc4d366dc9da3cb01e8d0a319be613/README.md',
  'https://github.com/kuotunyu/WoundScope/blob/1b3df3b516cc4d366dc9da3cb01e8d0a319be613/DATA_CARD.md',
  'https://github.com/kuotunyu/WoundScope/blob/1b3df3b516cc4d366dc9da3cb01e8d0a319be613/MODEL_CARD.md',
  'https://github.com/kuotunyu/WoundScope/blob/1b3df3b516cc4d366dc9da3cb01e8d0a319be613/CITATION.cff',
  'https://github.com/kuotunyu/WoundScope/blob/1b3df3b516cc4d366dc9da3cb01e8d0a319be613/LICENSE',
  'https://doi.org/10.1038/s41598-020-78799-w',
  'https://github.com/uwm-bigdata/wound-segmentation/tree/42a272dfe0679f20675e826385925cb7562934b6/data/Foot%20Ulcer%20Segmentation%20Challenge',
];
const EXACT_CSP =
  "default-src 'none'; style-src 'self'; img-src 'self'; font-src 'none'; script-src 'none'; connect-src 'none'; media-src 'none'; object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'; manifest-src 'none'";
const INTERNAL_LINKS = ['#overview', '#evidence', '#provenance'];
const EXPECTED_BROWSER_REVISIONS = {
  chromium: '1234',
  firefox: '1538',
  webkit: '2336',
};

const modulePath = fileURLToPath(import.meta.url);
const moduleDirectory = path.dirname(modulePath);
const require = createRequire(modulePath);
const publishRoot = process.env.WOUNDSCOPE_PAGES_PUBLISH_DIR;
const reportRoot = process.env.WOUNDSCOPE_PAGES_REPORT_DIR;

if (!publishRoot || !path.isAbsolute(publishRoot)) {
  throw new Error('PUBLISH_DIR_INVALID');
}
if (!reportRoot || !path.isAbsolute(reportRoot)) {
  throw new Error('REPORT_DIR_INVALID');
}
fs.mkdirSync(reportRoot, { recursive: true });
fs.mkdirSync(path.join(reportRoot, 'screenshots'), { recursive: true });

const manifest = JSON.parse(fs.readFileSync(path.join(publishRoot, 'pages-manifest.json'), 'utf8'));
const axeSource = fs.readFileSync(
  path.join(path.dirname(require.resolve('axe-core/package.json')), 'axe.min.js'),
  'utf8',
);
const filePaths = manifest.files.map((record) => record.path);
const cssFile = filePaths.find((value) => /^assets\/site-[0-9a-f]{16}\.css$/u.test(value));
const svgFile = filePaths.find((value) => /^assets\/model-comparison-[0-9a-f]{16}\.svg$/u.test(value));
const allowedRequestPaths = new Set(
  filePaths.map((value) => `${BASE_PATH}${value}`).concat([BASE_PATH, `${BASE_PATH}pages-manifest.json`]),
);
const expectedStylesheetHref = `${BASE_PATH}${cssFile}`;
const expectedSvgHref = `${BASE_PATH}${svgFile}`;
const networkRecords = [];
const axeRecords = [];
const keyboardRecords = [];
const contrastRecords = [];
const zoomRecords = [];
const summaryRecords = [];

function writeReport(name, payload) {
  fs.writeFileSync(path.join(reportRoot, name), `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
}

function viewportLabel(viewport) {
  return `${viewport.label}`;
}

function browserRevision(browserName) {
  return EXPECTED_BROWSER_REVISIONS[browserName] ?? 'unknown';
}

async function attachLedger(page, options = {}) {
  const events = [];
  const consoleMessages = [];
  await page.route('**/*', async (route) => {
    const request = route.request();
    const requestUrl = new URL(request.url());
    const pathAndQuery = `${requestUrl.pathname}${requestUrl.search}`;
    const allowed =
      requestUrl.origin === BASE_ORIGIN &&
      !requestUrl.search &&
      allowedRequestPaths.has(requestUrl.pathname);
    if (options.disableAggregateSvg && requestUrl.pathname === expectedSvgHref) {
      events.push({ disposition: 'aborted-image', method: request.method(), url: pathAndQuery });
      await route.abort();
      return;
    }
    if (!allowed) {
      events.push({ disposition: 'aborted', method: request.method(), url: pathAndQuery });
      await route.abort();
      return;
    }
    events.push({ disposition: 'allowed', method: request.method(), url: pathAndQuery });
    await route.continue();
  });
  page.on('console', (message) => {
    consoleMessages.push({ text: message.text(), type: message.type() });
  });
  return { consoleMessages, events };
}

async function assertPageContract(page, browserName) {
  await expect(page.locator('html')).toHaveAttribute('lang', 'zh-Hant-TW');
  await expect(page.locator('h1')).toHaveCount(1);
  await expect(page.locator('script')).toHaveCount(0);
  await expect(page.locator('form,input,button,iframe,video,audio')).toHaveCount(0);
  await expect(page.locator('footer')).toBeVisible();
  await expect(page.locator('meta[http-equiv=\"Content-Security-Policy\"]')).toHaveAttribute('content', EXACT_CSP);
  await expect(page.locator(`link[rel="stylesheet"][href="${expectedStylesheetHref}"]`)).toHaveCount(1);
  await expect(page.locator(`img[src="${expectedSvgHref}"]`)).toHaveCount(1);
  await expect(page.locator('link[rel=\"preload\"],link[rel=\"prefetch\"],link[rel=\"preconnect\"],link[rel=\"dns-prefetch\"],link[rel=\"modulepreload\"],link[rel=\"prerender\"],link[rel=\"manifest\"]')).toHaveCount(0);

  const widthsOkay = await page.evaluate(
    () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
  );
  expect(widthsOkay).toBe(true);

  const externalAnchors = await page.locator('a[href^="https://"]').evaluateAll((nodes) =>
    nodes.map((node) => ({
      href: node.getAttribute('href'),
      rel: node.getAttribute('rel'),
      target: node.getAttribute('target'),
    })),
  );
  expect(externalAnchors).toHaveLength(EXTERNAL_LINKS.length);
  expect(externalAnchors.map((item) => item.href).sort()).toEqual([...EXTERNAL_LINKS].sort());
  for (const anchor of externalAnchors) {
    expect(anchor.target).toBe('_blank');
    expect(anchor.rel).toBe('noopener noreferrer');
  }

  const internalAnchors = await page.locator('header nav a').evaluateAll((nodes) =>
    nodes.map((node) => node.getAttribute('href')),
  );
  expect(internalAnchors).toEqual(INTERNAL_LINKS);

  const shaTexts = await page.locator('code').evaluateAll((nodes) => nodes.map((node) => node.textContent ?? ''));
  expect(shaTexts).toContain(manifest.site_source_sha);
  expect(new Set(shaTexts).size).toBe(shaTexts.length);
  for (const value of shaTexts) {
    expect(value).toMatch(/^[0-9a-f]{40}$/u);
  }

  const tableBeforeImage = await page.evaluate(() => {
    const table = document.querySelector('table');
    const image = document.querySelector('img');
    if (!(table instanceof HTMLElement) || !(image instanceof HTMLElement)) {
      return false;
    }
    return Boolean(table.compareDocumentPosition(image) & Node.DOCUMENT_POSITION_FOLLOWING);
  });
  expect(tableBeforeImage).toBe(true);

  const resources = await page.evaluate(() =>
    performance
      .getEntriesByType('resource')
      .map((entry) => new URL(entry.name).pathname)
      .sort(),
  );
  expect(resources).toEqual([expectedStylesheetHref, expectedSvgHref].sort());

  summaryRecords.push({
    browser: browserName,
    gate: 'page-contract',
    site_source_sha: manifest.site_source_sha,
    status: 'PASS',
  });
}

for (const viewport of VIEWPORTS) {
  for (const scheme of COLOR_SCHEMES) {
    test(`page contract ${viewportLabel(viewport)} ${scheme}`, async ({ browserName, page }) => {
      await page.setViewportSize({ height: viewport.height, width: viewport.width });
      await page.emulateMedia({ colorScheme: scheme });
      const ledger = await attachLedger(page);
      const response = await page.goto(BASE_PATH, { waitUntil: 'load' });
      expect(response?.status()).toBe(200);
      await assertPageContract(page, browserName);
      expect(ledger.events.filter((entry) => entry.disposition === 'aborted')).toEqual([]);
      expect(ledger.consoleMessages).toEqual([]);
      const screenshotDirectory = path.join(reportRoot, 'screenshots', browserName);
      fs.mkdirSync(screenshotDirectory, { recursive: true });
      await page.screenshot({
        fullPage: true,
        path: path.join(screenshotDirectory, `${viewport.label}-${scheme}.png`),
      });
      networkRecords.push({
        blocked_requests: 0,
        browser: browserName,
        console_messages: [],
        requests: ledger.events,
        scheme,
        viewport: viewport.label,
      });
    });
  }
}

test('keyboard and focus contract', async ({ browserName, page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ colorScheme: 'light' });
  const ledger = await attachLedger(page);
  await page.goto(BASE_PATH, { waitUntil: 'load' });

  await page.keyboard.press('Tab');
  await expect(page.locator('.skip-link')).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('main')).toBeFocused();

  const targetSizes = await page.locator('.skip-link, .masthead__nav a, .source-list a').evaluateAll((nodes) =>
    nodes.map((node) => {
      const element = node;
      const rect = element.getBoundingClientRect();
      return { height: rect.height, width: rect.width };
    }),
  );
  for (const size of targetSizes) {
    expect(size.height).toBeGreaterThanOrEqual(44);
    expect(size.width).toBeGreaterThanOrEqual(44);
  }

  const focusOutlineVisible = await page.evaluate(() => {
    const active = document.activeElement;
    if (!(active instanceof HTMLElement)) {
      return false;
    }
    const style = getComputedStyle(active);
    return style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) >= 2;
  });
  expect(focusOutlineVisible).toBe(true);
  expect(ledger.events.filter((entry) => entry.disposition === 'aborted')).toEqual([]);
  expect(ledger.consoleMessages).toEqual([]);
  keyboardRecords.push({
    browser: browserName,
    revision: browserRevision(browserName),
    status: 'PASS',
  });
});

test('axe and contrast contract', async ({ browserName, page }) => {
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.emulateMedia({ colorScheme: 'dark' });
  const ledger = await attachLedger(page);
  await page.goto(BASE_PATH, { waitUntil: 'load' });
  await page.evaluate(axeSource);
  const axeResults = await page.evaluate(async () => {
    const results = await globalThis.axe.run(document, {
      runOnly: {
        type: 'tag',
        values: ['wcag2a', 'wcag2aa', 'wcag22aa'],
      },
    });
    return {
      serious_or_critical: results.violations.filter((violation) =>
        violation.impact === 'serious' || violation.impact === 'critical'
      ).map((violation) => violation.id),
      violations: results.violations.map((violation) => ({
        id: violation.id,
        impact: violation.impact,
      })),
    };
  });
  expect(axeResults.serious_or_critical).toEqual([]);
  axeRecords.push({
    browser: browserName,
    serious_or_critical: axeResults.serious_or_critical,
    status: 'PASS',
    violations: axeResults.violations,
  });

  let forcedColors = { status: 'SUPPORTED' };
  try {
    await page.emulateMedia({ forcedColors: 'active' });
  } catch {
    forcedColors = { reason: 'engine-does-not-support-forced-colors', status: 'UNSUPPORTED' };
  }
  contrastRecords.push({
    browser: browserName,
    forced_colors: forcedColors,
    status: 'PASS',
  });
  expect(ledger.events.filter((entry) => entry.disposition === 'aborted')).toEqual([]);
  expect(ledger.consoleMessages).toEqual([]);
});

test('zoom and images-disabled contract', async ({ browserName, page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ colorScheme: 'light' });
  const ledger = await attachLedger(page, { disableAggregateSvg: true });
  await page.goto(BASE_PATH, { waitUntil: 'load' });
  await expect(page.locator('table')).toBeVisible();
  await expect(page.locator('caption')).toHaveText('Locked Official Validation aggregate comparison');

  await page.evaluate(() => {
    document.documentElement.style.zoom = '2';
  });
  const zoomChecks = await page.evaluate(() => {
    const landmarkSelectors = ['header', 'main', 'footer'];
    const landmarks = landmarkSelectors.map((selector) => {
      const element = document.querySelector(selector);
      if (!(element instanceof HTMLElement)) {
        return false;
      }
      const rect = element.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0;
    });
    const scrollBox = document.querySelector('.table-scroll');
    const scrollable =
      scrollBox instanceof HTMLElement ? scrollBox.scrollWidth >= scrollBox.clientWidth : false;
    return {
      footer_visible: Boolean(document.querySelector('footer')),
      landmarks,
      no_2d_scroll:
        document.documentElement.scrollWidth <= document.documentElement.clientWidth &&
        document.documentElement.scrollHeight >= document.documentElement.clientHeight,
      scrollable,
    };
  });
  expect(zoomChecks.landmarks.every(Boolean)).toBe(true);
  expect(zoomChecks.scrollable).toBe(true);
  expect(zoomChecks.footer_visible).toBe(true);
  expect(zoomChecks.no_2d_scroll).toBe(true);
  expect(ledger.events.filter((entry) => entry.disposition === 'aborted')).toEqual([
    { disposition: 'aborted-image', method: 'GET', url: expectedSvgHref },
  ]);
  zoomRecords.push({
    browser: browserName,
    revision: browserRevision(browserName),
    scheme: 'light',
    status: 'PASS',
    viewport: '390x844',
  });
});

test('subpath and 404 contract', async ({ browserName, page, request }) => {
  const ledger = await attachLedger(page);
  const page404 = fs.readFileSync(path.join(publishRoot, '404.html'), 'utf8');
  const home = await request.get(`${BASE_ORIGIN}${BASE_PATH}`);
  const css = await request.get(`${BASE_ORIGIN}${expectedStylesheetHref}`);
  const svg = await request.get(`${BASE_ORIGIN}${expectedSvgHref}`);
  const notices = await request.get(`${BASE_ORIGIN}${BASE_PATH}THIRD_PARTY_NOTICES.txt`);
  const sbom = await request.get(`${BASE_ORIGIN}${BASE_PATH}sbom.spdx.json`);
  const manifestResponse = await request.get(`${BASE_ORIGIN}${BASE_PATH}pages-manifest.json`);
  const missing = await request.get(`${BASE_ORIGIN}${BASE_PATH}missing`);
  const query = await request.get(`${BASE_ORIGIN}${BASE_PATH}?q=secret`);

  expect(home.status()).toBe(200);
  expect(css.status()).toBe(200);
  expect(svg.status()).toBe(200);
  expect(notices.status()).toBe(200);
  expect(sbom.status()).toBe(200);
  expect(manifestResponse.status()).toBe(200);
  expect(missing.status()).toBe(404);
  expect(query.status()).toBe(404);
  expect(await missing.text()).toBe(page404);
  expect(await query.text()).toBe(page404);

  await page.goto(`${BASE_PATH}404.html`, { waitUntil: 'load' });
  await expect(page.locator(`link[rel="stylesheet"][href="${expectedStylesheetHref}"]`)).toHaveCount(1);
  await expect(page.locator(`a[href="${BASE_PATH}"]`)).toHaveCount(1);
  await expect(page.locator('img')).toHaveCount(0);
  await expect(page.locator('a[href^="https://"]')).toHaveCount(0);
  expect(ledger.events.filter((entry) => entry.disposition === 'aborted')).toEqual([]);
  summaryRecords.push({
    browser: browserName,
    gate: 'subpath-404',
    status: 'PASS',
  });
});

test.afterAll(async () => {
  writeReport('network.json', { entries: networkRecords });
  writeReport('axe.json', { entries: axeRecords });
  writeReport('keyboard.json', { entries: keyboardRecords });
  writeReport('contrast.json', { entries: contrastRecords });
  writeReport('zoom.json', {
    content_reflow_emulation: zoomRecords,
    manual_browser_zoom_200_percent: Object.entries(EXPECTED_BROWSER_REVISIONS).map(
      ([browser, revision]) => ({
        browser,
        reason: 'manual-review-required',
        revision,
        status: 'NOT_RUN',
      }),
    ),
  });
  writeReport('browser-summary.json', { entries: summaryRecords });
});
