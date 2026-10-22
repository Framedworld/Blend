import { chromium } from 'file:///C:/Users/mattk/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),out=path.join(root,'output/sculpt-design');
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--disable-gpu']});
const page=await browser.newPage({viewport:{width:1920,height:1080}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));
await page.goto(pathToFileURL(path.join(out,'index.html')).href);await page.waitForLoadState('networkidle');
const checks=[];function check(name,value){checks.push({name,ok:!!value});if(!value)throw Error(name)}
check('sculpt grid defaults off',!(await page.locator('#canvas').getAttribute('class')).includes('grid-on'));
await page.locator('[data-grid]').click();check('sculpt grid is optional',(await page.locator('#canvas').getAttribute('class')).includes('grid-on'));await page.locator('[data-grid]').click();
const canvasBox=await page.locator('#canvas').boundingBox(),tip={x:canvasBox.x+canvasBox.width*.5,y:canvasBox.y+canvasBox.height*.5};
await page.mouse.move(tip.x,tip.y);await page.mouse.down();check('press hides brush rings',await page.locator('#ring').evaluate(e=>getComputedStyle(e).visibility)==='hidden');
await page.mouse.move(tip.x+45,tip.y+20);const cross=await page.locator('#crosshair').boundingBox();check('held crosshair follows pointer',Math.abs(cross.x+4-tip.x-45)<1&&Math.abs(cross.y+4-tip.y-20)<1);
await page.mouse.up();check('release restores rings',await page.locator('#ring').evaluate(e=>getComputedStyle(e).visibility)==='visible');
await page.keyboard.press('b');check('B browser',await page.locator('#browser').isVisible());await page.keyboard.press('c');await page.keyboard.press('b');check('B C B selects ClayBuildup',(await page.locator('#activeName').textContent())==='ClayBuildup');
await page.keyboard.down('Space');check('Space quick menu',await page.locator('#quick').isVisible());await page.locator('#quick [data-field=size]').fill('88');await page.locator('#quick [data-field=size]').dispatchEvent('input');await page.keyboard.up('Space');check('Space release closes',!await page.locator('#quick').isVisible());check('shared slider',await page.locator('.header [data-field=size]').inputValue()==='88');
await page.keyboard.press('Tab');check('Tab focus',(await page.locator('#studio').getAttribute('class')).includes('focus'));await page.keyboard.press('Tab');await page.locator('#modeSwitch').click();check('Modeling transition',(await page.locator('#studio').getAttribute('class')).includes('modeling'));await page.screenshot({path:path.join(out,'modeling-reference.png')});await page.locator('#modeSwitch').click();
for(const [width,height] of [[1280,720],[1920,1080],[2560,1440]]){await page.setViewportSize({width,height});const c=await page.locator('#canvas').boundingBox();await page.mouse.move(c.x+c.width*.5,c.y+c.height*.5);await page.screenshot({path:path.join(out,`sculpt-reference-${width}.png`)});check('no document overflow '+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth))}
await page.setViewportSize({width:1920,height:1080});await page.locator('#brushWell').click();await page.screenshot({path:path.join(out,'brush-browser-reference.png')});await page.keyboard.press('Escape');await page.locator('#quickButton').click();await page.screenshot({path:path.join(out,'quick-controls-reference.png')});
await page.goto(pathToFileURL(path.join(out,'layout-reference.html')).href);await page.setViewportSize({width:1280,height:1120});await page.screenshot({path:path.join(out,'layout-reference.png'),fullPage:true});
fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify({checks,errors},null,2));await browser.close();console.log(JSON.stringify({checks,errors}));
