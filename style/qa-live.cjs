/* Thales-only hosted acceptance. Runs read-only against daily Wizard; candidate assets are
 * intercepted in this isolated browser context. No daily files, APIs or selections are written.
 * Requires: PLAYWRIGHT_PATH, STYLE_ROOT; QA_URL defaults to the stock tailnet URL.
 * The release reviewer must inspect the captured screenshots, not only these assertions. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const pw=require(process.env.PLAYWRIGHT_PATH || 'playwright');
const root=process.env.STYLE_ROOT || __dirname;
const url=process.env.QA_URL || 'https://wizard.tailc0f369.ts.net/wizard-os-home/';
const shots=process.env.QA_SHOTS || path.resolve('style-qa-shots');fs.mkdirSync(shots,{recursive:true});
const tokens=JSON.parse(fs.readFileSync(path.join(root,'tokens.json')));
const client=fs.readFileSync(path.join(root,'appearance-client.js'),'utf8');
const checks=[];const transparent='rgba(0, 0, 0, 0)';
const mark=(name,value)=>{assert(value,name);checks.push(name);};
(async()=>{
 const browser=await pw.chromium.launch();
 try{
  const context=await browser.newContext({viewport:{width:412,height:892},ignoreHTTPSErrors:true});
  await context.addInitScript(()=>localStorage.setItem('wos.coached','true'));
  await context.route('**/*',async route=>{
   const req=route.request();
   if(!['GET','HEAD'].includes(req.method()))return route.fulfill({status:403,body:'Read-only QA'});
   if(/\/wizard-appearance\.js(?:\?|$)/.test(req.url()))return route.fulfill({contentType:'text/javascript',body:client});
   return route.continue();
  });
  for(const app of ['topics','wizard-music','wizard-signal','wisdom']){
   const page=await context.newPage();
   await page.goto(url+'?open='+app,{waitUntil:'domcontentloaded'});
   await page.waitForFunction(id=>Object.values(window.__wos?.wins||{}).some(w=>w.appId===id),app);
   const frame=page.frames().find(f=>f!==page.mainFrame());
   assert(frame,'cold canonical app frame '+app);
   await frame.waitForFunction(()=>window.WizardTheme?.connected);
   const before=await frame.evaluate(()=>{window.__styleQAIdentity={};return{url:location.href,type:getComputedStyle(document.querySelector('h1,h2')||document.body).fontFamily};});
   for(const skin of Object.keys(tokens.skins)){
    // Device-local browser preference only. Blocked server writes prevent box settings changes.
    await page.evaluate(id=>WosSkin.set(id),skin);
    await frame.waitForFunction(id=>WizardTheme.current?.skin===id,skin);
    const observed=await frame.evaluate(()=>({skin:WizardTheme.current.skin,tokens:WizardTheme.current.tokens,html:getComputedStyle(document.documentElement).backgroundColor,body:getComputedStyle(document.body).backgroundColor,url:location.href,type:getComputedStyle(document.querySelector('h1,h2')||document.body).fontFamily,identity:!!window.__styleQAIdentity}));
    mark(app+' '+skin+' transparent',observed.html===transparent && observed.body===transparent);
    mark(app+' '+skin+' retained document',observed.identity && observed.url===before.url && observed.type===before.type);
    mark(app+' '+skin+' exact colors',Object.keys(tokens.skins[skin].tokens).every(k=>k==='canvas'||observed.tokens[k].replace(/\s/g,'')===tokens.skins[skin].tokens[k].replace(/\s/g,'')));
    await page.screenshot({path:path.join(shots,app+'-'+skin+'.png')});
   }
   await page.close();
  }
  await context.close();
 }finally{await browser.close();}
 fs.writeFileSync(path.join(shots,'receipt.json'),JSON.stringify({host:require('node:os').hostname(),status:'PASS',checks,source:tokens.source,scope:'read-only daily cold entry with candidate appearance client; other fixture and generated-app checks reported separately'},null,2));
 console.log('PASS: '+checks.length+' live app appearance checks');
})().catch(e=>{console.error(e);process.exitCode=1});
