import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {bindSkipLink} from '../app/navigation.js';
import {routeFrom} from '../app/model.js';

test('skip link moves focus and scroll without replacing a filtered evidence route',()=>{
 const calls=[],link=new EventTarget();
 const main={focus:options=>calls.push(['focus',options]),scrollIntoView:options=>calls.push(['scroll',options])};
 bindSkipLink(link,main);
 for(const route of ['#/','#/find?kind=collection&topic=municipal&q=winter&page=2','#/record/finance-022','#/audits?view=hrm&depth=evidence']){
  let hash=route;
  for(let i=0;i<2;i++){
   const click=new Event('click',{cancelable:true});
   // Simulate the anchor default action only when the handler permits it.
   if(link.dispatchEvent(click))hash='#main';
   assert.equal(click.defaultPrevented,true);
   assert.equal(hash,route);
   assert.notEqual(routeFrom(hash).page,'not-found');
  }
 }
 assert.deepEqual(calls,Array.from({length:8},()=>[['focus',{preventScroll:true}],['scroll',{block:'start'}]]).flat());
});

test('skip handler is installed before the application begins asynchronous loading',()=>{
 const source=readFileSync(new URL('../app/main.js',import.meta.url),'utf8');
 const bindingIndex=source.indexOf("bindSkipLink(document.querySelector('.skip'),main)"),loadingIndex=source.indexOf('await verifiedJSON(');
 assert.ok(bindingIndex>=0,'Skip binding must exist');
 assert.ok(loadingIndex>=0,'Evidence loading must exist');
 assert.ok(bindingIndex<loadingIndex);
 const html=readFileSync(new URL('../index.html',import.meta.url),'utf8');
 assert.match(html,/<a class="skip" href="#main">Skip to content<\/a>/);
 assert.match(html,/<main id="main" tabindex="-1">/);
});
