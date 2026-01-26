const SELECTED_FILL = "#bbdefb"; // light blue
const countryScores = {};

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

document.addEventListener("DOMContentLoaded", async () => {

  const countries = document.querySelectorAll("svg path");
  await loadCountryScores(countries);
  console.log("Countries found:", countries.length);

countries.forEach(country => {

  // Tooltip from SVG attribute
  const name = country.getAttribute("name");
  if (name) {
    country.setAttribute("title", name);
  }

  // Color country from JSON score
  const score = countryScores[country.id];

  if (score !== undefined) {
    const fill = scoreToColor(score);
    country.style.fill = fill;
    country.dataset.originalFill = fill;
    country.setAttribute("data-note", "scored");
  } else {
    // preserve original SVG fill
    country.dataset.originalFill = country.style.fill || "";
  }

  // Click popup
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
      setSelectedCountry(country.el); // add this line
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

      // Collect countries under this section
      while (node && !node.classList.contains("country-section")) {
        items.push(node);
        node = node.nextElementSibling;
      }

      // Score & filter
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

      // Sort by relevance, then alphabetically
      scored.sort((a, b) =>
        b.score - a.score ||
        a.name.localeCompare(b.name, "en")
      );

      // Reset all items
      items.forEach(li => {
        li.style.display = "none";
        li.innerHTML = li.dataset.originalName;
      });

      // Show matched items with highlight
      scored.forEach(({ li, name }) => {
        li.innerHTML = highlightMatch(name, query);
        li.style.display = "";
        sectionHeader.parentNode.insertBefore(li, node);
      });

      // Show / hide section header
      sectionHeader.style.display = scored.length ? "" : "none";
    });
});


});

let selectedCountryEl = null;  // global variable

function setSelectedCountry(countryEl) {
  selectedCountryEl = countryEl; // store the selected country
  const name = countryEl.getAttribute("name") || countryEl.id;
  document.getElementById("selected-country-name").innerText = name; // update legend text
  document.getElementById("calculate-score-btn").disabled = false;   // enable button
}

const PRANK_COUNTRY_ID = "NL"; // the country code in your SVG
const PRANK_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ";

document.getElementById("calculate-score-btn").addEventListener("click", () => {
  if (!selectedCountryEl) return;

  const countryId = selectedCountryEl.id; // get the country id from SVG path

  if (countryId === PRANK_COUNTRY_ID) {
    // Open new tab for prank country
    window.open(PRANK_URL, "_blank");
  } else {
    // Normal popup for other countries
    openPopup(selectedCountryEl);
  }
});

async function openPopup(countryEl) {
  const code = countryEl.id;
  const overlay = document.getElementById("overlay");
  const loadingEl = document.getElementById("popup-loading");
  const dataEl = document.getElementById("popup-data");
  const titleEl = document.getElementById("popup-country-name");
  const errorEl = document.getElementById("popup-error");

  // reset visibility
  errorEl.classList.add("hidden");
  document.getElementById("sentiment").style.display = "";

  // Always show country name in header
  const countryName = countryEl.getAttribute("name") || code;
  titleEl.innerText = countryName;

  // Show overlay and spinner, hide data
  overlay.classList.remove("hidden");
  loadingEl.classList.remove("hidden");
  dataEl.classList.add("hidden");

  // Force browser paint so spinner is visible
  await nextFrame();

  try {
    // Cache-busting query param ensures fresh fetch every time
    const res = await fetch(`countries/${code}.json?cacheBust=${Date.now()}`);
    if (!res.ok) throw new Error("No data");

    const data = await res.json();

    // Artificial UX delay
    await delay(1500);

    // Populate Score
    document.getElementById("countryScore").innerText = data.score;

    // Score color
    const level = scoreToLevel(data.score);
    
    const scoreEl = document.getElementById("countryScore");
    const scoreP = scoreEl.parentElement;
    
    scoreEl.innerText = data.score;
    scoreP.style.color = level.color;
    
    // Optional: show textual level
    document.getElementById("countryTrend").insertAdjacentHTML(
      "afterend",
      `<p><strong>Assessment:</strong> ${level.label}</p>`
    );

    // Trend
    const trendEl = document.getElementById("countryTrend");
    trendEl.innerText = `${data.trend.direction === "up" ? "▲" : "▼"} ${data.trend.delta}`;
    trendEl.style.color = data.trend.direction === "up" ? "green" : "red";

    // Articles
    document.getElementById("countryArticles").innerText = data.articles;

    // Sentiment text
    document.getElementById("sentPos").innerText = data.sentiment.positive;
    document.getElementById("sentNeu").innerText = data.sentiment.neutral;
    document.getElementById("sentNeg").innerText = data.sentiment.negative;
    
    // Stacked bar percentages (only if elements exist)
    const posBar = document.getElementById("sentPosBar");
    const neuBar = document.getElementById("sentNeuBar");
    const negBar = document.getElementById("sentNegBar");
    
    if (posBar && neuBar && negBar) {
      const totalSent = data.sentiment.positive + data.sentiment.neutral + data.sentiment.negative;
    
      posBar.style.width = `${(data.sentiment.positive / totalSent) * 100}%`;
      neuBar.style.width = `${(data.sentiment.neutral / totalSent) * 100}%`;
      negBar.style.width = `${(data.sentiment.negative / totalSent) * 100}%`;
    }

    // Last updated
    document.getElementById("lastUpdated").innerText = new Date(data.last_updated).toLocaleString();

  } catch (err) {
  errorEl.classList.remove("hidden");

  // hide data sections but keep DOM intact
  document.getElementById("sentiment").style.display = "none";
  document.getElementById("countryScore").innerText = "—";
  document.getElementById("countryTrend").innerText = "";
  document.getElementById("countryArticles").innerText = "—";
  document.getElementById("lastUpdated").innerText = "—";
} finally {
    // Hide spinner and show data
    loadingEl.classList.add("hidden");
    dataEl.classList.remove("hidden");
  }
}


function closePopup() {
  document.getElementById("overlay").classList.add("hidden");
}

function highlightCountry(countryId) {

  // Reset all map highlights
  document.querySelectorAll("svg path").forEach(p => {
    p.style.strokeWidth = "0.5";

    // Restore original fill
    if (p.dataset.originalFill !== undefined) {
      p.style.fill = p.dataset.originalFill;
    }
  });

  // Reset list highlights
  document.querySelectorAll("#country-list li").forEach(li => {
    li.classList.remove("active");
  });

  // Highlight map country
  const countryPath = document.getElementById(countryId);
  if (countryPath) {
    countryPath.style.strokeWidth = "2";
    countryPath.style.fill = SELECTED_FILL;
  }

  // Highlight list item
  const listItem = document.querySelector(
    `#country-list li[data-country-id="${countryId}"]`
  );
  if (listItem) {
    listItem.classList.add("active");
  }
}


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

  // 1. Starts with typed text (best)
  if (n.startsWith(q)) return 300;

  // 2. Word starts with typed text (e.g. "Bosnia and Herzegovina")
  if (n.split(" ").some(word => word.startsWith(q))) return 200;

  // 3. Contains typed text anywhere
  if (n.includes(q)) return 100;

  return 0;
}

function highlightMatch(text, query) {
  if (!query) return text;

  const safe = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const regex = new RegExp(`(${safe})`, "ig");

  return text.replace(regex, "<mark>$1</mark>");
}

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function nextFrame() {
  return new Promise(resolve => requestAnimationFrame(resolve));
}

