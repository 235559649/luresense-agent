/* Render untrusted model/user text using textContent, never innerHTML. */
const $ = id => document.getElementById(id);
let config, current, busy = false;
const names = {waterbody: '水域', cover: '可见结构', temperature_source: '温度来源'};
const routes = {knowledge:'知识问答',site:'现场条件',temperature:'温度条件',out_of_scope:'范围不适用'};
function node(tag, text, cls) { const el = document.createElement(tag); if(text !== undefined) el.textContent=text; if(cls) el.className=cls; return el; }
function error(message) { $('error').textContent=message; $('error').hidden=!message; }
function setBusy(value) { busy=value; document.querySelectorAll('button,select,textarea').forEach(el=>el.disabled=value); $('export').disabled=value || !current; $('activity').textContent=value?'正在处理，请稍候；真实模式可能需要等待模型返回。':''; }
async function request(path,data) { const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-LureSense-Token':config.csrf_token},body:JSON.stringify(data)}); const body=await response.json(); if(!response.ok) throw Error(body.error||'请求失败'); return body; }
async function execute(action) { if(busy || !config) return; error(''); setBusy(true); try { await action(); } catch(e){error(e.message);} finally{setBusy(false);} }
function render(data) {
  current=data;
  $('followup-card').hidden=!data.followup;
  $('followup-options').replaceChildren();
  if(data.followup){
    $('followup-text').textContent=names[data.followup.slot]+'还需要确认，不知道也可以继续。';
    data.followup.options.forEach(option=>{const b=node('button',option.label); b.type='button'; b.onclick=()=>choose(data.followup.slot,option.value); $('followup-options').append(b);});
  }
  $('context').replaceChildren();
  Object.entries(data.context).forEach(([key,fact])=>{
    const row=node('div',undefined,'context-row'), label=node('label',names[key]);
    const select=node('select'); select.id='condition-'+key; label.htmlFor=select.id;
    const empty=node('option',fact.status==='unanswered'?'尚未提供':'请选择'); empty.value=''; empty.disabled=true; select.append(empty);
    data.choices[key].forEach(option=>{const o=node('option',option.label);o.value=option.value;select.append(o);});
    select.value=fact.status==='unanswered'?'':Object.entries(data.choices[key]).map(([,v])=>v).find(v=>v.label===(fact.value===null?'不知道':fact.value))?.value||'';
    select.onchange=()=>choose(key,select.value);
    row.append(label,select,node('small',fact.corrected?'已修改 · 用户自述未验证':fact.status==='unknown'?'明确未知':fact.status==='unanswered'?'等待补充':'用户自述 · 未验证'));
    $('context').append(row);
  });
  $('metrics').textContent=`${routes[data.task]||data.task} · 自动追问 ${data.questions_asked}/2 · 模型请求 ${data.model_requests}/3`;
  $('trace').replaceChildren();
  data.events.forEach(event=>{
    let text=event.event==='start'?'识别问题类型：'+(routes[event.task]||event.task):event.event==='ask'?'询问'+names[event.slot]:event.event==='update'?'更新'+names[event.slot]+'：'+(event.current.value??'不知道'):event.event==='response'?'处理结果：'+event.result.status+(event.result.request_attempted?'（尝试模型请求）':'（未请求模型）'):event.event;
    $('trace').append(node('li',text));
  });
  $('answer').replaceChildren();$('evidence').replaceChildren();
  const result=data.result;
  if(!result){$('answer').append(node('p','补齐必要条件后继续。','placeholder'));$('evidence-count').textContent='0 条';return;}
  if(result.message) $('answer').append(node('p',result.message));
  if(result.status==='insufficient_evidence'&&!result.message) $('answer').append(node('p','当前证据不足以支持回答。'));
  result.claims.forEach(claim=>{
    const card=node('div',undefined,'claim');card.append(node('span',claim.kind==='source_fact'?'来源事实 · 待核对':'项目推断','kind '+(claim.kind==='project_inference'?'inference':'')),node('p',claim.text));
    (claim.anchors||[]).forEach(a=>card.append(node('div',`${a.card_id} / 知识卡摘录：${a.quote}`,'quote')));
    if(claim.caveat) card.append(node('p','限制：'+claim.caveat,'caveat'));
    $('answer').append(card);
  });
  const evidence=result.evidence||[];$('evidence-count').textContent=evidence.length+' 条';
  if(!evidence.length) $('evidence').append(node('p','本次没有可展示的引用证据。','placeholder'));
  evidence.forEach(row=>{
    const d=node('details');d.append(node('summary',row.card.id+' · '+row.card.title),node('p',row.card.claim),node('p','适用条件：'+row.card.applicability),node('p','项目推断：'+row.card.application_note));
    row.sources.forEach(source=>{try{const url=new URL(source.url);if(url.protocol==='https:'){const a=node('a',source.title+' ↗');a.href=url.href;a.target='_blank';a.rel='noopener noreferrer';d.append(a);}}catch(e){}d.append(node('p','来源限制：'+source.limitations));});$('evidence').append(d);
  });
}
function choose(slot,choice){return execute(async()=>render(await request('/api/choose',{session_id:current.session_id,slot,choice})));}
$('question-form').onsubmit=event=>{event.preventDefault();const question=$('question').value.trim();if(!question)return;execute(async()=>render(await request('/api/start',{question})));};
document.querySelectorAll('[data-example]').forEach(button=>button.onclick=()=>{$('question').value=button.dataset.example;$('question').focus();});
$('export').onclick=()=>execute(async()=>{const data=await request('/api/export',{session_id:current.session_id});const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=node('a');a.href=url;a.download='luresense_web_'+Date.now()+'.json';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);});
setBusy(true);
fetch('/api/config').then(r=>{if(!r.ok)throw Error('连接失败');return r.json();}).then(data=>{config=data;$('mode').textContent=data.mode==='mock'?'模拟模式 · 不调用模型':'真实模型模式';}).catch(e=>error(e.message)).finally(()=>setBusy(false));
