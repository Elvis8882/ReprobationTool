/* =========================
   CONSTANTS & GLOBAL STATE
========================= */

const SELECTED_FILL = "#bbdefb"; // light blue
const NEUTRAL_SCORE = 90;
const NO_DATA_SCORE_TEXT = "Not enough data";
const NO_DATA_ASSESSMENT_TEXT = "No information available";
const countryScores = {};
const countryArticleCounts = {};

const PRANK_COUNTRY_ID = "NL"; // the country code in your SVG
const PRANK_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ";

let selectedCountryEl = null;  // global variable
let DATA_VERSION = null;


/* =========================
   Custom tooltip
========================= */
// Only create tooltip once
let tooltip = document.getElementById("sent-tooltip");
if (!tooltip) {
  tooltip = document.createElement("div");
  tooltip.id = "sent-tooltip";
  tooltip.style.position = "absolute";
  tooltip.style.padding = "6px 10px";
  tooltip.style.background = "#fff";
  tooltip.style.border = "1px solid #ccc";
  tooltip.style.borderRadius = "4px";
  tooltip.style.boxShadow = "0 2px 6px rgba(0,0,0,0.2)";
  tooltip.style.pointerEvents = "none";
  tooltip.style.whiteSpace = "nowrap";
  tooltip.style.transition = "opacity 0.2s";
  tooltip.style.opacity = 0;
  tooltip.style.zIndex = 2000;
  document.body.appendChild(tooltip);
}

/* =========================
   SCORE LEVELS & MAPPING
========================= */

const SCORE_LEVELS = [
  { min: 0,   max: 9,   label: "Damnation",            color: "#b71c1c" },
  { min: 10,  max: 18,  label: "Excommunication",     color: "#c62828" },
  { min: 19,  max: 27,  label: "Reprobation",         color: "#d32f2f" },
  { min: 28,  max: 36,  label: "Strong Denunciation", color: "#e53935" },
  { min: 37,  max: 45,  label: "Denunciation",        color: "#ef5350" },

  { min: 46,  max: 54,  label: "Strong Reproach",     color: "#ffb74d" },
  { min: 55,  max: 63,  label: "Reproach",            color: "#ffd54f" },

  { min: 64,  max: 72,  label: "Extreme Disapproval", color: "#fff176" },
  { min: 73,  max: 81,  label: "Strong Disapproval",  color: "#dce775" },
  { min: 82,  max: 90,  label: "Disapproval",         color: "#aed581" },

  { min: 91,  max: 100, label: "No Commentary",       color: "#66bb6a" }
];

function scoreToLevel(score) {
  return SCORE_LEVELS.find(l => score >= l.min && score <= l.max);
}

function scoreToColor(score) {
  return scoreToLevel(score)?.color || "#ccc";
}


/* =========================
   ASYNC & TIMING HELPERS
========================= */

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function nextFrame() {
  return new Promise(resolve => requestAnimationFrame(resolve));
}


/* =========================
   DATA LOADING
========================= */

async function loadCountryScores(countries) {
  const tasks = Array.from(countries).map(async country => {
    const code = country.id;
    countryScores[code] = NEUTRAL_SCORE;
    countryArticleCounts[code] = 0;

    try {
      const data = await fetchCountryData(code);
      if (!data) return;
      const articleCount = Number(data.sources ?? data.articles ?? data.latest_articles?.length ?? 0) || 0;
      countryArticleCounts[code] = articleCount;
      if (articleCount > 0 && typeof data.score === "number") {
        countryScores[code] = data.score;
      }
    } catch {
      // no JSON → ignore
    }
  });

  await Promise.all(tasks);
}

async function fetchCountryData(code) {
  const v = DATA_VERSION ? encodeURIComponent(DATA_VERSION) : Date.now();
  const url = `countries/${code}.json?v=${v}`;

  return fetch(url, { cache: "no-store" })
    .then(res => (res.ok ? res.json() : null))
    .catch(() => null);
}


function truncateText(text, maxLength = 160) {
  if (!text) return "";
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength).trim()}…`;
}

function createNewsItem(article) {
  const li = document.createElement("li");
  li.className = "news-item";

  const title = document.createElement("div");
  title.className = "news-title";

  if (article.url) {
    const link = document.createElement("a");
    link.href = article.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = article.title || "Untitled article";
    title.appendChild(link);
  } else {
    title.textContent = article.title || "Untitled article";
  }

  const summary = document.createElement("p");
  summary.className = "news-summary";
  summary.textContent = truncateText(article.summary || "Summary not available.");

  const date = document.createElement("div");
  date.className = "news-date";
  date.textContent = formatDateYMD(article.published_at);

  li.appendChild(title);
  li.appendChild(summary);
  li.appendChild(date);

  return li;
}

function renderArticles(listEl, articles, emptyMessage) {
  if (!listEl) return;
  listEl.innerHTML = "";

  if (!articles.length) {
    const emptyItem = document.createElement("li");
    emptyItem.className = "news-empty";
    emptyItem.textContent = emptyMessage;
    listEl.appendChild(emptyItem);
    return;
  }

  articles.forEach(article => {
    listEl.appendChild(createNewsItem(article));
  });
}

function dedupeArticles(articles) {
  const seen = new Set();
  const unique = [];

  articles.forEach(article => {
    const key = article.id || article.url || article.title;
    if (!key || seen.has(key)) return;
    seen.add(key);
    unique.push(article);
  });

  return unique;
}

function calculateSentimentShares(pos, neu, neg) {
  const total = pos + neu + neg;
  const emptyShare = 100 / 3;

  if (total === 0) {
    return { posShare: emptyShare, neuShare: emptyShare, negShare: emptyShare };
  }

  const minShare = 5;
  const zeroCount = [pos, neu, neg].filter(value => value === 0).length;

  if (zeroCount === 0) {
    return {
      posShare: (pos / total) * 100,
      neuShare: (neu / total) * 100,
      negShare: (neg / total) * 100
    };
  }

  const reserved = minShare * zeroCount;
  const remaining = Math.max(100 - reserved, 0);
  const nonZeroTotal = pos + neu + neg;

  const posShare = pos === 0 ? minShare : (pos / nonZeroTotal) * remaining;
  const neuShare = neu === 0 ? minShare : (neu / nonZeroTotal) * remaining;
  const negShare = neg === 0 ? minShare : (neg / nonZeroTotal) * remaining;

  return { posShare, neuShare, negShare };
}

async function loadLatestNews(countries) {
  const listEl = document.getElementById("latest-news-list");
  const placeholderEl = document.getElementById("latest-news-placeholder");

  const tasks = Array.from(countries).map(async country => {
    const data = await fetchCountryData(country.id);
    if (!data || !Array.isArray(data.latest_articles)) {
      return [];
    }
    return data.latest_articles;
  });

  const results = await Promise.all(tasks);
  const articles = results.flat().map(article => ({
    ...article,
    publishedAtMs: Date.parse(article.published_at) || 0
  }));

  const uniqueArticles = dedupeArticles(articles);
  uniqueArticles.sort((a, b) => b.publishedAtMs - a.publishedAtMs);
  const latestTwenty = uniqueArticles.slice(0, 20);

  if (placeholderEl) {
    placeholderEl.style.display = latestTwenty.length ? "none" : "";
  }

  renderArticles(listEl, latestTwenty, "No recent articles available.");
}


/* =========================
   SELECTION & HIGHLIGHTING
========================= */

function setSelectedCountry(countryEl) {
  selectedCountryEl = countryEl;
  const name = countryEl.getAttribute("name") || countryEl.id;
  document.getElementById("selected-country-name").innerText = name;
  document.getElementById("calculate-score-btn").disabled = false;
}

function highlightCountry(countryId) {

  document.querySelectorAll("svg path").forEach(p => {
    p.style.strokeWidth = "0.5";

    if (p.dataset.originalFill !== undefined) {
      p.style.fill = p.dataset.originalFill;
    }
  });

  document.querySelectorAll("#country-list li").forEach(li => {
    li.classList.remove("active");
  });

  const countryPath = document.getElementById(countryId);
  if (countryPath) {
    countryPath.style.strokeWidth = "2";
    countryPath.style.fill = SELECTED_FILL;
  }

  const listItem = document.querySelector(
    `#country-list li[data-country-id="${countryId}"]`
  );
  if (listItem) {
    listItem.classList.add("active");
  }
}


/* =========================
   POPUP UI LOGIC
========================= */

function resetPopupData() {
  document.getElementById("countryScore").innerText = "";
  document.getElementById("countryTrend").innerText = "";
  document.getElementById("countryArticles").innerText = "";
  document.getElementById("countryAssessmentValue").innerText = "";

  document.getElementById("sentPos").innerText = "";
  document.getElementById("sentNeu").innerText = "";
  document.getElementById("sentNeg").innerText = "";

  document.getElementById("lastUpdated").innerText = "";
  const popupNewsList = document.getElementById("popup-country-news");
  if (popupNewsList) popupNewsList.innerHTML = "";

  ["sentPosBar", "sentNeuBar", "sentNegBar"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.width = "0%";
  });
}

function parseTrend(trend) {
  // Accept: "+3", "-2", "+0", 0, 2, -5, null/undefined
  if (trend === null || trend === undefined) return null;

  // If backend ever sends object, support it safely
  if (typeof trend === "object") {
    const delta = Number(trend.delta);
    return Number.isFinite(delta) ? delta : null;
  }

  const delta = Number(trend);
  return Number.isFinite(delta) ? delta : null;
}


async function openPopup(countryEl) {
  const code = countryEl.id;
  const overlay = document.getElementById("overlay");
  const loadingEl = document.getElementById("popup-loading");
  const dataEl = document.getElementById("popup-data");
  const titleEl = document.getElementById("popup-country-name");
  const errorEl = document.getElementById("popup-error");

  errorEl.classList.add("hidden");
  document.getElementById("sentiment").style.display = "";

  titleEl.innerText = countryEl.getAttribute("name") || code;

  resetPopupData();

  overlay.classList.remove("hidden");
  loadingEl.classList.remove("hidden");
  dataEl.classList.add("hidden");

  await nextFrame();

  try {
    const res = await fetch(`countries/${code}.json?cacheBust=${Date.now()}`);
    if (!res.ok) throw new Error("No data");

    const data = await res.json();
    await delay(1500);

    const scoreEl = document.getElementById("countryScore");
    const scoreP = scoreEl.parentElement;
    const articleCount = data.articles ?? data.sources ?? data.latest_articles?.length ?? 0;
    const level = scoreToLevel(data.score);

    scoreEl.style.fontWeight = "bold"; // value bold 

    const assessmentValueEl = document.getElementById("countryAssessmentValue");
       if (articleCount === 0) {
     scoreEl.innerText = NO_DATA_SCORE_TEXT;
     scoreEl.style.color = "#777";
   
     assessmentValueEl.innerText = NO_DATA_ASSESSMENT_TEXT;
     assessmentValueEl.style.color = "#777";
   } else {
     scoreEl.innerText = data.score;
     scoreEl.style.color = level?.color || "#777";
   
     assessmentValueEl.innerText = level.label;
     assessmentValueEl.style.color = level.color;
   }


      const trendEl = document.getElementById("countryTrend");
      trendEl.classList.remove("up", "down");
      
      // NO DATA → NO TREND AT ALL
      if (articleCount === 0) {
        trendEl.innerText = "";
      } else {
        const delta = Number(data.trend);
      
        if (!Number.isFinite(delta)) {
          trendEl.innerText = "";
        } else if (delta === 0) {
          trendEl.innerText = "= 0";
        } else if (delta > 0) {
          trendEl.classList.add("up");
          trendEl.innerText = `▲ +${delta}`;
        } else {
          trendEl.classList.add("down");
          trendEl.innerText = `▼ ${delta}`; // already negative
        }
      }



    document.getElementById("countryArticles").innerText = articleCount;

    const popupNewsList = document.getElementById("popup-country-news");
    const countryArticles = Array.isArray(data.latest_articles)
      ? data.latest_articles.map(article => ({
          ...article,
          publishedAtMs: Date.parse(article.published_at) || 0
        }))
      : [];

    countryArticles.sort((a, b) => b.publishedAtMs - a.publishedAtMs);
    renderArticles(
      popupNewsList,
      countryArticles.slice(0, 12),
      "No recent articles available for this country."
    );

      const posBar = document.getElementById("sentPosBar");
      const neuBar = document.getElementById("sentNeuBar");
      const negBar = document.getElementById("sentNegBar");
      
      const posNum = document.getElementById("sentPos");
      const neuNum = document.getElementById("sentNeu");
      const negNum = document.getElementById("sentNeg");
      
      if (posBar && neuBar && negBar) {
        const pos = data.sentiment?.positive || 0;
        const neu = data.sentiment?.neutral || 0;
        const neg = data.sentiment?.negative || 0;
        const { posShare, neuShare, negShare } = calculateSentimentShares(
          pos,
          neu,
          neg
        );
      
        // set bar widths
        posBar.style.width = `${posShare}%`;
        neuBar.style.width = `${neuShare}%`;
        negBar.style.width = `${negShare}%`;
      
        // set numbers above proportionally (width = bar width)
        posNum.style.flex = `0 0 ${posShare}%`;
        neuNum.style.flex = `0 0 ${neuShare}%`;
        negNum.style.flex = `0 0 ${negShare}%`;
      
        posNum.innerText = pos;
        neuNum.innerText = neu;
        negNum.innerText = neg;

        // Add tooltips
         const bars = [
           { el: posBar, label: "Positive", value: pos, color: "#66bb6a" },
           { el: neuBar, label: "Neutral", value: neu, color: "#ffee58" },
           { el: negBar, label: "Negative", value: neg, color: "#ef5350" },
         ];
         
         bars.forEach(b => {
           b.el.addEventListener("mouseenter", (e) => {
             tooltip.innerHTML = `
               <div style="display:flex; align-items:center; gap:6px;">
                 <div style="width:12px; height:12px; background:${b.color}; border-radius:50%;"></div>
                 <span><strong>${b.label}:</strong> ${b.value}</span>
               </div>
             `;
             tooltip.style.opacity = 1;
             tooltip.style.left = `${e.pageX + 10}px`;
             tooltip.style.top = `${e.pageY + 10}px`;
           });
         
           b.el.addEventListener("mousemove", (e) => {
             tooltip.style.left = `${e.pageX + 10}px`;
             tooltip.style.top = `${e.pageY + 10}px`;
           });
         
           b.el.addEventListener("mouseleave", () => {
             tooltip.style.opacity = 0;
           });
         });

      }

    document.getElementById("lastUpdated").innerText =
      new Date(data.last_updated).toLocaleString();

  } catch {
    errorEl.classList.remove("hidden");
    document.getElementById("sentiment").style.display = "none";
    document.getElementById("countryScore").innerText = "—";
    document.getElementById("countryArticles").innerText = "—";
    document.getElementById("lastUpdated").innerText = "—";
    renderArticles(
      document.getElementById("popup-country-news"),
      [],
      "No recent articles available for this country."
    );
  } finally {
    loadingEl.classList.add("hidden");
    dataEl.classList.remove("hidden");
  }
}

function closePopup() {
  document.getElementById("overlay").classList.add("hidden");
}

function openLegalNotes() {
  document.getElementById("legal-overlay").classList.remove("hidden");
}

function closeLegalNotes() {
  document.getElementById("legal-overlay").classList.add("hidden");
}

const legalTrigger = document.getElementById("legal-notes-trigger");
const legalOverlay = document.getElementById("legal-overlay");
const legalClose = document.querySelector(".legal-close");

if (legalTrigger) {
  legalTrigger.addEventListener("click", openLegalNotes);
}

if (legalOverlay) {
  legalOverlay.addEventListener("click", closeLegalNotes);
}

if (legalClose) {
  legalClose.addEventListener("click", closeLegalNotes);
}

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeLegalNotes();
  }
});


/* =========================
   SEARCH & FILTER HELPERS
========================= */

function normalize(str) {
  return str
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function relevanceScore(name, query) {
  if (!query) return 1;

  const n = normalize(name);
  const q = normalize(query);

  if (n.startsWith(q)) return 300;
  if (n.split(" ").some(word => word.startsWith(q))) return 200;
  if (n.includes(q)) return 100;

  return 0;
}

function highlightMatch(text, query) {
  if (!query) return text;

  const safe = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const regex = new RegExp(`(${safe})`, "ig");

  return text.replace(regex, "<mark>$1</mark>");
}

function formatDateYMD(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  // "sv-SE" reliably outputs YYYY-MM-DD
  return d.toLocaleDateString("sv-SE");
}

/* =========================
   DOM BOOTSTRAP (UNCHANGED)
========================= */

document.addEventListener("DOMContentLoaded", async () => {

  const countries = document.querySelectorAll("svg path");
  
async function loadDataVersion() {
  const res = await fetch(`countries/index.json?cb=${Date.now()}`, { cache: "no-store" });
  if (!res.ok) return null;
  const idx = await res.json();
  return idx?.last_updated || null;
}

   DATA_VERSION = await loadDataVersion();
   await loadCountryScores(countries);
   await loadLatestNews(countries);

  console.log("Countries found:", countries.length);

  countries.forEach(country => {

    const name = country.getAttribute("name");
    if (name) {
      country.setAttribute("title", name);
    }

    const score = countryScores[country.id];

    if (score !== undefined) {
      const articleCount = countryArticleCounts[country.id] ?? 0;
      const fill = articleCount === 0 ? "#bdbdbd" : scoreToColor(score);
      country.style.fill = fill;
      country.dataset.originalFill = fill;
      country.setAttribute("data-note", articleCount === 0 ? "no-articles" : "scored");
    } else {
      country.dataset.originalFill = country.style.fill || "";
    }

    country.addEventListener("click", () => {
      highlightCountry(country.id);
      setSelectedCountry(country);
    });
  });

  const countryListEl = document.getElementById("country-list");

  const euCountries = [];
  const otherCountries = [];

  countries.forEach(country => {
    const name = country.getAttribute("name");
    if (!name) return;

    const entry = {
      id: country.id,
      name,
      el: country
    };

    if (country.classList.contains("European_Union")) {
      euCountries.push(entry);
    } else {
      otherCountries.push(entry);
    }
  });

  const sortByName = (a, b) =>
    a.name.localeCompare(b.name, "en");

  euCountries.sort(sortByName);
  otherCountries.sort(sortByName);

  countryListEl.innerHTML = "";

  function renderSection(title, items) {
    const header = document.createElement("li");
    header.textContent = title;
    header.className = "country-section";
    countryListEl.appendChild(header);

    items.forEach(country => {
      const li = document.createElement("li");
      li.textContent = country.name;
      li.dataset.originalName = country.name;
      li.dataset.countryId = country.id;

      li.addEventListener("click", () => {
        highlightCountry(country.id);
        setSelectedCountry(country.el);
      });

      countryListEl.appendChild(li);
    });
  }

  renderSection("European Union", euCountries);
  renderSection("Other", otherCountries);

  const filterInput = document.getElementById("country-filter");

  filterInput.addEventListener("input", () => {
    const query = filterInput.value.trim();

    document
      .querySelectorAll("#country-list li.country-section")
      .forEach(sectionHeader => {

        let items = [];
        let node = sectionHeader.nextElementSibling;

        while (node && !node.classList.contains("country-section")) {
          items.push(node);
          node = node.nextElementSibling;
        }

        const scored = items
          .map(li => {
            const name = li.dataset.originalName;
            return {
              li,
              name,
              score: relevanceScore(name, query)
            };
          })
          .filter(item => !query || item.score > 0);

        scored.sort((a, b) =>
          b.score - a.score ||
          a.name.localeCompare(b.name, "en")
        );

        items.forEach(li => {
          li.style.display = "none";
          li.innerHTML = li.dataset.originalName;
        });

        scored.forEach(({ li, name }) => {
          li.innerHTML = highlightMatch(name, query);
          li.style.display = "";
          sectionHeader.parentNode.insertBefore(li, node);
        });

        sectionHeader.style.display = scored.length ? "" : "none";
      });
  });

  document
    .getElementById("calculate-score-btn")
    .addEventListener("click", () => {
      if (!selectedCountryEl) return;

      const countryId = selectedCountryEl.id;

      if (countryId === PRANK_COUNTRY_ID) {
        window.open(PRANK_URL, "_blank");
      } else {
        openPopup(selectedCountryEl);
      }
    });

});

/* =========================
   Panzoom library
========================= */

// Select the container div (not the SVG directly)
const mapContainer = document.getElementById("map-container");

// Initialize Panzoom
const panzoom = Panzoom(mapContainer, {
  maxScale: 5,     // max zoom level
  minScale: 1,     // min zoom level
  contain: 'outside', // allow pan outside edges
  step: 0.2,       // zoom step for buttons
});

// Make mouse wheel zoom
mapContainer.parentElement.addEventListener('wheel', panzoom.zoomWithWheel);

// Zoom buttons
document.getElementById("zoom-in").addEventListener("click", () => panzoom.zoomIn());
document.getElementById("zoom-out").addEventListener("click", () => panzoom.zoomOut());
