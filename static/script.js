const contextInput = document.getElementById("context");
const charCountDiv = document.getElementById("char-count");

function updateCharCount() {
  const text = document.getElementById("post-output").textContent;
  charCountDiv.textContent = text ? `${text.length}/280 caracteres` : "";
}

async function generatePost() {
  const context = contextInput.value;
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
  updateCharCount();
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
  if (data.status === "success") {
    loadScheduledPosts();
  }
}

async function loadScheduledPosts() {
  const response = await fetch("/scheduled");
  const posts = await response.json();
  const container = document.getElementById("scheduled-posts");
  container.innerHTML = "";
  if (posts.length === 0) {
    container.innerHTML = "<p>Nenhum post agendado.</p>";
    return;
  }
  posts.forEach((item) => {
    const div = document.createElement("div");
    div.className = "scheduled-post";
    div.innerHTML = `<p>${item.post}</p><small>Agendado para: ${item.time}</small>`;
    container.appendChild(div);
  });
}

document.getElementById("generate-btn").addEventListener("click", generatePost);
document.getElementById("post-btn").addEventListener("click", postNow);
document.getElementById("schedule-btn").addEventListener("click", schedulePost);
document.getElementById("load-scheduled-btn").addEventListener("click", loadScheduledPosts);