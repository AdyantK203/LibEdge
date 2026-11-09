export default function ThemeToggle({ theme, onChange }) {
  const nextTheme = theme === "dark" ? "light" : "dark";
  return (
    <button
      type="button"
      className="theme-toggle"
      role="switch"
      aria-label="Dark theme"
      aria-checked={theme === "dark"}
      title={`Switch to ${nextTheme} theme`}
      onClick={() => onChange(nextTheme)}
    >
      <span className="theme-sun" aria-hidden="true">☀</span>
      <span className="theme-moon" aria-hidden="true">☾</span>
      <span className="theme-thumb" aria-hidden="true" />
    </button>
  );
}
