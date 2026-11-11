import assert from 'node:assert/strict';
const ready=page=>page.waitForFunction(()=>document.querySelector('main')?.dataset.route===(location.hash||'#/'));
const snapshot=page=>page.evaluate(()=>({url:location.href,history:history.length,render:document.querySelector('main').dataset.renderVersion}));
async function clipboard(page,mode='success'){
 await page.evaluate(mode=>{
  window.sharedLinks=[];
  Object.defineProperty(navigator,'clipboard',{configurable:true,value:mode==='missing'?undefined:{writeText:text=>{
   window.sharedLinks.push(text);
   if(mode==='failure')return Promise.reject(new Error('Clipboard denied'));
   if(mode==='pending')return new Promise((resolve,reject)=>{window.finishCopy=resolve;window.rejectCopy=reject;});
   return Promise.resolve();
  }}});
 },mode);
}
const open=page=>page.getByRole('button',{name:'Share this view',exact:true}).click();
const status=page=>page.locator('.view-sharing-status');
export async function sharingJourneys(page,width,root,out,report){
 const route='#/transit?q=Not+Provided&group=accessible-trips&year=2024%2F25&depth=detail';
 await page.goto(root+'/?transport=omit'+route);await ready(page);
 await page.waitForFunction(()=>document.querySelector('.results-count')?.textContent.startsWith('1 matching evidence row ·'));
 await clipboard(page);const before=await snapshot(page);
 const toggle=page.getByRole('button',{name:'Share this view',exact:true});
 await toggle.focus();await page.keyboard.press('Enter');
 assert.equal(await toggle.getAttribute('aria-expanded'),'true');
 await page.keyboard.press('Escape');assert.equal(await toggle.getAttribute('aria-expanded'),'false');
 await page.keyboard.press('Enter');assert.equal(await toggle.getAttribute('aria-expanded'),'true');
 const url=root+'/'+route;
 assert.equal(await page.getByLabel('Link to this view',{exact:true}).inputValue(),url);
 assert.match(await page.locator('.view-sharing-panel').innerText(),/not a frozen snapshot/);
 await page.getByRole('button',{name:'Copy link',exact:true}).click();
 await status(page).getByText('Link copied. Paste it wherever you want to share this view.',{exact:true}).waitFor();
 assert.deepEqual(await page.evaluate(()=>window.sharedLinks),[url]);
 assert.deepEqual(await snapshot(page),before);
 await page.getByRole('button',{name:'Select link',exact:true}).click();
 assert.deepEqual(await page.getByLabel('Link to this view').evaluate(el=>[el.selectionStart,el.selectionEnd]),[0,url.length]);
 await page.keyboard.press('Escape');
 assert.equal(await toggle.getAttribute('aria-expanded'),'false');assert.equal(await toggle.evaluate(el=>el===document.activeElement),true);
 assert.deepEqual(await snapshot(page),before);
 await open(page);assert.equal(await status(page).textContent(),'');
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 await page.screenshot({path:`${out}/${width}-share-filtered-view.png`,fullPage:true});
 await page.getByRole('button',{name:'Close',exact:true}).click();assert.equal(await toggle.evaluate(el=>el===document.activeElement),true);
 // Reopening the copied URL restores the actual applied group/year/query/depth.
 await page.goto(url);await ready(page);await page.locator('.transit-access').waitFor();
 assert.equal(await page.getByLabel('Search transit evidence',{exact:true}).inputValue(),'Not Provided');
 assert.equal(await page.getByLabel('Transit reporting year',{exact:true}).inputValue(),'2024/25');
 assert.equal(await page.getByLabel('Transit evidence group',{exact:true}).inputValue(),'accessible-trips');
 assert.equal(await page.locator('.transit-access').count(),1);
 // Unsaved form edits are not silently represented as applied filters.
 await page.getByLabel('Search transit evidence',{exact:true}).fill('unapplied draft');await open(page);
 assert.equal(await page.getByLabel('Link to this view').inputValue(),url);
 assert.match(await page.locator('.view-sharing-panel').innerText(),/Apply search changes before copying/);
 await page.getByRole('button',{name:'Close',exact:true}).click();
 await page.getByRole('link',{name:'Original evidence',exact:true}).click();await ready(page);await open(page);
 assert.match(await page.getByLabel('Link to this view').inputValue(),/depth=evidence/);
 await page.goBack();await ready(page);assert.equal(await page.locator('.view-sharing-panel').isVisible(),false);await open(page);
 assert.equal(await page.getByLabel('Link to this view').inputValue(),url);
 await page.goForward();await ready(page);assert.equal(await page.locator('.view-sharing-panel').isVisible(),false);
 // Permission denied and unavailable APIs both leave a usable, selected URL.
 for(const mode of ['failure','missing']){
  await clipboard(page,mode);await open(page);await page.getByRole('button',{name:'Copy link',exact:true}).click();
  await status(page).getByText('Automatic copy is unavailable. Link selected; use your device’s Copy command.',{exact:true}).waitFor();
  const input=page.getByLabel('Link to this view');assert.equal(await input.evaluate(el=>el===document.activeElement),true);
  assert.deepEqual(await input.evaluate(el=>[el.selectionStart,el.selectionEnd]),[0,(await input.inputValue()).length]);
  assert.doesNotMatch(await status(page).innerText(),/Link copied/);
  await page.getByRole('button',{name:'Close',exact:true}).click();
 }
 // Repeated clicks while pending issue one write. Dismissal suppresses late UI.
 await clipboard(page,'pending');await open(page);await page.getByRole('button',{name:'Copy link',exact:true}).click();
 assert.equal(await page.getByRole('button',{name:'Copying…',exact:true}).isDisabled(),true);
 await page.getByRole('button',{name:'Close',exact:true}).click();await open(page);
 await page.evaluate(()=>window.finishCopy());await page.getByRole('button',{name:'Copy link',exact:true}).waitFor();
 assert.equal(await status(page).textContent(),'');assert.equal(await page.evaluate(()=>window.sharedLinks.length),1);
 // Navigation wins over a delayed failure. New view gets no stale status or focus.
 await clipboard(page,'pending');await page.getByRole('button',{name:'Copy link',exact:true}).click();
 await page.locator('[data-nav="find"]').click();await ready(page);await page.evaluate(()=>window.rejectCopy(new Error('late denial')));
 await page.waitForTimeout(20);assert.equal(await page.locator('.view-sharing-panel').isVisible(),false);
 assert.equal(await page.evaluate(()=>document.activeElement?.id),'main');assert.equal(await page.locator('.view-sharing').count(),1);
 await page.goto(root+'/#/not-a-route');await ready(page);assert.equal(await page.locator('.view-sharing').count(),0);
 report.assertions.push({width,shareAppliedView:true,shareKeyboardClose:true,shareClipboardFallback:true,sharePendingAndNavigation:true,shareHistoryAndRestore:true});
}
