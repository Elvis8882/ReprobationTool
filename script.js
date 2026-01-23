const SELECTED_FILL = "#bbdefb"; // light blue

const mockScores = {
  DE: 72,
  FR: 65,
  IT: 48,
  ES: 55,
  PL: 60
};

function scoreToColor(score) {
  if (score >= 70) return "#66bb6a";
  if (score >= 50) return "#ffee58";
  return "#ef5350";
}

document.addEventListener("DOMContentLoaded", () => {

  const countries = document.querySelectorAll("svg path");
  console.log("Countries found:", countries.length);

  countries.forEach(country => {

    // Tooltip from SVG attribute
    const name = country.getAttribute("name");
    if (name) {
      country.setAttribute("title", name);
    }

    // Color country
    const score = mockScores[country.id];
    if (score !== undefined) {
    const fill = scoreToColor(score);
    country.style.fill = fill;
    country.dataset.originalFill = fill;
    country.setAttribute("data-note", "scored");

}

    if (!country.dataset.originalFill) {
    country.dataset.originalFill = country.style.fill || "";
  }


    // Click popup
  country.addEventListener("click", () => {
    highlightCountry(country.id);
    openPopup(country);
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
      openPopup(country.el);
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

function openPopup(countryEl) {
  const name =
    countryEl.getAttribute("name") ||
    countryEl.getAttribute("title") ||
    countryEl.id;

  document.getElementById("country-name").innerText = name;
  document.getElementById("country-content").innerText =
    "Media score and insights coming soon.";

  document.getElementById("overlay").classList.remove("hidden");
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
