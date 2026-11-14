const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');
const { execSync } = require('child_process');

const EDGE_PATH = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const ROOT_DIR = path.resolve(__dirname, '..');
const SCREENSHOTS_DIR = path.join(ROOT_DIR, 'docs', 'screenshots');

if (!fs.existsSync(SCREENSHOTS_DIR)) {
  fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
}

// 1. Generate fresh session tokens from Python
console.log('Generating fresh test sessions...');
const pythonOutput = execSync('python scripts/generate_qa_sessions.py', {
  cwd: ROOT_DIR,
  env: { ...process.env, PYTHONPATH: '.' }
}).toString().trim();

const sessionTokens = JSON.parse(pythonOutput);
console.log('Generated session tokens:', {
  user_sid: sessionTokens.user_sid ? sessionTokens.user_sid.slice(0, 8) + '...' : null,
  admin_sid: sessionTokens.admin_sid ? sessionTokens.admin_sid.slice(0, 8) + '...' : null,
  sample_opp_id: sessionTokens.sample_opp_id
});

async function runFullQA() {
  console.log('Launching Edge for complete visual verification...');
  const browser = await puppeteer.launch({
    executablePath: EDGE_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu']
  });

  const report = [];

  // ==========================================
  // PART 1: PUBLIC PAGES
  // ==========================================
  const publicPages = [
    { id: 1, name: 'Homepage', url: 'http://localhost:5000/', filename: '01_homepage.png' },
    { id: 2, name: 'User Login', url: 'http://localhost:5000/login', filename: '02_user_login.png' },
    { id: 3, name: 'Registration', url: 'http://localhost:5000/register', filename: '03_registration.png' },
  ];

  const publicContext = await browser.createBrowserContext();
  for (const pageDef of publicPages) {
    console.log(`\n--- Inspecting [${pageDef.id}/15] ${pageDef.name} (${pageDef.url}) ---`);
    const page = await publicContext.newPage();
    await page.setViewport({ width: 1280, height: 800 });

    const consoleLogs = [];
    const pageErrors = [];
    page.on('console', msg => { if (msg.type() === 'error' || msg.type() === 'warn') consoleLogs.push(msg.text()); });
    page.on('pageerror', err => pageErrors.push(err.message));

    await page.goto(pageDef.url, { waitUntil: 'networkidle2', timeout: 15000 });
    await new Promise(r => setTimeout(r, 1500));

    const dom = await page.evaluate(() => ({
      title: document.title,
      headerText: document.querySelector('h1, h2')?.innerText || '',
      hasHorizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      navCount: document.querySelectorAll('nav a, aside a').length
    }));

    const dest = path.join(SCREENSHOTS_DIR, pageDef.filename);
    await page.screenshot({ path: dest, fullPage: true });
    console.log(`Saved: ${pageDef.filename} (${fs.statSync(dest).size} bytes)`);

    report.push({ ...pageDef, auth: 'public', dom, consoleLogs, pageErrors, size: fs.statSync(dest).size });
    await page.close();
  }
  await publicContext.close();

  // ==========================================
  // PART 2: USER AUTHENTICATED PAGES
  // ==========================================
  const userPages = [
    { id: 4, name: 'User Dashboard', url: 'http://localhost:5000/dashboard', filename: '04_user_dashboard.png' },
    { id: 5, name: 'Explore Opportunities', url: 'http://localhost:5000/opportunities', filename: '05_explore_opportunities.png' },
    { id: 6, name: 'Opportunity Details', url: `http://localhost:5000/opportunities/${sessionTokens.sample_opp_id}`, filename: '06_opportunity_details.png' },
    { id: 7, name: 'Saved Opportunities', url: 'http://localhost:5000/saved', filename: '07_saved_opportunities.png' },
    { id: 8, name: 'Notifications', url: 'http://localhost:5000/notifications', filename: '08_notifications.png' },
    { id: 9, name: 'User Profile', url: 'http://localhost:5000/profile', filename: '09_user_profile.png' },
  ];

  const userContext = await browser.createBrowserContext();
  const userAuthPage = await userContext.newPage();
  await userAuthPage.setViewport({ width: 1280, height: 800 });
  await userAuthPage.goto('http://localhost:5000/login', { waitUntil: 'networkidle2' });

  console.log('Authenticating user session...');
  await userAuthPage.evaluate(async () => {
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content;
    await fetch('/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json', 'X-CSRFToken': csrf },
      body: JSON.stringify({ username: 'test_e2e_user', password: 'E2ETestPassword2026!' })
    });
  });
  await userAuthPage.close();

  for (const pageDef of userPages) {
    console.log(`\n--- Inspecting [${pageDef.id}/15] ${pageDef.name} (${pageDef.url}) ---`);
    const page = await userContext.newPage();
    await page.setViewport({ width: 1280, height: 800 });

    const consoleLogs = [];
    const pageErrors = [];
    page.on('console', msg => { if (msg.type() === 'error' || msg.type() === 'warn') consoleLogs.push(msg.text()); });
    page.on('pageerror', err => pageErrors.push(err.message));

    await page.goto(pageDef.url, { waitUntil: 'networkidle2', timeout: 15000 });
    await new Promise(r => setTimeout(r, 1500));

    const dom = await page.evaluate(() => ({
      title: document.title,
      headerText: document.querySelector('h1, h2')?.innerText || '',
      hasHorizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      navCount: document.querySelectorAll('nav a, aside a').length
    }));

    const dest = path.join(SCREENSHOTS_DIR, pageDef.filename);
    await page.screenshot({ path: dest, fullPage: true });
    console.log(`Saved: ${pageDef.filename} (${fs.statSync(dest).size} bytes)`);

    report.push({ ...pageDef, auth: 'user', dom, consoleLogs, pageErrors, size: fs.statSync(dest).size });
    await page.close();
  }
  await userContext.close();

  // ==========================================
  // PART 3: ADMIN AUTHENTICATED PAGES
  // ==========================================
  const adminPages = [
    { id: 10, name: 'Admin Dashboard', url: 'http://localhost:5000/admin/dashboard', filename: '10_admin_dashboard.png' },
    { id: 11, name: 'Admin Collectors', url: 'http://localhost:5000/admin/collectors', filename: '11_admin_collectors.png' },
    { id: 12, name: 'Admin Data Quality', url: 'http://localhost:5000/admin/data-quality', filename: '12_admin_data_quality.png' },
    { id: 13, name: 'Admin Analytics', url: 'http://localhost:5000/admin/analytics', filename: '13_admin_analytics.png' },
    { id: 14, name: 'Admin Audit Logs', url: 'http://localhost:5000/admin/logs', filename: '14_admin_audit_logs.png' },
    { id: 15, name: 'Admin User Management', url: 'http://localhost:5000/admin/users', filename: '15_admin_users.png' },
  ];

  const adminContext = await browser.createBrowserContext();
  for (const pageDef of adminPages) {
    console.log(`\n--- Inspecting [${pageDef.id}/15] ${pageDef.name} (${pageDef.url}) ---`);
    const page = await adminContext.newPage();
    await page.setViewport({ width: 1280, height: 800 });

    await page.setCookie({
      name: 'cyberscout_session',
      value: sessionTokens.admin_sid,
      url: 'http://localhost:5000'
    });

    const consoleLogs = [];
    const pageErrors = [];
    page.on('console', msg => { if (msg.type() === 'error' || msg.type() === 'warn') consoleLogs.push(msg.text()); });
    page.on('pageerror', err => pageErrors.push(err.message));

    await page.goto(pageDef.url, { waitUntil: 'networkidle2', timeout: 15000 });
    await new Promise(r => setTimeout(r, 1500));

    const dom = await page.evaluate(() => ({
      title: document.title,
      headerText: document.querySelector('h1, h2')?.innerText || '',
      hasHorizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      navCount: document.querySelectorAll('nav a, aside a').length
    }));

    const dest = path.join(SCREENSHOTS_DIR, pageDef.filename);
    await page.screenshot({ path: dest, fullPage: true });
    console.log(`Saved: ${pageDef.filename} (${fs.statSync(dest).size} bytes)`);

    report.push({ ...pageDef, auth: 'admin', dom, consoleLogs, pageErrors, size: fs.statSync(dest).size });
    await page.close();
  }
  await adminContext.close();

  // ==========================================
  // PART 4: MOBILE RESPONSIVE TESTS
  // ==========================================
  console.log('\n--- Running Mobile Responsive Tests (375x812) ---');
  const mobilePages = [
    { name: 'Homepage (Mobile)', url: 'http://localhost:5000/', auth: 'none', filename: '01_homepage_mobile.png' },
    { name: 'User Dashboard (Mobile)', url: 'http://localhost:5000/dashboard', auth: 'user', filename: '04_user_dashboard_mobile.png' },
    { name: 'Admin Dashboard (Mobile)', url: 'http://localhost:5000/admin/dashboard', auth: 'admin', filename: '10_admin_dashboard_mobile.png' }
  ];

  for (const mDef of mobilePages) {
    const mPage = await browser.newPage();
    await mPage.setViewport({ width: 375, height: 812, isMobile: true, hasTouch: true });

    if (mDef.auth === 'user') {
      await mPage.setCookie({ name: 'cyberscout_session', value: sessionTokens.user_sid, url: 'http://localhost:5000' });
    } else if (mDef.auth === 'admin') {
      await mPage.setCookie({ name: 'cyberscout_session', value: sessionTokens.admin_sid, url: 'http://localhost:5000' });
    }

    await mPage.goto(mDef.url, { waitUntil: 'networkidle2', timeout: 15000 });
    await new Promise(r => setTimeout(r, 1500));

    const overflow = await mPage.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    const mDest = path.join(SCREENSHOTS_DIR, mDef.filename);
    await mPage.screenshot({ path: mDest, fullPage: true });
    console.log(`Saved Mobile: ${mDef.filename} | Overflow: ${overflow} (${fs.statSync(mDest).size} bytes)`);

    await mPage.close();
  }

  await browser.close();

  const reportPath = path.join(ROOT_DIR, 'docs', 'visual_qa_raw_report.json');
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  console.log(`\nVisual QA completed! Raw report written to: ${reportPath}`);
}

runFullQA().catch(err => {
  console.error('Visual QA run failed:', err);
  process.exit(1);
});
