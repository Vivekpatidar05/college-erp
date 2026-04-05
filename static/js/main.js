// ── Date display ──────────────────────────────────────────────────────────────
const dateEl = document.getElementById("current-date");
if (dateEl) {
  dateEl.textContent = new Date().toLocaleDateString("en-IN", {
    weekday: "short", day: "numeric", month: "short", year: "numeric"
  });
}

// ── Sidebar toggle (mobile) ────────────────────────────────────────────────────
function toggleSidebar() {
  document.getElementById("sidebar").classList.toggle("open");
}
document.addEventListener("click", (e) => {
  const sidebar   = document.getElementById("sidebar");
  const hamburger = document.querySelector(".hamburger");
  if (!sidebar || !hamburger) return;
  if (!sidebar.contains(e.target) && !hamburger.contains(e.target)) {
    sidebar.classList.remove("open");
  }
});

// ── Student autocomplete (roll no → name + course) ───────────────────────────
document.querySelectorAll(".roll-lookup").forEach(input => {
  input.addEventListener("blur", async () => {
    const roll = input.value.trim();
    if (!roll) return;
    try {
      const res  = await fetch(`/api/student/${encodeURIComponent(roll)}`);
      if (!res.ok) return;
      const data = await res.json();
      const form = input.closest("form");
      const nameF   = form && form.querySelector(".student-name-fill");
      const courseF = form && form.querySelector(".student-course-fill");
      if (nameF   && data.name)   nameF.value   = data.name;
      if (courseF && data.course) courseF.value = data.course;
    } catch (_) {}
  });
});

// ── Confirm before delete ──────────────────────────────────────────────────────
document.querySelectorAll(".delete-btn").forEach(btn => {
  btn.addEventListener("click", e => {
    if (!confirm("Delete this record? This cannot be undone.")) e.preventDefault();
  });
});

// ── Auto-dismiss flash alerts (4 s) ───────────────────────────────────────────
document.querySelectorAll(".alert").forEach(a => {
  setTimeout(() => {
    a.style.transition = "opacity 0.4s, transform 0.4s";
    a.style.opacity    = "0";
    a.style.transform  = "translateY(-8px)";
    setTimeout(() => a.remove(), 400);
  }, 4000);
});

// ── Mark-all Present / Absent buttons ─────────────────────────────────────────
const presentAll = document.getElementById("mark-all-present");
const absentAll  = document.getElementById("mark-all-absent");
if (presentAll) presentAll.addEventListener("click", () =>
  document.querySelectorAll(".att-status").forEach(s => s.value = "Present"));
if (absentAll)  absentAll.addEventListener("click",  () =>
  document.querySelectorAll(".att-status").forEach(s => s.value = "Absent"));
