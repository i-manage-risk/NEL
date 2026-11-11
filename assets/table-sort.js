/* Shared table sorting: descending → ascending → original row order. */
(() => {
 if(window.nelTableSorting)return;window.nelTableSorting=true;
 const states=new WeakMap(),collator=new Intl.Collator(undefined,{numeric:true,sensitivity:'base'});
 function value(cell){
  if(!cell)return null;
  const explicit=cell.dataset.sortValue;
  const text=(explicit!==undefined?explicit:(cell.querySelector('button,a')?.textContent||cell.textContent)).replace(/\u2212/g,'-').trim();
  if(!text||/^(?:—|–|-|n\/a|unavailable|null|undefined)$/i.test(text))return null;
  if(explicit!==undefined&&Number.isFinite(Number(text)))return Number(text);
  if(/^\d{4}-\d{2}-\d{2}/.test(text))return Date.parse(text.slice(0,10));
  if(/^\d{1,2}\/\d{1,2}\/\d{4}$/.test(text))return Date.parse(text);
  if(/^(above|below)$/i.test(text))return /^above$/i.test(text)?1:0;
  const match=text.replace(/,/g,'').match(/^\(?\s*([+-]?)\s*\$?\s*(\d+(?:\.\d+)?)(?:\s*([KMBT])\b)?/i);
  if(match){let n=Number(match[2])*({K:1e3,M:1e6,B:1e9,T:1e12}[match[3]?.toUpperCase()]||1);if(match[1]==='-'||text.startsWith('('))n=-n;return n;}
  return text.replace(/[↑↓]/g,'').trim();
 }
 function cells(row){const result=[];for(const cell of row.cells)for(let n=0;n<cell.colSpan;n++)result.push(cell);return result;}
 function headers(table){
  const grid=[],result=[];
  [...(table.tHead?.rows||[])].forEach((row,r)=>{grid[r]??=[];let c=0;for(const cell of row.cells){while(grid[r][c])c++;result.push({cell,column:c});for(let y=r;y<r+cell.rowSpan;y++){grid[y]??=[];for(let x=c;x<c+cell.colSpan;x++)grid[y][x]=true;}c+=cell.colSpan;}});
  return result;
 }
 function remember(table){
  let state=states.get(table);if(!state){state={column:null,direction:null,order:new WeakMap(),next:0};states.set(table,state);}
  for(const body of table.tBodies)for(const row of body.rows)if(!state.order.has(row))state.order.set(row,state.next++);
  return state;
 }
 function prepare(table){
  remember(table);
  for(const {cell,column} of headers(table)){
   if(cell.tagName!=='TH')continue;
   cell.dataset.nelColumn=column;cell.classList.add('nel-sortable');
   if(!cell.hasAttribute('tabindex'))cell.tabIndex=0;
   if(!cell.hasAttribute('aria-sort'))cell.setAttribute('aria-sort','none');
   // Replace page-specific arrows with a single shared state indicator.
   const walker=document.createTreeWalker(cell,NodeFilter.SHOW_TEXT);let node;
   while((node=walker.nextNode()))if(/[↑↓]/.test(node.nodeValue))node.nodeValue=node.nodeValue.replace(/\s*[↑↓]/g,'');
  }
 }
 function sort(header){
  const table=header.closest('table');prepare(table);const state=remember(table),column=Number(header.dataset.nelColumn);
  state.direction=state.column!==column||state.direction===null?'descending':state.direction==='descending'?'ascending':null;state.column=state.direction?column:null;
  for(const body of table.tBodies){const rows=[...body.rows];rows.sort((a,b)=>{
   const fallback=state.order.get(a)-state.order.get(b);if(!state.direction)return fallback;
   const av=value(cells(a)[column]),bv=value(cells(b)[column]);if(av===null||bv===null)return av===bv?fallback:av===null?1:-1;
   const difference=typeof av==='number'&&typeof bv==='number'?av-bv:collator.compare(String(av),String(bv));return difference*(state.direction==='descending'?-1:1)||fallback;
  });body.append(...rows);}
  for(const {cell,column:c} of headers(table))cell.setAttribute('aria-sort',c===state.column?state.direction:'none');
  table.dispatchEvent(new CustomEvent('nel:table-sorted',{bubbles:true,detail:{column:state.column,direction:state.direction}}));
 }
 function target(event){const header=event.target.closest?.('thead th');return header?.closest('table')?header:null;}
 document.addEventListener('click',event=>{const header=target(event);if(!header)return;event.preventDefault();event.stopImmediatePropagation();sort(header);},true);
 document.addEventListener('keydown',event=>{if(!['Enter',' '].includes(event.key))return;const header=target(event);if(!header)return;event.preventDefault();event.stopImmediatePropagation();sort(header);},true);
 const style=document.createElement('style');style.textContent='.nel-sortable{cursor:pointer}.nel-sortable[aria-sort="descending"]::after{content:" ↓";color:#85d65d}.nel-sortable[aria-sort="ascending"]::after{content:" ↑";color:#85d65d}.nel-sortable:focus-visible{outline:2px solid #85d65d;outline-offset:-2px}';document.head.append(style);
 const pending=new Set();let scheduled=false;
 const scan=root=>{if(root.nodeType!==1)return;if(root.matches('table'))pending.add(root);root.querySelectorAll('table').forEach(t=>pending.add(t));const parent=root.closest('table');if(parent)pending.add(parent);};
 new MutationObserver(records=>{for(const record of records){scan(record.target);for(const node of record.addedNodes)scan(node);}if(!pending.size||scheduled)return;scheduled=true;requestAnimationFrame(()=>{scheduled=false;for(const table of pending)if(table.isConnected)prepare(table);pending.clear();});}).observe(document.body,{childList:true,subtree:true});
 document.querySelectorAll('table').forEach(prepare);
})();
