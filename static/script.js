function showNotification(message, isError = false){
  const notif=document.createElement("div");
  notif.className=`notification ${isError?"error":""}`;
  notif.textContent=message;
  document.body.appendChild(notif);
  setTimeout(()=>notif.classList.add("show"),10);
  setTimeout(()=>{
    notif.classList.remove("show");
    setTimeout(()=>notif.remove(),300);
  },3000);
}

const output=document.getElementById("post-output");
const charCount=document.getElementById("char-count");

function updateCharCount(){
  charCount.textContent=output.textContent?`${output.textContent.length}/280 caracteres`:"";
}

async function generatePost(){
  const context=document.getElementById("context").value;
  const res=await fetch("/generate",{
    method:"POST",
    headers:{ "Content-Type":"application/x-www-form-urlencoded"},
    body:`context=${encodeURIComponent(context)}&csrf_token=${encodeURIComponent(csrfToken)}`
  });
  const data=await res.json();
  output.textContent=data.post;
  document.getElementById("post-btn").classList.remove("hidden");
  document.getElementById("schedule-time").classList.remove("hidden");
  document.getElementById("schedule-btn").classList.remove("hidden");
  updateCharCount();
}

async function postNow(){
  const post=output.textContent;
  if(!post){showNotification("Nenhum post gerado.",true);return;}
  const res=await fetch("/post",{
    method:"POST",
    headers:{ "Content-Type":"application/x-www-form-urlencoded"},
    body:`post=${encodeURIComponent(post)}&csrf_token=${encodeURIComponent(csrfToken)}`
  });
  const data=await res.json();
  showNotification(data.message,data.status==="error");
}

async function schedulePost(){
  const post=output.textContent;
  const time=document.getElementById("schedule-time").value;
  if(!post){showNotification("Nenhum post gerado.",true);return;}
  if(!time){showNotification("Selecione um horário.",true);return;}
  const res=await fetch("/schedule",{
    method:"POST",
    headers:{ "Content-Type":"application/x-www-form-urlencoded"},
    body:`post=${encodeURIComponent(post)}&time=${time}&csrf_token=${encodeURIComponent(csrfToken)}`
  });
  const data=await res.json();
  showNotification(data.message,data.status==="error");
  if(data.status==="success"){loadScheduledPosts()}
}

async function deleteScheduled(index){
  const res=await fetch("/delete_scheduled",{
    method:"POST",
    headers:{ "Content-Type":"application/x-www-form-urlencoded"},
    body:`index=${index}&csrf_token=${encodeURIComponent(csrfToken)}`
  });
  const data=await res.json();
  showNotification(data.message,data.status==="error");
  if(data.status==="success"){loadScheduledPosts();}
}

async function loadScheduledPosts(){
  const res=await fetch("/scheduled");
  const posts=await res.json();
  const container=document.getElementById("scheduled-posts");
  container.innerHTML="";
  if(posts.length===0){container.innerHTML="<p>Nenhum post agendado.</p>";return;}
  posts.forEach((item,idx)=>{
    const div=document.createElement("div");
    div.className="scheduled-post";
    div.innerHTML=`<p>${item.post}</p><small>Agendado para: ${item.time}</small>
    <button onclick="deleteScheduled(${idx})">Excluir</button>`;
    container.appendChild(div);
  });
}

async function loadHistory(){
  const res=await fetch("/history");
  const container=document.getElementById("tweet-history");
  container.innerHTML="";
  if(res.status!==200){
    const data=await res.json();
    showNotification(data.message,true);
    return;
  }
  const tweets=await res.json();
  if(tweets.length===0){container.innerHTML="<p>Sem tweets recentes.</p>";return;}
  tweets.forEach(t=>{
    const div=document.createElement("div");
    div.className="history-item";
    div.innerHTML=`<p>${t.text}</p><small>${new Date(t.date).toLocaleString()}</small>`;
    container.appendChild(div);
  });
}

document.getElementById("generate-btn").addEventListener("click",generatePost);
document.getElementById("post-btn").addEventListener("click",postNow);
document.getElementById("schedule-btn").addEventListener("click",schedulePost);
document.getElementById("load-scheduled-btn").addEventListener("click",loadScheduledPosts);
document.getElementById("load-history-btn").addEventListener("click",loadHistory);

/* update char count on typing output (if user edits) */
output.addEventListener("input",updateCharCount);