const API_BASE_URL = "http://127.0.0.1:8000";

async function api(path, options = {}) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  const isJson = (res.headers.get("content-type") || "").includes("application/json");
  const body = isJson ? await res.json() : await res.text();

  if (!res.ok) {
    // FastAPI uses "detail" for errors; sometimes it's a list
    const detail = body?.detail;
    const msg = Array.isArray(detail) ? detail.join(" ") : detail || body?.error || "Request failed";
    throw new Error(msg);
  }
  return body;
}

export async function getMe() {
  return api("/me", { method: "GET" });
}

export async function logout() {
  return api("/logout", { method: "POST" });
}

export async function setNavbarAuthState() {
  const nav = document.getElementById("navAuth");
  if (!nav) return;

  const { user } = await getMe();
  if (!user) {
    nav.innerHTML = `
      <a class="nav-link" href="./login.html">Login</a>
      <a class="nav-link" href="./register.html">Register</a>
    `;
    return;
  }

  const verifiedBadge = user.is_age_verified ? `<span class="badge verified">ID verified</span>` : "";
  nav.innerHTML = `
    <div class="account-pill" role="group" aria-label="Account">
      <a class="pill-link" href="./profile.html">Profile</a>
      <button class="pill-user" id="myDetailsBtn" type="button" aria-label="Open my details">Hi, ${user.username}</button>
      ${verifiedBadge}
      <span class="pill-sep" aria-hidden="true"></span>
      <button class="pill-logout" id="logoutBtn" type="button">Logout</button>
    </div>
  `;

  const drawer = document.getElementById("profileDrawer");
  const overlay = document.getElementById("profileDrawerOverlay");
  const closeBtn = document.getElementById("profileDrawerCloseBtn");

  function setDrawerOpen(open) {
    if (!drawer || !overlay) return;
    drawer.classList.toggle("open", open);
    drawer.setAttribute("aria-hidden", open ? "false" : "true");
    overlay.classList.toggle("hidden", !open);
    overlay.setAttribute("aria-hidden", open ? "false" : "true");
    document.body.style.overflow = open ? "hidden" : "";
  }

  async function renderDrawer() {
    if (!drawer) return;
    const { user: u } = await getMe().catch(() => ({ user: null }));
    if (!u) return;

    const $ = (id) => document.getElementById(id);
    $("pdFullName").textContent = u.full_name || "—";
    $("pdUsername").textContent = u.username || "—";
    $("pdEmail").textContent = u.email || "—";
    $("pdDob").textContent = u.birth_date ? String(u.birth_date) : "—";
    $("pdVerify").textContent = `${u.verification_status || "pending"} (${u.is_age_verified ? "verified" : "not verified"})`;
    $("pdAdult").textContent = u.is_age_verified ? (u.is_adult ? "Adult (18+)" : "Under 18") : "Unknown";

    let restrictionText = "No restrictions.";
    if (!u.is_age_verified) restrictionText = "Adult movies are hidden until you verify your age.";
    else if (!u.is_adult) restrictionText = "Adult movies are restricted because you are under 18.";
    $("pdRestriction").textContent = restrictionText;
  }

  document.getElementById("myDetailsBtn")?.addEventListener("click", async () => {
    await renderDrawer();
    setDrawerOpen(true);
  });
  overlay?.addEventListener("click", () => setDrawerOpen(false));
  closeBtn?.addEventListener("click", () => setDrawerOpen(false));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") setDrawerOpen(false);
  });

  document.getElementById("logoutBtn")?.addEventListener("click", async () => {
    await logout();
    window.location.reload();
  });
}

