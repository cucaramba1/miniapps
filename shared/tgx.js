/* tgx: tiny runtime shared by all mini-app prototypes.
   Uses the real Telegram.WebApp when present, otherwise a mock so the same file works in a browser.
   Screen registry is exposed on window.__app for the e2e/stress tests. */
(function(){
  const real = window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData ? window.Telegram.WebApp : null;
  const $ = (s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
  const state = { stack:[], current:null, haptics:0, log:[] };
  const screens = {};

  function haptic(kind){ state.haptics++; try{ real && real.HapticFeedback && real.HapticFeedback.impactOccurred(kind||'light'); }catch(e){} }

  function toast(msg){
    const t=$('#toast'); if(!t) return; t.textContent=msg; t.classList.add('on');
    clearTimeout(toast._t); toast._t=setTimeout(()=>t.classList.remove('on'),1800);
  }

  let mainHandler=null;
  function setMain(text,handler,opts={}){
    const b=$('#mainbtn'); if(!b) return;
    if(!text){ b.classList.remove('show'); mainHandler=null; return; }
    b.textContent=text; b.classList.add('show'); b.disabled=!!opts.disabled; mainHandler=handler;
  }

  function go(id,opts={}){
    const def=screens[id]; if(!def){ console.error('no screen',id); return; }
    const prev=state.current;
    if(prev && !opts.replace && !def.tab) state.stack.push({id:prev,params:state.params});
    if(def.tab) state.stack=[];
    state.params=opts.params||{};
    $$('.screen').forEach(s=>s.classList.toggle('on',s.id==='s-'+id));
    state.current=id;
    $$('.tab').forEach(t=>t.classList.toggle('on',t.dataset.go===(def.tab||def.parentTab||'')));
    $('.tabbar')?.classList.toggle('hidden',!!def.hideTabs);
    const el=$('#s-'+id); if(el){ el.scrollTop=0; }
    if(def.enter) def.enter(el,opts.params||{});
    else setMain(null);
    $('#tgtitle') && ($('#tgtitle').textContent=def.title||'');
    const bb=$('#tgback'); if(bb) bb.style.visibility = state.stack.length ? 'visible':'hidden';
    nativeBack();
    state.log.push(id); haptic('light');
  }
  /* Native Telegram BackButton follows the screen stack: the system back (Android button, iOS swipe) steps back instead of closing the app. */
  function nativeBack(){ try{ if(real && real.BackButton){ state.stack.length ? real.BackButton.show() : real.BackButton.hide(); } }catch(e){} }
  function back(){ const p=state.stack.pop(); if(p) go(p.id,{replace:true,params:p.params}); }

  function sheet(id,on){
    $('#scrim').classList.toggle('on',on); $('#'+id).classList.toggle('on',on);
    if(on) haptic('medium');
  }

  /* Clipboard can be denied inside Telegram WebView: never let it throw. */
  function copy(text){
    const done=()=>toast('Скопировано');
    const fb=()=>{ try{ const t=document.createElement('textarea'); t.value=text; t.style.position='fixed'; t.style.opacity='0'; document.body.appendChild(t); t.select(); const ok=document.execCommand('copy'); t.remove(); ok?done():toast('Не удалось скопировать, выделите текст вручную'); }catch(e){ toast('Не удалось скопировать'); } };
    try{ navigator.clipboard.writeText(text).then(done,fb); }catch(e){ fb(); }
  }
  const esc=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function register(defs){ Object.assign(screens,defs); }

  function boot(start){
    document.body.classList.toggle('frame', !real && matchMedia('(min-width:600px)').matches);
    const dark = real ? real.colorScheme==='dark' : matchMedia('(prefers-color-scheme: dark)').matches;
    const saved=(()=>{try{return localStorage.getItem('theme')}catch(e){return null}})();
    document.documentElement.dataset.theme = saved || (dark?'dark':'light');
    if(real){ real.ready(); real.expand(); real.disableVerticalSwipes && real.disableVerticalSwipes(); try{ real.BackButton && real.BackButton.onClick(back); }catch(e){} }
    document.addEventListener('click',e=>{
      const t=e.target.closest('[data-go],[data-back],[data-sheet],[data-close],[data-toast],[data-act]'); if(!t) return;
      if(t.dataset.back!==undefined) return back();
      if(t.dataset.go) go(t.dataset.go,{params:{...t.dataset}});
      if(t.dataset.sheet) sheet(t.dataset.sheet,true);
      if(t.dataset.close!==undefined) $$('.sheet').forEach(s=>sheet(s.id,false));
      if(t.dataset.toast) toast(t.dataset.toast);
      if(t.dataset.act && api.acts[t.dataset.act]) api.acts[t.dataset.act](t,e);
    });
    $('#mainbtn')?.addEventListener('click',()=>{ haptic('medium'); mainHandler && mainHandler(); });
    $('#scrim')?.addEventListener('click',()=>$$('.sheet').forEach(s=>sheet(s.id,false)));
    $('.themebtn')?.addEventListener('click',()=>{
      const d=document.documentElement; d.dataset.theme=d.dataset.theme==='dark'?'light':'dark';
      try{localStorage.setItem('theme',d.dataset.theme)}catch(e){}
    });
    $('#tgback')?.addEventListener('click',back);
    go(start);
  }

  const api={ esc,copy,$,$$,go,back,sheet,toast,setMain,register,boot,haptic,state,screens,acts:{},real };
  window.tgx=api;
  window.__app={ screens, state, go, ids:()=>Object.keys(screens) };
})();
