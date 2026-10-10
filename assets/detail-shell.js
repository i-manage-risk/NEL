(() => {
 const page=document.currentScript.dataset.page;
 document.body.classList.add('detail-page');
 const selectedNav=page==='breadth'?'environment':page==='themes'||page==='sectors'?'leadership':'screener';
 const rail=document.createElement('aside');rail.className='rail';
 const nav=[['briefing','◉','Now'],['environment','◌','Pulse'],['leadership','◆','Flow'],['positioning','◎','Crowding'],['screener','⌕','Stocks'],['review','↺','Replay']];
 rail.innerHTML='<a class="brand" href="index.html"><img src="assets/nel-favicon.png" alt="">NEL<span>MARKET CONSOLE</span></a><nav aria-label="Workspace">'+nav.map(([key,icon,label])=>'<a class="'+(key===selectedNav?'active':'')+'" href="index.html#'+key+'"><i>'+icon+'</i><span>'+label+'</span></a>').join('')+'</nav><div class="rail-bottom"><details class="research-menu"><summary>Research ▾</summary><div><a href="industry_flow_dashboard.html">Liquid stocks</a><a href="super-liquid.html">Super Liquid</a><a href="themes.html">Themes</a><a href="sectors.html">Sectors</a><a href="breadth.html">Breadth / Time Machine</a></div></details></div>';
 document.body.prepend(rail);
 const main=document.querySelector('main'), heading=document.createElement('div');heading.className='detail-heading';
 heading.innerHTML='<div><span class="eyebrow">DETAILED RESEARCH</span><p>Full history, exports and drill-down charts.</p></div><a href="index.html#'+selectedNav+'">← Console</a>';
 main.prepend(heading);
 if(page==='breadth')return;
 const controls=document.createElement('div');controls.className='detail-controls';
 const isStock=page==='liquid'||page==='super';
 const windows=[['1w','1W'],['1m','1M'],['3m','3M'],['6m','6M'],['1y','1Y'],['all','All windows']];
 controls.innerHTML='<div class="control-group"><span>Ranking horizon</span><div class="segments">'+windows.map(([key,label])=>'<button data-window="'+key+'">'+label+'</button>').join('')+'</div></div>'+(isStock?'<div class="control-group"><span>Show</span><div class="segments">'+[['nel','NEL'],['tight','Tight NEL'],['liquid','All leaders'],['leadership','Group leadership'],['all','All sections']].map(([key,label])=>'<button data-section="'+key+'">'+label+'</button>').join('')+'</div></div>':'');
 const top=main.querySelector('.topbar');if(top)top.after(controls);else heading.after(controls);
 let activeWindow='1m', activeSection='nel';
 function apply(){
   document.body.classList.toggle('show-all-windows',activeWindow==='all');
   main.querySelectorAll('.window-sections>[data-frame],.windows>[data-frame]').forEach(el=>el.classList.toggle('detail-hidden',activeWindow!=='all'&&el.dataset.frame!==activeWindow));
   controls.querySelectorAll('[data-window]').forEach(el=>el.classList.toggle('active',el.dataset.window===activeWindow));
   if(isStock){
     ['leadership','liquid','nel','tight'].forEach(key=>{
       const el=document.getElementById(key+'-sections');if(!el)return;
       const hidden=activeSection!=='all'&&key!==activeSection;el.classList.toggle('detail-hidden',hidden);
       if(el.previousElementSibling?.classList.contains('section-heading'))el.previousElementSibling.classList.toggle('detail-hidden',hidden);
     });
     controls.querySelectorAll('[data-section]').forEach(el=>el.classList.toggle('active',el.dataset.section===activeSection));
   }
 }
 controls.addEventListener('click',event=>{const b=event.target.closest('button');if(!b)return;if(b.dataset.window)activeWindow=b.dataset.window;if(b.dataset.section)activeSection=b.dataset.section;apply();window.dispatchEvent(new Event('resize'));});
 const observer=new MutationObserver(apply);main.querySelectorAll('.windows,.window-sections').forEach(el=>observer.observe(el,{childList:true}));
 apply();
})();
