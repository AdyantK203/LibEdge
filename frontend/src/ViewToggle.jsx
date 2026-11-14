export default function ViewToggle({ view, onChange }) {
  const isPhone = view === "phone";
  return (
    <button
      type="button"
      className="view-toggle"
      role="switch"
      aria-label="Phone preview"
      aria-checked={isPhone}
      title={`Switch to ${isPhone ? "laptop" : "phone"} view`}
      onClick={() => onChange(isPhone ? "desktop" : "phone")}
    >
      <span aria-hidden="true">▭</span>
      <span aria-hidden="true">▯</span>
    </button>
  );
}
