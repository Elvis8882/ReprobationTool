// ================= COUNTRY NAME MAPPING =================
const countryNames = {
  // Europe
  AL: "Albania", AD: "Andorra", AT: "Austria", BY: "Belarus", BE: "Belgium",
  BA: "Bosnia and Herzegovina", BG: "Bulgaria", HR: "Croatia", CY: "Cyprus",
  CZ: "Czech Republic", DK: "Denmark", EE: "Estonia", FI: "Finland",
  FR: "France", DE: "Germany", GR: "Greece", HU: "Hungary", IS: "Iceland",
  IE: "Ireland", IT: "Italy", XK: "Kosovo", LV: "Latvia", LI: "Liechtenstein",
  LT: "Lithuania", LU: "Luxembourg", MT: "Malta", MD: "Moldova",
  MC: "Monaco", ME: "Montenegro", NL: "Netherlands", MK: "North Macedonia",
  NO: "Norway", PL: "Poland", PT: "Portugal", RO: "Romania", RU: "Russia",
  SM: "San Marino", RS: "Serbia", SK: "Slovakia", SI: "Slovenia",
  ES: "Spain", SE: "Sweden", CH: "Switzerland", UA: "Ukraine",
  GB: "United Kingdom", VA: "Vatican City",

  // West Asia
  AM: "Armenia", AZ: "Azerbaijan", BH: "Bahrain", GE: "Georgia",
  IR: "Iran", IQ: "Iraq", IL: "Israel", JO: "Jordan", KW: "Kuwait",
  LB: "Lebanon", OM: "Oman", PS: "Palestine", QA: "Qatar",
  SA: "Saudi Arabia", SY: "Syria", TR: "Turkey", KZ: "Kazakhstan", TM: "Turkmenistan",
  AE: "United Arab Emirates", YE: "Yemen", ru-kaliningrad: "Russia (Kaliningrad)", ru-main: "Russia (Mainland),

  // North Africa
  DZ: "Algeria", EG: "Egypt", LY: "Libya", MA: "Morocco",
  SD: "Sudan", TN: "Tunisia", EH: "Western Sahara"
};

// ================= MOCK SCORES =================
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

// ================= DOM READY =================
document.addEventListener("DOMContentLoaded", () => {
  const countries = document.querySelectorAll("svg path");
  const countryListEl = document.getElementById("country-list");

  console.log("Countries found:", countries.length);

  countries.forEach(country => {
    const code = country.id;
    const name = countryNames[code] || code;

    // Tooltip
    country.setAttribute("title", name);

    // Color country
    const score = mockScores[code];
    if (score !== undefined) {
      country.style.fill = scoreToColor(score);
      country.setAttribute("data-note", "scored");
    }

    // Map click
    country.addEventListener("click", () => {
      highlightCountry(code);
      openPopup(country);
    });

    // Country list entry
    if (countryNames[code]) {
      const li = document.createElement("li");
      li.textContent = name;
      li.dataset.countryId = code;

      li.addEventListener("click", () => {
        highlightCountry(code);
        openPopup(country);
      });

      countryListEl.appendChild(li);
    }
  });
});

// ================= POPUP =================
function openPopup(countryEl) {
  const code = countryEl.id;
  const name = countryNames[code] || code;

  document.getElementById("country-name").innerText = name;
  document.getElementById("country-content").innerText =
    "Media score and insights coming soon.";

  document.getElementById("overlay").classList.remove("hidden");
}

function closePopup() {
  document.getElementById("overlay").classList.add("hidden");
}

// ================= HIGHLIGHTING =================
function highlightCountry(countryId) {

  // Reset all
  document.querySelectorAll("svg path").forEach(p => {
    p.style.strokeWidth = "0.5";
    p.style.stroke = "#ffffff";
    p.style.vectorEffect = "non-scaling-stroke";
  });

  // Highlight selected country (all its paths)
  document
    .querySelectorAll(`svg path[id^="${countryId}"]`)
    .forEach(p => {
      p.style.stroke = "#000000";
      p.style.strokeWidth = "2.5";
      p.style.vectorEffect = "non-scaling-stroke";
    });

  // Highlight list item
  document.querySelectorAll("#country-list li").forEach(li => {
    li.classList.toggle(
      "active",
      li.dataset.countryId === countryId
    );
  });
}
