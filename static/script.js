async function generatePost() {
  const context = document.getElementById("context").value;
  const response = await fetch("/generate", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `context=${encodeURIComponent(context)}`,
  });
  const data = await response.json();
  const output = document.getElementById("post-output");
  output.textContent = data.post;
  document.getElementById("post-btn").style.display = "inline-block";
  document.getElementById("schedule-time").style.display = "inline-block";
  document.getElementById("schedule-btn").style.display = "inline-block";
}

async function postNow() {
  const post = document.getElementById("post-output").textContent;
  if (!post) {
    alert("Nenhum post gerado.");
    return;
  }
  const response = await fetch("/post", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `post=${encodeURIComponent(post)}`,
  });
  const data = await response.json();
  alert(data.message);
}

async function schedulePost() {
  const post = document.getElementById("post-output").textContent;
  const time = document.getElementById("schedule-time").value;
  if (!post) {
    alert("Nenhum post gerado.");
    return;
  }
  if (!time) {
    alert("Por favor, selecione um horário!");
    return;
  }
  const response = await fetch("/schedule", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `post=${encodeURIComponent(post)}&time=${time}`,
  });
  const data = await response.json();
  alert(data.message);
}

document.getElementById("generate-btn").addEventListener("click", generatePost);
document.getElementById("post-btn").addEventListener("click", postNow);
document.getElementById("schedule-btn").addEventListener("click", schedulePost);