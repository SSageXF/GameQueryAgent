const $ = (id) => document.getElementById(id);
const conversation = $('conversation');
const input = $('message');
const labels = {knowledge:'规则问答', advice:'情境建议', chitchat:'闲聊', out_of_scope:'能力说明'};
const states = {answered:'已回答', needs_clarification:'需要补充', insufficient_evidence:'资料不足', unsupported:'未接入'};
let history = [], active = null, timeoutSeconds = 50;

function scrollBottom() { conversation.scrollTop = conversation.scrollHeight; }
function addMessage(role, text, className = '') {
  $('welcome').hidden = true;
  const wrapper = document.createElement('article');
  wrapper.className = `message ${role} ${className}`;
  const speaker = document.createElement('div');
  speaker.className = 'speaker'; speaker.textContent = role === 'user' ? '你 / PLAYER' : '弈宝 / YOUR GUIDE';
  const bubble = document.createElement('div'); bubble.className = 'bubble'; bubble.textContent = text;
  wrapper.append(speaker, bubble); conversation.append(wrapper); scrollBottom();
  return wrapper;
}
function boundedHistory(items) {
  let selected = items.slice(-12);
  while (selected.reduce((n, item) => n + item.content.length, 0) > 12000) selected = selected.slice(2);
  return selected;
}
async function send(message, retryRow = null) {
  if (active || !message.trim()) return;
  message = message.trim();
  if (message.length > 1000) return;
  if (retryRow) retryRow.remove(); else addMessage('user', message);
  const pending = addMessage('assistant', '让我看看，马上来…', 'loading');
  const controller = new AbortController(); active = controller;
  $('send').disabled = true; input.value = ''; updateCounter();
  const timer = setTimeout(() => controller.abort('timeout'), timeoutSeconds * 1000);
  try {
    const response = await fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({message, history:boundedHistory(history)}), signal:controller.signal});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error?.message || `请求失败（${response.status}）`);
    if (active !== controller) return;
    pending.remove();
    const row = addMessage('assistant', result.answer);
    const meta = document.createElement('div'); meta.className = 'meta';
    meta.textContent = `${labels[result.intent]} · ${states[result.status]} · ${result.latency_ms < 1000 ? result.latency_ms + ' ms' : (result.latency_ms / 1000).toFixed(1) + ' s'}${result.mode === 'mock' ? ' · MOCK' : ''}`;
    row.append(meta);
    if (result.sources.length) {
      const details = document.createElement('details'); details.className = 'sources';
      const summary = document.createElement('summary'); summary.textContent = `查看引用原文与来源（${result.sources.length}）`; details.append(summary);
      for (const source of result.sources) {
        const url = new URL(source.url);
        if (url.protocol !== 'https:') continue;
        const link = document.createElement('a'); link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer';
        link.textContent = `${source.id} · ${source.title} ↗`;
        const kinds = {official_original:'官方原文 · 已逐字段核对', wiki_original:'Wiki收录原文', wiki_reference:'Wiki结构化资料', site_model:'站点工具模型 · 非实战保证', site_interpretation:'站方解释 · 非官方结论', pending:'待确认 · 不作确定依据', rule:'官网规则整理', official_recommendation:'官方入门推荐'};
        const scope = document.createElement('small'); scope.textContent = `${kinds[source.claim_type] || source.claim_type} · ${source.source_title} · 采集于 ${source.collected_at} · ${source.version_scope}`;
        details.append(link, scope);
        if (source.excerpt) {
          const quote = document.createElement('blockquote'); quote.textContent = source.excerpt;
          details.append(quote);
        }
        if (source.official_url) {
          const official = new URL(source.official_url);
          if (official.protocol === 'https:' && official.hostname === 'game.gtimg.cn') {
            const proof = document.createElement('a'); proof.href = official.href; proof.target = '_blank'; proof.rel = 'noopener noreferrer'; proof.textContent = '官网比对数据 ↗'; details.append(proof);
          }
        }
      }
      row.append(details);
      const note = document.createElement('small'); note.className = 'source-scope';
      note.textContent = '引用来自已收录的资料快照，日期和原文见来源。'; row.append(note);
    }
    if (result.routing?.status === 'fallback') {
      const note = document.createElement('div'); note.className = 'meta';
      note.textContent = '这次模型分类未完成，已使用基础识别。'; row.append(note);
    }
    if (result.retrieval_plan) {
      const plan = result.retrieval_plan;
      const detail = document.createElement('details'); detail.className = 'sources';
      const summary = document.createElement('summary'); summary.textContent = '查看检索词';
      const text = document.createElement('small');
      text.textContent = `${plan.status === 'model' ? '模型生成' : plan.status === 'mock_rules' ? 'Mock规则' : '规划失败，使用回退检索'} · ${plan.mode}\n${plan.queries.join('；')}\n关键词：${plan.keywords.join('、') || '原问题'}`;
      detail.append(summary, text); row.append(detail);
    }
    history = boundedHistory([...history, {role:'user', content:message}, {role:'assistant', content:result.answer.slice(0,3000)}]);
    scrollBottom();
  } catch (error) {
    if (active !== controller) return;
    pending.remove();
    const errorText = controller.signal.aborted ? '等待超时，请重试。' : error instanceof TypeError ? '无法连接后端，请确认服务已启动后重试。' : error.message || '请求失败，请稍后重试。';
    const row = addMessage('assistant', errorText, 'error');
    const retry = document.createElement('button'); retry.type = 'button'; retry.className = 'retry'; retry.textContent = '重新发送';
    retry.addEventListener('click', () => send(message, row)); row.append(retry); scrollBottom();
  } finally {
    clearTimeout(timer);
    if (active === controller) { active = null; $('send').disabled = false; input.focus(); }
  }
}
function updateCounter() { $('counter').textContent = `${input.value.length} / 1000`; }
$('chat-form').addEventListener('submit', (event) => { event.preventDefault(); send(input.value); });
input.addEventListener('input', updateCounter);
input.addEventListener('keydown', (event) => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); send(input.value); } });
document.querySelectorAll('[data-question]').forEach(button => button.addEventListener('click', () => send(button.dataset.question)));
$('clear').addEventListener('click', () => {
  if (active) active.abort('clear'); active = null; history = [];
  document.querySelectorAll('.message').forEach(row => row.remove());
  $('welcome').hidden = false; $('send').disabled = false; input.value = ''; updateCounter(); input.focus();
});
fetch('/api/health').then(response => { if (!response.ok) throw new Error(); return response.json(); }).then(health => {
  timeoutSeconds = health.request_timeout_seconds + 5;
  $('mode').className = 'mode-banner ' + (health.mode === 'mock' ? 'mock' : !health.model_configured ? 'unready' : '');
  document.querySelector('time').dateTime = health.snapshot_date;
  document.querySelector('time').textContent = health.snapshot_date.replaceAll('-', '.');
  $('mode').textContent = health.mode === 'mock' ? 'MOCK 联调模式 · 当前展示为规则与资料拼接，不是真实模型回答，不能用于模型质量评测。' : health.model_configured ? `向导已连接 · ${health.knowledge_count} 条分层资料 · 原文、解释与待确认项分开处理` : '模型尚未配置 · 请按 README 在后端 .env 中配置模型，再重启服务。';
}).catch(() => { $('mode').className = 'mode-banner unready'; $('mode').textContent = '暂时无法连接服务，请检查后端后刷新页面。'; });
