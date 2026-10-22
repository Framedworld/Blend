import { chromium } from 'file:///C:/Users/mattk/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import {pathToFileURL} from 'node:url';
import fs from 'node:fs';
import path from 'node:path';
const out=path.resolve('Blend/output'), checks=[],errors=[];
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--disable-gpu']});
const page=await browser.newPage({viewport:{width:1440,height:1000}});page.on('pageerror',e=>errors.push(String(e)));
await page.goto(pathToFileURL(path.join(out,'sculpt-reference-gallery.html')).href);
for(const button of await page.locator('button[data-index]').all()){
 const name=await button.innerText();await button.click();
 const panel=page.locator('.pair.active');await panel.locator('img').first().waitFor();
 const valid=await panel.locator('img').evaluateAll(imgs=>imgs.length===2&&imgs.every(i=>i.complete&&i.naturalWidth>0));
 checks.push({name,images:valid,selected:await button.getAttribute('aria-selected')==='true'});
}
await page.getByRole('button',{name:'Geometry',exact:true}).click();await page.screenshot({path:path.join(out,'sculpt-reference-gallery.png'),fullPage:true});
await page.setViewportSize({width:680,height:1000});checks.push({name:'narrow viewer',noOverflow:await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)});
fs.writeFileSync(path.join(out,'sculpt_reference_gallery_results.json'),JSON.stringify({checks,errors},null,2));
await browser.close();console.log(JSON.stringify({checks,errors}));
