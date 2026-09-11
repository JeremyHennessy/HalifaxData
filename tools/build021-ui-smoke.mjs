import { chromium } from 'playwright';
import fs from 'node:fs/promises';

const BASE_URL=(process.env.HALIFAXDATA_URL||'http://127.0.0.1:8000/').replace(/\/?$/,'/');
const OUTPUT='artifacts/ui-smoke';
const viewports=[['desktop',{width:1440,height:1100}],['mobile',{width:390,height:844}]];
await fs.mkdir(OUTPUT,{recursive:true});
const browser=await chromium.launch({headless:true});
const report={generated_at:new Date().toISOString(),base_url:BASE_URL,views:[],errors:[]};
function requirePhrases(text,phrases,label){for(const phrase of phrases) if(!text.includes(phrase)) throw new Error(`${label}: missing "${phrase}"`);}
async function noOverflow(page,label){const d=await page.evaluate(()=>({scrollWidth:document.documentElement.scrollWidth,clientWidth:document.documentElement.clientWidth}));if(d.scrollWidth>d.clientWidth+2) throw new Error(`${label}: horizontal overflow ${JSON.stringify(d)}`);return d;}
try{
  for(const [viewportName,viewport] of viewports){
    const context=await browser.newContext({viewport,deviceScaleFactor:1});
    const page=await context.newPage();
    page.on('pageerror',e=>report.errors.push({viewport:viewportName,type:'pageerror',text:e.message}));
    page.on('console',m=>{if(m.type()==='error'&&!m.text().startsWith('Failed to load resource: the server responded with a status of 404')) report.errors.push({viewport:viewportName,type:'console',text:m.text()});});
    await page.goto(`${BASE_URL}#overview`,{waitUntil:'networkidle'});
    await page.waitForFunction(()=>Boolean(document.querySelector('[data-build021-province="ready"]')&&typeof b21Payments==='function'&&b21Payments().length===21),null,{timeout:30000});
    const stats=await page.evaluate(()=>({rows:b21Payments().length,departments:b21Summary().departments,hrmRows:b21Summary().hrm_rows,waterRows:b21Summary().halifax_water_rows,hrmAmount:b21Summary().hrm_amount,waterAmount:b21Summary().halifax_water_amount,combined:b21Summary().combined_exact_payee_amount,navItems:document.querySelectorAll('.nav-item').length,tableRows:document.querySelectorAll('[data-build021-payments-table] tbody tr').length}));
    if(stats.rows!==21||stats.departments!==12||stats.hrmRows!==15||stats.waterRows!==6||stats.tableRows!==21) throw new Error(`${viewportName}: Build 021 row controls changed ${JSON.stringify(stats)}`);
    if(Math.abs(stats.hrmAmount-98487725.96)>.01||Math.abs(stats.waterAmount-4046146.59)>.01||Math.abs(stats.combined-102533872.55)>.01) throw new Error(`${viewportName}: Build 021 amount controls changed ${JSON.stringify(stats)}`);
    if(stats.navItems!==8) throw new Error(`${viewportName}: approved navigation changed; expected 8 items, got ${stats.navItems}`);
    const p=(await page.locator('[data-build021-province="ready"]').innerText()).toLowerCase();
    requirePhrases(p,['province → halifax cash payments','separate provincial accounting scope','cash-basis','not hrm expenses','not an hrm spending total','accumulated annual payee','halifax regional water commission'],`${viewportName} province panel`);
    const overview=await noOverflow(page,`${viewportName} overview`);
    await page.screenshot({path:`${OUTPUT}/${viewportName}-build021-province-overview.png`,fullPage:true});
    await page.goto(`${BASE_URL}#budget`,{waitUntil:'networkidle'});
    await page.waitForSelector('[data-build021-budget="ready"]');
    const b=(await page.locator('[data-build021-budget="ready"]').innerText()).toLowerCase();
    requirePhrases(b,['nova scotia 2026/27 expense-plan context','never merged into, hrm budget or actual totals','different government, different denominator','health and wellness','35.5%','education and early childhood development','12.4%'],`${viewportName} provincial budget panel`);
    const budget=await noOverflow(page,`${viewportName} budget`);
    await page.screenshot({path:`${OUTPUT}/${viewportName}-build021-provincial-budget.png`,fullPage:true});
    await page.goto(`${BASE_URL}#sources`,{waitUntil:'networkidle'});
    await page.waitForSelector('[data-build021-sources]');
    const s=(await page.locator('[data-build021-sources]').innerText()).toLowerCase();
    requirePhrases(s,['provincial context sources','nova scotia public accounts volume 3','nova scotia budget 2026-27','separate provincial evidence type','do not convert a tender award into an hrm payment fact'],`${viewportName} provincial sources panel`);
    const sources=await noOverflow(page,`${viewportName} sources`);
    await page.screenshot({path:`${OUTPUT}/${viewportName}-build021-provincial-sources.png`,fullPage:true});
    report.views.push({viewport:viewportName,stats,dimensions:{overview,budget,sources}});
    await context.close();
  }
}finally{await browser.close();}
await fs.writeFile(`${OUTPUT}/build021-report.json`,JSON.stringify(report,null,2));
if(report.errors.length){console.error(JSON.stringify(report,null,2));process.exit(1);}console.log(JSON.stringify(report,null,2));
