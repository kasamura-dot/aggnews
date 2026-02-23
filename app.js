const API_CANDIDATES = window.location.protocol === "file:"
  ? ["http://127.0.0.1:8000/api/headlines", "./headlines.json"]
  : ["api/headlines", "./headlines.json", "http://127.0.0.1:8000/api/headlines"];

const statusEl = document.getElementById("status");
const updatedAtEl = document.getElementById("updatedAt");
const newsGridEl = document.getElementById("newsGrid");
const refreshBtn = document.getElementById("refreshBtn");
const limitSelect = document.getElementById("limitSelect");
const cardTemplate = document.getElementById("sourceCardTemplate");

function formatDate(date) {
  try {
    return new Intl.DateTimeFormat("ja-JP", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    }).format(date);
  } catch {
    return date.toLocaleString("ja-JP");
  }
}

function buildSourceCard(source) {
  const fragment = cardTemplate.content.cloneNode(true);
  const nameEl = fragment.querySelector(".source-name");
  const linkEl = fragment.querySelector(".source-link");
  const listEl = fragment.querySelector(".headline-list");

  nameEl.textContent = source.name;
  linkEl.href = source.site_url;

  const meta = document.createElement("p");
  meta.className = "source-meta";
  if (source.terms_url) {
    const terms = document.createElement("a");
    terms.href = source.terms_url;
    terms.target = "_blank";
    terms.rel = "noopener noreferrer";
    terms.textContent = "利用規約";
    meta.append("出典: 公式RSS | ");
    meta.appendChild(terms);
  } else {
    meta.textContent = "出典: 公式RSS";
  }

  listEl.parentElement.insertBefore(meta, listEl);

  if (source.error) {
    const li = document.createElement("li");
    li.className = "error";
    li.textContent = `取得エラー: ${source.error}`;
    listEl.appendChild(li);
    return fragment;
  }

  const headlines = Array.isArray(source.headlines) ? source.headlines : [];
  if (headlines.length === 0) {
    const li = document.createElement("li");
    li.className = "error";
    li.textContent = "見出しがありません。";
    listEl.appendChild(li);
    return fragment;
  }

  for (const item of headlines) {
    const li = document.createElement("li");
    li.className = "headline-item";

    if (item.image_url) {
      const img = document.createElement("img");
      img.className = "headline-thumb";
      img.src = item.image_url;
      img.alt = "";
      img.loading = "lazy";
      img.referrerPolicy = "no-referrer";
      img.addEventListener("error", () => {
        img.style.display = "none";
      });
      li.appendChild(img);
    }

    const body = document.createElement("div");
    body.className = "headline-body";

    const titleLink = document.createElement("a");
    titleLink.href = item.link || source.site_url;
    titleLink.target = "_blank";
    titleLink.rel = "noopener noreferrer";
    titleLink.textContent = item.translated_title || item.title || "(no title)";
    body.appendChild(titleLink);

    if (item.translated_title && item.title) {
      const originalEl = document.createElement("p");
      originalEl.className = "original-title";
      originalEl.textContent = item.title;
      body.appendChild(originalEl);
    }

    if (item.published_at) {
      const timeEl = document.createElement("time");
      const date = new Date(item.published_at);
      if (!Number.isNaN(date.getTime())) {
        timeEl.dateTime = date.toISOString();
        timeEl.textContent = formatDate(date);
        body.appendChild(timeEl);
      }
    }

    li.appendChild(body);
    listEl.appendChild(li);
  }

  return fragment;
}

async function fetchHeadlines(limit) {
  const query = `?limit=${encodeURIComponent(String(limit))}`;
  const errors = [];

  for (const base of API_CANDIDATES) {
    const endpoint = base.endsWith(".json") ? base : `${base}${query}`;
    try {
      const response = await fetch(endpoint, { cache: "no-store" });
      if (!response.ok) {
        errors.push(`${endpoint} -> HTTP ${response.status}`);
        continue;
      }

      const payload = await response.json();
      if (base.endsWith(".json")) {
        payload.sources = (payload.sources || []).map((source) => ({
          ...source,
          headlines: (source.headlines || []).slice(0, limit)
        }));
      }

      return { payload, endpoint };
    } catch (error) {
      errors.push(`${endpoint} -> ${error.message || "fetch failed"}`);
    }
  }

  throw new Error(errors.join(" | "));
}

function buildConnectionHint(error) {
  const reason = String(error?.message || "");
  if (/headlines\.json.+HTTP 404/.test(reason)) {
    return "GitHub Pages用の `headlines.json` が未生成です。Actions の `Update headlines.json` を実行してください。";
  }
  if (/HTTP 404/.test(reason)) {
    return "表示中のホストにAPIがありません。`python news_server.py` を起動して `http://127.0.0.1:8000` で開くか、`headlines.json` を用意してください。";
  }
  if (/failed to fetch|networkerror|load failed/i.test(reason)) {
    return "`python news_server.py` が起動中か確認し、`headlines.json` の存在も確認してください。";
  }
  return "サーバー起動状態とネットワークを確認してください。";
}

async function renderNews() {
  const limit = Number.parseInt(limitSelect.value, 10) || 8;

  statusEl.textContent = "見出しを取得中...";
  updatedAtEl.textContent = "";
  newsGridEl.textContent = "";
  refreshBtn.disabled = true;

  try {
    const { payload, endpoint } = await fetchHeadlines(limit);
    const sources = Array.isArray(payload.sources) ? payload.sources : [];

    let okCount = 0;
    for (const source of sources) {
      if (!source.error) {
        okCount += 1;
      }
      newsGridEl.appendChild(buildSourceCard(source));
    }

    const fetchedAt = payload.fetched_at ? new Date(payload.fetched_at) : new Date();
    statusEl.textContent = `${okCount}/${sources.length} サイトの見出しを表示中`;
    updatedAtEl.textContent = `最終更新: ${formatDate(fetchedAt)} | API: ${endpoint}`;
  } catch (error) {
    statusEl.textContent = `エラー: ${error.message}`;
    updatedAtEl.textContent = buildConnectionHint(error);
  } finally {
    refreshBtn.disabled = false;
  }
}

refreshBtn.addEventListener("click", renderNews);
limitSelect.addEventListener("change", renderNews);

renderNews();
setInterval(renderNews, 5 * 60 * 1000);

