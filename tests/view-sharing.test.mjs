import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {viewURL,createViewSharing} from '../app/view-sharing.js';

const example='https://example.test/HalifaxData/?commit=123#/transit?q=Not+Provided&group=accessible-trips&year=2024%2F25&depth=evidence';
test('view links preserve applied hash filters and base path without transport query or credentials',()=>{
 assert.equal(viewURL(example),'https://example.test/HalifaxData/#/transit?q=Not+Provided&group=accessible-trips&year=2024%2F25&depth=evidence');
 assert.equal(viewURL('https://name:secret@example.test/HalifaxData/?cache=1'),'https://example.test/HalifaxData/#/');
 assert.equal(viewURL('http://127.0.0.1:4173/#/find?q=%3Cscript%3E&topic=municipal&page=2'),'http://127.0.0.1:4173/#/find?q=%3Cscript%3E&topic=municipal&page=2');
 for(const url of ['file:///tmp/index.html','javascript:alert(1)','not a URL'])assert.throws(()=>viewURL(url));
});

function fixture(clipboard){
 const all=[];let focused=null;
 class Element extends EventTarget{
  constructor(tag){super();this.tag=tag;this.attributes={};this.children=[];this.hidden=false;this.disabled=false;this.isConnected=true;this.textContent='';this.value='';all.push(this);}
  setAttribute(k,v){this.attributes[k]=String(v);if(k==='hidden')this.hidden=true;if(k==='value')this.value=v;}
  append(...children){this.children.push(...children);}
  focus(){focused=this;}
  select(){this.selected=true;}
  setSelectionRange(a,b){this.range=[a,b];}
 }
 const host=createViewSharing({document:{createElement:tag=>new Element(tag)},href:example,clipboard});
 const button=text=>all.find(n=>n.tag==='button'&&n.textContent===text);
 const controls={host,toggle:button('Share this view'),copy:button('Copy link'),select:button('Select link'),close:button('Close'),panel:all.find(n=>n.tag==='section'),input:all.find(n=>n.tag==='input'),status:all.find(n=>n.attributes.role==='status')};
 const click=node=>node.dispatchEvent(new Event('click'));
 return{...controls,click,focus:()=>focused};
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));

test('opening, manual selection, close and Escape never invoke clipboard',()=>{
 let calls=0;const f=fixture(()=>{calls++;throw Error('unexpected');});
 assert.equal(f.panel.hidden,true);assert.equal(f.toggle.attributes['aria-expanded'],'false');
 f.click(f.toggle);assert.equal(f.panel.hidden,false);assert.equal(f.toggle.attributes['aria-expanded'],'true');
 f.click(f.select);assert.equal(f.focus(),f.input);assert.deepEqual(f.input.range,[0,viewURL(example).length]);
 assert.match(f.status.textContent,/Link selected/);f.click(f.close);assert.equal(f.panel.hidden,true);assert.equal(f.focus(),f.toggle);
 f.click(f.toggle);assert.equal(f.status.textContent,'');const escape=new Event('keydown',{cancelable:true});Object.defineProperty(escape,'key',{value:'Escape'});f.host.dispatchEvent(escape);
 assert.equal(escape.defaultPrevented,true);assert.equal(f.panel.hidden,true);assert.equal(f.focus(),f.toggle);assert.equal(calls,0);
});

test('copy only reports success after completion and suppresses repeated pending requests',async()=>{
 let resolve,calls=[];const f=fixture(()=>({writeText:value=>{calls.push(value);return new Promise(r=>resolve=r);}}));
 f.click(f.toggle);f.click(f.copy);assert.equal(f.copy.disabled,true);assert.equal(f.copy.textContent,'Copying…');assert.equal(f.status.textContent,'');
 f.click(f.copy);assert.equal(calls.length,1);assert.equal(calls[0],viewURL(example));resolve();await tick();
 assert.equal(f.copy.disabled,false);assert.equal(f.copy.textContent,'Copy link');assert.match(f.status.textContent,/Link copied/);
});

test('missing and rejected clipboard services select a manual fallback without a success claim',async()=>{
 for(const clipboard of [()=>undefined,()=>{throw Error('blocked');},()=>({writeText:()=>Promise.reject(Error('denied'))})]){
  const f=fixture(clipboard);f.click(f.toggle);f.click(f.copy);await tick();
  assert.match(f.status.textContent,/Automatic copy is unavailable/);assert.doesNotMatch(f.status.textContent,/Link copied/);assert.equal(f.focus(),f.input);assert.equal(f.input.selected,true);assert.equal(f.copy.disabled,false);
 }
});

test('late clipboard completion cannot reopen or announce into a dismissed or replaced view',async()=>{
 for(const ending of ['close','reopen','replace'])for(const outcome of ['success','failure']){
  let resolve,reject;const f=fixture(()=>({writeText:()=>new Promise((yes,no)=>{resolve=yes;reject=no;})}));
  f.click(f.toggle);f.click(f.copy);
  if(ending==='replace')f.host.isConnected=false;else {f.click(f.close);if(ending==='reopen')f.click(f.toggle);}
  outcome==='success'?resolve():reject(Error('blocked'));await tick();
  assert.equal(f.status.textContent,'');assert.equal(f.copy.disabled,false);
  if(ending==='close')assert.equal(f.panel.hidden,true);
  if(ending!=='replace')assert.equal(f.focus(),f.toggle);
 }
});

test('sharing module is explicitly published and mounted once after the routed heading',()=>{
 const build=readFileSync(new URL('../scripts/build.py',import.meta.url),'utf8'),main=readFileSync(new URL('../app/main.js',import.meta.url),'utf8');
 assert.ok(build.includes("'app/view-sharing.js'"));
 assert.ok(main.includes("from './view-sharing.js'"));
 assert.ok(main.includes("if(route.page!=='not-found')main.querySelector('h1')?.after(createViewSharing())"));
 assert.equal((main.match(/createViewSharing\(\)/g)||[]).length,1);
});
