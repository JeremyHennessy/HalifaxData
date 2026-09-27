import {chromium} from 'playwright';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
const base=(process.env.HALIFAXDATA_URL||'http://127.0.0.1:8000/').replace(/\/?$/,'/');
const browser=await chromium.launch({headless:true});const report=[];
await fs.mkdir('artifacts/ui-smoke',{recursive:true});
try{
 for(const [name,viewport] of [['desktop',{width:1440,height:1100}],['mobile',{width:390,height:844}]]){
  const context=await browser.newContext({viewport,acceptDownloads:true});const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const started=Date.now();await page.goto(base+'#signals',{waitUntil:'networkidle'});
  await page.locator('#b23-workspace').waitFor();await page.locator('[data-build019-investigation-id]').first().click();
  await page.locator('#b23-reviewer').fill('Regression reviewer');await page.locator('#b23-notes').fill('Verify the original source before drawing conclusions.');await page.locator('#b23-status').selectOption('reviewed');await page.locator('#b23-watch').check();await page.locator('#b23-save').click();
  assert.match(await page.locator('#b23-save-result').innerText(),/saved in this browser/);
  const packet=await page.evaluate(()=>JSON.parse(localStorage.getItem('halifaxdata.workspace.v1')).items[0]);
  const exportPromise=page.waitForEvent('download');await page.locator('[data-b23-export="json"]').click();const download=await exportPromise;const exportPath=await download.path();const exported=JSON.parse(await fs.readFile(exportPath,'utf8'));assert.equal(exported.id,packet.id);assert.ok(exported.sources.length>0);
  await page.reload({waitUntil:'networkidle'});assert.match(await page.locator('#b23-workspace').innerText(),/Verify the original source/);assert.match(await page.locator('#b23-workspace').innerText(),/No evidence change/);
  await page.goto(packet.url,{waitUntil:'networkidle'});await page.locator('#b23-notes').waitFor();assert.equal(await page.locator('#b23-notes').inputValue(),packet.notes);
  await page.locator('#drawer-close').click();const backupPromise=page.waitForEvent('download');await page.locator('#b23-backup').click();const backup=await (await backupPromise).path();
  const fresh=await browser.newContext({viewport});const imported=await fresh.newPage();await imported.goto(base+'#signals',{waitUntil:'networkidle'});await imported.locator('#b23-import').setInputFiles(backup);await imported.getByText(packet.notes,{exact:true}).waitFor();
  await page.goto(base+'#spending',{waitUntil:'networkidle'});await page.locator('[data-spending-index]').first().focus();await page.keyboard.press('Enter');await page.locator('#b23-save').waitFor();assert.match(await page.locator('#drawer-body').innerText(),/Current YTD actual/);await page.locator('#drawer-close').click();
  const dimensions=await page.evaluate(()=>({width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth}));assert.ok(dimensions.scroll<=dimensions.width+2);
  const perf=await page.evaluate(()=>({resources:performance.getEntriesByType('resource').length,transferBytes:performance.getEntriesByType('resource').reduce((a,r)=>a+r.transferSize,0),navigation:performance.getEntriesByType('navigation')[0]?.toJSON()}));
  await page.screenshot({path:`artifacts/ui-smoke/${name}-build023-spending.png`,fullPage:true});
  assert.deepEqual(errors,[]);report.push({viewport:name,duration_ms:Date.now()-started,save_reload_deep_link_export_import_keyboard:true,performance:perf});await fresh.close();await context.close();
 }
}finally{await browser.close();await fs.writeFile('artifacts/ui-smoke/build023-report.json',JSON.stringify(report,null,2));}
console.log(JSON.stringify(report,null,2));
