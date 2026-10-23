// Trusted fixed checks. Generated source runs only inside an opaque sandboxed frame.
const { chromium } = require(process.argv[2]);
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => { input += chunk; if (input.length > 800000) process.exit(2); });
process.stdin.on('end', async () => {
  let browser;
  try {
    const { html } = JSON.parse(input);
    browser = await chromium.launch({ headless: true, chromiumSandbox: true,
      args:['--force-webrtc-ip-handling-policy=disable_non_proxied_udp','--host-resolver-rules=MAP * ~NOTFOUND'] });
    const results = [];
    for (const viewport of [{name:'desktop',width:1440,height:900},{name:'mobile',width:390,height:844}]) {
      const context = await browser.newContext({ viewport, serviceWorkers:'block', acceptDownloads:false });
      await context.addInitScript(() => {
        Object.defineProperty(globalThis, 'RTCPeerConnection', {value:undefined,configurable:false});
        Object.defineProperty(globalThis, 'Worker', {value:undefined,configurable:false});
        Object.defineProperty(globalThis, 'SharedWorker', {value:undefined,configurable:false});
      });
      await context.route('**/*', route => route.abort());
      const page = await context.newPage();
      page.setDefaultTimeout(8000);
      const errors = [], resources = [];
      const record = (list, message) => { if (list.length < 20) list.push(String(message).slice(0,400)); };
      page.on('pageerror', error => record(errors,error.message));
      page.on('console', message => { if(message.type()==='error') record(resources,message.text()); });
      page.on('requestfailed', request => record(resources, `${request.resourceType()}: ${request.failure()?.errorText || 'blocked'}`));
      context.on('page', popup => { if(popup !== page) void popup.close(); });
      await page.setContent('<!doctype html><html><head><style>html,body{margin:0;width:100%;height:100%;overflow:hidden}iframe{display:block;width:100%;height:100%;border:0}</style></head><body><iframe title="Website under test" sandbox="allow-scripts" referrerpolicy="no-referrer"></iframe></body></html>');
      await page.locator('iframe').evaluate((frame, source) => { frame.srcdoc = source; },html);
      const frame = page.frames().find(frame => frame.parentFrame());
      await frame.waitForURL('about:srcdoc');
      await frame.waitForFunction(() => document.readyState === 'complete' && !!document.body);
      const metrics = await frame.evaluate(() => ({
        loaded: document.readyState === 'complete' && !!document.body,
        overflow: Math.max(document.documentElement.scrollWidth,document.body.scrollWidth) > innerWidth + 1,
        brokenImages: [...document.images].filter(img => img.complete && img.naturalWidth === 0).length,
      }));
      const screenshot = await page.screenshot({type:'jpeg',quality:55,timeout:8000});
      if(screenshot.length > 700000) throw new Error('screenshot_budget');
      results.push({viewport:viewport.name,width:viewport.width,height:viewport.height,
        loaded:metrics.loaded,horizontal_overflow:metrics.overflow,broken_images:metrics.brokenImages,
        javascript_errors:errors,resource_errors:resources,screenshot_base64:screenshot.toString('base64')});
      await context.close();
    }
    process.stdout.write(JSON.stringify({browser_tests_executed:true,engine:'chromium',viewports:results,
      scope:'Fixed page-load checks in a network-blocked sandbox. No interaction, performance or full acceptance tests.'}));
  } catch {
    process.exitCode = 2;
  } finally {
    if(browser) await browser.close();
  }
});
