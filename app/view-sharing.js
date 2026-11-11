// Share the applied hash route, never a transport/cache query or URL credentials.
// A view link is deliberately not represented as an immutable evidence snapshot.
export function viewURL(href) {
 const url=new URL(href);
 if(!['http:','https:'].includes(url.protocol))throw Error('A web address is required.');
 return url.origin+url.pathname+(url.hash||'#/');
}

export function createViewSharing({document:doc=document,href=location.href,clipboard=()=>navigator.clipboard}={}) {
 const url=viewURL(href);
 const make=(tag,attrs={},text='')=>{
  const node=doc.createElement(tag);
  for(const [key,value] of Object.entries(attrs))node.setAttribute(key,value);
  if(text)node.textContent=text;
  return node;
 };
 const host=make('div',{class:'view-sharing'});
 const toggle=make('button',{type:'button',class:'button secondary small','aria-expanded':'false','aria-controls':'view-sharing-panel'},'Share this view');
 const panel=make('section',{id:'view-sharing-panel',class:'view-sharing-panel',hidden:'','aria-label':'Share this view'});
 const explanation=make('p',{},'Keeps the filters and reading depth in the address bar. Apply search changes before copying.');
 const label=make('label',{for:'view-sharing-url'},'Link to this view');
 const input=make('input',{id:'view-sharing-url',type:'text',readonly:'',value:url,spellcheck:'false','aria-describedby':'view-sharing-limits'});
 const limits=make('p',{id:'view-sharing-limits',class:'small'},'Evidence can change in later releases. This is not a frozen snapshot or a current-status claim. Use the reviewed download and receipt where provided.');
 const actions=make('div',{class:'view-sharing-actions'});
 const copy=make('button',{type:'button',class:'button small'},'Copy link');
 const select=make('button',{type:'button',class:'button secondary small'},'Select link');
 const close=make('button',{type:'button',class:'button secondary small'},'Close');
 const status=make('p',{class:'view-sharing-status small',role:'status','aria-live':'polite','aria-atomic':'true'});
 const selectLink=()=>{input.focus();input.select();input.setSelectionRange(0,input.value.length);};
 let generation=0;
 const setOpen=open=>{
  generation++;
  panel.hidden=!open;toggle.setAttribute('aria-expanded',String(open));status.textContent='';
  if(!open)toggle.focus();
 };
 toggle.addEventListener('click',()=>setOpen(panel.hidden));
 close.addEventListener('click',()=>setOpen(false));
 host.addEventListener('keydown',event=>{
  if(event.key==='Escape'){event.preventDefault();setOpen(false);}
 });
 select.addEventListener('click',()=>{
  selectLink();status.textContent='Link selected. Use your device’s Copy command.';
 });
 copy.addEventListener('click',async()=>{
  if(copy.disabled)return;
  const current=generation;copy.disabled=true;copy.textContent='Copying…';status.textContent='';
  const active=()=>host.isConnected&&!panel.hidden&&current===generation;
  try{
   const service=clipboard();
   if(!service?.writeText)throw Error('Clipboard unavailable');
   await service.writeText(url);
   if(active())status.textContent='Link copied. Paste it wherever you want to share this view.';
  }catch{
   if(active()){
    selectLink();status.textContent='Automatic copy is unavailable. Link selected; use your device’s Copy command.';
   }
  }finally{
   copy.disabled=false;copy.textContent='Copy link';
  }
 });
 actions.append(copy,select,close);
 panel.append(explanation,label,input,limits,actions,status);
 host.append(toggle,panel);
 return host;
}
