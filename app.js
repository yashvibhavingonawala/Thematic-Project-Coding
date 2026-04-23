const API_BASE_URL = "http://127.0.0.1:8000";

let currentMovies = [];
let genreNameToId = {};
let genreIdToName = {};
let currentPage = 1;
let pageSize = 24;
let totalCount = null;
let activeRoute = "home";
let activeGenreId = null;
let activeGenreName = null;
let modalMovie = null;
/** Extra query params for the current paged list (so “Load more” keeps genre/person filters). */
let paginationExtra = {};
let allowPagination = false;
let featuredHeroMovie = null;

const movieGrid = document.getElementById("movieGrid");
const resultsCount = document.getElementById("resultsCount");
const cardTemplate = document.getElementById("movieCardTemplate");
const heroTitle = document.getElementById("heroTitle");
const heroDescription = document.getElementById("heroDescription");
const heroYear = document.getElementById("heroYear");
const heroRuntime = document.getElementById("heroRuntime");
const heroGenre = document.getElementById("heroGenre");
const heroEyebrow = document.getElementById("heroEyebrow");

const globalSearch = document.getElementById("globalSearch");
const yearFromInput = document.getElementById("yearFrom");
const yearToInput = document.getElementById("yearTo");
const budgetRange = document.getElementById("budgetRange");
const revenueRange = document.getElementById("revenueRange");
const actorFilter = document.getElementById("actorFilter");
const directorFilter = document.getElementById("directorFilter");
const applyFiltersBtn = document.getElementById("applyFiltersBtn");
const clearFiltersBtn = document.getElementById("clearFiltersBtn");
const genreFilterContainer = document.getElementById("genreFilters");

const toUSD = (value) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value);

const movieModal = document.getElementById("movieModal");
const modalCloseBtn = document.getElementById("modalCloseBtn");
const modalPoster = document.getElementById("modalPoster");
const modalTitle = document.getElementById("modalTitle");
const modalSub = document.getElementById("modalSub");
const modalGenres = document.getElementById("modalGenres");
const modalOverview = document.getElementById("modalOverview");
const modalDirector = document.getElementById("modalDirector");
const modalCast = document.getElementById("modalCast");
const modalBudget = document.getElementById("modalBudget");
const modalRevenue = document.getElementById("modalRevenue");
const watchlistToggleBtn = document.getElementById("watchlistToggleBtn");
const clearHistoryBtn = document.getElementById("clearHistoryBtn");
const reviewForm = document.getElementById("reviewForm");
const reviewText = document.getElementById("reviewText");
const reviewMsg = document.getElementById("reviewMsg");
const reviewsList = document.getElementById("reviewsList");
const reviewsCount = document.getElementById("reviewsCount");

const authModal = document.getElementById("authModal");
const authCloseBtn = document.getElementById("authCloseBtn");
const authTabLogin = document.getElementById("authTabLogin");
const authTabRegister = document.getElementById("authTabRegister");
const authLoginForm = document.getElementById("authLoginForm");
const authRegisterForm = document.getElementById("authRegisterForm");
const authVerifyInlineForm = document.getElementById("authVerifyInlineForm");
const authVerifySubmitBtn = document.getElementById("authVerifySubmitBtn");
const authMsg = document.getElementById("authMsg");

let cachedMe = null;
let cachedMeAt = 0;
let lastKnownUserId = null;

function syncLastUserIdFromMe(me) {
  const id = me?.user?.id;
  if (!id) return;
  lastKnownUserId = String(id);
  try {
    localStorage.setItem("moviecrew_last_user_id", String(id));
  } catch {
    // ignore
  }
}

async function getMeCached() {
  const now = Date.now();
  if (cachedMe && now - cachedMeAt < 8000) return cachedMe;
  try {
    const res = await fetch(`${API_BASE_URL}/me`, { credentials: "include" });
    const body = await res.json().catch(() => ({}));
    cachedMe = body;
    cachedMeAt = now;
    syncLastUserIdFromMe(body);
    return body;
  } catch {
    cachedMe = { user: null };
    cachedMeAt = now;
    return cachedMe;
  }
}

function openAuthModal(mode = "login") {
  if (!authModal) return;
  authModal.classList.add("open");
  authModal.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
  setAuthMode(mode);
}

function closeAuthModal() {
  if (!authModal) return;
  authModal.classList.remove("open");
  authModal.setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
  if (authMsg) {
    authMsg.textContent = "";
    authMsg.classList.add("hidden");
  }
}

function setAuthMode(mode) {
  const isLogin = mode === "login";
  const isRegister = mode === "register";
  authTabLogin?.classList.toggle("active", isLogin);
  authTabRegister?.classList.toggle("active", isRegister);
  authLoginForm?.classList.toggle("hidden", !isLogin);
  authRegisterForm?.classList.toggle("hidden", !isRegister);
  authVerifyInlineForm?.classList.toggle("hidden", !isRegister);
  if (authMsg) {
    authMsg.textContent = "";
    authMsg.classList.add("hidden");
  }
}

function refreshVerifyTabVisibility(me) {
  const verified = Boolean(me?.user?.is_age_verified);
  // Inline verify section lives under Register.
  if (authVerifySubmitBtn) authVerifySubmitBtn.disabled = !me?.user || verified;
}

async function ensureLoggedIn(actionName = "use Watchlist") {
  const me = await getMeCached();
  refreshVerifyTabVisibility(me);
  if (me.user) return true;
  openAuthModal("login");
  if (authMsg) {
    authMsg.textContent = `Please login or register to ${actionName}.`;
    authMsg.classList.remove("hidden");
  }
  return false;
}

const topnav = document.getElementById("topnav");
const watchlistCount = document.getElementById("watchlistCount");
const filtersPanel = document.getElementById("filtersPanel");
const pageTitle = document.getElementById("pageTitle");
const genresBar = document.getElementById("genresBar");
const genreChips = document.getElementById("genreChips");
const heroBanner = document.getElementById("heroBanner");
const heroRandomBtn = document.getElementById("heroRandomBtn");

function copyPaginationExtra(extra) {
  const e = { ...extra };
  if (Array.isArray(extra.genres)) e.genres = [...extra.genres];
  return e;
}

function posterCandidatesFor(movie, tmdbSize = "w500") {
  const candidates = [];
  const id = movie?.movie_id;
  const posterPath = movie?.poster_path;

  // 1) Local cached by movie_id (our downloader script uses this).
  if (id != null) candidates.push(`./assets/posters/${id}.jpg`);

  // 2) Local posters named like TMDB's poster_path basename (common dataset layout).
  // poster_path looks like "/rhIRbceoE9lR4veEXuwCC2wARtG.jpg"
  if (posterPath && typeof posterPath === "string") {
    const base = posterPath.replace(/^\/+/, "");
    if (base) candidates.push(`./assets/posters/${base}`);
  }

  // 3) TMDB CDN
  const tmdb = tmdbPosterUrl(posterPath, tmdbSize);
  if (tmdb) candidates.push(tmdb);

  // 4) Placeholder
  candidates.push(fallbackPosterDataUri(movie?.title || "MovieCrew"));

  return candidates;
}

let posterReorderTimer = null;

function reorderMissingPosterCardsToEnd() {
  if (!movieGrid) return;
  const cards = Array.from(movieGrid.querySelectorAll(".movie-card"));
  if (cards.length === 0) return;

  const loaded = [];
  const loading = [];
  const missing = [];

  for (const c of cards) {
    const state = c.dataset.posterState || "loading";
    if (state === "loaded") loaded.push(c);
    else if (state === "missing") missing.push(c);
    else loading.push(c);
  }

  // Re-append in order (stable within each group)
  const frag = document.createDocumentFragment();
  loaded.forEach((c) => frag.appendChild(c));
  loading.forEach((c) => frag.appendChild(c));
  missing.forEach((c) => frag.appendChild(c));
  movieGrid.appendChild(frag);
}

function scheduleReorderMissingPosterCards() {
  if (posterReorderTimer) return;
  posterReorderTimer = window.setTimeout(() => {
    posterReorderTimer = null;
    reorderMissingPosterCardsToEnd();
  }, 300);
}

function setPosterWithFallback(imgEl, movie, tmdbSize = "w500", opts = {}) {
  if (!imgEl) return;
  const candidates = posterCandidatesFor(movie, tmdbSize);
  let idx = 0;
  const placeholderIdx = Math.max(0, candidates.length - 1);

  const withBust = (url) => {
    // During bulk downloads, posters might appear after the card is rendered.
    // Add a cache-buster so the browser will retry the local file later.
    if (!url || typeof url !== "string") return url;
    if (url.startsWith("./assets/posters/")) {
      return `${url}${url.includes("?") ? "&" : "?"}v=${Date.now()}`;
    }
    return url;
  };

  const setSrc = (i) => {
    const u = candidates[i];
    imgEl.src = withBust(u);
  };

  imgEl.onerror = () => {
    idx += 1;
    if (idx < candidates.length) {
      // If we're about to show the placeholder, mark as "missing poster" immediately.
      if (idx === placeholderIdx) opts?.onMissing?.();
      setSrc(idx);
    }
    else {
      // Tell the caller we exhausted all candidates (meaning we landed on the placeholder).
      opts?.onExhausted?.();
      // If we ended on the placeholder, retry local candidates in the background
      // (so posters can “pop in” as downloads finish).
      idx = candidates.length - 1;
      window.setTimeout(() => {
        idx = 0;
        setSrc(0);
      }, 20000);
    }
  };

  imgEl.onload = () => {
    // If a real poster loads later, clear missing flag.
    const s = String(imgEl.currentSrc || imgEl.src || "");
    if (s.includes("poster-placeholder.svg")) opts?.onMissing?.();
    else opts?.onLoaded?.();
  };

  setSrc(0);
}

function tmdbPosterUrl(posterPath, size = "w500") {
  if (!posterPath) return null;
  // TMDB image CDN does not require an API key.
  return `https://image.tmdb.org/t/p/${size}${posterPath}`;
}

function fallbackPosterDataUri(title) {
  // Use a local placeholder asset instead of generating a “fake” poster.
  // (Still keeps UI stable when a poster is missing.)
  return "./assets/poster-placeholder.svg";
}

function parseRange(rangeString) {
  if (!rangeString) {
    return null;
  }
  const [minRaw, maxRaw] = rangeString.split("-");
  return { min: Number(minRaw), max: Number(maxRaw) };
}

function getSelectedGenres() {
  const checked = genreFilterContainer.querySelectorAll("input[type='checkbox']:checked");
  return Array.from(checked).map((item) => item.value);
}

async function fetchJSON(path) {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API error ${response.status}: ${text}`);
  }
  return { data: await response.json(), headers: response.headers };
}

async function loadGenres() {
  const { data: genres } = await fetchJSON("/genres");
  genreNameToId = {};
  genreIdToName = {};
  genres.forEach((g) => {
    genreNameToId[g.genre_name] = g.genre_id;
    genreIdToName[g.genre_id] = g.genre_name;
  });

  // Build the genre checkbox list from DB so it matches your real data.
  genreFilterContainer.innerHTML = "";
  genres.forEach((g) => {
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = g.genre_name;
    label.appendChild(input);
    label.append(` ${g.genre_name}`);
    genreFilterContainer.appendChild(label);
  });

  // Build genre chips for the Genres page
  if (genreChips) {
    genreChips.innerHTML = "";
    genres.forEach((g) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chip";
      chip.textContent = g.genre_name;
      chip.addEventListener("click", () => {
        window.location.hash = `#/genres/${g.genre_id}`;
      });
      genreChips.appendChild(chip);
    });
  }
}

function buildMoviesQuery(page, extra = {}) {
  const params = new URLSearchParams();

  const q = globalSearch?.value?.trim?.() ?? "";
  if (q && activeRoute === "movies") params.set("q", q);

  if (activeRoute === "movies") {
    const yearFrom = yearFromInput.value.trim();
    const yearTo = yearToInput.value.trim();
    if (yearFrom) params.set("year_from", yearFrom);
    if (yearTo) params.set("year_to", yearTo);

    const budget = parseRange(budgetRange.value);
    if (budget) {
      params.set("budget_min", String(budget.min));
      params.set("budget_max", String(budget.max));
    }

    const revenue = parseRange(revenueRange.value);
    if (revenue) {
      params.set("revenue_min", String(revenue.min));
      params.set("revenue_max", String(revenue.max));
    }

    const actor = actorFilter.value.trim();
    if (actor) params.set("actor", actor);

    const director = directorFilter.value.trim();
    if (director) params.set("director", director);

    const selectedGenreNames = getSelectedGenres();
    selectedGenreNames.forEach((name) => {
      const id = genreNameToId[name];
      if (id) params.append("genres", String(id));
    });
  }

  if (extra.genres) {
    extra.genres.forEach((id) => params.append("genres", String(id)));
  }
  if (extra.actor) params.set("actor", extra.actor);
  if (extra.director) params.set("director", extra.director);

  params.set("page", String(page));
  params.set("page_size", String(pageSize));
  return params.toString();
}

function ensureLoadMoreButton() {
  let row = document.querySelector(".load-more-row");
  if (!row) {
    row = document.createElement("div");
    row.className = "load-more-row";
    row.innerHTML = '<button class="primary-btn" type="button" id="loadMoreBtn">Load more</button>';
    movieGrid.parentElement.appendChild(row);
  }
  const btn = row.querySelector("#loadMoreBtn");
  btn.onclick = () => {
    if (!allowPagination) return;
    loadMovies({ append: true, extra: copyPaginationExtra(paginationExtra) });
  };
  const show = allowPagination && totalCount != null && currentMovies.length < totalCount;
  row.style.display = show ? "flex" : "none";
}

async function loadMovies({ append, extra = {} } = {}) {
  const page = append ? currentPage + 1 : 1;
  if (!append) {
    paginationExtra = copyPaginationExtra(extra);
    allowPagination =
      activeRoute === "home" ||
      activeRoute === "movies" ||
      (activeRoute === "genres" && activeGenreId != null);
  }
  const query = buildMoviesQuery(page, extra);
  const { data, headers } = await fetchJSON(`/movies?${query}`);

  const headerTotal = headers.get("X-Total-Count");
  totalCount = headerTotal ? Number(headerTotal) : null;

  currentPage = page;
  currentMovies = append ? currentMovies.concat(data) : data;

  renderHero(currentMovies);
  renderMovies(currentMovies);
  ensureLoadMoreButton();
}

function openModal() {
  movieModal.classList.add("open");
  movieModal.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
}

function closeModal() {
  movieModal.classList.remove("open");
  movieModal.setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
}

async function openMovieDetails(movie) {
  modalMovie = movie;
  recordHistory(movie.movie_id);
  modalTitle.textContent = movie.title;
  modalSub.textContent = `${movie.release_year ?? "—"} • ${movie.runtime ?? "—"} mins • IMDb ${
    movie.vote_average != null ? Number(movie.vote_average).toFixed(1) : "—"
  }`;
  modalOverview.textContent = movie.overview ?? "—";
  modalBudget.textContent = `Budget: ${movie.budget != null ? toUSD(movie.budget) : "—"}`;
  modalRevenue.textContent = `Revenue: ${movie.revenue != null ? toUSD(movie.revenue) : "—"}`;

  modalGenres.innerHTML = "";
  (movie.genres || []).forEach((g) => {
    const tag = document.createElement("span");
    tag.className = "tag";
    tag.textContent = g;
    modalGenres.appendChild(tag);
  });

  // Prefer local cached poster first, then dataset basename, then TMDB, then placeholder.
  setPosterWithFallback(modalPoster, movie, "w780");
  modalPoster.alt = `${movie.title} poster`;

  modalDirector.textContent = "Director: loading...";
  modalCast.textContent = "Cast: loading...";

  openModal();
  updateWatchlistButton();

  try {
    const { data: detail } = await fetchJSON(`/movies/${movie.movie_id}`);
    modalDirector.textContent = `Director: ${detail.director || "—"}`;
    modalCast.textContent = `Cast: ${(detail.cast || []).join(", ") || "—"}`;
  } catch (e) {
    modalDirector.textContent = "Director: (failed to load)";
    modalCast.textContent = "Cast: (failed to load)";
  }

  loadReviewsForMovie(movie.movie_id);
}

function renderMovies(movies) {
  movieGrid.innerHTML = "";

  if (movies.length === 0) {
    movieGrid.innerHTML = '<div class="empty-state">No movies matched the selected filters.</div>';
    resultsCount.textContent = "Showing 0 results";
    return;
  }

  const fragment = document.createDocumentFragment();

  movies.forEach((movie) => {
    const clone = cardTemplate.content.cloneNode(true);

    const card = clone.querySelector(".movie-card");
    card.tabIndex = 0;
    // Default state until image finishes loading
    card.dataset.posterState = "loading";

    const posterImg = clone.querySelector(".movie-poster-img");
    // Prefer local cached poster first, then dataset basename, then TMDB, then placeholder.
  setPosterWithFallback(posterImg, movie, "w500", {
    onMissing: () => {
        card.dataset.posterState = "missing";
      scheduleReorderMissingPosterCards();
    },
    onLoaded: () => {
        if (card.dataset.posterState !== "loaded") {
          card.dataset.posterState = "loaded";
          scheduleReorderMissingPosterCards();
        }
    },
  });
    posterImg.alt = `${movie.title} poster`;

    clone.querySelector(".movie-title").textContent = movie.title;
    clone.querySelector(".movie-rating").textContent =
      movie.vote_average != null ? `IMDb ${Number(movie.vote_average).toFixed(1)}` : "IMDb —";

    // Watchlist page: show quick remove button on each card
    if (activeRoute === "watchlist") {
      const titleRow = clone.querySelector(".title-row");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "watchlist-remove-btn";
      btn.textContent = "Remove";
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        toggleWatchlist(movie.movie_id);
        loadWatchlistMovies();
      });
      titleRow.appendChild(btn);
    }
    clone.querySelector(".movie-meta").textContent = `${movie.release_year ?? "—"} • ${movie.runtime ?? "—"} mins`;
    clone.querySelector(".movie-overview").textContent = movie.overview ?? "";
    clone.querySelector(".movie-cast").textContent = "Cast: (expand to load)";
    clone.querySelector(".movie-director").textContent = "Director: (expand to load)";
    clone.querySelector(".movie-budget").textContent = `Budget: ${movie.budget != null ? toUSD(movie.budget) : "—"}`;
    clone.querySelector(".movie-revenue").textContent = `Revenue: ${movie.revenue != null ? toUSD(movie.revenue) : "—"}`;

    const tagRow = clone.querySelector(".tag-row");
    (movie.genres || []).forEach((genre) => {
      const tag = document.createElement("span");
      tag.className = "tag";
      tag.textContent = genre;
      tagRow.appendChild(tag);
    });

    const openFromCard = (event) => {
      // Don't open modal when user is interacting with <details>
      if (event.target?.closest?.("details")) return;
      openMovieDetails(movie);
    };

    card.addEventListener("click", openFromCard);
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openMovieDetails(movie);
      }
    });

    fragment.appendChild(clone);
  });

  movieGrid.appendChild(fragment);
  resultsCount.textContent =
    totalCount != null ? `Showing ${movies.length} of ${totalCount} movies` : `Showing ${movies.length} movies`;
}

function renderHero(movies) {
  const featuredMovie = movies.length > 0 ? movies[0] : null;
  featuredHeroMovie = featuredMovie;

  // Home-like branded hero across main pages (no featured movie title/meta injected).
  // (Home, Movies, Genres, History)
  if (activeRoute === "home" || activeRoute === "movies" || activeRoute === "genres" || activeRoute === "history") {
    if (heroTitle) heroTitle.textContent = "";
    if (heroYear) heroYear.textContent = "";
    if (heroRuntime) heroRuntime.textContent = "";
    if (heroGenre) heroGenre.textContent = "";
    if (heroBanner) {
      heroBanner.classList.remove("hero-clickable");
      heroBanner.tabIndex = -1;
      heroBanner.setAttribute("aria-label", "MovieCrew");
      heroBanner.style.removeProperty("--hero-poster");
    }
    return;
  }

  if (!featuredMovie) {
    heroTitle.textContent = "No featured movie";
    heroDescription.textContent = "Try removing some filters.";
    heroYear.textContent = "—";
    heroRuntime.textContent = "—";
    heroGenre.textContent = "—";
    if (heroBanner) {
      heroBanner.classList.remove("hero-clickable");
      heroBanner.tabIndex = -1;
      heroBanner.setAttribute("aria-label", "No featured movie");
      heroBanner.style.removeProperty("--hero-poster");
    }
    return;
  }
  if (heroBanner) {
    heroBanner.classList.add("hero-clickable");
    heroBanner.tabIndex = 0;
    heroBanner.setAttribute("aria-label", "Open featured movie");
  }
  // Keep hero as a branded banner across the site (home-style).
  // We still keep the banner clickable to open the featured movie, but we don't overwrite the copy.
  if (heroBanner) {
    heroBanner.style.removeProperty("--hero-poster");
  }
}

function pickRandomFeatured() {
  if (!Array.isArray(currentMovies) || currentMovies.length === 0) return;
  const pick = currentMovies[Math.floor(Math.random() * currentMovies.length)];
  if (!pick) return;
  renderHero([pick, ...currentMovies.filter((m) => m?.movie_id !== pick.movie_id)]);
}

heroRandomBtn?.addEventListener("click", (event) => {
  // Avoid triggering the hero click (which opens modal)
  event.preventDefault();
  event.stopPropagation();
  pickRandomFeatured();
});

function applyFilters() {
  currentPage = 1;
  totalCount = null;
  window.location.hash = "#/movies";
  loadMovies({ append: false, extra: {} });
}

function clearFilters() {
  globalSearch.value = "";
  yearFromInput.value = "";
  yearToInput.value = "";
  budgetRange.value = "";
  revenueRange.value = "";
  actorFilter.value = "";
  directorFilter.value = "";
  genreFilterContainer.querySelectorAll("input[type='checkbox']").forEach((item) => {
    item.checked = false;
  });
  currentPage = 1;
  totalCount = null;
  window.location.hash = "#/movies";
  loadMovies({ append: false, extra: {} });
}

applyFiltersBtn.addEventListener("click", applyFilters);
clearFiltersBtn.addEventListener("click", clearFilters);
globalSearch.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    applyFilters();
  }
});

async function init() {
  try {
    await loadGenres();
    setupRouting();
    await handleRouteChange();
  } catch (e) {
    movieGrid.innerHTML = '<div class="empty-state">Backend not reachable. Start the API at http://127.0.0.1:8000</div>';
    resultsCount.textContent = "Showing 0 results";
  }
}

init();

modalCloseBtn?.addEventListener("click", closeModal);
movieModal?.addEventListener("click", (event) => {
  if (event.target === movieModal) closeModal();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && movieModal?.classList.contains("open")) {
    closeModal();
  }
});

function getWatchlist() {
  try {
    // Watchlist is per-user. If not logged in, it's disabled.
    const rawUser = localStorage.getItem("moviecrew_last_user_id") || lastKnownUserId;
    if (!rawUser) return [];
    const raw = localStorage.getItem(`moviecrew_watchlist_${rawUser}`);
    const ids = raw ? JSON.parse(raw) : [];
    return Array.isArray(ids) ? ids : [];
  } catch {
    return [];
  }
}

function getHistory() {
  try {
    const raw = localStorage.getItem("moviescope_history");
    const ids = raw ? JSON.parse(raw) : [];
    return Array.isArray(ids) ? ids : [];
  } catch {
    return [];
  }
}

function setHistory(ids) {
  localStorage.setItem("moviescope_history", JSON.stringify(ids));
}

function recordHistory(movieId) {
  const ids = getHistory().filter((x) => x !== movieId);
  ids.unshift(movieId);
  setHistory(ids.slice(0, 200));
}

function clearHistory() {
  setHistory([]);
}

function setWatchlist(ids) {
  const rawUser = localStorage.getItem("moviecrew_last_user_id") || lastKnownUserId;
  if (!rawUser) return;
  localStorage.setItem(`moviecrew_watchlist_${rawUser}`, JSON.stringify(ids));
  updateWatchlistCount();
}

function isInWatchlist(movieId) {
  return getWatchlist().includes(movieId);
}

function toggleWatchlist(movieId) {
  const ids = getWatchlist();
  const idx = ids.indexOf(movieId);
  if (idx >= 0) ids.splice(idx, 1);
  else ids.unshift(movieId);
  setWatchlist(ids);
}

function updateWatchlistCount() {
  const count = getWatchlist().length;
  if (watchlistCount) watchlistCount.textContent = String(count);
}

function updateWatchlistButton() {
  if (!watchlistToggleBtn || !modalMovie) return;
  const inList = isInWatchlist(modalMovie.movie_id);
  watchlistToggleBtn.textContent = inList ? "Remove from Watchlist" : "Add to Watchlist";
}

watchlistToggleBtn?.addEventListener("click", () => {
  if (!modalMovie) return;
  ensureLoggedIn("add movies to your Watchlist").then((ok) => {
    if (!ok) return;
    toggleWatchlist(modalMovie.movie_id);
    updateWatchlistButton();
  });
});

function setActiveNav(route) {
  document.querySelectorAll("[data-route]").forEach((el) => {
    el.classList.toggle("active", el.dataset.route === route);
  });
}

function setupRouting() {
  updateWatchlistCount();
  window.addEventListener("hashchange", handleRouteChange);
  if (!window.location.hash) window.location.hash = "#/home";
}

async function handleRouteChange() {
  const hash = window.location.hash || "#/home";
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  const route = parts[0] || "home";
  activeRoute = route;
  setActiveNav(route);
  document.body.dataset.route = route;

  // Hero banner: keep a consistent branded look on main pages.
  const branded = route === "home" || route === "movies" || route === "genres" || route === "history";
  heroBanner?.classList.toggle("hero-branded", branded);

  // Show/hide UI blocks
  const showFilters = route === "movies";
  filtersPanel?.classList.toggle("hidden", !showFilters);
  document.body.dataset.showFilters = showFilters ? "1" : "0";
  genresBar?.classList.toggle("hidden", route !== "genres");
  clearHistoryBtn?.classList.toggle("hidden", route !== "history");

  // Reset paging on route changes
  currentPage = 1;
  totalCount = null;

  if (route === "home") {
    pageTitle.textContent = "Top Rated";
    if (heroEyebrow) heroEyebrow.textContent = "Welcome to";
    if (heroDescription) {
      heroDescription.textContent =
        "Discover top-rated films, explore genres, and build your watchlist — with fast search and filters.";
    }
    await loadMovies({ append: false, extra: {} });
    return;
  }

  if (route === "movies") {
    pageTitle.textContent = "Movies";
    if (heroEyebrow) heroEyebrow.textContent = "Welcome to";
    if (heroDescription) {
      heroDescription.textContent =
        "Discover top-rated films, explore genres, and build your watchlist — with fast search and filters.";
    }
    await loadMovies({ append: false, extra: {} });
    return;
  }

  if (route === "genres") {
    const genreId = parts[1] ? Number(parts[1]) : null;
    activeGenreId = Number.isFinite(genreId) ? genreId : null;
    activeGenreName = activeGenreId ? genreIdToName[activeGenreId] : null;
    pageTitle.textContent = activeGenreName ? `Genre: ${activeGenreName}` : "Genres";
    if (heroEyebrow) heroEyebrow.textContent = "Welcome to";
    if (heroDescription) {
      heroDescription.textContent =
        "Browse genres and find movies faster — the same experience, organized your way.";
    }

    // Chip active state
    genreChips?.querySelectorAll(".chip").forEach((chip) => {
      const name = chip.textContent;
      const id = name ? genreNameToId[name] : null;
      chip.classList.toggle("active", id && activeGenreId && id === activeGenreId);
    });

    if (activeGenreId) {
      await loadMovies({ append: false, extra: { genres: [activeGenreId] } });
    } else {
      allowPagination = false;
      paginationExtra = {};
      document.querySelector(".load-more-row")?.style.setProperty("display", "none");
      movieGrid.innerHTML = '<div class="empty-state">Pick a genre above to view movies.</div>';
      resultsCount.textContent = "Showing 0 results";
      renderHero([]);
    }
    return;
  }

  if (route === "watchlist") {
    pageTitle.textContent = "My Watchlist";
    const ok = await ensureLoggedIn("view your Watchlist");
    if (!ok) {
      movieGrid.innerHTML = '<div class="empty-state">Login to view your Watchlist.</div>';
      resultsCount.textContent = "Showing 0 results";
      renderHero([]);
      return;
    }
    await loadWatchlistMovies();
    return;
  }

  if (route === "history") {
    pageTitle.textContent = "Recently Reviewed";
    if (heroEyebrow) heroEyebrow.textContent = "Welcome to";
    if (heroDescription) {
      heroDescription.textContent = "Your recently reviewed movies — pick up where you left off.";
    }
    await loadHistoryMovies();
    return;
  }

  // Fallback
  window.location.hash = "#/home";
}

// People section removed

async function loadWatchlistMovies() {
  allowPagination = false;
  paginationExtra = {};
  document.querySelector(".load-more-row")?.style.setProperty("display", "none");

  const ids = getWatchlist();
  if (ids.length === 0) {
    movieGrid.innerHTML = '<div class="empty-state">Your watchlist is empty. Open a movie and click “Add to Watchlist”.</div>';
    resultsCount.textContent = "Showing 0 results";
    renderHero([]);
    return;
  }

  // Fetch details for each movie so we also get cast/director when needed.
  const details = await Promise.all(
    ids.slice(0, 200).map(async (id) => {
      try {
        const { data } = await fetchJSON(`/movies/${id}`);
        return {
          movie_id: data.movie_id,
          title: data.title,
          overview: data.overview,
          release_year: data.release_year,
          runtime: data.runtime,
          budget: data.budget,
          revenue: data.revenue,
          vote_average: data.vote_average,
          vote_count: data.vote_count,
          genres: (data.genres || []).map((g) => g.genre_name),
          poster_path: data.poster_path,
        };
      } catch {
        return null;
      }
    })
  );

  currentMovies = details.filter(Boolean);
  totalCount = currentMovies.length;
  renderHero(currentMovies);
  renderMovies(currentMovies);
  ensureLoadMoreButton();
}

// Auth modal events (popup)
authCloseBtn?.addEventListener("click", closeAuthModal);
authModal?.addEventListener("click", (event) => {
  if (event.target === authModal) closeAuthModal();
});
authTabLogin?.addEventListener("click", () => setAuthMode("login"));
authTabRegister?.addEventListener("click", () => setAuthMode("register"));

async function authApi(path, payload) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = body?.detail;
    const msg = Array.isArray(detail) ? detail.join(" ") : detail || "Request failed";
    throw new Error(msg);
  }
  return body;
}

authLoginForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const data = Object.fromEntries(new FormData(authLoginForm).entries());
    const user = await authApi("/login", data);
    localStorage.setItem("moviecrew_last_user_id", String(user.id));
    cachedMe = { user };
    cachedMeAt = Date.now();
    updateWatchlistCount();
    refreshVerifyTabVisibility(cachedMe);
    closeAuthModal();
    window.location.reload();
  } catch (err) {
    if (authMsg) {
      authMsg.textContent = err.message;
      authMsg.classList.remove("hidden");
    }
  }
});

authRegisterForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const data = Object.fromEntries(new FormData(authRegisterForm).entries());
    const user = await authApi("/register", data);
    localStorage.setItem("moviecrew_last_user_id", String(user.id));
    cachedMe = { user };
    cachedMeAt = Date.now();
    updateWatchlistCount();
    refreshVerifyTabVisibility(cachedMe);
    if (authMsg) {
      authMsg.textContent = "Account created. Now verify your ID below to access reviews (age restriction).";
      authMsg.classList.remove("hidden");
    }
  } catch (err) {
    if (authMsg) {
      authMsg.textContent = err.message;
      authMsg.classList.remove("hidden");
    }
  }
});

authVerifyInlineForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const ok = await ensureLoggedIn("verify your ID");
  if (!ok) return;

  if (authMsg) {
    authMsg.textContent = "Submitting verification…";
    authMsg.classList.remove("hidden");
  }

  try {
    const fd = new FormData(authVerifyInlineForm);
    const res = await fetch(`${API_BASE_URL}/verify-id`, {
      method: "POST",
      credentials: "include",
      body: fd,
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = body?.detail;
      const msg = Array.isArray(detail) ? detail.join(" ") : detail || "Verification failed";
      throw new Error(msg);
    }

    // Refresh /me cache
    cachedMe = await getMeCached();
    cachedMeAt = Date.now();
    refreshVerifyTabVisibility(cachedMe);

    if (authMsg) {
      authMsg.textContent = `Status: ${body.verification_status}. Verified: ${body.is_age_verified ? "Yes" : "No"}`;
      authMsg.classList.remove("hidden");
    }
    if (body.is_age_verified) {
      // Keep UX clear: show success for a moment, then close the modal.
      if (authMsg) {
        authMsg.textContent = `✓ ID verified. You can now submit reviews.`;
        authMsg.classList.remove("hidden");
      }
      refreshVerifyTabVisibility(cachedMe);
      setTimeout(() => {
        closeAuthModal();
        // Refresh navbar and drawer badge
        window.location.reload();
      }, 900);
    }
  } catch (err) {
    if (authMsg) {
      authMsg.textContent = err.message;
      authMsg.classList.remove("hidden");
    }
  }
});

function renderStars(n) {
  const full = "★".repeat(Math.max(0, Math.min(5, n)));
  const empty = "☆".repeat(Math.max(0, 5 - Math.min(5, n)));
  return full + empty;
}

async function loadReviewsForMovie(movieId) {
  if (!reviewsList || !reviewsCount) return;
  reviewsList.innerHTML = '<div class="empty-state">Loading reviews…</div>';
  try {
    const { data } = await fetchJSON(`/movies/${movieId}/reviews`);
    const reviews = Array.isArray(data) ? data : [];
    reviewsCount.textContent = `Showing ${reviews.length}`;
    if (reviews.length === 0) {
      reviewsList.innerHTML = '<div class="empty-state">No reviews yet. Be the first to review!</div>';
      return;
    }
    reviewsList.innerHTML = "";
    const frag = document.createDocumentFragment();
    reviews.forEach((r) => {
      const row = document.createElement("div");
      row.className = "review-item";
      row.innerHTML = `
        <div class="review-top">
          <div class="review-user">${r.username}</div>
          <div class="review-rating" aria-label="Rating">${renderStars(Number(r.rating) || 0)}</div>
        </div>
        ${r.review_text ? `<div class="review-text"></div>` : ""}
      `;
      if (r.review_text) {
        row.querySelector(".review-text").textContent = r.review_text;
      }
      frag.appendChild(row);
    });
    reviewsList.appendChild(frag);
  } catch (e) {
    reviewsList.innerHTML = '<div class="empty-state">Failed to load reviews.</div>';
  }
}

reviewForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!modalMovie) return;

  const ok = await ensureLoggedIn("submit a review");
  if (!ok) return;

  const rating = Number(new FormData(reviewForm).get("rating") || 0);
  const text = (reviewText?.value || "").trim();

  if (!rating || rating < 1 || rating > 5) {
    if (reviewMsg) reviewMsg.textContent = "Please select a star rating (1–5).";
    return;
  }

  if (reviewMsg) reviewMsg.textContent = "Submitting…";
  try {
    await fetch(`${API_BASE_URL}/movies/${modalMovie.movie_id}/reviews`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rating, review_text: text || null }),
    }).then(async (res) => {
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = body?.detail;
        const msg = Array.isArray(detail) ? detail.join(" ") : detail || "Failed to submit review";
        const err = new Error(msg);
        err.status = res.status;
        throw err;
      }
      return body;
    });

    if (reviewMsg) reviewMsg.textContent = "Saved.";
    await loadReviewsForMovie(modalMovie.movie_id);
  } catch (err) {
    if (err?.status === 403) {
      openAuthModal("register");
      const me = await getMeCached();
      refreshVerifyTabVisibility(me);
      if (authMsg) {
        authMsg.textContent = "Age verification required to submit reviews. Please verify your ID.";
        authMsg.classList.remove("hidden");
      }
      if (reviewMsg) reviewMsg.textContent = "Age verification required.";
      return;
    }
    if (reviewMsg) reviewMsg.textContent = err.message;
  }
});

clearHistoryBtn?.addEventListener("click", async () => {
  clearHistory();
  if (activeRoute === "history") {
    await loadHistoryMovies();
  }
});

async function loadHistoryMovies() {
  allowPagination = false;
  paginationExtra = {};
  document.querySelector(".load-more-row")?.style.setProperty("display", "none");

  const ids = getHistory();
  if (ids.length === 0) {
    movieGrid.innerHTML =
      '<div class="empty-state">No reviews yet. Submit a review to start building your recently reviewed list.</div>';
    resultsCount.textContent = "Showing 0 results";
    renderHero([]);
    return;
  }

  const details = await Promise.all(
    ids.slice(0, 200).map(async (id) => {
      try {
        const { data } = await fetchJSON(`/movies/${id}`);
        return {
          movie_id: data.movie_id,
          title: data.title,
          overview: data.overview,
          release_year: data.release_year,
          runtime: data.runtime,
          budget: data.budget,
          revenue: data.revenue,
          vote_average: data.vote_average,
          vote_count: data.vote_count,
          genres: (data.genres || []).map((g) => g.genre_name),
          poster_path: data.poster_path,
        };
      } catch {
        return null;
      }
    })
  );

  currentMovies = details.filter(Boolean);
  totalCount = currentMovies.length;
  renderHero(currentMovies);
  renderMovies(currentMovies);
  ensureLoadMoreButton();
}

heroBanner?.addEventListener("click", () => {
  if (featuredHeroMovie) openMovieDetails(featuredHeroMovie);
});

heroBanner?.addEventListener("keydown", (event) => {
  if ((event.key === "Enter" || event.key === " ") && featuredHeroMovie) {
    event.preventDefault();
    openMovieDetails(featuredHeroMovie);
  }
});
