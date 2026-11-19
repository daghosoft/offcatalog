"""Pagine HTML del pannello e delle impostazioni (JavaScript minimale)."""

PANEL_CSS = """:root{--bg:#f4f5f7;--card:#fff;--text:#111827;--muted:#6b7280;--faint:#9ca3af;--border:#e5e7eb;--hover:#f9fafb;
--bar:#0f172a;--bar-text:#e5e7eb;--accent:#2563eb;--accent-soft:#eff4ff;--on-accent:#fff;--on:#16a34a;--on-soft:#ecfdf3;
--warn:#d97706;--warn-soft:#fffbeb;--off:#9ca3af;--off-soft:#f3f4f6;--danger:#dc2626;--danger-soft:#fef2f2;
--shadow:0 1px 2px rgba(16,24,40,.05)}
@media (prefers-color-scheme: dark){:root{--bg:#0b0d12;--card:#131720;--text:#e5e7eb;--muted:#9aa3b2;--faint:#6b7280;
--border:#232a36;--hover:#182030;--bar:#0f131b;--bar-text:#e5e7eb;--accent:#60a5fa;--accent-soft:#15233d;--on-accent:#0b0d12;
--on:#34d399;--on-soft:#0f2a20;--warn:#fbbf24;--warn-soft:#2d2410;--off:#6b7280;--off-soft:#1c222d;
--danger:#f87171;--danger-soft:#2e1517;--shadow:none}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}
a{color:var(--accent)}
.mono{font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace}
.num,.kv b,td.n,.sc b{font-variant-numeric:tabular-nums}
.topbar{background:var(--bar);color:var(--bar-text);border-bottom:1px solid var(--border)}
.topbar .in{max-width:1200px;margin:0 auto;padding:0 16px;height:52px;display:flex;align-items:center;gap:14px}
.topbar h1{font-size:16px;font-weight:600;margin:0;letter-spacing:.01em}
.topbar small{color:var(--faint);font-weight:500;margin-left:6px}
.topbar .sp{flex:1}
.toplink{color:var(--bar-text);text-decoration:none;font-size:13px;padding:6px 10px;border-radius:6px}
.toplink:hover{background:var(--hover);color:var(--text)}
main{max-width:1200px;margin:0 auto;padding:20px 16px 48px}
.grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-bottom:16px;align-items:start}
@media (max-width:900px){.grid2{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--border);border-radius:10px;box-shadow:var(--shadow);margin-bottom:16px;min-width:0}
.grid2 .card{margin-bottom:0}
.card>h2{font-size:14px;font-weight:600;margin:0;padding:12px 16px;border-bottom:1px solid var(--border)}
.card .body{padding:14px 16px}
.muted{color:var(--muted)}
.kpi .v{font-size:22px;font-weight:600;font-variant-numeric:tabular-nums}
.kpi .v small{font-size:13px;color:var(--muted);font-weight:500}
.meter{height:6px;border-radius:3px;background:var(--off-soft);margin:8px 0 12px;overflow:hidden}
.meter b{display:block;height:100%;background:var(--accent);border-radius:3px;transition:width .3s}
.meter b.hi{background:var(--warn)}.meter b.crit{background:var(--danger)}
.kv{display:grid;grid-template-columns:170px minmax(0,1fr);gap:10px;padding:7px 0;border-bottom:1px solid var(--border);font-size:13px}
.kv:last-child{border-bottom:0}
.kv>span:first-child{color:var(--muted)}
.kv>span:last-child{overflow-wrap:anywhere;font-variant-numeric:tabular-nums}
.status{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:500;padding:2px 9px 2px 7px;border-radius:999px;white-space:nowrap}
.status::before{content:"";width:7px;height:7px;border-radius:50%;background:currentColor}
.st-in_corso{color:var(--accent);background:var(--accent-soft)}
.st-completata{color:var(--on);background:var(--on-soft)}
.st-interrotta{color:var(--warn);background:var(--warn-soft)}
.st-errore{color:var(--danger);background:var(--danger-soft)}
.st-nessuna_novita,.st-nessuna{color:var(--muted);background:var(--off-soft)}
.st-nessuna_novita::before,.st-nessuna::before{background:var(--off)}
.tag{font-size:11px;font-weight:500;color:var(--muted);border:1px solid var(--border);border-radius:4px;padding:0 5px;white-space:nowrap}
.err{color:var(--danger)}
.sc{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:4px 14px;font-size:13px}
.sc span:nth-child(3n+2),.sc span:nth-child(3n){text-align:right;font-variant-numeric:tabular-nums}
.sc .h{color:var(--muted);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.05em}
.sc .z{color:var(--faint)}
.tbl{overflow-x:auto}
table{border-collapse:collapse;width:100%}
th,td{text-align:left;padding:8px 12px;border-bottom:1px solid var(--border);font-size:13px;vertical-align:top;white-space:nowrap}
td.n{font-variant-numeric:tabular-nums}
th{color:var(--muted);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.05em}
tr:last-child td{border-bottom:0}
tbody tr:hover{background:var(--hover)}
td.w{white-space:normal;min-width:160px}
.empty{color:var(--faint);font-size:13px}
pre.mono{margin:0;padding:10px 12px;background:var(--bg);border:1px solid var(--border);border-radius:7px;font-size:12px;line-height:1.5;max-height:260px;overflow:auto;white-space:pre}
button{font:inherit;font-size:13px;font-weight:500;cursor:pointer;border-radius:7px;height:36px;padding:0 14px;border:1px solid var(--border);background:var(--card);color:var(--text)}
button:hover:not(:disabled){border-color:var(--muted)}
button:focus-visible,input:focus-visible,a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
button:disabled{opacity:.35;cursor:default}
button.primary{border:0;background:var(--accent);color:var(--on-accent);font-weight:600}
button.primary:hover:not(:disabled){filter:brightness(1.08)}
button.danger{border-color:var(--danger);background:transparent;color:var(--danger)}
button.danger:hover:not(:disabled){background:var(--danger-soft);border-color:var(--danger)}
button.warn{border-color:var(--warn);background:var(--warn-soft);color:var(--warn)}
button.warn:hover:not(:disabled){border-color:var(--warn);filter:brightness(.95)}
.cmds{display:flex;flex-wrap:wrap;gap:8px}
#msg{min-height:1.4em;margin-top:10px;font-size:13px;color:var(--muted)}
label{display:block;font-size:12px;font-weight:500;color:var(--muted);margin-bottom:4px}
input[type=text],input[type=number]{width:100%;max-width:340px;font:inherit;font-size:14px;height:36px;padding:0 10px;border-radius:7px;border:1px solid var(--border);background:var(--bg);color:var(--text)}
input:disabled{opacity:.6}
input[type=checkbox]{width:18px;height:18px;accent-color:var(--accent)}
.campo{padding:10px 0;border-bottom:1px solid var(--border)}
.campo:first-child{padding-top:0}
.campo label{font-size:13px;font-weight:600;color:var(--text)}
.hint{color:var(--muted);font-size:12px;margin-top:4px}
.ov{color:var(--warn);font-weight:600}
.errc{color:var(--danger);font-size:12px}
.campo button{height:30px;padding:0 10px;margin-top:6px;font-size:12px}
.bar2{display:flex;align-items:center;gap:12px;margin-top:14px}
@media (max-width:680px){
  .kv{grid-template-columns:1fr;gap:0}
  th,td{padding:8px}
}
@media (max-width:520px){
  main{padding:14px 12px 40px}
  .topbar .in{padding:0 12px}
  .cmds button{flex:1 1 calc(50% - 8px)}
}
"""

_PAGE_HEAD = """<!doctype html>
<html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>offcatalog</title>
<style>
@@CSS@@</style></head><body>"""

PANEL_HTML = (_PAGE_HEAD + """<div class="topbar"><div class="in"><h1>offcatalog<small id="ver"></small></h1><span class="sp"></span>
<a class="toplink" href="/settings">Impostazioni</a></div></div>
<main>
<div class="grid2">
<div class="card"><h2>Stato</h2><div class="body" id="stato"></div></div>
<div class="card"><h2>Avanzamento</h2><div class="body" id="avanz"></div></div>
</div>
<div class="grid2">
<div class="card"><h2>Scarti per motivo</h2><div class="body" id="scarti"></div></div>
<div class="card"><h2>Catalogo pubblicato</h2><div class="body"><div id="pub"></div><div id="api" class="muted" style="margin-top:8px"></div></div></div>
</div>
<div class="card"><h2>Comandi</h2><div class="body"><div class="cmds">
<button class="primary" data-cmd="avvia">Avvia</button>
<button class="danger" data-cmd="interrompi">Interrompi</button>
<button class="warn" data-cmd="forza">Forza</button>
<button data-cmd="riprendi">Riprendi</button>
<button class="warn" data-cmd="riparti">Riparti da zero</button></div>
<div id="msg" aria-live="polite"></div></div></div>
<div class="card"><h2>Log</h2><div class="body"><pre class="mono" id="log" tabindex="0"></pre></div></div>
<div class="card"><h2>Storico (ultime 20)</h2><div class="tbl" id="hist"></div></div>
</main>
<script>
const $=id=>document.getElementById(id);
const esc=s=>String(s==null?'-':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const mb=b=>b==null?'-':(b/1048576).toFixed(1)+' MB';
let TZ='UTC';
const DF=()=>{try{return new Intl.DateTimeFormat('it-IT',{timeZone:TZ,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'})}catch(e){return new Intl.DateTimeFormat('it-IT',{timeZone:'UTC',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'})}};
function fmtData(s){
  if(s==null||s==='')return '-';
  const t=new Date(s);if(isNaN(t))return String(s);
  const o={};DF().formatToParts(t).forEach(x=>{o[x.type]=x.value});
  return o.day+'/'+o.month+'/'+o.year+' '+o.hour+':'+o.minute+':'+o.second;
}
const num=n=>n==null?'-':Number(n).toLocaleString('it-IT');
const dur=s=>{if(s==null)return '-';s=Math.round(s);const h=Math.floor(s/3600),m=Math.floor(s%3600/60);
  return (h?h+'h ':'')+(h||m?m+'m ':'')+(s%60)+'s'};
const ETI={in_corso:'In corso',completata:'Completata',interrotta:'Interrotta',errore:'Errore',nessuna_novita:'Nessuna novita'};
const pill=st=>'<span class="status st-'+(ETI[st]?st:'nessuna')+'">'+esc(ETI[st]||st)+'</span>';
const kv=(k,v)=>'<div class="kv"><span>'+k+'</span><span>'+v+'</span></div>';
async function cmd(name){
  $('msg').textContent='...';
  try{const r=await fetch('/panel/cmd/'+name,{method:'POST',headers:{'X-Requested-With':'panel'}});
    const j=await r.json();$('msg').textContent=j.messaggio||j.esito||'';}
  catch(e){$('msg').textContent='errore: '+e}
  refresh();
}
document.querySelectorAll('button[data-cmd]').forEach(b=>b.onclick=()=>cmd(b.dataset.cmd));
function render(d){
  TZ=d.tz||'UTC';
  const s=d.stato,p=s.catalogo_pubblicato,r=s.esecuzione,a=s.ultima_chiamata_api;
  $('ver').textContent='v'+d.versione;
  $('pub').innerHTML=p.data?(kv('Data',esc(fmtData(p.data)))+kv('Prodotti',num(p.prodotti))+kv('Dimensione',mb(p.dimensione))
    +kv('Export del',esc(fmtData(p.data_export)))):'<b>Nessun catalogo pubblicato.</b> Premi Avvia.';
  $('api').textContent=a?('Ultima chiamata endpoint: '+fmtData(a.data)+' ('+a.esito+')'):'Nessuna chiamata ricevuta dall\\'endpoint.';
  const run=s.in_corso, wait=s.in_attesa_di_ripresa;
  document.querySelector('[data-cmd=avvia]').disabled=run||wait;
  document.querySelector('[data-cmd=forza]').disabled=run||wait;
  document.querySelector('[data-cmd=interrompi]').disabled=!run;
  document.querySelector('[data-cmd=riprendi]').disabled=run||!wait;
  document.querySelector('[data-cmd=riparti]').disabled=run;
  if(!r){
    $('stato').innerHTML=pill('nessuna')+' <span class="muted">Nessuna esecuzione.</span>';
    $('avanz').innerHTML='<div class="empty">Nessuna esecuzione.</div>';
    $('scarti').innerHTML='<div class="empty">Nessuna esecuzione.</div>';
  }else{
    $('stato').innerHTML='<div style="margin-bottom:8px">'+pill(r.stato)+'</div>'
      +kv('Esecuzione','#'+r.run_id)+kv('Fase',esc(r.fase))+kv('Origine',esc(r.origine))
      +(r.errore?kv('Errore','<span class="err">'+esc(r.errore)+'</span>'):'');
    const pc=Math.max(0,Math.min(100,Number(r.percentuale)||0));
    const fasi=(r.fasi||[]).map(f=>kv(esc(f.nome),dur(f.durata_s)+(f.fine?'':' <span class="muted">(in corso)</span>'))).join('');
    $('avanz').innerHTML='<div class="kpi"><div class="v">'+pc+'<small>%</small></div></div>'
      +'<div class="meter"><b style="width:'+pc+'%"></b></div>'
      +kv('Trascorso / stima rimanente',dur(r.durata_s)+' / '+dur(r.stima_secondi_rimanenti))
      +kv('Scaricati',mb(r.byte_scaricati)+' di '+mb(r.byte_totali))
      +kv('Velocita',r.velocita_bps==null?'-':mb(r.velocita_bps)+'/s')
      +kv('Righe lette',num(r.righe_lette))+kv('Prodotti tenuti',num(r.prodotti_tenuti))
      +(fasi?'<div class="muted" style="margin-top:10px;font-size:12px">Fasi</div>'+fasi:'');
    if(!r.scarti){$('scarti').innerHTML='<div class="empty">Nessun dato sugli scarti.</div>'}
    else{
      const tot=Number(r.righe_lette)||0;
      $('scarti').innerHTML='<div class="sc"><span class="h">Motivo</span><span class="h">Righe</span><span class="h">% lette</span>'
        +Object.entries(r.scarti).map(([k,v])=>'<span>'+esc(k.replace(/_/g,' '))+'</span><span'+(v?'':' class="z"')+'>'+num(v)+'</span><span'+(v?'':' class="z"')+'>'
          +(tot?(v*100/tot).toLocaleString('it-IT',{maximumFractionDigits:2})+'%':'-')+'</span>').join('')+'</div>';
    }
  }
  $('log').textContent=d.log.map(l=>fmtData(l.ts)+'  '+l.line).join('\\n');
  $('log').scrollTop=$('log').scrollHeight;
  $('hist').innerHTML='<table><thead><tr><th>#</th><th>Inizio</th><th>Origine</th><th>Esito</th><th>Durata</th><th>Prodotti</th><th>Errore</th></tr></thead><tbody>'
    +d.storico.map(h=>'<tr><td class="n">'+h.run_id+'</td><td class="n">'+esc(fmtData(h.inizio))+'</td><td>'+esc(h.origine)+'</td><td>'+pill(h.stato)
      +'</td><td class="n">'+dur(h.durata_s)+'</td><td class="n">'+num(h.prodotti_tenuti)+'</td><td class="w err">'+esc(h.errore||'')+'</td></tr>').join('')+'</tbody></table>';
}
async function refresh(){
  try{const r=await fetch('/panel/data');if(r.ok)render(await r.json())}catch(e){}
}
refresh();setInterval(refresh,2000);
</script></body></html>
""").replace("@@CSS@@", PANEL_CSS)

_TOP_SET = """<div class="topbar"><div class="in"><h1>offcatalog<small>Impostazioni</small></h1><span class="sp"></span>
<a class="toplink" href="/">Torna al pannello</a></div></div>"""

SETTINGS_LOCKED_HTML = (_PAGE_HEAD + _TOP_SET + """
<main><div class="card"><h2>Impostazioni</h2><div class="body"><p style="margin:0">Sync in corso: impostazioni non disponibili.</p>
<p style="margin:10px 0 0"><a href="/">Torna al pannello</a></p></div></div></main></body></html>
""").replace("@@CSS@@", PANEL_CSS)

SETTINGS_HTML = (_PAGE_HEAD + _TOP_SET + """
<main><div class="card"><h2>Impostazioni</h2><div class="body"><div id="set"></div>
<div class="bar2"><button class="primary" id="setsave">Salva</button><span id="setmsg" class="muted" aria-live="polite"></span></div>
<p style="margin:14px 0 0"><a href="/">Torna al pannello</a></p></div></div></main>
<script>
const $=id=>document.getElementById(id);
const esc=s=>String(s==null?'-':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const HDR={'Content-Type':'application/json','X-Requested-With':'panel'};
function setRender(v){
  $('set').innerHTML=v.campi.map(f=>{
    const val=f.tipo==='bool'?'':esc(f.valore), dflt=f.tipo==='bool'?(f.default?'si':'no'):esc(f.default);
    const inp=f.tipo==='bool'?'<input type="checkbox" id="s_'+f.chiave+'"'+(f.valore?' checked':'')+'>'
      :'<input type="'+(f.tipo==='testo'?'text':'number')+'" step="any" id="s_'+f.chiave+'" value="'+val+'">';
    return '<div class="campo"><label for="s_'+f.chiave+'">'+esc(f.etichetta)+'</label>'+inp
      +'<div class="hint">'+esc(f.descrizione)+'</div>'
      +'<div class="hint">Valore di partenza: <b>'+dflt+'</b> &middot; '+(f.sovrascritto?'<span class="ov">modificato dal pannello</span>':'nessuna modifica')+'</div>'
      +'<div class="errc" id="e_'+f.chiave+'"></div>'
      +(f.sovrascritto?'<button data-reset="'+f.chiave+'">Ripristina</button>':'')+'</div>';
  }).join('');
  document.querySelectorAll('button[data-reset]').forEach(b=>b.onclick=()=>setReset(b.dataset.reset));
  v.campi.forEach(f=>{f._cur=f.valore});window._setFields=v.campi;
}
async function setLoad(){
  try{const r=await fetch('/panel/settings');if(r.ok)setRender(await r.json())}catch(e){}
}
async function setSave(){
  const body={};
  (window._setFields||[]).forEach(f=>{
    const el=$('s_'+f.chiave);if(!el)return;
    const cur=f.tipo==='bool'?el.checked:el.value;
    if(String(cur)!==String(f._cur))body[f.chiave]=cur;
    $('e_'+f.chiave).textContent='';
  });
  if(!Object.keys(body).length){$('setmsg').textContent='Nessuna modifica.';return}
  const r=await fetch('/panel/settings',{method:'POST',headers:HDR,body:JSON.stringify(body)});
  const j=await r.json();
  if(r.ok){$('setmsg').textContent='Salvato.';setRender(j)}
  else{$('setmsg').textContent=j.errore||'errore';
    if(r.status===409)setTimeout(()=>location.reload(),1500);
    Object.entries(j.campi||{}).forEach(([k,m])=>{const e=$('e_'+k);if(e)e.textContent=m});}
}
async function setReset(key){
  const r=await fetch('/panel/settings/reset/'+key,{method:'POST',headers:HDR});
  const j=await r.json();
  if(r.ok){$('setmsg').textContent='Ripristinato.';setRender(j)}else $('setmsg').textContent=j.errore||'errore';
}
$('setsave').onclick=setSave;
setLoad();
</script></body></html>
""").replace("@@CSS@@", PANEL_CSS)
