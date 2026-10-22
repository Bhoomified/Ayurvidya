// Ayurvidya dashboard app.
// Pages: #/ dashboard · #/verses library · #/v/<id>/<step> study · #/chat/<id> ask AI · #/study and #/ask open the last verse.
// Data: GET /chapters/<id>/shlokas, GET /shlokas/<id>, POST /chat (same server).
const CHAPTER = "su.ni.1";
const STEPS = {
  1: { deva: "सम्प्रदानम्", en: "Sampradanam", why: "How the verse divides into its four padas." },
  2: { deva: "पदविभागः", en: "Padavibhaga", why: "Every word separated out, with its grammatical form." },
  3: { deva: "अन्वयः", en: "Anvaya", why: "The same words, arranged in natural prose order." },
  4: { deva: "अन्वयार्थः", en: "Anvayartha", why: "The meaning of each word, then of the whole verse." },
  5: { deva: "भावार्थः", en: "Bhavartha", why: "What the author intends to say, in brief." },
  6: { deva: "पदकृत्यम्", en: "Padakrityam", why: "Each word's root, synonyms and grammar. Tap a word to open it." },
  7: { deva: "ध्वनितार्थः", en: "Dhvanitartha", why: "The meaning between the lines: what the author hints at." },
};
// The chapter's own structure, used to group verses on the dashboard and in the library.
const SECTIONS = [
  { from: 1, to: 6, deva: "उपोद्घातः", en: "Opening and the greatness of Vayu" },
  { from: 7, to: 10, deva: "वायुस्वरूपम्", en: "Nature, qualities and functions of Vayu" },
  { from: 11, to: 21, deva: "पञ्चवायवः", en: "The five Vayus: seats, actions, disorders" },
  { from: 22, to: 31, deva: "स्थानगतवातः", en: "Vayu lodged in organs and tissues" },
  { from: 32, to: 39, deva: "आवरणम्", en: "Vata joined with or covered by other doshas" },
  { from: 40, to: 50, deva: "वातरक्तम्", en: "Vatarakta: causes, signs and prognosis" },
  { from: 51, to: 59, deva: "आक्षेपकः", en: "Convulsions, spasms and rigidity" },
  { from: 60, to: 67, deva: "पक्षाघातादयः", en: "Hemiplegia, Apatantraka, stiff neck" },
  { from: 68, to: 73, deva: "अर्दितम्", en: "Facial palsy" },
  { from: 74, to: 91, deva: "अन्ये वातव्याधयः", en: "Disorders of limbs, senses and abdomen" },
];
const DIGITS = "०१२३४५६७८९";

const $ = s => document.querySelector(s);
const view = $("#view");
const cache = { list: null, verse: {} };
const chats = {};
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const store = {
  get(k, d) { try { return localStorage.getItem(k) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* storage unavailable */ } },
};

// ---------------------------------------------------------------- helpers
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const refs = s => s.replace(/\s*\[((?:[RS]\d+)(?:\s*,\s*[RS]?\d+)*)\]/g, '<span class="ref">$1</span>');
const fmt = s => refs(esc(s));
const mixed = s => fmt(s).replace(/([\u0900-\u097F][\u0900-\u097F\s\-ऽ।॥]*[\u0900-\u097F।॥]|[\u0900-\u097F])/g, '<span class="deva-in">$1</span>');
const dn = n => String(n).replace(/\d/g, d => DIGITS[d]);
const first = id => parseInt(id.split(".").pop(), 10);
const clean = t => t.replace(/\s*[।॥|]+\s*[०-९0-9\-]+\s*[।॥|]+/g, "").replace(/[ \t]+([।॥])/g, "\u00a0$1").trim();
const sectionOf = n => SECTIONS.find(s => n >= s.from && n <= s.to) || SECTIONS[SECTIONS.length - 1];
const seen = () => new Set(JSON.parse(store.get("ayv.seen", "[]")));
const doneSteps = id => new Set(JSON.parse(store.get(`ayv.d.${id}`, "[]")));

function markStep(id, step) {
  const d = doneSteps(id); d.add(step); store.set(`ayv.d.${id}`, JSON.stringify([...d]));
  const s = seen(); s.add(id); store.set("ayv.seen", JSON.stringify([...s]));
  store.set("ayv.last", id);
}
async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) {
    let msg = `Server error ${r.status}.`;
    try { const j = await r.json(); if (typeof j.detail === "string") msg = j.detail; } catch { /* not JSON */ }
    throw new Error(msg);
  }
  return r.json();
}
const getList = async () => (cache.list = cache.list || await api(`/chapters/${CHAPTER}/shlokas`));
const getVerse = async id => (cache.verse[id] = cache.verse[id] || await api(`/shlokas/${encodeURIComponent(id)}`));

function page(nav, title, sub = "", isSub = false) {
  document.querySelectorAll("[data-nav]").forEach(a => a.classList.toggle("on", a.dataset.nav === nav));
  $("#pageTitle").textContent = title;
  $("#pageSub").textContent = sub;
  document.body.classList.toggle("sub", isSub);
  document.title = nav === "home" ? "Ayurvidya" : `${title} · Ayurvidya`;
}
function skeleton(n = 3) {
  view.innerHTML = `<div class="card"><div class="sk" style="height:28px;width:40%"></div>
    ${Array.from({ length: n }, () => '<div class="sk" style="height:16px;margin-top:16px"></div>').join("")}</div>`;
}
function failed(e) {
  view.innerHTML = `<div class="card empty"><h3>Could not reach the Ayurvidya server</h3>
    <p>${esc(e.message)} Check that serve.py is running and that this device is on the same Wi-Fi.</p>
    <button class="btn grad" onclick="route()">Try again</button></div>`;
}
function countUp(el, to) {
  if (reduced) { el.textContent = to; return; }
  const t0 = performance.now(), dur = 900;
  const tick = t => { const p = Math.min(1, (t - t0) / dur); el.textContent = Math.round(to * (1 - Math.pow(1 - p, 3))); if (p < 1) requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
}
const ICON = {
  book: '<svg viewBox="0 0 24 24"><path d="M5 4h11l3 3v13H5zM8 9h8M8 13h8M8 17h5"/></svg>',
  layers: '<svg viewBox="0 0 24 24"><path d="M12 3l9 5-9 5-9-5zM3 13l9 5 9-5"/></svg>',
  check: '<svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>',
  steps: '<svg viewBox="0 0 24 24"><path d="M4 18h4v-4h4v-4h4V6h4"/></svg>',
  arrow: '<svg viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
  left: '<svg viewBox="0 0 24 24"><path d="M15 5l-7 7 7 7"/></svg>',
  chat: '<svg viewBox="0 0 24 24"><path d="M4 5h16v11H9l-5 4z"/></svg>',
  chev: '<svg viewBox="0 0 24 24" class="chev"><path d="M6 9l6 6 6-6"/></svg>',
};

// ---------------------------------------------------------------- dashboard
async function showHome() {
  page("home", "Dashboard", "Sushruta Samhita, Nidana Sthana 1");
  skeleton(4);
  let list;
  try { list = await getList(); } catch (e) { return failed(e); }
  const s = seen(), total = list.length, studied = list.filter(v => s.has(v.id)).length;
  const steps = list.reduce((a, v) => a + doneSteps(v.id).size, 0);
  const lastId = store.get("ayv.last", null), last = list.find(v => v.id === lastId);
  const today = list[Math.floor(Date.now() / 864e5) % total];
  const pct = Math.round(100 * studied / total), C = 2 * Math.PI * 54;

  view.innerHTML = `
    <section class="hero enter">
      <div class="card hero-main">
        <div class="eyebrow">Chapter 1 of Nidana Sthana</div>
        <div class="deva big">वातव्याधिनिदानम्</div>
        <p>The diagnosis of Vata disorders: ${total} verses, each opened up in seven steps from the words to the meaning between the lines.</p>
        <div class="hero-actions">
          <a class="btn grad" href="#/v/${(last || list[0]).id}">${last ? "Continue studying" : "Start with verse 1"} ${ICON.arrow}</a>
          <a class="btn ghost" href="#/verses">Browse all verses</a>
        </div>
      </div>
      <div class="card ring-card">
        <div class="ring">
          <svg viewBox="0 0 132 132"><defs><linearGradient id="ringGrad" x1="0" x2="1"><stop offset="0" stop-color="#ffb347"/><stop offset="1" stop-color="#ff5e7e"/></linearGradient></defs>
            <circle class="track" cx="66" cy="66" r="54"/><circle class="val" id="ringVal" cx="66" cy="66" r="54" stroke-dasharray="${C}" stroke-dashoffset="${C}"/></svg>
          <div class="pct"><div><b><span id="pctNum">0</span>%</b><small>studied</small></div></div>
        </div>
        <div><h3>Your progress</h3><p>${studied ? `${studied} of ${total} verses opened. Keep the streak going.` : "Open your first verse to start tracking."}</p>
          <a class="btn ghost" href="#/study">${ICON.steps} Study now</a></div>
      </div>
    </section>

    <section class="stats">
      <div class="card stat lift"><div class="ic">${ICON.book}</div><div><b data-count="${total}">0</b><span>verses in the chapter</span></div></div>
      <div class="card stat lift" style="--c:var(--teal)"><div class="ic">${ICON.check}</div><div><b data-count="${studied}">0</b><span>verses you have opened</span></div></div>
      <div class="card stat lift" style="--c:var(--rose)"><div class="ic">${ICON.steps}</div><div><b data-count="${steps}">0</b><span>steps completed</span></div></div>
      <div class="card stat lift" style="--c:#8b8bff"><div class="ic">${ICON.layers}</div><div><b data-count="${SECTIONS.length}">0</b><span>sections to master</span></div></div>
    </section>

    <section class="two" style="margin-top:20px">
      <a class="card continue lift" href="#/v/${(last || list[0]).id}">
        <div class="eyebrow">${last ? "Continue where you left off" : "Begin here"}</div>
        <div class="deva">${esc(clean((last || list[0]).text))}</div>
        <span class="muted">Verse ${dn((last || list[0]).number)} · ${esc(sectionOf(first((last || list[0]).id)).en)}</span>
      </a>
      <a class="card continue lift" href="#/v/${today.id}">
        <div class="eyebrow">Verse of the day</div>
        <div class="deva">${esc(clean(today.text))}</div>
        <span class="muted">Verse ${dn(today.number)} · ${esc(sectionOf(first(today.id)).en)}</span>
      </a>
    </section>

    <div class="h-sec"><h2>Chapter map</h2><a href="#/verses">See every verse</a></div>
    <section class="sections">${SECTIONS.map((sec, i) => {
      const vs = list.filter(v => first(v.id) >= sec.from && first(v.id) <= sec.to);
      const d = vs.filter(v => s.has(v.id)).length;
      return `<button class="card section lift" data-sec="${i}">
        <div class="top"><span class="deva">${sec.deva}</span><span class="range">${sec.from}–${sec.to}</span></div>
        <p>${esc(sec.en)}</p>
        <div class="bar"><i data-w="${vs.length ? Math.round(100 * d / vs.length) : 0}"></i></div>
        <small>${d} of ${vs.length} verses opened</small></button>`;
    }).join("")}</section>`;

  view.querySelectorAll("[data-count]").forEach(el => countUp(el, +el.dataset.count));
  countUp($("#pctNum"), pct);
  requestAnimationFrame(() => requestAnimationFrame(() => {
    $("#ringVal").style.strokeDashoffset = C * (1 - pct / 100);
    view.querySelectorAll(".bar i").forEach(b => (b.style.width = b.dataset.w + "%"));
  }));
  view.querySelector(".sections").addEventListener("click", e => {
    const b = e.target.closest("[data-sec]"); if (b) { store.set("ayv.sec", b.dataset.sec); location.hash = "#/verses"; }
  });
}

// ---------------------------------------------------------------- verse library
async function showVerses() {
  page("verses", "All verses", "Filter by section or search by number and word");
  skeleton(6);
  let list;
  try { list = await getList(); } catch (e) { return failed(e); }
  let sec = store.get("ayv.sec", "all");
  view.innerHTML = `
    <div class="filters" id="filters">
      <button class="chip" data-sec="all">All ${list.length}</button>
      ${SECTIONS.map((s, i) => `<button class="chip" data-sec="${i}"><span class="deva">${s.deva}</span></button>`).join("")}
    </div>
    <div class="grid" id="grid"></div>`;
  const s = seen();
  const draw = () => {
    store.set("ayv.sec", sec);
    view.querySelectorAll(".chip").forEach(c => c.classList.toggle("on", c.dataset.sec === String(sec)));
    const S = SECTIONS[sec];
    const rows = list.filter(v => sec === "all" || (first(v.id) >= S.from && first(v.id) <= S.to));
    $("#grid").innerHTML = rows.map((v, i) => `
      <button class="card vcard lift ${s.has(v.id) ? "done" : ""} enter" style="animation-delay:${Math.min(i, 12) * 30}ms" data-id="${esc(v.id)}">
        <span class="vnum">${dn(v.number)}</span>
        <span><span class="deva">${esc(clean(v.text))}</span>
        ${v.topic ? `<span class="topic">${esc(v.topic)}</span>` : ""}</span></button>`).join("") || '<div class="empty">No verses here.</div>';
  };
  $("#filters").addEventListener("click", e => { const c = e.target.closest(".chip"); if (c) { sec = c.dataset.sec; draw(); } });
  $("#grid").addEventListener("click", e => { const c = e.target.closest(".vcard"); if (c) location.hash = `#/v/${c.dataset.id}`; });
  draw();
  view.querySelector(".chip.on")?.scrollIntoView({ inline: "center", block: "nearest" });
}

// ---------------------------------------------------------------- step renderers (fall back to plain text)
const render = {
  1(out) {
    const rows = out.split("\n").map(l => l.match(/^\s*\S+\s*पाद\s*[-–:]\s*(.+)$/)).filter(Boolean);
    if (rows.length < 2) return null;
    return `<div class="padas">${rows.map((m, i) => `<div class="pada enter" style="animation-delay:${i * 60}ms"><span>पादः ${dn(i + 1)}</span><div>${fmt(m[1])}</div></div>`).join("")}</div>`;
  },
  2(out) {
    const rows = out.split("\n").map(l => l.match(/^\s*\d+\.\s*(.+?)\s+—\s+(.+?)(?:\s+—\s+(.+))?$/)).filter(Boolean);
    if (rows.length < 2) return null;
    return `<table class="wtable"><tbody>${rows.map(m => `<tr><td>${fmt(m[1])}</td>
      <td><span class="tag">${fmt(m[2])}</span><span class="form">${m[3] ? mixed(m[3]) : ""}</span></td></tr>`).join("")}</tbody></table>`;
  },
  3(out) { return `<p class="anvaya">${fmt(out.trim())}</p>`; },
  4(out) {
    const [head, ...rest] = out.trim().split(/\n\s*\n/);
    const pairs = head.split(/\s*\|\s*|\n/).map(p => p.match(/^\s*(?:हे\s+)?([^=]+?)\s*=\s*(.+)$/)).filter(Boolean);
    if (pairs.length < 2) return null;
    const sentence = rest.join("\n\n").replace(/^\s*Sentence meaning\s*:\s*/i, "").trim();
    return `<table class="wtable"><tbody>${pairs.map(m => `<tr><td>${fmt(m[1])}</td><td>${mixed(m[2])}</td></tr>`).join("")}</tbody></table>
      ${sentence ? `<div class="sense"><b>The whole verse means</b>${mixed(sentence)}</div>` : ""}`;
  },
  5(out) { return `<div class="prose">${out.trim().split(/\n\s*\n|\n/).map(p => `<p>${mixed(p)}</p>`).join("")}</div>`; },
  6(out) {
    const blocks = out.split(/^\s*पद\s*:\s*/m).slice(1);
    if (!blocks.length) return null;
    return `<div class="wcards">${blocks.map((b, i) => {
      const lines = b.trim().split("\n");
      const word = lines.shift().trim();
      const fields = [];
      for (const l of lines) for (const part of l.split(/\s+\|\s+/)) {
        const m = part.match(/^\s*([^:]{1,24}):\s*(.+)$/);
        if (m) fields.push([m[1].trim(), m[2].trim()]);
        else if (fields.length) fields[fields.length - 1][1] += " " + part.trim();
      }
      const gram = ((fields.find(f => /grammar/i.test(f[0])) || [])[1] || "").replace(/\s*\[[^\]]*\]/g, "").split(/[,—(]/)[0];
      return `<details class="wcard" ${i === 0 ? "open" : ""}><summary><span class="deva">${esc(word)}</span>
        ${gram ? `<span class="tag">${esc(gram)}</span>` : ""}${ICON.chev}</summary>
        <dl>${fields.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${mixed(v)}</dd>`).join("")}</dl></details>`;
    }).join("")}</div>`;
  },
  7(out) { return render[5](out); },
};

// ---------------------------------------------------------------- study one verse
async function showVerse(id, step) {
  let list, data;
  page("study", `Verse ${dn(first(id))}`, "", true);
  skeleton(5);
  try { [list, data] = await Promise.all([getList(), getVerse(id)]); } catch (e) { return failed(e); }
  const i = list.findIndex(v => v.id === id), prev = list[i - 1], next = list[i + 1];
  const v = data.shloka, sec = sectionOf(first(id));
  page("study", `Verse ${dn(v.number)}`, sec.en, true);
  step = Number(step || 1);
  if (!STEPS[step]) step = 1;

  view.innerHTML = `
    <div class="study">
      <div class="study-left">
        <div class="card verse-card enter">
          <div class="num">श्लोकः ${dn(v.number)}</div>
          <div class="text">${esc(clean(v.text))}</div>
          ${v.topic ? `<div class="topic">${esc(v.topic)}</div>` : ""}
          ${v.variant ? `<div class="variant">पाठान्तरम्: <span class="deva">${esc(v.variant)}</span></div>` : ""}
        </div>
        <div class="pager">
          <button class="btn ghost" id="pv" ${prev ? "" : "disabled"}>${ICON.left} ${prev ? dn(prev.number) : ""}</button>
          <button class="btn ghost" id="nv" ${next ? "" : "disabled"}>${next ? dn(next.number) : ""} ${ICON.arrow}</button>
        </div>
        <ol class="card steps" id="steps" aria-label="The seven steps"></ol>
        <a class="btn ghost" href="#/chat/${id}" style="justify-content:center">${ICON.chat} Ask a doubt about this verse</a>
      </div>
      <section class="card step-panel" id="panel"></section>
    </div>`;

  const drawSteps = () => {
    const d = doneSteps(id);
    $("#steps").innerHTML = Object.entries(STEPS).map(([n, s]) => `
      <li class="${d.has(+n) && +n !== step ? "done" : ""}"><button data-step="${n}" ${+n === step ? 'aria-current="step"' : ""}>
        <span class="n">${d.has(+n) && +n !== step ? ICON.check : n}</span><span><b>${s.en}</b><small>${s.deva}</small></span></button></li>`).join("");
    $("#steps [aria-current]")?.scrollIntoView({ inline: "center", block: "nearest" });
  };
  const drawPanel = () => {
    const S = STEPS[step], d = data.steps[step];
    let body = '<div class="empty">This step has not been generated for this verse yet.</div>';
    if (d) { try { body = render[step](d.output) || `<div class="raw">${mixed(d.output)}</div>`; } catch { body = `<div class="raw">${mixed(d.output)}</div>`; } }
    $("#panel").innerHTML = `
      <div class="step-head enter"><div><div class="deva">${S.deva}</div><p>${S.en}: ${S.why}</p></div>
        <span class="step-count">Step <b>${step}</b> / 7</span></div>
      <div class="progress-line"><i style="width:${(step / 7) * 100}%"></i></div>
      <div class="enter" style="animation-delay:60ms">${body}</div>
      <div class="step-foot">
        ${step > 1 ? `<button class="btn ghost" data-go="${step - 1}">${ICON.left} ${STEPS[step - 1].en}</button>` : ""}
        ${step < 7 ? `<button class="btn grad" data-go="${step + 1}">Next: ${STEPS[step + 1].en} ${ICON.arrow}</button>`
                   : next ? `<a class="btn grad" href="#/v/${next.id}/1">Next verse ${dn(next.number)} ${ICON.arrow}</a>` : ""}
      </div>`;
    markStep(id, step);
  };
  const go = n => {
    step = Number(n);
    history.replaceState(null, "", `#/v/${id}/${step}`);
    drawSteps(); drawPanel();
    if (innerWidth < 1100) $("#panel").scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
  };
  $("#steps").addEventListener("click", e => { const b = e.target.closest("[data-step]"); if (b) go(b.dataset.step); });
  $("#panel").addEventListener("click", e => { const b = e.target.closest("[data-go]"); if (b) go(b.dataset.go); });
  $("#pv").onclick = () => prev && (location.hash = `#/v/${prev.id}/1`);
  $("#nv").onclick = () => next && (location.hash = `#/v/${next.id}/1`);
  drawSteps(); drawPanel();
}

// ---------------------------------------------------------------- ask AI
async function showChat(id) {
  page("ask", "Ask AI", `Doubts on verse ${dn(first(id))}`, true);
  skeleton(3);
  let data;
  try { data = await getVerse(id); } catch (e) { return failed(e); }
  store.set("ayv.last", id);
  const history = chats[id] = chats[id] || [];
  const words = (data.steps[2]?.output || "").split("\n").map(l => (l.match(/^\s*\d+\.\s*(\S+)/) || [])[1]).filter(Boolean);
  const ideas = [
    words[0] && `What does ${words[0]} mean here?`,
    "Explain the grammar of this verse simply",
    "Why does the author say this, and what follows from it?",
    words[1] && `Which root does ${words[1]} come from?`,
  ].filter(Boolean);

  view.innerHTML = `
    <div class="chat-wrap">
      <div class="chat-side">
        <a class="card verse-card lift" href="#/v/${id}">
          <div class="num">श्लोकः ${dn(data.shloka.number)}</div>
          <div class="text" style="font-size:1.15rem">${esc(clean(data.shloka.text))}</div>
          <div class="topic">Open the 7-step study</div></a>
        <div class="card"><div class="eyebrow" style="margin-bottom:10px">Try asking</div><div class="suggest" id="ideas">
          ${ideas.map(t => `<button>${esc(t)}</button>`).join("")}</div></div>
      </div>
      <div class="card chat-main">
        <div class="thread" id="thread">
          <div class="intro-ai"><div class="avatar">AI</div><div class="bubble">Ask me anything about this verse: a word, its grammar, or what the आचार्य means. I answer only from this chapter and its study notes, and I show my sources. Confirm important points with your teacher.</div></div>
        </div>
        <form class="composer" id="f">
          <textarea id="msg" rows="1" placeholder="Type your doubt…" aria-label="Your doubt"></textarea>
          <button class="btn grad" id="send">Ask ${ICON.arrow}</button>
        </form>
      </div>
    </div>`;
  const thread = $("#thread"), input = $("#msg"), send = $("#send"), form = $("#f");
  const add = (who, html) => {
    const row = document.createElement("div");
    row.className = `row ${who} enter`;
    row.innerHTML = (who === "me" ? "" : '<div class="avatar">AI</div>') + `<div class="bubble">${html}</div>`;
    thread.appendChild(row);
    row.scrollIntoView({ block: "end", behavior: reduced ? "auto" : "smooth" });
    return row;
  };
  const answer = (a, src) => mixed(a) + (src?.length ? `<div class="sources">${src.map(s => `<span>${esc(s.label)}</span>`).join("")}</div>` : "");
  history.forEach(h => { add("me", esc(h.q)); add("bot", answer(h.a, h.sources)); });

  async function ask(q) {
    add("me", esc(q));
    const wait = add("bot", '<span class="typing" aria-label="Thinking"><i></i><i></i><i></i></span>');
    send.disabled = true;
    try {
      const r = await api("/chat", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, shloka_id: id, history: history.slice(-4).map(h => [h.q, h.a]) }) });
      wait.querySelector(".bubble").innerHTML = answer(r.answer, r.sources);
      history.push({ q, a: r.answer, sources: r.sources || [] });
    } catch (err) {
      wait.classList.add("err");
      wait.querySelector(".bubble").innerHTML = `No answer this time. ${esc(err.message)}`;
    } finally { send.disabled = false; }
  }
  $("#ideas").addEventListener("click", e => { const b = e.target.closest("button"); if (b) ask(b.textContent); });
  input.addEventListener("input", () => { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 140) + "px"; });
  input.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); } });
  form.addEventListener("submit", e => {
    e.preventDefault();
    const q = input.value.trim();
    if (!q) return;
    input.value = ""; input.style.height = "auto";
    ask(q);
  });
}

// ---------------------------------------------------------------- router + shell
async function route() {
  const h = decodeURIComponent(location.hash);
  let m;
  const run = async () => {
    if ((m = h.match(/^#\/v\/([^/]+)(?:\/(\d))?$/))) return showVerse(m[1], m[2]);
    if ((m = h.match(/^#\/chat\/(.+)$/))) return showChat(m[1]);
    if (h === "#/verses") return showVerses();
    if (h === "#/study" || h === "#/ask") {
      let id = store.get("ayv.last", null);
      if (!id) { try { id = (await getList())[0].id; } catch (e) { return failed(e); } }
      location.replace(h === "#/study" ? `#/v/${id}` : `#/chat/${id}`);
      return;
    }
    return showHome();
  };
  window.scrollTo(0, 0);
  if (document.startViewTransition && !reduced) document.startViewTransition(run); else run();
}
$("#back").onclick = () => history.length > 1 ? history.back() : (location.hash = "#/");
$("#theme").onclick = () => {
  const t = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = t;
  store.set("ayv.theme", t);
};
$("#jump").addEventListener("submit", async e => {
  e.preventDefault();
  const n = $("#jumpIn").value.trim().replace(/[०-९]/g, d => DIGITS.indexOf(d));
  if (!n) return;
  try {
    const v = (await getList()).find(x => x.number.split("-").includes(n));
    if (v) { $("#jumpIn").value = ""; $("#jumpIn").blur(); location.hash = `#/v/${v.id}`; }
    else $("#jumpIn").value = "";
  } catch (err) { failed(err); }
});
window.addEventListener("hashchange", route);
route();

if ("serviceWorker" in navigator && window.isSecureContext) {
  navigator.serviceWorker.register("sw.js").catch(() => { /* offline support is optional */ });
}