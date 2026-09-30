// Set theme for website
function setTheme(theme) {
  document.documentElement.dataset.theme = theme;

  const button = document.getElementById("themeToggle");

  // Flip theme from current one to other
  if (button) {
    button.textContent =
      theme === "dark" ? "LIGHT MODE" : "DARK MODE";
  }

  // Write theme to localStorage to be remembered
  try { localStorage.setItem("logicGamesTheme", theme); } catch (_) {}
}

// Toggle between light and dark mode
function toggleTheme() {
  const current =
    document.documentElement.dataset.theme || "light";

  setTheme(current === "dark" ? "light" : "dark");
}

// Default to dark mode
document.addEventListener("DOMContentLoaded", () => {
  let savedTheme = "dark";
  try { savedTheme = localStorage.getItem("logicGamesTheme") || "dark"; } catch (_) {}

  setTheme(savedTheme);

  const button = document.getElementById("themeToggle");

  if (button) {
    button.addEventListener("click", toggleTheme);
  }
});