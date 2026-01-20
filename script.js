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

