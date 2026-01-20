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
  country.style.fill = scoreToColor(score);
  country.setAttribute("data-note", "scored");
}

    // Click popup
  country.addEventListener("click", () => {
    highlightCountry(country.id);
    openPopup(country);
  });

  });
  const countryListEl = document.getElementById("country-list");

countries.forEach(country => {
  const name = country.getAttribute("name");
  if (!name) return;

  const li = document.createElement("li");
  li.textContent = name;
  li.dataset.countryId = country.id;

  li.addEventListener("click", () => {
    highlightCountry(country.id);
    openPopup(country);
  });

  countryListEl.appendChild(li);
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
  });

  // Reset list highlights
  document.querySelectorAll("#country-list li").forEach(li => {
    li.classList.remove("active");
  });

  // Highlight map country
  const countryPath = document.getElementById(countryId);
  if (countryPath) {
    countryPath.style.strokeWidth = "2";
  }

  // Highlight list item
  const listItem = document.querySelector(
    `#country-list li[data-country-id="${countryId}"]`
  );
  if (listItem) {
    listItem.classList.add("active");
  }
}
