/* =========================
   CONSTANTS & GLOBAL STATE
========================= */

const SELECTED_FILL = "#bbdefb"; // light blue
const countryScores = {};

const PRANK_COUNTRY_ID = "NL"; // the country code in your SVG
const PRANK_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ";

let selectedCountryEl = null;  // global variable


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

    try {
      const res = await fetch(`countries/${code}.json`);
      if (!res.ok) return;

      const data = await res.json();
      countryScores[code] = data.score;
    } catch {
      // no JSON → ignore
    }
  });

  await Promise.all(tasks);
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

  ["sentPosBar", "sentNeuBar", "sentNegBar"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.width = "0%";
  });
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

    const level = scoreToLevel(data.score);

    const scoreEl = document.getElementById("countryScore");
    const scoreP = scoreEl.parentElement;

    scoreEl.innerText = data.score;
    scoreEl.style.color = level.color; // only the value
     scoreEl.style.fontWeight = "bold"; // value bold 

    const assessmentValueEl = document.getElementById("countryAssessmentValue");
    assessmentValueEl.innerText = level.label;
    assessmentValueEl.style.color = level.color;

    const trendEl = document.getElementById("countryTrend");
    trendEl.innerText = `${data.trend.delta}`;
    trendEl.classList.remove("up","down");
    trendEl.classList.add(data.trend.direction === "up" ? "up" : "down");
    trendEl.insertAdjacentText("afterbegin", data.trend.direction === "up" ? "▲ " : "▼ ");

    document.getElementById("countryArticles").innerText = data.articles;

      const posBar = document.getElementById("sentPosBar");
      const neuBar = document.getElementById("sentNeuBar");
      const negBar = document.getElementById("sentNegBar");
      
      const posNum = document.getElementById("sentPos");
      const neuNum = document.getElementById("sentNeu");
      const negNum = document.getElementById("sentNeg");
      
      if (posBar && neuBar && negBar) {
        const pos = data.sentiment.positive || 0;
        const neu = data.sentiment.neutral || 0;
        const neg = data.sentiment.negative || 0;
        const total = pos + neu + neg || 1;
      
        /* proportional widths */
      const posWrap = posBar.parentElement;
      const neuWrap = neuBar.parentElement;
      const negWrap = negBar.parentElement;
      
      posWrap.style.width = `${(pos / total) * 100}%`;
      neuWrap.style.width = `${(neu / total) * 100}%`;
      negWrap.style.width = `${(neg / total) * 100}%`;

      
        /* numbers above bars */
        posNum.innerText = pos;
        neuNum.innerText = neu;
        negNum.innerText = neg;
      }


    document.getElementById("lastUpdated").innerText =
      new Date(data.last_updated).toLocaleString();

  } catch {
    errorEl.classList.remove("hidden");
    document.getElementById("sentiment").style.display = "none";
    document.getElementById("countryScore").innerText = "—";
    document.getElementById("countryArticles").innerText = "—";
    document.getElementById("lastUpdated").innerText = "—";
  } finally {
    loadingEl.classList.add("hidden");
    dataEl.classList.remove("hidden");
  }
}

function closePopup() {
  document.getElementById("overlay").classList.add("hidden");
}


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


/* =========================
   DOM BOOTSTRAP (UNCHANGED)
========================= */

document.addEventListener("DOMContentLoaded", async () => {

  const countries = document.querySelectorAll("svg path");
  await loadCountryScores(countries);
  console.log("Countries found:", countries.length);

  countries.forEach(country => {

    const name = country.getAttribute("name");
    if (name) {
      country.setAttribute("title", name);
    }

    const score = countryScores[country.id];

    if (score !== undefined) {
      const fill = scoreToColor(score);
      country.style.fill = fill;
      country.dataset.originalFill = fill;
      country.setAttribute("data-note", "scored");
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

