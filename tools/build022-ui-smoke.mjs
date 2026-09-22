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
async function directPanelOrder(page){
  return page.evaluate(()=>{
    const stack=document.querySelector('#content .page-stack');
    const rows=[...stack.children].map((el,index)=>({index,label:(el.querySelector?.('h2')?.textContent||'').trim().toLowerCase(),cls:el.className||'',start:Boolean(el.matches?.('[data-build022-start]'))}));
    const find=(phrase)=>rows.find(row=>row.label===phrase)?.index??-1;
    return {rows,start:rows.find(row=>row.start)?.index??-1,attention:find('what deserves attention?'),authority:find('authority-backed oversight'),pattern:find('automated pattern engine')};
  });
}
try{
  for(const [viewportName,viewport] of viewports){
    const context=await browser.newContext({viewport,deviceScaleFactor:1});
    const page=await context.newPage();
    page.on('pageerror',e=>report.errors.push({viewport:viewportName,type:'pageerror',text:e.message}));
    page.on('console',m=>{if(m.type()==='error'&&!m.text().startsWith('Failed to load resource: the server responded with a status of 404')) report.errors.push({viewport:viewportName,type:'console',text:m.text()});});

    await page.goto(`${BASE_URL}#overview`,{waitUntil:'networkidle'});
    await page.waitForSelector('[data-build022-start]');
    const overviewStats=await page.evaluate(()=>({
      navItems:document.querySelectorAll('.nav-item').length,
      startCards:document.querySelectorAll('[data-build022-start] .b22-action-grid a').length,
      provinceRowsOnOverview:document.querySelectorAll('[data-build022-province-row]').length
    }));
    if(overviewStats.navItems!==11) throw new Error(`${viewportName}: approved navigation changed; expected 11 items, got ${overviewStats.navItems}`);
    if(overviewStats.startCards!==3) throw new Error(`${viewportName}: Start here should expose three primary paths`);
    if(overviewStats.provinceRowsOnOverview!==0) throw new Error(`${viewportName}: raw provincial payee rows must not dominate Command Center`);
    const order=await directPanelOrder(page);
    if(order.start<0||order.attention<0||order.attention!==order.start+1) throw new Error(`${viewportName}: What deserves attention must immediately follow Start here: ${JSON.stringify(order)}`);
    if(order.authority>=0&&order.authority<order.attention) throw new Error(`${viewportName}: oversight methodology precedes the primary investigation queue: ${JSON.stringify(order)}`);
    if(order.pattern>=0&&order.pattern<order.attention) throw new Error(`${viewportName}: pattern methodology precedes the primary investigation queue: ${JSON.stringify(order)}`);
    const startText=(await page.locator('[data-build022-start]').innerText()).toLowerCase();
    requirePhrases(startText,['review prioritized investigations','trace the financial context','check freshness and gaps'],`${viewportName} Start here`);
    const overview=await noOverflow(page,`${viewportName} overview`);
    await page.screenshot({path:`${OUTPUT}/${viewportName}-build022-overview.png`,fullPage:true});

    await page.goto(`${BASE_URL}#benchmarks`,{waitUntil:'networkidle'});
    await page.waitForSelector('[data-build022-province="ready"]');
    const province=page.locator('[data-build022-province="ready"]');
    const provinceText=(await province.innerText()).toLowerCase();
    requirePhrases(provinceText,['province → halifax funding context','separate accounting scope','cash-basis','not hrm expenses','not an hrm accounts-payable ledger','halifax regional water commission'],`${viewportName} province context`);
    const provinceStats=await page.evaluate(()=>({
      payeeRows:document.querySelectorAll('[data-build022-province-table] tbody tr').length,
      rawOpen:document.querySelector('[data-build022-province-details]')?.open,
      benchmarkOpen:document.querySelector('[data-build022-benchmark-details]')?.open,
      benchmarkExplorerNested:Boolean(document.querySelector('[data-build022-benchmark-details] .panel'))
    }));
    if(provinceStats.payeeRows!==21) throw new Error(`${viewportName}: expected 21 verified provincial payee rows, got ${provinceStats.payeeRows}`);
    if(provinceStats.rawOpen!==false) throw new Error(`${viewportName}: raw provincial rows must be collapsed by default`);
    if(provinceStats.benchmarkOpen!==false||!provinceStats.benchmarkExplorerNested) throw new Error(`${viewportName}: detailed benchmark explorer must remain available but collapsed by default`);
    const taxText=(await page.locator('[data-build022-tax]').innerText()).toLowerCase();
    requirePhrases(taxText,['where my taxes go','federal · 2026/27','nova scotia · 2026/27','halifax · property tax','not a complete property-tax bill'],`${viewportName} tax context`);
    const benchmarks=await noOverflow(page,`${viewportName} benchmarks`);
    await page.screenshot({path:`${OUTPUT}/${viewportName}-build022-benchmarks.png`,fullPage:true});

    await page.goto(`${BASE_URL}#sources`,{waitUntil:'networkidle'});
    await page.waitForSelector('[data-build022-freshness]');
    const freshnessText=(await page.locator('[data-build022-freshness]').innerText()).toLowerCase();
    requirePhrases(freshnessText,['source freshness & unresolved gaps','publication status','newer source not yet verified'],`${viewportName} freshness`);
    const sourceText=(await page.locator('[data-build022-context-sources]').innerText()).toLowerCase();
    requirePhrases(sourceText,['additional provincial context sources','public accounts volume 3','nova scotia budget 2026-27','separate evidence layer'],`${viewportName} source context`);
    const sources=await noOverflow(page,`${viewportName} sources`);
    await page.screenshot({path:`${OUTPUT}/${viewportName}-build022-sources.png`,fullPage:true});

    report.views.push({viewport:viewportName,overviewStats,order,provinceStats,dimensions:{overview,benchmarks,sources}});
    await context.close();
  }
}finally{await browser.close();}
await fs.writeFile(`${OUTPUT}/build022-report.json`,JSON.stringify(report,null,2));
if(report.errors.length){console.error(JSON.stringify(report,null,2));process.exit(1);}
console.log(JSON.stringify(report,null,2));
