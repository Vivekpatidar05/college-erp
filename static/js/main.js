// ── Date in topbar ────────────────────────────────────────────
const dateEl = document.getElementById("topbar-date");
if (dateEl) dateEl.textContent = new Date().toLocaleDateString("en-IN",
  { weekday:"short", day:"numeric", month:"short", year:"numeric" });

// ── Sidebar toggle ────────────────────────────────────────────
function toggleSidebar() {
  document.getElementById("sidebar").classList.toggle("open");
}
document.addEventListener("click", e => {
  const sb = document.getElementById("sidebar");
  const hm = document.querySelector(".hamburger");
  if (sb && hm && !sb.contains(e.target) && !hm.contains(e.target))
    sb.classList.remove("open");
});

// ── Auto-dismiss alerts ───────────────────────────────────────
document.querySelectorAll(".alert").forEach(a => {
  setTimeout(() => {
    a.style.transition = "opacity .4s, transform .4s";
    a.style.opacity = "0"; a.style.transform = "translateY(-8px)";
    setTimeout(() => a.remove(), 400);
  }, 4500);
});

// ── Confirm delete ────────────────────────────────────────────
document.querySelectorAll(".delete-btn").forEach(btn =>
  btn.addEventListener("click", e => {
    if (!confirm("Delete this record permanently?")) e.preventDefault();
  })
);

// ── Roll-no → name/course autocomplete ───────────────────────
document.querySelectorAll(".roll-lookup").forEach(inp => {
  inp.addEventListener("blur", async () => {
    const roll = inp.value.trim(); if (!roll) return;
    try {
      const res  = await fetch(`/api/student/${encodeURIComponent(roll)}`);
      if (!res.ok) return;
      const data = await res.json();
      const form = inp.closest("form");
      const nf = form?.querySelector(".s-name");
      const cf = form?.querySelector(".s-course");
      const sf = form?.querySelector(".s-sem");
      if (nf && data.name)     nf.value = data.name;
      if (cf && data.course)   cf.value = data.course;
      if (sf && data.semester) sf.value = data.semester;
    } catch(_) {}
  });
});

// ── Mark all present / absent ─────────────────────────────────
const presAll = document.getElementById("mark-all-present");
const absAll  = document.getElementById("mark-all-absent");
if (presAll) presAll.onclick = () =>
  document.querySelectorAll(".att-status").forEach(s => s.value = "Present");
if (absAll)  absAll.onclick  = () =>
  document.querySelectorAll(".att-status").forEach(s => s.value = "Absent");

// ── Chart.js helpers (used in analytics) ─────────────────────
function mkChart(id, type, labels, data, colors, opts = {}) {
  const ctx = document.getElementById(id);
  if (!ctx) return;
  return new Chart(ctx, {
    type, data: { labels, datasets: [{ data, backgroundColor: colors,
      borderColor: type === "line" ? colors[0] : colors,
      borderWidth: type === "line" ? 2 : 1, fill: type === "line",
      tension: 0.4, pointBackgroundColor: colors[0] }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { labels: { color: "#8b90a8", font: { family:"Plus Jakarta Sans", size:11 } } },
        tooltip: { backgroundColor:"#1d2035", titleColor:"#e2e5f0", bodyColor:"#8b90a8",
          borderColor:"rgba(255,255,255,0.1)", borderWidth:1 }},
      scales: type !== "pie" && type !== "doughnut" ? {
        x: { ticks: { color:"#8b90a8" }, grid: { color:"rgba(255,255,255,0.04)" } },
        y: { ticks: { color:"#8b90a8" }, grid: { color:"rgba(255,255,255,0.04)" } }
      } : {},
      ...opts
    }
  });
}

// ── Print helper ──────────────────────────────────────────────
function printPage() { window.print(); }
