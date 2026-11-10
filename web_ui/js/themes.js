/**
 * Cintamani Theme Management System
 * Manages the 4 Cognitive Neo-Brutalism Palettes (PRD Section 4.1).
 */

const THEMES = {
  terminal: {
    id: "terminal",
    name: "Cognitive Terminal (Dark)",
    mode: "dark",
    colors: {
      canvas: "#18181A",
      surface: "#09090B",
      border: "#F1F5F9",
      accent1: "#4ADE80",
      accent2: "#A78BFA",
    },
  },
  draft: {
    id: "draft",
    name: "Architect's Draft (Light)",
    mode: "light",
    colors: {
      canvas: "#F4F4F0",
      surface: "#FFFFFF",
      border: "#111111",
      accent1: "#81A1C1",
      accent2: "#E5FE54",
    },
  },
  archive: {
    id: "archive",
    name: "Industrial Archive (Light)",
    mode: "light",
    colors: {
      canvas: "#E8E4D9",
      surface: "#F5F5F0",
      border: "#1C1917",
      accent1: "#A3B18A",
      accent2: "#FF6B35",
    },
  },
  blueprint: {
    id: "blueprint",
    name: "Midnight Blueprint (Dark)",
    mode: "dark",
    colors: {
      canvas: "#0F172A",
      surface: "#1E293B",
      border: "#94A3B8",
      accent1: "#22D3EE",
      accent2: "#FB7185",
    },
  },
};

const THEME_STORAGE_KEY = "cintamani_theme";

function applyTheme(themeId) {
  if (!THEMES[themeId]) {
    themeId = "terminal";
  }
  document.documentElement.setAttribute("data-theme", themeId);
  localStorage.setItem(THEME_STORAGE_KEY, themeId);
  return themeId;
}

function initTheme() {
  const saved = localStorage.getItem(THEME_STORAGE_KEY);
  const activeId = saved && THEMES[saved] ? saved : "terminal";
  applyTheme(activeId);
  return activeId;
}

// Expose to window for vanilla JS / Vue usage
window.CintamaniThemes = {
  THEMES,
  applyTheme,
  initTheme,
};
