import { chromium } from 'playwright';
import fs from 'node:fs/promises';

const BASE_URL=(process.env.HALIFAXDATA_URL||'http://127.0.0.1:8000/').replace(/\/?$/,'/');
const OUTPUT='artifacts/ui-smoke';
const routes=[['overview','Command Center'],['budget','Budget & Actuals'],['people','People & Compensation'],['spending','Spend Explorer'],['vendors','Vendors & Contracts'],['projects','Capital Projects'],['signals','Signals Lab'],['sources','Sources & Evidence']];
const viewports=[['desktop',{width:1440,height:1100}],['mobile',{width:390,height:844}]];
await fs.rm(OUTPUT,{recursive:true,force:true}); await fs.mkdir(OUTPUT,{recursive:true});
const browser=await chromium.launch({headless:true});
const report={generated_at:new Date().toISOString(),base_url:BASE_URL,console_errors:[],page_errors:[],http_errors:[],views:[],interactions:[]};

async function waitForDashboard(page){await page.waitForSelector('#content',{state:'visible'});await page.waitForFunction(()=>{const c=document.querySelector('#content');return c&&!c.querySelector('.loading-card')});}
async function openRoute(page,route){await page.goto(`${BASE_URL}#${route}`,{waitUntil:'networkidle'});await waitForDashboard(page);}
async function closeDrawer(page){const d=page.locator('#evidence-drawer');if(await d.getAttribute('open')!==null){await page.locator('#drawer-close').click();await page.waitForFunction(()=>!document.querySelector('#evidence-drawer')?.open);}}
async function assertDrawerSource(page,label){await page.waitForSelector('#evidence-drawer[open]');const href=await page.locator('#evidence-drawer .source-link').getAttribute('href');if(!href||!/^https?:\/\//.test(href))throw new Error(`${label}: official source link missing`);return href;}

try{
 for(const [viewportName,viewport] of viewports){
  const context=await browser.newContext({viewport,deviceScaleFactor:1}); const page=await context.newPage();
  page.on('console',m=>{if(m.type()==='error'&&!m.text().startsWith('Failed to load resource: the server responded with a status of 404'))report.console_errors.push({viewport:viewportName,text:m.text()})});
  page.on('pageerror',e=>report.page_errors.push({viewport:viewportName,text:e.message}));
  page.on('response',r=>{if(r.status()>=400&&!((r.status()===404)&&new URL(r.url()).pathname.endsWith('/data/generated/signals.json')))report.http_errors.push({viewport:viewportName,status:r.status(),url:r.url()})});

  for(const [route,expectedTitle] of routes){
   await openRoute(page,route); const title=(await page.locator('#view-title').textContent())?.trim(); if(title!==expectedTitle)throw new Error(`${viewportName}/${route}: title ${title}`);
   const state=await page.evaluate(()=>({bg:getComputedStyle(document.body).backgroundColor,color:getComputedStyle(document.body).color,text:document.querySelector('#content')?.innerText?.trim().length||0,error:document.querySelector('.error-state')?.textContent?.trim()||'',sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth}));
   if(state.error)throw new Error(`${viewportName}/${route}: ${state.error}`); if(state.text<40)throw new Error(`${viewportName}/${route}: sparse render`); if(state.sw>state.cw+2)throw new Error(`${viewportName}/${route}: page overflow ${state.sw}>${state.cw}`);
   if(!state.bg.includes('244')&&!state.bg.includes('255'))throw new Error(`${viewportName}/${route}: expected light background, got ${state.bg}`);
   await page.screenshot({path:`${OUTPUT}/${viewportName}-${route}.png`,fullPage:true}); report.views.push({viewport:viewportName,route,title,...state});
  }

  // Compensation filter + evidence regression.
  await openRoute(page,'overview'); const before=(await page.locator('.metrics-grid .metric-card').nth(1).locator('.metric-value').textContent())?.trim(); await page.locator('#global-year').selectOption('2025'); const after=(await page.locator('.metrics-grid .metric-card').nth(1).locator('.metric-value').textContent())?.trim(); if(!before||!after||before===after)throw new Error(`${viewportName}: compensation year filter failed`); await page.locator('#global-year').selectOption('all');
  await page.locator('#global-search').fill('Campbell');await page.locator('#global-search').press('Enter');await page.waitForSelector('#evidence-drawer[open]');const people=page.locator('#drawer-body [data-search-person]');if(await people.count()<1)throw new Error(`${viewportName}: person search empty`);await people.first().click();await page.waitForSelector('#evidence-drawer[open] .mini-history');await assertDrawerSource(page,`${viewportName}/person`);await closeDrawer(page);

  // Report-level spending semantics and evidence.
  await openRoute(page,'spending'); const spendText=(await page.locator('#content').innerText()).toLowerCase(); if(!spendText.includes('not a transaction ledger')||!spendText.includes('report-level'))throw new Error(`${viewportName}/spending: scope boundary missing`); const spendRows=page.locator('[data-spend-key]');if(await spendRows.count()<1)throw new Error(`${viewportName}/spending: no rows`);await spendRows.first().click();await assertDrawerSource(page,`${viewportName}/spending`);await closeDrawer(page);

  // Procurement paging/filter/evidence.
  await openRoute(page,'vendors'); const procRows=page.locator('[data-proc-key]');if(await procRows.count()<1||await procRows.count()>100)throw new Error(`${viewportName}/procurement: invalid page size`);const procText=(await page.locator('#content').innerText()).toLowerCase();if(!procText.includes('not an accounts-payable ledger'))throw new Error(`${viewportName}/procurement: AP boundary missing`);await procRows.first().click();await assertDrawerSource(page,`${viewportName}/procurement`);await closeDrawer(page);

  // Historical capital scope/evidence.
  await openRoute(page,'projects'); const capRows=page.locator('[data-cap-key]');if(await capRows.count()<1||await capRows.count()>100)throw new Error(`${viewportName}/capital: invalid page size`);const capText=(await page.locator('#content').innerText()).toLowerCase();if(!capText.includes('historical')||!capText.includes('not the current hrm capital universe'))throw new Error(`${viewportName}/capital: historical boundary missing`);await capRows.first().click();await assertDrawerSource(page,`${viewportName}/capital`);await closeDrawer(page);

  await openRoute(page,'sources'); const sourceCards=page.locator('#content [data-source-id]');if(await sourceCards.count()<40)throw new Error(`${viewportName}/sources: expected expanded registry, got ${await sourceCards.count()}`);await sourceCards.first().click();await assertDrawerSource(page,`${viewportName}/sources`);await closeDrawer(page);

  if(viewportName==='mobile'){await openRoute(page,'overview');await page.locator('#menu-button').click();await page.waitForFunction(()=>document.querySelector('#sidebar')?.classList.contains('open'));await page.locator('#nav [data-view="budget"]').click();await page.waitForFunction(()=>document.querySelector('#view-title')?.textContent?.trim()==='Budget & Actuals');if(await page.locator('#sidebar').evaluate(el=>el.classList.contains('open')))throw new Error('mobile navigation remained open');}
  report.interactions.push({viewport:viewportName,check:'compensation + spending + procurement + capital + source evidence'}); await context.close();
 }
}finally{await browser.close();}
await fs.writeFile(`${OUTPUT}/report.json`,JSON.stringify(report,null,2));
if(report.console_errors.length||report.page_errors.length||report.http_errors.length){console.error(JSON.stringify(report,null,2));process.exit(1)}
console.log(JSON.stringify(report,null,2));
