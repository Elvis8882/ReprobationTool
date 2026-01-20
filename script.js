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

document.querySelectorAll("svg path").forEach(country => {
  const score = mockScores[country.id];
  if (score) {
    country.style.fill = scoreToColor(score);
  }
});

document.querySelectorAll("svg path").forEach(country => {
  country.addEventListener("click", () => {
    openPopup(country);
  });
});

function openPopup(countryEl) {
  const countryCode = countryEl.id;
  const countryName =
    countryEl.getAttribute("name") ||
    countryEl.getAttribute("title") ||
    countryCode;

  document.getElementById("country-name").innerText = countryName;

  document.getElementById("country-content").innerText =
    "Media score and insights coming soon.";

  document.getElementById("overlay").classList.remove("hidden");
}


function closePopup() {
  document.getElementById("popup").classList.add("hidden");
}

document.querySelectorAll("svg path").forEach(country => {
  country.addEventListener("mouseenter", e => {
    e.target.setAttribute("title", countryNames[country.id]);
  });
});
