"use strict";
const $=s=>document.querySelector(s);
let selected="",last="",busy=false;
const escapeHTML=s=>String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
async function api(path,body){const r=await fetch(path,{method:body?"POST":"GET",headers:body?{"Content-Type":"application/json"}:{},body:body?JSON.stringify(body):undefined});const data=await r.json();if(!r.ok)throw new Error(data.error);return data;}
async function update(){try{const state=await api("/api/state");if(!selected&&state.recent.length)selected=state.recent[0].buyer_id;const html=state.recent.map(s=>`<div class="customer ${s.buyer_id===selected?"active":""}"><span>${escapeHTML(s.buyer_id)}</span><small>${s.unread} 条未读</small></div>`).join("");if($("#customers").innerHTML!==html)$("#customers").innerHTML=html;if(selected){const buyer=selected;const chat=await api("/api/chat?user="+encodeURIComponent(buyer));if(buyer!==selected)return;$("#customer-title").textContent=buyer;const key=buyer+chat.messages.map(m=>m.id).join();if(key!==last){last=key;$("#history").innerHTML=chat.messages.map(m=>`<div class="turn ${m.role}"><small>${m.role==="customer"?"客户":m.role==="agent"?"客服":"系统"} · ${escapeHTML(m.ts)}</small>${escapeHTML(m.text)}</div>`).join("");$("#history").scrollTop=$("#history").scrollHeight;}}}catch(e){$("#status").textContent=e.message;}}
$("#customers").addEventListener("click",e=>{const row=e.target.closest(".customer");if(row){selected=row.querySelector("span").textContent;update();}});
$("#create").addEventListener("submit",async e=>{e.preventDefault();try{const data=await api("/api/users",{name:new FormData(e.target).get("name")});selected=data.user.name;e.target.reset();await update();}catch(err){$("#status").textContent=err.message;}});
$("#inbound").addEventListener("submit",async e=>{e.preventDefault();if(!selected||busy)return;busy=true;try{await api("/api/send",{user:selected,text:new FormData(e.target).get("text")});e.target.reset();$("#status").textContent="客户消息已发送";await update();}catch(err){$("#status").textContent=err.message;}finally{busy=false;}});
$("#template").addEventListener("change",e=>{$("textarea").value=e.target.value;});
api("/api/templates").then(data=>{data.cases.forEach(c=>{const o=document.createElement("option");o.value=c.question;o.textContent=c.question;$("#template").append(o);});});
lucide.createIcons();
(async function poll(){await update();setTimeout(poll,800);})();
