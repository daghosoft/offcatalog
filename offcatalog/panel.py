"""Pagina HTML del pannello (JavaScript minimale, polling ogni 2 secondi)."""

PANEL_HTML = """<!doctype html>
<html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>offcatalog</title>
<style>
:root{color-scheme:light;--bg:#f4f5f7;--surface:#fff;--border:#d8dce0;--text:#1c1e21;--muted:#57606a;
--head:#24292f;--head-text:#fff;--primary:#0969da;--primary-text:#fff;--warn:#9a6700;--warn-text:#fff;
--danger:#cf222e;--danger-text:#fff;--ok:#1a7f37;--err:#cf222e;--note:#9a6700;--btn:#f6f8fa;--btn-border:#8c959f;
--track:#e3e6ea;--row:#eceef0;--ok-fill:#2da44e;--pre-bg:#0d1117;--pre-text:#c9d1d9}
@media (prefers-color-scheme: dark){:root{color-scheme:dark;--bg:#0d1117;--surface:#161b22;--border:#30363d;
--text:#e6edf3;--muted:#9198a1;--head:#010409;--head-text:#e6edf3;--primary:#1f6feb;--primary-text:#fff;
--warn:#d29922;--warn-text:#0d1117;--danger:#da3633;--danger-text:#fff;--ok:#3fb950;--err:#ff7b72;--note:#e3b341;
--btn:#21262d;--btn-border:#484f58;--track:#30363d;--row:#21262d;--ok-fill:#2ea043;--pre-bg:#010409;--pre-text:#c9d1d9}}
body{font:14px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;margin:0;background:var(--bg);color:var(--text)}
header{background:var(--head);color:var(--head-text);padding:12px 20px;font-size:16px;font-weight:600}
header .k{color:var(--head-text);font-weight:400;opacity:.8}
main{max-width:980px;margin:16px auto;padding:0 12px}
section{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:14px 16px;margin-bottom:14px}
h2{font-size:13px;margin:0 0 10px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
button{font:inherit;font-weight:600;min-height:36px;padding:6px 14px;margin:0 8px 8px 0;border:1px solid var(--btn-border);border-radius:6px;background:var(--btn);color:var(--text);cursor:pointer}
button:hover:not(:disabled){border-color:var(--text)}
button:focus-visible{outline:2px solid var(--primary);outline-offset:2px}
button:disabled{opacity:.45;cursor:default}
[data-cmd=avvia]{background:var(--primary);color:var(--primary-text);border-color:var(--primary)}
[data-cmd=forza],[data-cmd=riparti]{background:var(--warn);color:var(--warn-text);border-color:var(--warn)}
[data-cmd=interrompi]{background:var(--danger);color:var(--danger-text);border-color:var(--danger)}
#msg{min-height:1.4em;color:var(--note);font-size:13px}
.bar{height:18px;background:var(--track);border-radius:9px;overflow:hidden;margin:10px 0 12px}
.bar>div{height:100%;background:var(--ok-fill);width:0;transition:width .5s ease}
#run b{display:inline-block;padding:1px 9px;border-radius:999px;background:var(--track);color:var(--text);font-size:12px;text-transform:uppercase;letter-spacing:.03em}
table{border-collapse:collapse;width:100%}
td,th{text-align:left;padding:6px 8px;border-bottom:1px solid var(--row);font-size:13px;vertical-align:top}
th{color:var(--muted);font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.03em}
#run td.k{color:var(--muted);white-space:nowrap}
#set .campo{padding:8px 0;border-bottom:1px solid var(--row)}
#set label{font-weight:600;display:block}
#set input[type=text],#set input[type=number]{font:inherit;padding:5px 8px;min-height:32px;width:100%;max-width:340px;box-sizing:border-box;border:1px solid var(--btn-border);border-radius:6px;background:var(--surface);color:var(--text)}
#set input:disabled{opacity:.6}
#set .info{color:var(--muted);font-size:12px;margin-top:2px}
#set .ov{color:var(--note);font-weight:600}
#set .errc{color:var(--err);font-size:12px}
#set button{min-height:30px;padding:3px 10px;margin:4px 8px 0 0;font-size:12px}
#setnote{color:var(--note);font-size:13px;margin-bottom:6px}
#hist{overflow-x:auto}
#hist td,#hist th{white-space:nowrap}
#hist td:last-child{white-space:normal}
pre{background:var(--pre-bg);color:var(--pre-text);padding:10px 12px;border-radius:6px;max-height:240px;overflow:auto;font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;margin:0;white-space:pre}
.k{color:var(--muted)}.err{color:var(--err)}.ok{color:var(--ok)}
@media (max-width:699px){
  body{font-size:15px}
  main{padding:0 8px;margin:10px auto}
  section{padding:12px}
  header{font-size:15px;padding:10px 14px}
  #run table,#run tbody,#run tr{display:block;width:100%}
  #run tr{display:grid;grid-template-columns:auto 1fr;gap:2px 12px;padding:6px 0;border-bottom:1px solid var(--row)}
  #run td{border:0;padding:1px 0;font-size:14px}
  #run td[colspan]{grid-column:1/-1}
  #run td.k{white-space:normal}
  pre{max-height:200px}
}
</style></head><body>
<header>offcatalog <span class="k" id="ver"></span></header>
<main>
<section><h2>Catalogo pubblicato</h2><div id="pub"></div><div id="api" class="k"></div></section>
<section><h2>Comandi</h2>
<button data-cmd="avvia">Avvia</button><button data-cmd="forza">Forza</button>
<button data-cmd="interrompi">Interrompi</button><button data-cmd="riprendi">Riprendi</button>
<button data-cmd="riparti">Riparti da zero</button><div id="msg" aria-live="polite"></div></section>
<section><h2>Impostazioni</h2><div id="setnote" aria-live="polite"></div><div id="set"></div>
<button id="setsave">Salva</button><span id="setmsg" class="k" aria-live="polite"></span></section>
<section><h2>Esecuzione</h2><div id="run"></div></section>
<section><h2>Registro</h2><pre id="log" tabindex="0"></pre></section>
<section><h2>Storico (ultime 20)</h2><div id="hist"></div></section>
</main>
<script>
const $=id=>document.getElementById(id);
const esc=s=>String(s==null?'-':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const mb=b=>b==null?'-':(b/1048576).toFixed(1)+' MB';
const num=n=>n==null?'-':Number(n).toLocaleString('it-IT');
const dur=s=>{if(s==null)return '-';s=Math.round(s);const h=Math.floor(s/3600),m=Math.floor(s%3600/60);
  return (h?h+'h ':'')+(h||m?m+'m ':'')+(s%60)+'s'};
async function cmd(name){
  $('msg').textContent='...';
  try{const r=await fetch('/panel/cmd/'+name,{method:'POST',headers:{'X-Requested-With':'panel'}});
    const j=await r.json();$('msg').textContent=j.messaggio||j.esito||'';}
  catch(e){$('msg').textContent='errore: '+e}
  refresh();
}
document.querySelectorAll('button[data-cmd]').forEach(b=>b.onclick=()=>cmd(b.dataset.cmd));
const HDR={'Content-Type':'application/json','X-Requested-With':'panel'};
let setLocked=false;
function setApplyLock(b){
  setLocked=!!(b&&b.bloccato);
  $('setnote').textContent=!setLocked?'':(b.motivo==='interrotta'?'Sync interrotta: annullala per cambiare i filtri.':'Sync in corso: impostazioni in sola lettura.');
  document.querySelectorAll('#set input,#set button,#setsave').forEach(e=>e.disabled=setLocked);
}
function setRender(v){
  $('set').innerHTML=v.campi.map(f=>{
    const val=f.tipo==='bool'?'':esc(f.valore), dflt=f.tipo==='bool'?(f.default?'si':'no'):esc(f.default);
    const inp=f.tipo==='bool'?'<input type="checkbox" id="s_'+f.chiave+'"'+(f.valore?' checked':'')+'>'
      :'<input type="'+(f.tipo==='testo'?'text':'number')+'" step="any" id="s_'+f.chiave+'" value="'+val+'">';
    return '<div class="campo"><label for="s_'+f.chiave+'">'+esc(f.etichetta)+'</label>'+inp
      +'<div class="info">'+esc(f.descrizione)+'</div>'
      +'<div class="info">Valore di partenza: <b>'+dflt+'</b> &middot; '+(f.sovrascritto?'<span class="ov">modificato dal pannello</span>':'nessuna modifica')+'</div>'
      +'<div class="errc" id="e_'+f.chiave+'"></div>'
      +(f.sovrascritto?'<button data-reset="'+f.chiave+'">Ripristina</button>':'')+'</div>';
  }).join('');
  document.querySelectorAll('button[data-reset]').forEach(b=>b.onclick=()=>setReset(b.dataset.reset));
  v.campi.forEach(f=>{f._cur=f.valore});window._setFields=v.campi;
  setApplyLock(v);
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
    Object.entries(j.campi||{}).forEach(([k,m])=>{const e=$('e_'+k);if(e)e.textContent=m});}
}
async function setReset(key){
  const r=await fetch('/panel/settings/reset/'+key,{method:'POST',headers:HDR});
  const j=await r.json();
  if(r.ok){$('setmsg').textContent='Ripristinato.';setRender(j)}else $('setmsg').textContent=j.errore||'errore';
}
$('setsave').onclick=setSave;
let lastLock=null;
function render(d){
  const lk=d.impostazioni_blocco;
  const lkey=lk.bloccato+'/'+lk.motivo;
  if(lkey!==lastLock){lastLock=lkey;if(window._setFields)setApplyLock(lk);}
  if(!window._setFields)setLoad();
  const s=d.stato,p=s.catalogo_pubblicato,r=s.esecuzione,a=s.ultima_chiamata_api;
  $('ver').textContent='v'+d.versione;
  $('pub').innerHTML=p.data?('Data: '+esc(p.data)+' &middot; prodotti: '+num(p.prodotti)+' &middot; dimensione: '+mb(p.dimensione)
    +' &middot; export del: '+esc(p.data_export)):'<b>Nessun catalogo pubblicato.</b> Premi Avvia.';
  $('api').textContent=a?('Ultima chiamata endpoint: '+a.data+' ('+a.esito+')'):'Nessuna chiamata ricevuta dall\\'endpoint.';
  const run=s.in_corso, wait=s.in_attesa_di_ripresa;
  document.querySelector('[data-cmd=avvia]').disabled=run||wait;
  document.querySelector('[data-cmd=forza]').disabled=run||wait;
  document.querySelector('[data-cmd=interrompi]').disabled=!run;
  document.querySelector('[data-cmd=riprendi]').disabled=run||!wait;
  document.querySelector('[data-cmd=riparti]').disabled=run;
  if(!r){$('run').textContent='Nessuna esecuzione.'}else{
    const sc=r.scarti?Object.entries(r.scarti).map(([k,v])=>k+': '+num(v)).join(' &middot; '):'-';
    $('run').innerHTML='<div>#'+r.run_id+' &middot; <b>'+esc(r.stato)+'</b> &middot; fase: '+esc(r.fase)
      +' &middot; origine: '+esc(r.origine)+'</div><div class="bar"><div style="width:'+r.percentuale+'%"></div></div>'
      +'<table>'
      +'<tr><td class="k">Avanzamento</td><td>'+r.percentuale+'%</td><td class="k">Trascorso / stima rimanente</td><td>'+dur(r.durata_s)+' / '+dur(r.stima_secondi_rimanenti)+'</td></tr>'
      +'<tr><td class="k">Scaricati</td><td>'+mb(r.byte_scaricati)+' di '+mb(r.byte_totali)+'</td><td class="k">Velocita</td><td>'+(r.velocita_bps==null?'-':mb(r.velocita_bps)+'/s')+'</td></tr>'
      +'<tr><td class="k">Righe lette</td><td>'+num(r.righe_lette)+'</td><td class="k">Prodotti tenuti</td><td>'+num(r.prodotti_tenuti)+'</td></tr>'
      +'<tr><td class="k">Scarti</td><td colspan="3">'+sc+'</td></tr>'
      +(r.errore?'<tr><td class="k">Errore</td><td colspan="3" class="err">'+esc(r.errore)+'</td></tr>':'')
      +'</table>';
  }
  $('log').textContent=d.log.map(l=>l.ts+'  '+l.line).join('\\n');
  $('log').scrollTop=$('log').scrollHeight;
  $('hist').innerHTML='<table><tr><th>#</th><th>Inizio</th><th>Origine</th><th>Esito</th><th>Durata</th><th>Prodotti</th><th>Errore</th></tr>'
    +d.storico.map(h=>'<tr><td>'+h.run_id+'</td><td>'+esc(h.inizio)+'</td><td>'+esc(h.origine)+'</td><td>'+esc(h.stato)
      +'</td><td>'+dur(h.durata_s)+'</td><td>'+num(h.prodotti_tenuti)+'</td><td class="err">'+esc(h.errore||'')+'</td></tr>').join('')+'</table>';
}
async function refresh(){
  try{const r=await fetch('/panel/data');if(r.ok)render(await r.json())}catch(e){}
}
refresh();setInterval(refresh,2000);
</script></body></html>
"""
