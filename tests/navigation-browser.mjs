import assert from 'node:assert/strict';
const ready=page=>page.waitForFunction(()=>document.querySelector('main')?.dataset.route===(location.hash||'#/'));
export async function navigationJourneys(page,width,root,report){
 await page.goto(root+'/#/methods');await ready(page);
 await page.getByRole('link',{name:'Find evidence',exact:true}).click();await ready(page);
 await page.getByRole('searchbox').fill('winter');
 await page.getByRole('button',{name:'Find evidence',exact:true}).click();await ready(page);
 const before=await page.evaluate(()=>({url:location.href,history:history.length,version:document.querySelector('main').dataset.renderVersion}));
 for(let i=0;i<2;i++){
  await page.getByRole('link',{name:'Skip to content',exact:true}).focus();
  await page.keyboard.press('Enter');
  assert.equal(await page.evaluate(()=>document.activeElement?.id),'main');
  assert.deepEqual(await page.evaluate(()=>({url:location.href,history:history.length,version:document.querySelector('main').dataset.renderVersion})),before);
  assert.equal(await page.getByRole('searchbox').inputValue(),'winter');
  assert.equal(await page.locator('.finder-result').count(),1);
 }
 await page.keyboard.press('Tab');
 assert.equal(await page.evaluate(()=>document.querySelector('main').contains(document.activeElement)),true);
 await page.goBack();await ready(page);assert.equal(await page.getByRole('searchbox').inputValue(),'');
 await page.goForward();await ready(page);assert.equal(await page.getByRole('searchbox').inputValue(),'winter');
 // Hold an optional collection response to exercise skipping during loading.
 let release,started;const gate=new Promise(resolve=>release=resolve),intercepted=new Promise(resolve=>started=resolve);
 const pending='**/data/hrm-winter/records.json';
 await page.route(pending,async route=>{started();await gate;await route.continue();});
 try{
  await page.locator('[data-directory-id="collection:hrm-winter"]').getByRole('link',{name:'Open this collection →',exact:true}).click();await ready(page);
  await intercepted;
  const loading=await page.evaluate(()=>({url:location.href,version:document.querySelector('main').dataset.renderVersion}));
  assert.equal(await page.getByRole('status').innerText(),'Checking independently reviewed winter evidence…');
  assert.equal(await page.locator('.winter-cost').count(),0);
  await page.getByRole('link',{name:'Skip to content',exact:true}).focus();
  await page.getByRole('link',{name:'Skip to content',exact:true}).click();
  assert.deepEqual(await page.evaluate(()=>({url:location.href,version:document.querySelector('main').dataset.renderVersion})),loading);
  assert.equal(await page.getByRole('status').innerText(),'Checking independently reviewed winter evidence…');
  assert.equal(await page.locator('.winter-cost').count(),0);
  assert.equal(await page.evaluate(()=>document.activeElement?.id),'main');
  assert.equal(new URL(page.url()).hash,'#/hrm-winter');
 }finally{release();}
 await page.locator('.winter-cost').first().waitFor();await page.unroute(pending);
 report.assertions.push({width,skipKeepsRouteAndFilters:true,skipKeepsHistory:true,skipKeyboardFocus:true,skipDuringEvidenceLoad:true});
}
