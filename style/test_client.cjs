/* Protocol unit fixtures. Real CSS/color and canvas checks belong to the browser receipt. */
const vm = require('node:vm'), fs = require('node:fs'), assert = require('node:assert/strict');
const source = fs.readFileSync(__dirname + '/appearance-client.js', 'utf8');
const palette = JSON.parse(fs.readFileSync(__dirname + '/tokens.json', 'utf8')).skins.nebula.tokens;
function setup() {
  const props = {}, listeners = {}, sent = [], events = [];
  const root = { dataset: {}, style: {setProperty:(k,v)=>props[k]=v}, setAttribute:()=>{}, classList:{add:()=>{}} };
  const parent = {postMessage:(data,origin)=>sent.push({data,origin})};
  const ctx = {document:{documentElement:root}, location:{origin:'https://box.example'}, parent,
    CSS:{supports:(_,v)=>v !== 'not-a-color'}, addEventListener:(n,fn)=>listeners[n]=fn,
    dispatchEvent:e=>events.push(e), CustomEvent:class {constructor(type,init){this.type=type;this.detail=init.detail;}}};
  ctx.window = ctx;
  vm.runInNewContext(source,ctx);
  const send = (a, overrides={}) => listeners.message({source:parent,origin:'https://box.example',data:{type:'wizard:appearance',appearance:a},...overrides});
  const a = (revision=1) => ({version:1,revision,skin:'nebula',colorScheme:'dark',presentation:'window',tokens:{...palette,canvas:'transparent'}});
  return {ctx,root,props,sent,events,send,a};
}
const f=setup(); assert.equal(f.sent[0].data.type,'wizard:appearance:ready'); f.send(f.a());
assert.equal(f.ctx.WizardTheme.connected,true); assert.equal(f.ctx.WizardTheme.current.revision,1);
assert.equal(Object.keys(f.props).length,14); assert.equal(f.props['--wz-canvas'],'transparent');
assert(Object.isFrozen(f.ctx.WizardTheme.current.tokens)); assert.equal(f.events.length,1);
const reversed={...f.a(),tokens:Object.fromEntries(Object.entries(f.a().tokens).reverse())};
f.send(reversed); assert.equal(f.sent.at(-1).data.type,'wizard:appearance:ack'); assert.equal(f.sent.length,3); assert.equal(f.events.length,1);
f.send(f.a(0)); assert.equal(f.sent.length,3); assert.equal(f.events.length,1);
f.send({...f.a(1),skin:'grove'}); assert.equal(f.events.length,1);
f.send({...f.a(2),skin:'signal',presentation:'immersive'}); assert.equal(f.root.dataset.skin,'signal'); assert.equal(f.events.length,2);
const bads=[a=>({...a,version:2}),a=>({...a,revision:-1}),a=>({...a,revision:1.2}),a=>({...a,skin:'bad;skin'}),a=>({...a,presentation:'standalone'}),a=>({...a,colorScheme:'blue'}),a=>({...a,tokens:{...a.tokens,canvas:'#000'}}),a=>({...a,tokens:{...a.tokens,text:undefined}}),...['var(--wz-text)','color-mix(in srgb, var(--x), red)','env(color)','attr(color)','inherit','initial','unset','revert','revert-layer','currentcolor','url(x)','red; color:blue','not-a-color'].map(v=>a=>({...a,tokens:{...a.tokens,text:v}}))];
for(const change of bads){const t=setup();t.send(change(t.a()));assert.equal(t.ctx.WizardTheme.connected,false);assert.equal(t.sent.length,1);}
for(const overrides of [{origin:'https://wrong.example'},{source:{}},{data:{type:'wrong'}}]){const t=setup();t.send(t.a(),overrides);assert.equal(t.ctx.WizardTheme.connected,false);}
const light=setup();light.send({...light.a(),skin:'generic-light',colorScheme:'light'});assert.equal(light.root.style.colorScheme,'light');
console.log('PASS: Appearance v1 schema, parent/origin, 14 colors, transparency, reordered retransmissions, stale revisions and generic light fixtures.');
