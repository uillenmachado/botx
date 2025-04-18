
function showNotification(msg,err=false){
  const n=document.createElement('div');
  n.className='notification '+(err?'error':'success');
  n.textContent=msg;
  document.body.appendChild(n);
  setTimeout(()=>n.classList.add('show'),10);
  setTimeout(()=>{n.classList.remove('show');setTimeout(()=>n.remove(),300)},3000);
}
const out=document.getElementById('post-output');const cc=document.getElementById('char-count');
function upd(){cc.textContent=out.textContent?out.textContent.length+'/280':''}
async function send(url,body){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body});return r.json()}
document.getElementById('generate-btn').onclick=async()=>{
  const ctx=document.getElementById('context').value;
  const d=await send('/generate','context='+encodeURIComponent(ctx)+'&csrf_token='+csrfToken);
  out.textContent=d.post;upd();['post-btn','schedule-time','schedule-btn'].forEach(id=>document.getElementById(id).classList.remove('hidden'));
};
document.getElementById('post-btn').onclick=async()=>{
  const btn=this;btn.disabled=true;btn.textContent='Enviando...';
  const d=await send('/post','post='+encodeURIComponent(out.textContent)+'&csrf_token='+csrfToken);
  showNotification(d.message,d.status==='error');btn.disabled=false;btn.textContent='Postar Agora';
};
document.getElementById('schedule-btn').onclick=async()=>{
  const time=document.getElementById('schedule-time').value;if(!time)return showNotification('Horário?',true);
  const d=await send('/schedule','post='+encodeURIComponent(out.textContent)+'&time='+time+'&csrf_token='+csrfToken);
  showNotification(d.message,d.status==='error');
};
out.addEventListener('input',upd);
