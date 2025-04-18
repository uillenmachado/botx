
async function fetchHistory(){
  const r=await fetch('/history');
  const data=await r.json();
  const labels=data.map(t=>new Date(t.metrics.created_at||t.date).toLocaleDateString());
  const likes=data.map(t=>t.metrics? t.metrics.like_count : (t.likes||0));
  const rts=data.map(t=>t.metrics? t.metrics.retweet_count : (t.retweets||0));
  const ctx=document.getElementById('chart').getContext('2d');
  new Chart(ctx,{type:'bar',data:{labels,
    datasets:[{label:'Likes',data:likes},{label:'RTs',data:rts}]},
    options:{responsive:true}});
}
fetchHistory();

const uploadInput=document.createElement('input');uploadInput.type='file';
document.body.appendChild(uploadInput);
let currentMedia=null;
uploadInput.onchange=async()=>{const file=uploadInput.files[0];
  const fd=new FormData();fd.append('file',file);
  const r=await fetch('/upload',{method:'POST',body:fd});
  const d=await r.json();if(d.status==='success'){currentMedia=d.media_id;alert('imagem ok');}};
document.getElementById('tweet').onclick=async()=>{
  const text=document.getElementById('post').textContent;
  const body='post='+encodeURIComponent(text)+'&media_id='+(currentMedia||'');
  const r=await fetch('/post',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded','X-CSRFToken':csrfToken},body});
  alert((await r.json()).message);
};
