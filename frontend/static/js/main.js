"use strict";
/* ===== Démarrage : authentification, routage ===== */

let authMode = "login";

const PAGE_TITLES = {
  accueil: "Accueil", entreprises: "Entreprises", offres: "Offres", carte: "Carte",
  candidatures: "Candidatures", cv: "Mes CV", profil: "Profil & Matching",
  statistiques: "Statistiques", donnees: "Collecte & Import",
};

function setNavOpen(open) {
  document.body.classList.toggle("nav-open", open);
  const t = $("#nav-toggle"); if (t) t.setAttribute("aria-expanded", String(open));
}

function showAuth(notice = "") {
  $("#app").hidden = true; $("#auth").hidden = false;
  const err = $("#auth-error"); err.textContent = notice; err.hidden = !notice;
}

function showApp() {
  $("#auth").hidden = true; $("#app").hidden = false;
  $("#user-name").textContent = state.user.username;
  $("#user-avatar").textContent = state.user.username.charAt(0).toUpperCase();
  $("#user-role").hidden = !state.user.is_admin;
  route();
}

function setAuthMode(mode) {
  authMode = mode;
  $$("[data-auth-tab]").forEach((b) => b.classList.toggle("active", b.dataset.authTab === mode));
  $("#confirm-row").hidden = mode !== "register";
  $("#auth-submit").textContent = mode === "login" ? "Se connecter" : "Créer mon compte";
  $("#auth-form").password.autocomplete = mode === "login" ? "current-password" : "new-password";
  $("#auth-error").hidden = true;
}

async function route() {
  if (!state.token) return;
  const name = (location.hash.replace(/^#\//, "") || "accueil").split("?")[0];
  const render = pages[name] || pages.accueil;
  const current = pages[name] ? name : "accueil";
  $$("#nav a").forEach((a) => {
    const active = a.dataset.route === current;
    a.classList.toggle("active", active);
    if (active) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
  const title = PAGE_TITLES[current] || "Career Finder";
  document.title = title + " · Career Finder";
  $("#topbar-title").textContent = title;
  setNavOpen(false);
  destroyCharts();
  const view = $("#view");
  view.innerHTML = skeleton();
  try {
    await render(view);
  } catch (e) {
    if (e.status === 401) return;   // logout() a déjà affiché l'écran de connexion
    view.innerHTML = `<div class="notice">⚠️ ${esc(e.message)}</div>`;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  $$("[data-auth-tab]").forEach((b) => b.addEventListener("click", () => setAuthMode(b.dataset.authTab)));

  $("#auth-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const f = ev.target, err = $("#auth-error"); err.hidden = true;
    if (authMode === "register" && f.password.value !== f.confirm.value) {
      err.textContent = "Les mots de passe ne correspondent pas."; err.hidden = false; return;
    }
    const btn = $("#auth-submit"); btn.disabled = true;
    try {
      const data = await api(authMode === "login" ? "/auth/login" : "/auth/register", {
        method: "POST", json: { username: f.username.value.trim(), password: f.password.value } });
      setSession(data); f.reset(); showApp();
    } catch (e) { err.textContent = e.message; err.hidden = false; }
    btn.disabled = false;
  });

  $("#logout").addEventListener("click", () => { setNavOpen(false); logout(); });
  $("#nav-toggle").addEventListener("click", () => setNavOpen(!document.body.classList.contains("nav-open")));
  $("#scrim").addEventListener("click", () => setNavOpen(false));
  document.addEventListener("keydown", (ev) => { if (ev.key === "Escape") setNavOpen(false); });
  window.addEventListener("hashchange", route);

  if (state.token && state.user) showApp(); else showAuth();
});
