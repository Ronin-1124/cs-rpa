"use strict";
const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const icon = name => `<i data-lucide="${name}"></i>`;
const hydrateIcons = () => lucide.createIcons({attrs:{"stroke-width":1.25}});
const editor = $(".EditorContent"), content = $(".c-c"), scroller = $(".c-wrap");
let selected = sessionStorage.getItem("replica.customer") || "";
let tab = Number(sessionStorage.getItem("replica.tab") || 0), state, cases = [], generation = 0;
let loadedBuyer = "", lastMessages = "", sending = false, loading = false, sendMode = localStorage.getItem("replica.sendMode") || "enter";
let phraseTab = 0;
const collapsed = new Set(), drafts = new Map(), pendingRequests = new Map();

async function api(path, body) {
  const response = await fetch(path, {method:body ? "POST" : "GET", headers:body ? {"Content-Type":"application/json"} : {}, body:body ? JSON.stringify(body) : undefined});
  const result = await response.json();
  if (!response.ok || result.ok === false) throw new Error(result.error || "请求失败");
  return result;
}
function saveDraft() {
  if (!selected || loadedBuyer !== selected) return;
  drafts.set(selected, editor.innerText);
  sessionStorage.setItem("replica.drafts", JSON.stringify([...drafts]));
}
try { for (const [k,v] of JSON.parse(sessionStorage.getItem("replica.drafts") || "[]")) drafts.set(k,v); } catch {}

function selectTab(index) {
  tab = index;
  sessionStorage.setItem("replica.tab", String(tab));
  $$(".c_tabs-nav-container > .c_tabs-tab").forEach((e,i) => e.classList.toggle("c_tabs-tab_check", i === tab));
  $$(".c_tabs-tabpane").forEach((e,i) => e.classList.toggle("c_tabs-tab_inactive", i !== tab));
}

function row(s) {
  return `<div class="c_stream-item-w"><div class="alluser-item-content"><div class="alluser-item t-item-h alluser-item__normal ${s.buyer_id === selected ? "alluser-item_check t-item-ck alluser-current" : ""}">
    <div class="alluser-item-tag-w"><div class="alluser-item-tag-content"></div></div>
    <div class="alluser-item-avatar-w"><img class="alluser-item-avatar alluser-item-avater_check alluser-item-avatar_gray" src="/avatar-customer.svg" alt="">${s.unread ? `<span class="replica-unread">${s.unread}</span>` : ""}</div>
    <div class="alluser-item-brief-w"><div class="alluser-item-brief"><div class="alluser-item-name-w"><span class="alluser-item-name over-elps t-color-2" title="${esc(s.buyer_id)}">${esc(s.buyer_id)}</span><div class="alluser-item-icon-w"></div></div><div class="alluser-item-date-w t-color-2">${esc(s.time)}</div></div>
    <div class="alluser-item-breifmsg-w"><span class="alluser-item-breifmsg"><span class="alluser-item-breifdesc over-elps t-color-2" title="${esc(s.preview)}">${esc(s.preview)}</span><span class="alluser-item-func alluser-item-leavemsg">${icon("message-square-more")}</span></span></div></div>
    <div class="alluser-item-del"><i class="back-icon grp-item-del"></i></div></div></div></div>`;
}
function group(title, sessions) {
  const hidden = collapsed.has(title);
  return `<div class="c_cas-head ${hidden ? "collapsed" : ""}" data-group="${esc(title)}">${esc(title)}(${sessions.length})</div><div class="replica-group" ${hidden ? "hidden" : ""}>${sessions.map(row).join("")}</div>`;
}
function renderLists() {
  if (!state) return;
  const term = $("#t-search_input").value.trim().toLowerCase();
  const filter = s => s.buyer_id.toLowerCase().includes(term) && (!$(".unread-filter").checked || s.unread > 0);
  const streams = $$(".c_stream-content");
  const values = [group("正在咨询",state.consulting.filter(filter)) + group("留言",state.recent.filter(s=>s.unread>0).filter(filter)) + group("内部会话&群聊",[]), group("专享顾客",[]) + group("最近联系人",state.recent.filter(filter))];
  streams.forEach((e,i) => {if (e.innerHTML !== values[i]) e.innerHTML = values[i];});
  $(".today-count").textContent = state.consulting.length;
  hydrateIcons();
}
function linkedText(text) {
  return text.split(/(https?:\/\/[^\s]+)/g).map(part => /^https?:\/\//.test(part) ? `<a class="msg-link editor-text" href="#" title="${esc(part)}">${esc(part)}</a>` : esc(part)).join("");
}
function renderMessage(m) {
  if (m.kind === "divider") return `<div class="message"><div class="message_center" id="${esc(m.id)}"><div class="message_componet-center"><div><div class="last-chat-divider"><div class="last-chat-line last-chat-line-l"></div><span>${esc(m.text)}</span><div class="last-chat-line last-chat-line-r"></div></div></div></div></div></div>`;
  if (m.role === "system") return `<div class="message"><div id="${esc(m.id)}"><div class="message__system_wrap"><div class="message__system_box"><span class="message__system spe">${esc(m.text)}</span><div class="message__system_custom"></div></div></div></div></div>`;
  const right = m.role === "agent", direction = right ? "right" : "left";
  const name = right ? "本地测试客服" : selected;
  const time = `<span class="message__time_str">${esc(m.ts.slice(5).replace("T"," "))}</span>`;
  let body;
  if (m.kind.startsWith("product")) {
    body = `<div class="message_componet-${direction}"><div class="CardWrapper ProductCard"><div>${m.kind === "product_error" ? `<div class="Error">${icon("package-x")}<span>卡片加载失败</span></div>` : `<img src="/product.svg" alt="测试开发板示意图"><div class="product-copy">${esc(m.text)}<br><small>sku: LOCAL-Q8B</small></div>`}</div></div></div>`;
  } else {
    body = `<div class="message-body"><pre class="message__text message__text_${direction} t-sl-msg-${direction}"><span class="message__content">${linkedText(m.text)}</span>${right ? '<div class="message__read_status read">已读</div>' : ""}</pre></div>`;
  }
  return `<div class="message message-undefined undefined"><div class="message_${direction}" id="${esc(m.id)}"><div class="message__nickname t-color-2">${right ? time + esc(name) : esc(name) + time}</div><img class="message__avatar" src="/avatar-${right ? "agent" : "customer"}.svg" alt="">${body}</div></div>`;
}
async function refreshChat(buyer, token, initial=false) {
  const chat = await api("/api/chat?user=" + encodeURIComponent(buyer));
  if (token !== generation || selected !== buyer) return;
  const signature = chat.messages.map(m=>m.id).join(",");
  if (signature !== lastMessages || initial) {
    const bottom = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 40;
    content.innerHTML = chat.messages.map(renderMessage).join("");
    lastMessages = signature;
    hydrateIcons();
    if (initial || bottom) scroller.scrollTop = scroller.scrollHeight;
  }
  loadedBuyer = buyer;
  editor.contentEditable = "true";
  if (initial) editor.textContent = drafts.get(buyer) || "";
  $(".SendButtonGroup").classList.toggle("busy", sending);
  $(".chat-product .name").textContent = chat.product + "  sku: LOCAL-Q8B";
  $(".chat-product").hidden = false;
  if (chat.unread && chat.messages.length) await api("/api/read",{user:buyer,through:chat.messages.at(-1).id});
}
async function selectBuyer(buyer) {
  saveDraft();
  selected = buyer;
  sessionStorage.setItem("replica.customer", buyer);
  const token = ++generation;
  loading = true;
  loadedBuyer = ""; lastMessages = "";
  editor.textContent = ""; editor.contentEditable = "false";
  content.replaceChildren();
  $(".chat-head-name").innerHTML = `<span>${esc(buyer)}</span><span class="consult-type">[在线咨询]</span><span></span><span class="chatHead-entering"></span>`;
  $(".chat-product").hidden = true;
  $(".SendButtonGroup").classList.add("busy");
  $(".send-error").textContent = "";
  renderLists();
  try {await refreshChat(buyer, token, true);} catch (error) {if(token===generation) $(".send-error").textContent=error.message;}
  finally {if(token===generation) loading=false;}
}
async function send() {
  const buyer = selected, text = editor.innerText.trim(), token = generation;
  if (!buyer || loadedBuyer !== buyer || !text || sending) return;
  if (text.length > 10000) {$(".send-error").textContent="消息不能超过 10000 字";return;}
  sending = true;
  $(".SendButtonGroup").classList.add("busy");
  $(".send-error").textContent = "";
  const key = JSON.stringify([buyer,text]);
  const request_id = pendingRequests.get(key) || crypto.randomUUID();
  pendingRequests.set(key,request_id);
  try {
    await api("/api/agent-send",{buyer_id:buyer,text,request_id});
    pendingRequests.delete(key);
    if ((drafts.get(buyer) || "").trim() === text) drafts.delete(buyer);
    sessionStorage.setItem("replica.drafts",JSON.stringify([...drafts]));
    if (selected === buyer && token === generation) {
      if (editor.innerText.trim() === text) editor.replaceChildren();
      saveDraft();
      await refreshChat(buyer, token);
      scroller.scrollTop = scroller.scrollHeight;
    }
  } catch (error) {
    if (selected === buyer) $(".send-error").textContent = "发送失败，可重试：" + error.message;
  } finally {sending=false;$(".SendButtonGroup").classList.toggle("busy",loadedBuyer!==selected);}
}
function renderPhrases() {
  const term = $(".phrase-search input").value;
  $(".phrase-list").innerHTML = phraseTab ? "" : cases.filter(c=>c.question.includes(term)||c.reply.includes(term)).map(c=>`<div class="phrase-item"><strong>${esc(c.question)}</strong><p>${esc(c.reply)}</p></div>`).join("");
}
$(".c_tabs-nav-container").addEventListener("click",e=>{const el=e.target.closest(".c_tabs-tab");if(el)selectTab($$(".c_tabs-tab").indexOf(el));});
$(".c_tabs-content").addEventListener("click", e=> {
  const el=e.target.closest(".alluser-item");
  if(el){selectBuyer($(".alluser-item-name",el).textContent);return;}
  const head=e.target.closest(".c_cas-head");
  if(head){const name=head.dataset.group;collapsed.has(name)?collapsed.delete(name):collapsed.add(name);renderLists();}
});
$("#t-search_input").addEventListener("input",renderLists);
$(".unread-filter").addEventListener("change",renderLists);
$(".send-button").addEventListener("click",send);
editor.addEventListener("input",saveDraft);
editor.addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.isComposing&&!e.shiftKey&&((sendMode==="enter"&&!e.ctrlKey)||(sendMode==="ctrl"&&e.ctrlKey))){e.preventDefault();send();}});
editor.addEventListener("paste",e=>{e.preventDefault();document.execCommand("insertText",false,e.clipboardData.getData("text/plain"));saveDraft();});
$(".SendButton-icon").addEventListener("click",()=>{$(".set-key-w").hidden=!$(".set-key-w").hidden;});
$(".set-key-w").addEventListener("click",e=>{const item=e.target.closest("[data-mode]");if(item){sendMode=item.dataset.mode;localStorage.setItem("replica.sendMode",sendMode);$(".set-key-w").hidden=true;}});
$(".phrase-tabs").addEventListener("click",e=>{if(e.target.tagName!=="SPAN")return;phraseTab=$$(".phrase-tabs span").indexOf(e.target);$$(".phrase-tabs span").forEach((s,i)=>s.classList.toggle("active",i===phraseTab));renderPhrases();});
$(".phrase-search input").addEventListener("input",renderPhrases);
$(".phrase-list").addEventListener("click",e=>{const item=e.target.closest(".phrase-item");if(item&&loadedBuyer===selected){editor.textContent=$("p",item).textContent;saveDraft();editor.focus();}});
$(".copy-link").addEventListener("click",async()=>{try{await navigator.clipboard.writeText($(".chat-product .name").textContent);}catch{$(".send-error").textContent="复制失败";}});
content.addEventListener("click",e=>{if(e.target.closest("a"))e.preventDefault();});
const emojis=["😀","🤔","😘","✌️","🤝","🙂","😎","😊","🌹","👍","❤️"];
$(".quick-emoji-w").innerHTML=emojis.map(e=>`<li title="${e}">${e}</li>`).join("");
$(".quick-emoji-w").addEventListener("click",e=>{const li=e.target.closest("li");if(li&&loadedBuyer===selected){editor.focus();document.execCommand("insertText",false,li.textContent);saveDraft();}});
selectTab(tab); hydrateIcons();
async function poll() {
  try {
    const next=await api("/api/state");
    const changed=!state||next.rev!==state.rev;
    state=next;
    $(".connection-status").textContent="";
    if(changed)renderLists();
    if(!state.recent.some(s=>s.buyer_id===selected)) {
      if(state.recent.length) await selectBuyer(state.recent[0].buyer_id);
      else {selected="";loadedBuyer="";content.replaceChildren();editor.textContent="";editor.contentEditable="false";$(".chat-head-name").textContent="";}
    } else if(!loadedBuyer && !loading) await selectBuyer(selected);
    else if(changed && loadedBuyer === selected) await refreshChat(selected,generation);
  } catch(error) {$(".connection-status").textContent="连接中断";}
  setTimeout(poll,700);
}
api("/api/templates").then(data=>{cases=data.cases;renderPhrases();}).catch(()=>{});
poll();
