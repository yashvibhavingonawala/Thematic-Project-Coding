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
    const detail = body?.detail;
    const msg = Array.isArray(detail) ? detail.join(" ") : detail || body?.error || "Request failed";
    throw new Error(msg);
  }
  return body;
}

async function getMe() {
  return api("/me", { method: "GET" });
}

async function logout() {
  return api("/logout", { method: "POST" });
}

async function setNavbarAuthState() {
  const nav = document.getElementById("navAuth");
  if (!nav) return;

  const { user } = await getMe().catch(() => ({ user: null }));
  if (!user) {
    nav.innerHTML = `
      <a class="nav-link" href="./login.html">Login</a>
      <a class="nav-link" href="./register.html">Register</a>
    `;
    return;
  }

  nav.innerHTML = `
    <a class="nav-link" href="./profile.html">Profile</a>
    <span class="nav-user">Hi, ${user.username}</span>
    <button class="nav-logout" id="logoutBtn" type="button">Logout</button>
  `;

  document.getElementById("logoutBtn")?.addEventListener("click", async () => {
    await logout().catch(() => null);
    window.location.reload();
  });
}

window.MovieCrewAuth = { api, getMe, logout, setNavbarAuthState };

