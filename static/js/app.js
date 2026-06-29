const form = document.getElementById("scrapeForm");
const input = document.getElementById("urlInput");
const button = document.getElementById("submitBtn");
const homeButton = document.getElementById("homeBtn");
const errorBox = document.getElementById("error");
const playerShell = document.getElementById("playerShell");
const episodePanel = document.getElementById("episodePanel");
const catalog = document.getElementById("catalog");
const summary = document.getElementById("summary");
const results = document.getElementById("results");
const defaultUrl = window.APP_DEFAULT_URL;

const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  "\"": "&quot;",
  "'": "&#039;",
}[char]));

const link = (url) => (
  url
    ? `<a href="${esc(url)}" target="_blank" rel="noreferrer">${esc(url)}</a>`
    : '<span class="empty">Kosong</span>'
);

function targetUrl(value) {
  const trimmed = value.trim();
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  const query = encodeURIComponent(trimmed);
  return `https://tv46.juragan.film/?s=${query}&post_type%5B%5D=post&post_type%5B%5D=tv`;
}

function renderRows(items, fields) {
  if (!items.length) return '<div class="empty">Tidak ditemukan.</div>';
  return items.map((item) => `
    <div class="row">
      ${fields.map((field) => {
        const value = item[field.key] ?? "";
        const rendered = field.type === "url" ? link(value) : esc(value);
        return `<div><div class="label">${esc(field.label)}</div><div>${rendered || '<span class="empty">Kosong</span>'}</div></div>`;
      }).join("")}
    </div>
  `).join("");
}

function panel(title, body) {
  return `<article class="panel"><h2>${esc(title)}</h2><div class="content">${body}</div></article>`;
}

function renderPlayer(data) {
  const iframe = data.iframes[0];
  if (!iframe || !iframe.src) {
    playerShell.style.display = "none";
    playerShell.innerHTML = "";
    return;
  }

  const allow = iframe.allow || "autoplay; fullscreen; picture-in-picture";
  const title = iframe.title || data.title || "Iframe video";
  playerShell.style.display = "block";
  playerShell.innerHTML = `
    <div class="player-stage" id="playerStage">
      <iframe
        id="videoFrame"
        src="${esc(iframe.src)}"
        title="${esc(title)}"
        allow="${esc(allow)}"
        allowfullscreen
        referrerpolicy="no-referrer-when-downgrade"></iframe>
    </div>
    <div class="player-actions">
      <button type="button" class="player-action" id="fullscreenBtn">▣ Mode Layar Lebar</button>
      <button type="button" class="player-action" id="copyIframeBtn">🔗 Salin Link</button>
      <button type="button" class="player-action" id="refreshIframeBtn">↻ Segarkan Iframe</button>
      <a class="player-action primary" href="${esc(iframe.src)}" target="_blank" rel="noreferrer">⬇ Buka Iframe</a>
      <div class="player-meta">◉ ${Number(data.counts.links || 0).toLocaleString("id-ID")} Link</div>
    </div>
  `;

  document.getElementById("fullscreenBtn").addEventListener("click", () => {
    const stage = document.getElementById("playerStage");
    if (stage.requestFullscreen) stage.requestFullscreen();
  });

  document.getElementById("copyIframeBtn").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(iframe.src);
    } catch (error) {
      const temp = document.createElement("input");
      temp.value = iframe.src;
      document.body.appendChild(temp);
      temp.select();
      document.execCommand("copy");
      temp.remove();
    }
  });

  document.getElementById("refreshIframeBtn").addEventListener("click", () => {
    const frame = document.getElementById("videoFrame");
    frame.src = iframe.src;
  });
}

function renderEpisodes(data) {
  const episodes = data.episodes || [];
  if (!episodes.length) {
    episodePanel.style.display = "none";
    episodePanel.innerHTML = "";
    return;
  }

  episodePanel.style.display = "block";
  episodePanel.innerHTML = `
    <h2>Pilih Episode Tayangan</h2>
    <div class="episode-grid">
      ${episodes.map((episode) => `
        <button
          type="button"
          class="episode-button${episode.active ? " active" : ""}"
          data-episode-url="${esc(episode.url)}"
          title="Episode ${esc(episode.number)}">
          ${esc(episode.number)}
        </button>
      `).join("")}
    </div>
  `;

  episodePanel.querySelectorAll(".episode-button").forEach((episodeButton) => {
    episodeButton.addEventListener("click", () => {
      input.value = episodeButton.dataset.episodeUrl;
      runScrape();
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  });
}

function renderCatalog(data) {
  const cards = data.cards || [];
  if (!cards.length || data.iframes.length) {
    catalog.style.display = "none";
    catalog.innerHTML = "";
    return;
  }

  catalog.style.display = "block";
  catalog.innerHTML = `
    <div class="section-title">
      <h2>Daftar Tayangan</h2>
      <span>${Number(cards.length).toLocaleString("id-ID")} item</span>
    </div>
    <div class="card-grid">
      ${cards.map((card) => `
        <a class="movie-card" href="${esc(card.url)}" data-card-url="${esc(card.url)}">
          <div class="poster">
            ${card.image ? `<img src="${esc(card.image)}" alt="${esc(card.alt || card.title)}" loading="lazy">` : '<div class="player-empty">Tanpa gambar</div>'}
            <div class="badge-row">
              ${card.quality ? `<span class="badge">${esc(card.quality)}</span>` : "<span></span>"}
              ${card.episode ? `<span class="badge">${esc(card.episode)}</span>` : ""}
            </div>
          </div>
          <div class="movie-info">
            <div class="movie-title">${esc(card.title)}</div>
            <div class="movie-url">${esc(card.url)}</div>
          </div>
        </a>
      `).join("")}
    </div>
  `;

  catalog.querySelectorAll(".movie-card").forEach((card) => {
    card.addEventListener("click", (event) => {
      event.preventDefault();
      input.value = card.dataset.cardUrl;
      runScrape();
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  });
}

function render(data) {
  const counts = data.counts;
  const isCatalog = (data.cards || []).length > 0 && data.iframes.length === 0;
  renderPlayer(data);
  renderEpisodes(data);
  renderCatalog(data);

  summary.innerHTML = [
    ["Card", counts.cards || 0],
    ["Iframe", counts.iframes],
    ["Link", counts.links],
    ["Episode", counts.episodes || 0],
  ].map(([label, count]) => `<div class="metric"><strong>${count}</strong><span>${label}</span></div>`).join("");

  const overview = `
    <div class="row"><div class="label">Status</div><div>${esc(data.status)} · ${esc(data.contentType || "unknown")}</div></div>
    <div class="row"><div class="label">Title</div><div>${esc(data.title || "-")}</div></div>
    <div class="row"><div class="label">Description</div><div>${esc(data.description || "-")}</div></div>
    <div class="row"><div class="label">Canonical</div><div>${link(data.canonical)}</div></div>
    <div class="row"><div class="label">Ukuran HTML</div><div>${Number(data.htmlBytes).toLocaleString("id-ID")} bytes</div></div>
  `;

  if (isCatalog) {
    results.innerHTML = "";
    return;
  }

  results.innerHTML = [
    panel("Ringkasan", overview),
    panel("Iframe", renderRows(data.iframes, [
      { key: "src", label: "src", type: "url" },
      { key: "title", label: "title" },
      { key: "allow", label: "allow" },
    ])),
    panel("Video", renderRows(data.videos, [
      { key: "src", label: "src", type: "url" },
      { key: "poster", label: "poster", type: "url" },
      { key: "controls", label: "controls" },
    ])),
    panel("Source", renderRows(data.sources, [
      { key: "src", label: "src", type: "url" },
      { key: "type", label: "type" },
      { key: "media", label: "media" },
    ])),
    panel("Gambar", renderRows(data.images, [
      { key: "src", label: "src", type: "url" },
      { key: "alt", label: "alt" },
    ])),
    panel("Link", renderRows(data.links, [
      { key: "text", label: "text" },
      { key: "href", label: "href", type: "url" },
    ])),
    panel("Heading", renderRows(data.headings, [
      { key: "level", label: "level" },
      { key: "text", label: "text" },
    ])),
    panel("Meta", `<pre>${esc(JSON.stringify(data.meta, null, 2))}</pre>`),
  ].join("");
}

function resetViews() {
  playerShell.style.display = "none";
  playerShell.innerHTML = "";
  episodePanel.style.display = "none";
  episodePanel.innerHTML = "";
  catalog.style.display = "none";
  catalog.innerHTML = "";
  summary.innerHTML = "";
  results.innerHTML = "";
}

async function runScrape() {
  errorBox.innerHTML = "";
  button.disabled = true;
  button.textContent = "Memproses...";
  const url = targetUrl(input.value);
  input.value = url;

  try {
    const response = await fetch(`/api/scrape?url=${encodeURIComponent(url)}`);
    const payload = await response.json();
    if (!payload.ok) throw new Error(payload.error || "Scrape gagal.");
    render(payload.data);
  } catch (error) {
    resetViews();
    errorBox.innerHTML = `<div class="error">${esc(error.message)}</div>`;
  } finally {
    button.disabled = false;
    button.textContent = "Buka";
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  runScrape();
});

homeButton.addEventListener("click", () => {
  input.value = defaultUrl;
  runScrape();
  window.scrollTo({ top: 0, behavior: "smooth" });
});

runScrape();
