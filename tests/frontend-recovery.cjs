// Run with Node.js and Playwright available (NODE_PATH may point to the bundled runtime).
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const root = path.resolve(__dirname, '..');
  const files = {'/':'static/index.html', '/static/app.js':'static/app.js', '/static/style.css':'static/style.css'};
  const server = http.createServer((req, res) => {
    if (req.url === '/api/health') {
      res.setHeader('Content-Type', 'application/json');
      return res.end(JSON.stringify({mode:'live', model_configured:true, knowledge_count:7731, snapshot_date:'2026-10-13', request_timeout_seconds:45}));
    }
    if (!files[req.url]) { res.writeHead(404); return res.end(); }
    res.setHeader('Content-Type', req.url.endsWith('.js') ? 'text/javascript' : req.url.endsWith('.css') ? 'text/css' : 'text/html');
    res.end(fs.readFileSync(path.join(root, files[req.url])));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch({headless:true, ...(process.env.BROWSER_CHANNEL ? {channel:process.env.BROWSER_CHANNEL} : {})});
    const page = await browser.newPage({viewport:{width:1280, height:900}});
    await page.emulateMedia({reducedMotion:'reduce'});
    let outcome = 'answer';
    const requests = [];
    const answer = {answer:'河洛新援属于初始天赋。', intent:'knowledge', status:'answered', latency_ms:123,
      mode:'live', sources:[{id:'SHORT', title:'河洛新援·天赋组', url:'https://wzwxq.com/explore/talent-635014',
        claim_type:'wiki_reference', source_title:'万象棋知识站', collected_at:'2026-10-13', version_scope:'公开快照',
        excerpt:'初始天赋', excerpt_kind:'reference', official_url:'bad-url'}]};
    await page.route('**/api/chat', async route => {
      requests.push(route.request().postDataJSON());
      if (outcome === 'network') return route.abort();
      if (outcome === 'html') return route.fulfill({status:500, contentType:'text/html', body:'private server stack'});
      if (outcome === 'api') return route.fulfill({status:502, json:{error:{code:'model_failure', message:'private provider detail'}}});
      return route.fulfill({json: outcome === 'bad-url' ? {...answer, sources:[{...answer.sources[0], url:'bad-url'}]} : answer});
    });
    const url = `http://127.0.0.1:${server.address().port}`;
    for (const scenario of ['answer', 'bad-url', 'api', 'html', 'network']) {
      outcome = scenario;
      await page.goto(url);
      await page.locator('#message').fill('和河洛相关的天赋有哪些？');
      await page.locator('#send').click();
      await page.waitForFunction(() => !document.querySelector('#send').disabled);
      assert.equal(await page.locator('.message.error').count(), 0);
      const bubble = page.locator('.message.assistant .bubble').last();
      assert.equal(await bubble.evaluate(el => getComputedStyle(el).backgroundColor), 'rgb(255, 254, 250)');
      const text = await bubble.textContent();
      assert(!text.includes('private'));
      if (scenario === 'answer' || scenario === 'bad-url') {
        assert.equal(text, answer.answer);
        assert.equal(await page.locator('.retry').count(), 0);
        if (scenario === 'answer') {
          await page.getByText('查看资料原文与来源（1）').click();
          assert.equal(await page.locator('blockquote').textContent(), '初始天赋');
          assert(await page.getByText('相关资料原文，供你核对').isVisible());
        }
      } else {
        assert(await page.getByRole('button', {name:'再试一次'}).isVisible());
        outcome = 'answer';
        await page.getByRole('button', {name:'再试一次'}).click();
        await page.waitForFunction(() => !document.querySelector('#send').disabled);
        assert.equal(await page.locator('.message.user').count(), 1);
        assert.equal(await page.locator('.message.assistant .bubble').textContent(), answer.answer);
        assert.equal(requests.at(-1).message, requests.at(-2).message);
      }
      console.log(`PASS ${scenario}: no red error bubble, content/retry preserved`);
    }
    outcome = 'answer';
    await page.goto(url);
    const longAnswer = '先讨论天赋的效果。'.repeat(700);
    const shortAnswer = answer.answer;
    answer.answer = longAnswer;
    await page.locator('#message').fill('先聊聊天赋');
    await page.locator('#send').click();
    await page.waitForFunction(() => !document.querySelector('#send').disabled);
    answer.answer = shortAnswer;
    await page.locator('#message').fill('把它们分别说清楚');
    await page.locator('#send').click();
    await page.waitForFunction(() => !document.querySelector('#send').disabled);
    assert.deepEqual(requests.at(-1).history, [
      {role:'user', content:'先聊聊天赋'}, {role:'assistant', content:longAnswer}
    ]);
    console.log('PASS dialogue: prior user question and full long answer sent with follow-up');
    await page.getByText('查看资料原文与来源（1）').last().click();
    outcome = 'network';
    await page.locator('#message').fill('再讲详细一点');
    await page.locator('#send').click();
    await page.waitForFunction(() => !document.querySelector('#send').disabled);
    fs.mkdirSync(path.join(root, 'artifacts'), {recursive:true});
    await page.screenshot({path:path.join(root, 'artifacts/no-red-bubbles.png'), fullPage:true});
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
