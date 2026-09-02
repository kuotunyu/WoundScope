import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const EXPECTED_NODE_VERSION = '24.16.0';
const EXPECTED_PNPM_VERSION = '11.16.0';
const EXPECTED_BROWSER_VERSIONS = {
  chromium: { revision: '1234', version: '151.0.7922.34' },
  firefox: { revision: '1538', version: '153.0' },
  webkit: { revision: '2336', version: '26.5' },
};
const EXPECTED_PACKAGES = {
  '@playwright/test': {
    integrity: 'sha512-DTcUc8qii+cpHvtOwggMtBRMjKZHXYWdw8syRYu2vtzuq4Wxphqq4NfCs5Zt44L6mA8rfDfj+PHnxFc/FeK6mQ==',
    license: 'Apache-2.0',
    scope: 'build-review-only',
    version: '1.62.1',
  },
  'axe-core': {
    integrity: 'sha512-UzGt8zg7Ny8djbYMhxl2zuEevVa7r2gJjYY5Lwr1xM7+XU2nd6CkIWFTVcCIbAP63vSz71NaVyyuSk9lHKcy0A==',
    license: 'MPL-2.0',
    scope: 'build-review-only',
    version: '4.13.0',
  },
  'fsevents': {
    integrity: 'sha512-xiqMQR4xAeHTuB9uWm+fFRcIOgKBMiOBP+eXiyT7jsgVCq1bkVygt00oASowB7EdtpOHaaPgKt812P9ab+DDKA==',
    license: 'MIT',
    optional: true,
    scope: 'build-review-only',
    version: '2.3.2',
  },
  'playwright': {
    integrity: 'sha512-0M+L3LAD8/nm554LOla9Ayx0j0tmFZ0FBcoQ7F1VuVHpM/XpiC8RcDzBQB8W5+hA8L22THxELzeF+2WcUzvcLg==',
    license: 'Apache-2.0',
    scope: 'build-review-only',
    version: '1.62.1',
  },
  'playwright-core': {
    integrity: 'sha512-wPYSwEBJY9GHraISXqyqtx0na0LpO3XEX7jNDhntbex7tzUS7kLnZsOlFruFJB4Hi/rhDMjXGqHewDZ68nYZVw==',
    license: 'Apache-2.0',
    scope: 'build-review-only',
    version: '1.62.1',
  },
};

function fail(code) {
  throw new Error(code);
}

function sha256(payload) {
  return crypto.createHash('sha256').update(payload).digest('hex');
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function ensureDirectory(directoryPath) {
  if (!directoryPath || !path.isAbsolute(directoryPath)) {
    fail('REPORT_DIR_INVALID');
  }
  fs.mkdirSync(directoryPath, { recursive: true });
}

async function main() {
  const modulePath = fileURLToPath(import.meta.url);
  const moduleDirectory = path.dirname(modulePath);
  const require = createRequire(modulePath);
  const reportRoot = process.env.WOUNDSCOPE_PAGES_REPORT_DIR;
  const packagePath = path.join(moduleDirectory, 'package.json');
  const lockfilePath = path.join(moduleDirectory, 'pnpm-lock.yaml');

  ensureDirectory(reportRoot);

  if (process.version !== `v${EXPECTED_NODE_VERSION}`) {
    fail('NODE_VERSION');
  }

  const userAgent = process.env.npm_config_user_agent ?? '';
  const pnpmMatch = userAgent.match(/(?:^|\s)pnpm\/([^\s]+)/u);
  if (!pnpmMatch || pnpmMatch[1] !== EXPECTED_PNPM_VERSION) {
    fail('PNPM_VERSION');
  }

  const packagePayload = readJson(packagePath);
  if (packagePayload.packageManager !== `pnpm@${EXPECTED_PNPM_VERSION}`) {
    fail('PACKAGE_MANAGER');
  }

  const lockfileBytes = fs.readFileSync(lockfilePath);
  const playwrightTestPackage = fs.realpathSync(
    require.resolve('@playwright/test/package.json'),
  );
  const playwrightTestRequire = createRequire(playwrightTestPackage);
  const playwrightPackage = fs.realpathSync(
    playwrightTestRequire.resolve('playwright/package.json'),
  );
  const playwrightRequire = createRequire(playwrightPackage);
  const packageResolvers = {
    '@playwright/test': require,
    'axe-core': require,
    'fsevents': playwrightRequire,
    'playwright': playwrightTestRequire,
    'playwright-core': playwrightRequire,
  };
  const packageRecords = {};
  for (const [name, expected] of Object.entries(EXPECTED_PACKAGES)) {
    let manifestPath;
    try {
      manifestPath = packageResolvers[name].resolve(`${name}/package.json`);
    } catch (error) {
      if (expected.optional) {
        packageRecords[name] = {
          installed: false,
          integrity: expected.integrity,
          license: expected.license,
          optional: true,
          scope: expected.scope,
          version: expected.version,
        };
        continue;
      }
      throw error;
    }
    const manifest = readJson(manifestPath);
    if (manifest.version !== expected.version) {
      fail('PACKAGE_VERSION');
    }
    if (manifest.license !== expected.license) {
      fail('PACKAGE_LICENSE');
    }
    packageRecords[name] = {
      installed: true,
      integrity: expected.integrity,
      license: manifest.license,
      optional: Boolean(expected.optional),
      scope: expected.scope,
      version: manifest.version,
    };
  }

  const playwright = playwrightTestRequire('playwright');
  const playwrightCorePackage = playwrightRequire.resolve('playwright-core/package.json');
  const browsersJsonPath = path.join(path.dirname(playwrightCorePackage), 'browsers.json');
  const browsersPayload = readJson(browsersJsonPath);
  const browserEntries = {};
  for (const entry of browsersPayload.browsers) {
    if (entry && typeof entry.name === 'string' && entry.name in EXPECTED_BROWSER_VERSIONS) {
      browserEntries[entry.name] = entry;
    }
  }

  const executableLookup = {
    chromium: playwright.chromium.executablePath(),
    firefox: playwright.firefox.executablePath(),
    webkit: playwright.webkit.executablePath(),
  };
  const browserRecords = {};
  for (const [name, expected] of Object.entries(EXPECTED_BROWSER_VERSIONS)) {
    const entry = browserEntries[name];
    if (!entry) {
      fail('BROWSER_MISSING');
    }
    if (String(entry.revision) !== expected.revision || String(entry.browserVersion) !== expected.version) {
      fail('BROWSER_REVISION');
    }
    const executablePath = executableLookup[name];
    const executablePresent = Boolean(executablePath) && fs.existsSync(executablePath);
    if (!executablePresent) {
      fail('BROWSER_EXECUTABLE');
    }
    browserRecords[name] = {
      executable_path_present: executablePresent,
      revision: String(entry.revision),
      version: String(entry.browserVersion),
    };
  }

  const output = {
    browsers: browserRecords,
    lockfile_sha256: sha256(lockfileBytes),
    node: {
      path: process.execPath,
      version: process.version.slice(1),
    },
    packages: packageRecords,
    pnpm: {
      license: 'MIT',
      scope: 'build-review-only',
      version: pnpmMatch[1],
    },
  };
  fs.writeFileSync(
    path.join(reportRoot, 'toolchain.json'),
    `${JSON.stringify(output, null, 2)}\n`,
    'utf8',
  );
}

await main();
