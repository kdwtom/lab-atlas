import {chromium} from 'playwright-core';
import {readFileSync,writeFileSync} from 'node:fs';
const browser=await chromium.launch({channel:process.env.BROWSER_CHANNEL??'msedge',headless:true});
const page=await browser.newPage();
try {
  const start=Date.now();await page.goto((process.env.BASE_URL??'http://localhost:4173/')+'#/?searchDebug=1&view=list');
  await page.waitForFunction(()=>window.__labAtlasSearch,{timeout:60000});
  await page.waitForSelector('[role="combobox"]',{timeout:60000});
  const readyMs=Date.now()-start;
  const inventory=JSON.parse(readFileSync('../docs/search/benchmark.json','utf8'));
  const results=await page.evaluate(cases=>{
    const api=window.__labAtlasSearch;const stats=api.stats();const before=performance.memory?.usedJSHeapSize;
    const rows=cases.map(c=>{for(let i=0;i<5;i++)api.run(c.query,c.filters);const samples=[];for(let i=0;i<30;i++)samples.push(api.run(c.query,c.filters).ms);samples.sort((a,b)=>a-b);return {id:c.id,p50:samples[15],p95:samples[28],max:samples[29]};});
    return {stats,beforeHeap:before,afterHeap:performance.memory?.usedJSHeapSize,queries:rows,resources:performance.getEntriesByType('resource').filter(r=>r.name.includes('/data/')).map(r=>({name:r.name.split('/').at(-1),transferSize:r.transferSize,encodedBodySize:r.encodedBodySize,decodedBodySize:r.decodedBodySize}))};
  },inventory.cases);
  const inputToResults=[];
  for(const query of ['machine learning','기계 학습','RNA','zxqvnomatch913']) {
    const before=await page.evaluate(()=>performance.now());
    await page.getByRole('combobox').fill(query);
    await page.waitForFunction(q=>new URLSearchParams(location.hash.split('?')[1]).get('q')===q,query);
    const after=await page.evaluate(()=>performance.now());inputToResults.push({query,msIncludingAutomation:after-before});
  }
  const report={date:new Date().toISOString(),browser:await browser.version(),environment:'Headless desktop on Windows; not a representative phone',readyMs,...results,inputToResults,phoneTarget:'Not validated: automated desktop checks only requested'};
  writeFileSync('../docs/search/performance-results.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({indexMs:results.stats.buildMs,worstP95:Math.max(...results.queries.map(q=>q.p95)),readyMs}));
} finally {await browser.close();}
