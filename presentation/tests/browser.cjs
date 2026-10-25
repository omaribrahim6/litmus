// Run with the bundled Playwright package, or install Playwright outside this deployment.
const { chromium } = require(process.env.PLAYWRIGHT_PACKAGE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
(async()=> {
 const browser = await chromium.launch({channel:'chrome',headless:true});
 try {
 const context=await browser.newContext({ viewport:{width:1440,height:1000},acceptDownloads:true });
 const page=await context.newPage(), errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(process.env.DEMO_URL || 'http://127.0.0.1:18350');
 const initial=await page.locator('#step-label').innerText();
 await page.waitForTimeout(1200); assert.equal(await page.locator('#step-label').innerText(),initial);
 for(let i=0;i<4;i++) await page.locator('#next').click();
 await page.locator('#analysis').waitFor({state:'visible'});
 await page.locator('#evidence-toggle').click();
 await page.screenshot({path:'verified-desktop.png',fullPage:true});
 await page.reload(); assert.match(await page.locator('#step-label').innerText(),/STEP 5/);
 await page.locator('#back').click(); assert.equal(await page.locator('#analysis').isVisible(),false);
 await page.locator('#next').click(); await page.locator('#next').click();
 const download=page.waitForEvent('download'); await page.locator('#export').click();
 const d=await download; await d.saveAs('verified-export.json');
 const exported=JSON.parse(await fs.readFile('verified-export.json','utf8'));
 assert.equal(exported.demo,true); assert.equal(exported.events.length,5);
 await page.locator('#reset').click(); await page.getByRole('button',{name:'Keep my place'}).click();
 assert.match(await page.locator('#step-label').innerText(),/STEP 6/);
 await page.locator('#reset').click(); await page.getByRole('button',{name:'Restart',exact:true}).click();
 assert.match(await page.locator('#step-label').innerText(),/STEP 1/);
 await page.locator('h1').click(); await page.keyboard.press('ArrowRight');
 assert.match(await page.locator('#step-label').innerText(),/STEP 2/);
 await page.locator('#camera-toggle').click();
 await page.waitForFunction(()=>!document.querySelector('#camera-toggle').disabled,{timeout:10000});
 assert.match(await page.locator('#camera-message').innerText(),/unavailable|denied/);
 assert.equal(await page.locator('#illustration').isVisible(),true);
 await page.setViewportSize({width:390,height:844});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await page.screenshot({path:'verified-mobile.png',fullPage:true});
 await page.evaluate(async()=>{await navigator.serviceWorker.ready;});
 await page.reload(); await context.setOffline(true); await page.reload();
 assert.match(await page.locator('#step-label').innerText(),/STEP 2/);
 await page.locator('#next').click(); assert.match(await page.locator('#step-label').innerText(),/STEP 3/);
 assert.deepEqual(errors,[]); console.log(JSON.stringify({passed:true,checks:['manual pacing','step sequence','back','reload recovery','export provenance','reset cancel','reset confirm','keyboard','camera failure fallback','mobile width','offline reload'],errors}));
 } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
