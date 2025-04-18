
async function loadTable(){
  const res=await fetch('/scheduled');
  const rows=await res.json();
  const tbody=document.querySelector('#sched-table tbody');
  tbody.innerHTML='';
  rows.forEach((r,i)=>{
    const tr=document.createElement('tr');
    tr.innerHTML=`<td>${r.id}</td><td>${r.content}</td><td>${r.time}</td>
      <td><button onclick="del(${i})">Excluir</button></td>`;
    tbody.appendChild(tr);
  });
}
async function del(idx){
  await fetch('/delete_scheduled',{method:'POST',
    headers:{'Content-Type':'application/x-www-form-urlencoded','X-CSRFToken':csrfToken},
    body:`index=${idx}`});
  loadTable();
}
loadTable();
