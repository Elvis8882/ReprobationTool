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
      openPopup(country);
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
