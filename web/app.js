// Ayurvidya mobile web app.
// Screens: verse list (#/), one verse studied through the 7 steps (#/v/<id>/<step>), doubt chat (#/chat/<id>).
// Data comes from the API on the same server: /chapters/<id>/shlokas, /shlokas/<id>, POST /chat
const CHAPTER = "su.ni.1";
const STEPS = {
  1: { deva: "सम्प्रदानम्", en: "Sampradanam", short: "Padas", why: "How the verse divides into its four quarters (padas)." },
  2: { deva: "पदविभागः", en: "Padavibhaga", short: "Words", why: "Every word separated out, with its grammatical form." },
  3: { deva: "अन्वयः", en: "Anvaya", short: "Order", why: "The same words, rearranged into natural prose order." },
  4: { deva: "अन्वयार्थः", en: "Anvayartha", short: "Meaning", why: "The meaning of each word, in prose order, then of the whole sentence." },
  5: { deva: "भावार्थः", en: "Bhavartha", short: "Gist", why: "What the author intends to say, in brief." },
  6: { deva: "पदकृत्यम्", en: "Padakrityam", short: "Analysis", why: "What each word contributes: its root, synonyms and grammar. Tap a word to open it." },
  7: { deva: "ध्वनितार्थः", en: "Dhvanitartha", short: "Implied", why: "The meaning between the lines: what the author hints at." },
};
const CHECK = { generated: "Written by AI, not yet checked by a scholar", reviewed: "Reviewed by a scholar", approved: "Approved by a scholar" };
const DEVA_DIGITS = "०१२३४५६७८९";

const $ = id => document.getElementById(id);
const side = $("side"), view = $("view");
const cache = { list: null, verse: {} };
const chats = {};
const store = {
  get(k, d) { try { return localStorage.getItem(k) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* storage unavailable */ } },
};

const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const refs = s => s.replace(/\s*\[((?:[RS]\d+)(?:\s*,\s*[RS]?\d+)*)\]/g, '<span class="ref">$1</span>');
const fmt = s => refs(esc(s));
const deva = n => String(n).replace(/\d/g, d => DEVA_DIGITS[d]);
const num = id => id.split(".").pop();
const isDeva = s => /[\u0900-\u097F]/.test(s) && !/[A-Za-z]/.test(s);
// wrap Devanagari runs inside English prose so they get the Sanskrit typeface
const mixed = s => fmt(s).replace(/([\u0900-\u097F][\u0900-\u097F\s\-ऽ।॥]*[\u0900-\u097F।॥]|[\u0900-\u097F])/g, '<span class="deva">$1</span>');

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) {
    let msg = `The server answered with error ${r.status}.`;
    try { const j = await r.json(); if (typeof j.detail === "string") msg = j.detail; } catch { /* not JSON */ }
    throw new Error(msg);
  }
  return r.json();
}
const getList = async () => (cache.list = cache.list || await api(`/chapters/${CHAPTER}/shlokas`));
const getVerse = async id => (cache.verse[id] = cache.verse[id] || await api(`/shlokas/${encodeURIComponent(id)}`));

function screen(name, crumb = "") {
  document.body.dataset.screen = name;
  $("crumb").textContent = crumb;
}
function failed(where, e) {
  where.innerHTML = `<p class="center">Could not reach the Ayurvidya server. ${esc(e.message)}<br>
    Check that <b>serve.py</b> is running and this device is on the same Wi-Fi.</p>
    <p class="center"><button class="btn ghost" onclick="route()">Try again</button></p>`;
}

// ================================================================ verse list (left pane / home screen)
async function drawList(activeId) {
  if (!side.dataset.ready) {
    side.innerHTML = '<p class="center thinking">Loading verses</p>';
    let list;
    try { list = await getList(); } catch (e) { return failed(side, e); }
    side.innerHTML = `
      <div class="chapter">
        <h1>वातव्याधिनिदानम्</h1>
        <p>Sushruta Samhita, Nidana Sthana, chapter 1: the diagnosis of Vata disorders</p>
        <div class="progress"><div class="track"><div class="fill" id="prog"></div></div><span id="progtxt"></span></div>
      </div>
      <input class="search" id="q" type="search" placeholder="Find a verse by number or word" aria-label="Find a verse">
      <nav id="list"></nav>`;
    const q = $("q");
    q.value = store.get("ayv.q", "");
    q.addEventListener("input", () => { store.set("ayv.q", q.value); fillList(list, document.querySelector(".verse-link[aria-current=true]")?.dataset.id); });
    $("list").addEventListener("click", e => { const b = e.target.closest(".verse-link"); if (b) location.hash = `#/v/${b.dataset.id}`; });
    const seen = JSON.parse(store.get("ayv.seen", "[]"));
    $("prog").style.width = `${Math.round(100 * seen.length / list.length)}%`;
    $("progtxt").textContent = `${seen.length} of ${list.length} studied`;
    side.dataset.ready = "1";
    fillList(list, activeId);
  } else {
    fillList(cache.list, activeId);
  }
}
function fillList(list, activeId) {
  const term = ($("q")?.value || "").trim();
  let lastTopic = null, html = "";
  for (const s of list) {
    if (term && !(s.number.split("-").includes(term) || s.text.includes(term) || (s.topic || "").toLowerCase().includes(term.toLowerCase()))) continue;
    if (s.topic && s.topic !== lastTopic && !term) { html += `<div class="topic">${esc(s.topic)}</div>`; lastTopic = s.topic; }
    const text = s.text.replace(/\s*[।॥|]+\s*[०-९0-9\-]+\s*[।॥|]+\s*$/, "").replace(/\s+([।॥])/g, "$1");
    html += `<button class="verse-link" data-id="${esc(s.id)}" aria-current="${s.id === activeId}">
      <span class="n">${deva(s.number)}</span><span class="t">${esc(text)}</span></button>`;
  }
  $("list").innerHTML = html || '<p class="empty">No verse has that number or word. Try a verse number like 13.</p>';
  document.querySelector(".verse-link[aria-current=true]")?.scrollIntoView({ block: "nearest" });
}
function markSeen(id) {
  const seen = new Set(JSON.parse(store.get("ayv.seen", "[]")));
  seen.add(id);
  store.set("ayv.seen", JSON.stringify([...seen]));
  if ($("prog") && cache.list) {
    $("prog").style.width = `${Math.round(100 * seen.size / cache.list.length)}%`;
    $("progtxt").textContent = `${seen.size} of ${cache.list.length} studied`;
  }
}

function welcome() {
  view.innerHTML = `<div class="welcome">
    <h2>Choose a verse to begin</h2>
    <p>Each verse is studied in seven steps, from hearing it to understanding what lies between its lines:</p>
    <ol>${Object.values(STEPS).map(s => `<li><span>${s.deva}</span> ${s.en}: ${s.why.split(":")[0].replace(/\.$/, "")}</li>`).join("")}</ol>
    <p class="muted">Stuck on a word? Every verse has a doubt chat that answers from the classical texts.</p></div>`;
}

// ================================================================ step renderers (fall back to plain text)
const render = {
  1(out) {
    const rows = out.split("\n").map(l => l.match(/^\s*\S+\s*पाद\s*[-–:]\s*(.+)$/)).filter(Boolean);
    if (rows.length < 2) return null;
    return `<ol class="padas">${rows.map(m => `<li><span class="deva">${fmt(m[1])}</span></li>`).join("")}</ol>`;
  },
  2(out) {
    const rows = out.split("\n").map(l => l.match(/^\s*\d+\.\s*(.+?)\s+—\s+(.+?)(?:\s+—\s+(.+))?$/)).filter(Boolean);
    if (rows.length < 2) return null;
    return `<table class="words"><tbody>${rows.map(m => `<tr><td>${fmt(m[1])}</td>
      <td><span class="kind">${fmt(m[2])}</span><span class="form">${m[3] ? mixed(m[3]) : ""}</span></td></tr>`).join("")}</tbody></table>`;
  },
  3(out) { return `<p class="anvaya">${fmt(out.trim())}</p>`; },
  4(out) {
    const [first, ...rest] = out.trim().split(/\n\s*\n/);
    const pairs = first.split(/\s*\|\s*|\n/).map(p => p.match(/^\s*(?:हे\s+)?([^=]+?)\s*=\s*(.+)$/)).filter(Boolean);
    if (pairs.length < 2) return null;
    const sentence = rest.join("\n\n").replace(/^\s*Sentence meaning\s*:\s*/i, "").trim();
    return `<table class="words"><tbody>${pairs.map(m => `<tr><td>${fmt(m[1])}</td><td>${mixed(m[2])}</td></tr>`).join("")}</tbody></table>
      ${sentence ? `<div class="sense"><b>The whole verse means</b>${mixed(sentence)}</div>` : ""}`;
  },
  5(out) { return `<div class="prose">${out.trim().split(/\n\s*\n|\n/).map(p => `<p>${mixed(p)}</p>`).join("")}</div>`; },
  6(out) {
    const blocks = out.split(/^\s*पद\s*:\s*/m).slice(1);
    if (!blocks.length) return null;
    return blocks.map((b, i) => {
      const lines = b.trim().split("\n");
      const word = lines.shift().trim();
      const fields = [];
      for (const l of lines) {
        for (const part of l.split(/\s+\|\s+/)) {
          const m = part.match(/^\s*([^:]{1,24}):\s*(.+)$/);
          if (m) fields.push([m[1].trim(), m[2].trim()]);
          else if (fields.length) fields[fields.length - 1][1] += " " + part.trim();
        }
      }
      const gram = (fields.find(f => /grammar/i.test(f[0])) || [, ""])[1].replace(/\s*\[[^\]]*\]/g, "");
      return `<details class="pada-card" ${i === 0 ? "open" : ""}>
        <summary><span class="deva">${esc(word)}</span><small class="deva">${esc(gram.split(/[,—(]/)[0])}</small></summary>
        <dl>${fields.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${mixed(v)}</dd>`).join("")}</dl></details>`;
    }).join("");
  },
  7(out) { return render[5](out); },
};

// ================================================================ one verse, studied step by step
async function showVerse(id, step) {
  screen("verse", `Verse ${num(id)}`);
  drawList(id);
  view.innerHTML = '<p class="center thinking">Opening the verse</p>';
  let data, list;
  try { [list, data] = await Promise.all([getList(), getVerse(id)]); } catch (e) { return failed(view, e); }
  const i = list.findIndex(s => s.id === id), prev = list[i - 1], next = list[i + 1];
  step = Number(step || store.get("ayv.step", "1"));
  if (!STEPS[step]) step = 1;
  store.set("ayv.step", String(step));
  markSeen(id);

  const d = data.steps[step], S = STEPS[step];
  let body = '<p class="center">This step has not been generated for this verse yet.</p>';
  if (d) { try { body = render[step](d.output) || `<div class="raw">${mixed(d.output)}</div>`; } catch { body = `<div class="raw">${mixed(d.output)}</div>`; } }
  const v = data.shloka;

  view.innerHTML = `
    <div class="verse-head">
      <h2>Verse <span class="deva">${deva(v.number)}</span></h2>
      <div class="pager">
        <button id="pv" ${prev ? "" : "disabled"} aria-label="Previous verse">‹ ${prev ? deva(prev.number) : ""}</button>
        <button id="nv" ${next ? "" : "disabled"} aria-label="Next verse">${next ? deva(next.number) : ""} ›</button>
      </div>
    </div>
    <div class="leaf"><div class="verse">${esc(v.text.replace(/[ \t]+([।॥])/g, "\u00a0$1"))}</div>
      ${v.variant ? `<div class="variant"><b>पाठान्तरम्</b> ${esc(v.variant)}</div>` : ""}</div>

    <ol class="path" aria-label="The seven steps">${Object.entries(STEPS).map(([n, s]) => `
      <li class="${n < step ? "done" : ""}"><button data-step="${n}" ${n == step ? 'aria-current="step"' : ""} aria-label="Step ${n}: ${s.en}">
        <span class="dot">${n}</span><span class="lbl">${s.short}</span></button></li>`).join("")}</ol>

    <section class="step">
      <div class="step-title"><h3>${S.deva}</h3><span>Step ${step} of 7: ${S.en}</span></div>
      <p class="step-why">${S.why}</p>
      ${body}
      ${d ? `<div class="check ${esc(d.status)}">${esc(CHECK[d.status] || d.status)}</div>` : ""}
      <div class="study-nav">
        ${step < 7 ? `<button class="btn primary" id="nextstep">Next: ${STEPS[step + 1].en}</button>`
                   : next ? `<button class="btn primary" id="nextverse">Go to verse ${deva(next.number)}</button>` : ""}
        <button class="btn ghost" id="ask">Ask a doubt about this verse</button>
      </div>
    </section>`;

  view.querySelector(".path").addEventListener("click", e => { const b = e.target.closest("button"); if (b) location.hash = `#/v/${id}/${b.dataset.step}`; });
  $("pv").onclick = () => prev && (location.hash = `#/v/${prev.id}/1`);
  $("nv").onclick = () => next && (location.hash = `#/v/${next.id}/1`);
  $("ask").onclick = () => (location.hash = `#/chat/${id}`);
  if ($("nextstep")) $("nextstep").onclick = () => (location.hash = `#/v/${id}/${step + 1}`);
  if ($("nextverse")) $("nextverse").onclick = () => (location.hash = `#/v/${next.id}/1`);
}

// ================================================================ doubt chat
async function showChat(id) {
  screen("chat", `Doubts on verse ${num(id)}`);
  drawList(id);
  let data;
  try { data = await getVerse(id); } catch (e) { return failed(view, e); }
  const history = chats[id] = chats[id] || [];
  const words = (data.steps[2]?.output || "").split("\n").map(l => (l.match(/^\s*\d+\.\s*(\S+)/) || [])[1]).filter(Boolean);
  const ideas = [
    words[0] && `What does ${words[0]} mean here?`,
    "Explain the grammar of this verse simply",
    "Why does the author say this, and what follows from it?",
    words[1] && `Which root does ${words[1]} come from?`,
  ].filter(Boolean);

  view.innerHTML = `<div class="chat" id="chat">
      <div class="verse-head"><h2>Doubts on verse <span class="deva">${deva(data.shloka.number)}</span></h2>
        <div class="pager"><button id="toverse">Back to the verse</button></div></div>
      <div class="chat-verse">${esc(data.shloka.text)}</div>
      <p class="step-why">Answers come only from this chapter, its commentary and the 7-step study. Each answer lists its sources; confirm important points with your teacher.</p>
      <div class="suggest" id="ideas">${history.length ? "" : ideas.map(t => `<button>${esc(t)}</button>`).join("")}</div>
    </div>
    <div class="composer"><form id="f">
      <textarea id="msg" rows="1" placeholder="Type your doubt" aria-label="Your doubt"></textarea>
      <button class="btn primary" id="send">Ask</button>
    </form></div>`;
  const box = $("chat"), input = $("msg"), send = $("send"), form = $("f");
  $("toverse").onclick = () => (location.hash = `#/v/${id}`);

  const add = (who, html) => {
    const el = document.createElement("div");
    el.className = `msg ${who}`;
    el.innerHTML = html;
    box.appendChild(el);
    el.scrollIntoView({ block: "end", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    return el;
  };
  const answer = (a, sources) => mixed(a) + (sources?.length ? `<div class="sources">Sources<ul>${sources.map(s => `<li>${esc(s.label)}</li>`).join("")}</ul></div>` : "");
  history.forEach(h => { add("me", esc(h.q)); add("bot", answer(h.a, h.sources)); });

  async function ask(q) {
    $("ideas").innerHTML = "";
    add("me", esc(q));
    const wait = add("bot", '<span class="thinking">Looking in the texts</span>');
    send.disabled = true;
    try {
      const r = await api("/chat", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, shloka_id: id, history: history.slice(-4).map(h => [h.q, h.a]) }) });
      wait.innerHTML = answer(r.answer, r.sources);
      history.push({ q, a: r.answer, sources: r.sources || [] });
    } catch (err) {
      wait.classList.add("err");
      wait.innerHTML = `No answer this time. ${esc(err.message)}`;
    } finally { send.disabled = false; }
  }
  $("ideas").addEventListener("click", e => { const b = e.target.closest("button"); if (b) ask(b.textContent); });
  input.addEventListener("input", () => { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 130) + "px"; });
  input.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); } });
  form.addEventListener("submit", e => {
    e.preventDefault();
    const q = input.value.trim();
    if (!q) return;
    input.value = ""; input.style.height = "auto";
    ask(q);
  });
}

// ================================================================ router
function route() {
  const h = decodeURIComponent(location.hash);
  let m;
  if ((m = h.match(/^#\/v\/([^/]+)(?:\/(\d))?$/))) showVerse(m[1], m[2]);
  else if ((m = h.match(/^#\/chat\/(.+)$/))) showChat(m[1]);
  else { screen("list"); drawList(null); welcome(); }
  window.scrollTo(0, 0);
}
$("back").onclick = () => {
  const m = location.hash.match(/^#\/chat\/(.+)$/);
  location.hash = m ? `#/v/${m[1]}` : "#/";
};
window.addEventListener("hashchange", route);
route();

if ("serviceWorker" in navigator && window.isSecureContext) {
  navigator.serviceWorker.register("sw.js").catch(() => { /* offline support is optional */ });
}