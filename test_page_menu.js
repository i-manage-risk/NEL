const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('assets/workspace.js','utf8');
const code=source.slice(source.indexOf('const closeMenu=()=>'),source.indexOf('if(!window.pageMenuOutsideBound)'));
let focuses=0;
const items=['debrief','environment','leadership','positioning','screener'].map(page=>({dataset:{page},classList:{toggle(){}},focus(){focuses++}}));
const menu={hidden:true,querySelectorAll:()=>items};
const button={attributes:{},setAttribute(k,v){this.attributes[k]=v},focus(){focuses++}};
const wrapper={contains:target=>items.includes(target)||target===button};
const location={hash:'#screener'};
vm.runInNewContext(code,{menu,menuButton:button,route:'screener',location,document:{activeElement:button,querySelector:()=>wrapper}});
button.onclick({detail:1});assert.equal(menu.hidden,false);assert.equal(focuses,0);
// Touch browsers can emit null relatedTarget before the item's click.
wrapper.onfocusout({relatedTarget:null,currentTarget:wrapper});assert.equal(menu.hidden,false);
items[2].onclick();assert.equal(location.hash,'leadership');assert.equal(menu.hidden,true);
button.onclick({detail:1});wrapper.onfocusout({relatedTarget:items[1],currentTarget:wrapper});assert.equal(menu.hidden,false);
wrapper.onfocusout({relatedTarget:{},currentTarget:wrapper});assert.equal(menu.hidden,true);
let prevented=false;button.onkeydown({key:'ArrowDown',preventDefault(){prevented=true}});assert(prevented);assert.equal(menu.hidden,false);assert(focuses>0);
console.log('Page menu: touch focus transitions, page selection, outside focus and keyboard opening passed.');
