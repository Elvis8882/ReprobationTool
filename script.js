document.querySelectorAll("svg path").forEach(country => {
  country.addEventListener("click", () => {
    openPopup(country.id);
  });
});

function openPopup(code) {
  document.getElementById("country-name").innerText = code;
  document.getElementById("country-content").innerText =
    "Country profile will appear here.";
  document.getElementById("popup").classList.remove("hidden");
}

function closePopup() {
  document.getElementById("popup").classList.add("hidden");
}

