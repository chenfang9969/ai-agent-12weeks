/* 企业知识库助手 —— 前端逻辑：只做"一张脸"，问答逻辑全在后端 /api/ask */
const API = { ask: "/api/ask", health: "/api/health" };
const TIMEOUT_MS = 90000;      // 模型偶尔慢，超过 90 秒就明确报错，不让用户干等
const el = (s, r = document) => r.querySelector(s);
const chat = el("#chat"), form = el("#form"), input = el("#q"),
      sendBtn = el("#send"), stats = el("#stats"), badge = el("#mode-badge"),
      subtitle = el("#subtitle"), welcome = el("#welcome");

let busy = false;
let statsData = null;

/* ---------- 1. 服务状态：先让用户知道"现在能不能用、用的是哪种模式" ---------- */
async function loadHealth() {
  try {
    const r = await fetch(API.health);
    if (!r.ok) throw new Error("HTTP " + r.status);
    const h = await r.json();
    statsData = h;
    const llm = h.llm_available;
    badge.textContent = llm ? "模型生成" : "检索模式";
    badge.className = "badge " + (llm ? "llm" : "retrieval");
    badge.title = llm ? "已配置模型：回答会做自然语言总结"
                      : "未配置模型：只返回原文片段，演示不受影响";
    subtitle.textContent = `知识库 ${h.chunks} 个切片 · ${h.mode === "llm" ? "模型可用" : "降级检索"}`;
    renderStats();
  } catch (e) {
    badge.textContent = "服务未连上";
    badge.className = "badge down";
    subtitle.textContent = "后端没起来：在 kb-api 目录跑 python server.py";
  }
}

function renderStats() {
  if (!statsData) return;
  const up = statsData.uptime_sec;
  const run = up < 60 ? `${up} 秒` : up < 3600 ? `${Math.floor(up / 60)} 分` : `${(up / 3600).toFixed(1)} 小时`;
  stats.textContent = `已问答 ${statsData.questions_asked} 次 · 运行 ${run}`;
}

/* ---------- 2. 提问 ---------- */
async function ask(question) {
  const q = question.trim();
  if (!q || busy) return;
  busy = true;
  welcome?.remove();
  input.value = "";
  autosize();
  sendBtn.disabled = true;

  addUser(q);
  const pending = addBot();
  pending.querySelector(".bubble").innerHTML =
    '<span class="dots"><i></i><i></i><i></i></span><span class="loading-text">检索资料中 0.0s</span>';
  const t0 = performance.now();
  const tick = setInterval(() => {
    const t = (performance.now() - t0) / 1000;
    const lt = pending.querySelector(".loading-text");
    if (lt) lt.textContent = `检索资料中 ${t.toFixed(1)}s`;
  }, 100);

  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const resp = await fetch(API.ask, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q, top_k: 3, min_score: 0.25 }),
      signal: ctrl.signal,
    });
    if (resp.status === 422) throw new Error("问题不合法：不能为空，且不超过 500 字。");
    if (!resp.ok) throw new Error(`服务返回 HTTP ${resp.status}`);
    const data = await resp.json();
    renderAnswer(pending, data, performance.now() - t0);
  } catch (e) {
    if (e.name === "AbortError") {
      renderError(pending, "90 秒没有响应。", "模型可能卡住了，或者网络断了 —— 后端仍在跑，可以稍后重试。");
    } else if (e instanceof TypeError) {
      renderError(pending, "连不上后端。", "确认 kb-api 已启动：python server.py（默认 127.0.0.1:8100）。");
    } else {
      renderError(pending, e.message || "请求失败");
    }
  } finally {
    clearTimeout(timer);
    clearInterval(tick);
    busy = false;
    sendBtn.disabled = false;
    input.focus();
    scrollToEnd();
  }
}

/* ---------- 3. 渲染 ---------- */
function addUser(text) {
  const d = document.createElement("div");
  d.className = "msg user";
  d.innerHTML = '<div class="avatar">我</div><div class="bubble"></div>';
  d.querySelector(".bubble").textContent = text;
  chat.appendChild(d);
  scrollToEnd();
}

function addBot() {
  const d = document.createElement("div");
  d.className = "msg bot";
  d.innerHTML = '<div class="avatar">知</div><div class="bubble"></div>';
  chat.appendChild(d);
  scrollToEnd();
  return d;
}

function renderAnswer(node, data, ms) {
  const bubble = node.querySelector(".bubble");
  bubble.innerHTML = "";

  const p = document.createElement("p");
  p.textContent = data.answer;
  bubble.appendChild(p);
  if (data.refused) {
    const s = document.createElement("small");
    s.style.cssText = "display:block;color:var(--ink-3);font-size:12px;margin-top:6px";
    s.textContent = "这是设计：宁可说没有，也不编一个答案。";
    bubble.appendChild(s);
  }

  const meta = document.createElement("div");
  meta.className = "meta";
  const modeTag = document.createElement("span");
  modeTag.className = "tag " + (data.mode === "llm" ? "llm" : "retrieval");
  modeTag.textContent = data.mode === "llm" ? "模型生成" : "检索模式";
  meta.appendChild(modeTag);
  if (data.refused) {
    const t = document.createElement("span");
    t.className = "tag refused";
    t.textContent = "已拒答 · 不编造";
    meta.appendChild(t);
  }
  const t = document.createElement("span");
  t.textContent = `${(ms / 1000).toFixed(1)}s · ${data.sources.length} 条来源`;
  meta.appendChild(t);
  bubble.appendChild(meta);

  if (data.sources.length) {
    const det = document.createElement("details");
    det.className = "sources";
    const sum = document.createElement("summary");
    sum.textContent = `查看依据（${data.sources.length} 段原文）`;
    det.appendChild(sum);
    for (const s of data.sources) {
      const box = document.createElement("div");
      box.className = "src";
      const sc = document.createElement("span");
      sc.className = "score";
      sc.textContent = "相关度 " + s.score.toFixed(2);
      const nm = document.createElement("span");
      nm.className = "name";
      nm.textContent = `${s.file} · ${s.section}`;
      const ex = document.createElement("p");
      ex.className = "excerpt";
      ex.textContent = s.excerpt;
      box.append(sc, nm, ex);
      det.appendChild(box);
    }
    bubble.appendChild(det);
  }
  refreshHealth();
}

function renderError(node, msg, detail) {
  const bubble = node.querySelector(".bubble");
  bubble.innerHTML = "";
  const p = document.createElement("p");
  p.className = "err";
  p.textContent = "⚠ " + msg;
  bubble.appendChild(p);
  if (detail) {
    const s = document.createElement("small");
    s.textContent = detail;
    p.appendChild(s);
  }
}

/* ---------- 4. 交互细节 ---------- */
function autosize() {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 132) + "px";
}
function scrollToEnd() { chat.scrollTop = chat.scrollHeight; }

async function refreshHealth() {
  try {
    const r = await fetch(API.health);
    if (r.ok) { statsData = await r.json(); renderStats(); }
  } catch { /* 状态刷新失败不影响主流程 */ }
}

form.addEventListener("submit", (e) => { e.preventDefault(); ask(input.value); });
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    ask(input.value);
  }
});
input.addEventListener("input", autosize);
document.addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (chip) ask(chip.dataset.q);
});
el("#btn-reset").addEventListener("click", () => {
  chat.innerHTML = "";
  const w = document.createElement("section");
  w.className = "welcome"; w.id = "welcome";
  w.innerHTML = `<h2>问点什么？</h2>
    <p>回答只依据企业资料，找到依据才回答，找不到会明确说“资料里没有”。</p>
    <div class="chips">
      <button class="chip" data-q="客户投诉怎么处理？">客户投诉怎么处理？</button>
      <button class="chip" data-q="客户说AI答不准怎么办？">客户说 AI 答不准怎么办？</button>
      <button class="chip" data-q="软件服务期多久？">软件服务期多久？</button>
      <button class="chip" data-q="私有化部署要什么服务器？">私有化部署要什么服务器？</button>
    </div>`;
  chat.appendChild(w);
  input.focus();
});

loadHealth();
setInterval(loadHealth, 60000);
input.focus();
