import {chromium} from '@playwright/test';
import fs from 'node:fs/promises';import assert from 'node:assert/strict';
const root=process.env.BASE_URL||'http://127.0.0.1:4173';
const out='artifacts/browser';await fs.mkdir(out,{recursive:true});
const browser=await chromium.launch({headless:true});const report={routes:[],errors:[],assertions:[]};
try{
 for(const width of [360,768,1440]){
  const context=await browser.newContext({viewport:{width,height:900},acceptDownloads:true});const page=await context.newPage();
  page.on('pageerror',e=>report.errors.push(e.message));
  for(const path of ['#/','#/record/finance-001','#/money','#/sources','#/methods','#/investigation/budget-revision-2026-27?depth=simple','#/investigation/budget-revision-2026-27?depth=detail','#/investigation/budget-revision-2026-27?depth=evidence']){
   await page.goto(root+'/'+path);await page.waitForSelector('main h1');await page.waitForFunction(()=>!document.querySelector('.loading'));
   assert.equal(await page.locator('main h1').count(),1);
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`overflow ${width} ${path}`);
   const unsafe=await page.locator('a[href^="javascript:"]').count();assert.equal(unsafe,0);
   const name=`${width}-${path.includes('investigation')?'case-'+path.split('=')[1]:path.replaceAll(/[\W]/g,'')||'home'}`;
   await page.screenshot({path:`${out}/${name}.png`,fullPage:true});report.routes.push({width,path});
  }
  await page.goto(root+'/#/sources');await page.getByRole('searchbox').fill('health');await page.getByRole('button',{name:'Search',exact:true}).click();await page.waitForURL(/q=health/);assert.match(await page.locator('.results-count').innerText(),/matching source/);
  await page.getByRole('searchbox').fill('impossible-match-zzzz');await page.getByRole('button',{name:'Search',exact:true}).click();await page.waitForURL(/impossible/);assert.match(await page.locator('.empty').innerText(),/No sources match/);
  await page.goto(root+'/#/money');await page.getByRole('searchbox').fill('revenue');await page.getByRole('button',{name:'Search',exact:true}).click();await page.waitForURL(/q=revenue/);assert.ok(await page.locator('tbody tr').count()>0);assert.ok((await page.locator('tbody').innerText()).toLowerCase().includes('revenue'));
  await page.goto(root+'/#/investigation/budget-revision-2026-27?depth=evidence');const downloadPromise=page.waitForEvent('download');await page.getByRole('button',{name:'Download evidence file (JSON)'}).click();const download=await downloadPromise;const file=await download.path();const exported=JSON.parse(await fs.readFile(file,'utf8'));assert.equal(exported.investigation.id,'budget-revision-2026-27');assert.equal(exported.moneyFacts.length,2);assert.equal(exported.sources.length,2);assert.equal(exported.publicationReview.status,'accepted');
  await page.getByRole('link',{name:'30-second brief'}).click();await page.waitForURL(/depth=simple/);await page.getByRole('link',{name:'The full picture'}).click();await page.waitForURL(/depth=detail/);await page.goBack();await page.waitForURL(/depth=simple/);assert.match(await page.locator('main').innerText(),/What the records say/);
  await page.goto(root+'/#/not-real');assert.match(await page.locator('main').innerText(),/could not be found/);
  await page.goto(root+'/#/investigation/unreviewed-private');assert.match(await page.locator('main').innerText(),/has not passed publication review/);
  report.assertions.push({width,search:true,emptyResults:true,download:true,history:true,unreviewedHidden:true});await context.close();
 }
 const context=await browser.newContext();const page=await context.newPage();await page.route('**/data/foundation.json',route=>route.fulfill({status:503,body:'unavailable'}));await page.goto(root);await page.waitForSelector('[role=alert]');assert.equal(await page.locator('.metric').count(),0);await page.screenshot({path:`out/unavailable.png`.replace('out/',out+'/'),fullPage:true});report.assertions.push({sourceFailure:true,noFalseZero:true});await context.close();
 assert.deepEqual(report.errors,[]);
}finally{await fs.writeFile(`${out}/report.json`,JSON.stringify(report,null,2));await browser.close();}
