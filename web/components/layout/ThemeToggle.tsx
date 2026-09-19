"use client";

import { useSyncExternalStore } from "react";
import styles from "./SiteHeader.module.css";

type Theme = "light" | "dark";

const STORAGE_KEY = "matchpoint-theme";
const CHANGE_EVENT = "matchpoint-theme-change";
const DARK_QUERY = "(prefers-color-scheme: dark)";

function currentTheme(): Theme {
  const explicit = document.documentElement.dataset.theme;
  if (explicit === "light" || explicit === "dark") {
    return explicit;
  }
  return window.matchMedia(DARK_QUERY).matches ? "dark" : "light";
}

function subscribe(onChange: () => void): () => void {
  const media = window.matchMedia(DARK_QUERY);
  media.addEventListener("change", onChange);
  window.addEventListener(CHANGE_EVENT, onChange);
  return () => {
    media.removeEventListener("change", onChange);
    window.removeEventListener(CHANGE_EVENT, onChange);
  };
}

function persist(theme: Theme): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    return;
  }
}

function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  persist(theme);
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

export const THEME_BOOTSTRAP = `(function(){try{var t=localStorage.getItem("${STORAGE_KEY}");if(t==="light"||t==="dark"){document.documentElement.dataset.theme=t;}}catch(e){}})();`;

export function ThemeToggle() {
  const theme = useSyncExternalStore<Theme | null>(subscribe, currentTheme, () => null);
  const next: Theme = theme === "dark" ? "light" : "dark";
  const label =
    theme === null
      ? "Changer de thème"
      : `Activer le thème ${next === "dark" ? "sombre" : "clair"}`;
  return (
    <button
      type="button"
      className={styles.themeToggle}
      onClick={() => applyTheme(next)}
      aria-label={label}
      title={label}
    >
      <svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20" focusable="false">
        {theme === "dark" ? (
          <g fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <circle cx="12" cy="12" r="4.2" />
            <path d="M12 2.5v2.2M12 19.3v2.2M4.6 4.6l1.6 1.6M17.8 17.8l1.6 1.6M2.5 12h2.2M19.3 12h2.2M4.6 19.4l1.6-1.6M17.8 6.2l1.6-1.6" />
          </g>
        ) : (
          <path
            d="M20.2 14.6A8.4 8.4 0 0 1 9.4 3.8a8.4 8.4 0 1 0 10.8 10.8Z"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinejoin="round"
          />
        )}
      </svg>
    </button>
  );
}
