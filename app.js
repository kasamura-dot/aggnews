const API_CANDIDATES = window.location.protocol === "file:"
  ? ["http://127.0.0.1:8000/api/headlines", "./headlines.json"]
  : ["api/headlines", "./headlines.json", "http://127.0.0.1:8000/api/headlines"];

const FIXED_SITE_COUNT = 11;
const FIXED_HEADLINES_PER_SITE = 1;

const statusEl = document.getElementById("status");
const updatedAtEl = document.getElementById("updatedAt");
const newsGridEl = document.getElementById("newsGrid");
const refreshBtn = document.getElementById("refreshBtn");
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

  if (source.error) {
    const li = document.createElement("li");
    li.className = "error";
    li.textContent = "取得エラー";
    listEl.appendChild(li);
    return fragment;
  }

  const headlines = Array.isArray(source.headlines) ? source.headlines : [];
  const shown = headlines.slice(0, FIXED_HEADLINES_PER_SITE);

  if (shown.length === 0) {
    const li = document.createElement("li");
    li.className = "error";
    li.textContent = "見出しなし";
    listEl.appendChild(li);
    return fragment;
  }

  for (const item of shown) {
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

    li.appendChild(body);
    listEl.appendChild(li);
  }

  return fragment;
}

async function fetchHeadlines() {
  const query = `?limit=${FIXED_HEADLINES_PER_SITE}`;
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
      payload.sources = (payload.sources || []).slice(0, FIXED_SITE_COUNT).map((source) => ({
        ...source,
        headlines: (source.headlines || []).slice(0, FIXED_HEADLINES_PER_SITE)
      }));

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
    return "`headlines.json` が未生成です。Actions の `Update headlines.json` を実行してください。";
  }
  if (/HTTP 404/.test(reason)) {
    return "APIまたはheadlines.jsonが見つかりません。";
  }
  if (/failed to fetch|networkerror|load failed/i.test(reason)) {
    return "ネットワークまたはサーバー起動状態を確認してください。";
  }
  return "サーバー起動状態とネットワークを確認してください。";
}

async function renderNews() {
  statusEl.textContent = "見出しを取得中...";
  updatedAtEl.textContent = "";
  newsGridEl.textContent = "";
  refreshBtn.disabled = true;

  try {
    const { payload, endpoint } = await fetchHeadlines();
    const sources = Array.isArray(payload.sources) ? payload.sources : [];

    let okCount = 0;
    for (const source of sources) {
      if (!source.error) {
        okCount += 1;
      }
      newsGridEl.appendChild(buildSourceCard(source));
    }

    const fetchedAt = payload.fetched_at ? new Date(payload.fetched_at) : new Date();
    statusEl.textContent = `${okCount}/${FIXED_SITE_COUNT} サイト表示`;
    updatedAtEl.textContent = `最終更新: ${formatDate(fetchedAt)} | ${endpoint}`;
  } catch (error) {
    statusEl.textContent = `エラー: ${error.message}`;
    updatedAtEl.textContent = buildConnectionHint(error);
  } finally {
    refreshBtn.disabled = false;
  }
}

refreshBtn.addEventListener("click", renderNews);

renderNews();
setInterval(renderNews, 5 * 60 * 1000);
