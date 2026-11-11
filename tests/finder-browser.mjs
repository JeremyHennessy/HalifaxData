import assert from 'node:assert/strict';
const ready=page=>page.waitForFunction(()=>document.querySelector('main')?.dataset.route===location.hash);
const fits=async page=>assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
export async function finderJourneys(page,width,root,out,report){
 await page.goto(root+'/#/find');await ready(page);
 const nav=page.getByRole('navigation',{name:'Browse reviewed collections by topic'});
 assert.equal(await nav.getByRole('link').count(),7);await nav.getByRole('link',{name:'All collections (26)',exact:true}).click();await ready(page);assert.equal(await nav.getByRole('link',{name:'All collections (26)',exact:true}).getAttribute('aria-current'),'page');await page.getByRole('link',{name:'Reset filters',exact:true}).click();await ready(page);assert.equal(await page.locator('.finder-result').count(),12);
 assert.match(await page.getByRole('status').innerText(),/55 matching directory entries/);
 const municipal=nav.getByRole('link',{name:'Municipal services (11)',exact:true});await municipal.focus();await page.keyboard.press('Enter');await ready(page);
 assert.match(page.url(),/kind=collection&topic=municipal$/);assert.equal(await page.locator('.finder-result').count(),11);
 assert.equal(await page.getByLabel('Topic',{exact:true}).inputValue(),'municipal');assert.equal(await page.getByLabel('Result type').inputValue(),'collection');
 assert.equal(await nav.getByRole('link',{name:'Municipal services (11)',exact:true}).getAttribute('aria-current'),'page');
 const winter=page.locator('[data-directory-id="collection:hrm-winter"]');assert.match(await winter.innerText(),/Independent snapshot review: 2026-11-11/);assert.match(await winter.innerText(),/Not the source period or current-status date/);
 assert.equal(await winter.getByRole('link',{name:'Accepted review receipt',exact:true}).getAttribute('href'),'data/hrm-winter/publication-review.json');
 const receipt=await page.request.get(root+'/data/hrm-winter/publication-review.json');assert.equal(receipt.status(),200);assert.equal((await receipt.json()).status,'accepted');
 await fits(page);await page.screenshot({path:`${out}/${width}-finder-municipal-topics.png`,fullPage:true});
 await page.getByRole('searchbox').fill('winter');await page.getByRole('button',{name:'Find evidence',exact:true}).click();await ready(page);assert.equal(await page.locator('.finder-result').count(),1);
 await page.getByRole('button',{name:'Find evidence',exact:true}).click();await ready(page);assert.equal(await page.locator('.finder-result').count(),1);
 await winter.getByRole('link',{name:'Open this collection →',exact:true}).click();await page.locator('.winter-cost').first().waitFor();await page.goBack();await ready(page);assert.equal(await page.getByRole('searchbox').inputValue(),'winter');assert.equal(await page.getByLabel('Topic',{exact:true}).inputValue(),'municipal');await page.goForward();await page.locator('.winter-cost').first().waitFor();await page.goBack();await ready(page);
 await page.getByRole('link',{name:'Budgets & accounts (10)',exact:true}).click();await ready(page);assert.equal(await page.getByRole('searchbox').inputValue(),'');
 await page.getByLabel('Result type').selectOption('');await page.getByRole('button',{name:'Find evidence',exact:true}).click();await ready(page);assert.match(await page.getByRole('status').innerText(),/39 matching directory entries · page 1 of 4/);
 await page.getByRole('link',{name:'Next page',exact:true}).click();await ready(page);assert.match(page.url(),/topic=budgets&page=2/);assert.match(await page.getByRole('status').innerText(),/page 2 of 4/);await page.goBack();await ready(page);assert.match(await page.getByRole('status').innerText(),/page 1 of 4/);
 await page.getByLabel('Result type').selectOption('fact');await page.getByRole('searchbox').fill('net debt');await page.getByRole('button',{name:'Find evidence',exact:true}).click();await ready(page);assert.equal(await page.locator('.finder-result').count(),1);assert.equal(await page.locator('.finder-result').getAttribute('data-directory-id'),'fact:finance-022');assert.equal(await page.locator('.finder-review').count(),0);
 await page.getByLabel('Topic',{exact:true}).selectOption('municipal');await page.getByRole('button',{name:'Find evidence',exact:true}).click();await ready(page);assert.match(await page.locator('.empty').innerText(),/does not establish/);assert.equal(await page.locator('.finder-result').count(),0);await fits(page);await page.screenshot({path:`${out}/${width}-finder-empty-topic.png`,fullPage:true});
 await page.getByRole('link',{name:'Reset filters',exact:true}).click();await ready(page);assert.equal(await page.getByRole('searchbox').inputValue(),'');assert.equal(await page.getByLabel('Topic',{exact:true}).inputValue(),'');assert.equal(await page.getByLabel('Result type').inputValue(),'');assert.match(await page.getByRole('status').innerText(),/55 matching/);
 await page.getByRole('link',{name:'What did the winter-operations audit measure?',exact:true}).click();await page.locator('.winter-cost').first().waitFor();await page.goBack();await ready(page);
 await page.goto(root+'/#/find?topic=%3Cscript%3E&kind=unknown&page=999');await ready(page);assert.equal(await page.getByLabel('Topic',{exact:true}).inputValue(),'');assert.equal(await page.getByLabel('Result type').inputValue(),'');assert.match(await page.getByRole('status').innerText(),/55 matching directory entries · page 5 of 5/);assert.equal(await page.locator('main script').count(),0);
 report.assertions.push({width,finderTopics:true,collectionCounts:true,reviewDatesNotSourceDates:true,topicKeyboard:true,combinedFilters:true,pagingAndHistory:true,resetAndEmpty:true});
}
export async function finderFailures(browser,root,report){
 const ctx=await browser.newContext();const p=await ctx.newPage();let shards=0;
 p.on('request',r=>{if(/\/data\/tenders\/tenders-/.test(r.url()))shards++;});
 await p.route('**/data/hrm-winter/publication-review.json',r=>r.fulfill({status:200,body:'{}'}));
 await p.goto(root+'/#/find?kind=collection&topic=municipal');await ready(p);
 assert.equal(await p.locator('.finder-result').count(),10);assert.equal(await p.locator('[data-directory-id="collection:hrm-winter"]').count(),0);
 for(const name of ['All collections (25)','Municipal services (10)','Contracts & suppliers (5)','Audits & oversight (8)'])assert.equal(await p.getByRole('navigation',{name:'Browse reviewed collections by topic'}).getByRole('link',{name,exact:true}).count(),1);
 assert.equal(await p.getByRole('link',{name:'What did the winter-operations audit measure?',exact:true}).count(),0);assert.equal(shards,0);
 report.assertions.push({finderFailedReceiptExcludedFromTopics:true,finderNoTenderShards:true});await ctx.close();
}
