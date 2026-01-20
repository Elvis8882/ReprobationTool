document.querySelectorAll("svg path").forEach(country => {
  country.addEventListener("click", () => {
    openPopup(country.id);
  });
});

const countryNames = {
  DE: "Germany",
  FR: "France",
  IT: "Italy",
  ES: "Spain",
  PL: "Poland",
  NL: "Netherlands",
  BE: "Belgium",
  AT: "Austria",
  SE: "Sweden",
  FI: "Finland",
  DK: "Denmark",
  CZ: "Czech Republic",
  SK: "Slovakia",
  HU: "Hungary",
  RO: "Romania",
  BG: "Bulgaria",
  HR: "Croatia",
  SI: "Slovenia",
  PT: "Portugal",
  IE: "Ireland",
  GR: "Greece",
  EE: "Estonia",
  LV: "Latvia",
  LT: "Lithuania",
  LU: "Luxembourg",
  MT: "Malta",
  CY: "Cyprus"
};


function openPopup(code) {
  document.getElementById("country-name").innerText =
    countryNames[code] || code;

  document.getElementById("country-content").innerText =
    "Country profile will appear here.";

  document.getElementById("popup").classList.remove("hidden");
}

function closePopup() {
  document.getElementById("popup").classList.add("hidden");
}

