import { useEffect, useRef, useState } from "react";
import { getRecommendation } from "./api";
import Admin from "./Admin";
import { ZONE_LOCATIONS } from "./zoneLocations";
import ThemeToggle from "./ThemeToggle";
import ViewToggle from "./ViewToggle";
import floorGeometry from "./floorGeometry.json";

const CELL = { e: "seat", o: "seat taken", b: "seat bag", "*": "seat pick", u: "seat unknown" };

function SeatMap({ map }) {
  return (
    <div className="map" aria-label="Seat map of your zone">
      {map.split("|").map((t, i) => (
        <div className="table" key={i}>
          <span className="table-label">Table {i + 1}</span>
          {[0, 1].map((r) => (
            <div className="row" key={r}>
              {[...t.slice(r * 4, r * 4 + 4)].map((c, j) => <span key={j} className={CELL[c] || "seat unknown"} role="img" aria-label={`Table ${i + 1}, row ${r + 1}, seat ${j + 1}: ${{e: "available", o: "occupied", b: "item on seat", "*": "suggested", u: "unknown"}[c] || "unknown"}`}>{r * 4 + j + 1}</span>)}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

function ZoneOptions({ options = [], need, bestFloor, bestZone, selectedFloor, selectedZone, choices = [], onSelect, preferQuiet }) {
  const hasFit = options.some(([, , , max]) => max >= need);
  const visibleOptions = hasFit ? options.filter(([, , , max]) => max >= need) : options;
  return (
    <section className="zone-options">
      <h3>{hasFit ? `Zones that fit ${need} students` : "Zone capacity"}</h3>
      <ul className="floors">
        {visibleOptions.map(([floor, zone, empty, max, noise]) => {
          const isBest = floor === bestFloor && zone === bestZone;
          const choice = choices.find((item) => item.f === floor && item.z === zone);
          const selected = floor === selectedFloor && zone === selectedZone;
          return <li key={`${floor}-${zone}`} className={`${max >= need ? "good" : "bad"}${selected ? " best" : ""}`}>
            <button type="button" className="zone-option-button" disabled={!choice} aria-pressed={selected} onClick={() => onSelect(choice)}>
              <b>Floor {floor} · {zone}<small>{ZONE_LOCATIONS[`${floor}:${zone}`]}</small></b><span>{empty} empty{Number.isFinite(noise) ? ` · ${noise} dB` : ""}</span>
              <em>{selected ? (isBest ? "Best match · Selected" : "Selected") : isBest ? "Best match" : max >= need ? `${max} together` : `max ${max} together`}</em>
            </button>
          </li>;
        })}
      </ul>
      {preferQuiet && hasFit && <p className="note">Results give more weight to quieter zones.</p>}
      {!hasFit && <p className="note">No zone currently has {need} adjacent seats. The list shows each zone’s largest available group.</p>}
    </section>
  );
}

function SpeakerIcon({ muted = false }) {
  return <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M3 10v4h4l5 4V6l-5 4H3Z" />
    {muted
      ? <><path d="m16 9 5 6" /><path d="m21 9-5 6" /></>
      : <><path d="M16 9.5a4 4 0 0 1 0 5" /><path d="M19 7a7.5 7.5 0 0 1 0 10" /></>}
  </svg>;
}

function QuietPreferenceCopy({ filled = false }) {
  return (
    <span className={`preference-copy${filled ? " preference-copy-filled" : ""}`} aria-hidden={filled || undefined}>
      {filled ? <span className="quiet-icon-placeholder" /> : <span className="quiet-icon"><SpeakerIcon /></span>}
      <span><b>Prefer a quieter place</b><small>Prioritise lower-noise zones when suitable seats are available.</small></span>
    </span>
  );
}

function LoadingLabel({ children }) {
  return <><span className="button-spinner" aria-hidden="true" />{children}</>;
}

function LocateMap({ result, theme, onClose }) {
  const dialogRef = useRef(null);
  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog && !dialog.open) dialog.showModal();
    return () => { if (dialog?.open) dialog.close(); };
  }, []);
  const firstSeat = result.seat_ids?.[0];
  const seatMatch = typeof firstSeat === "string" ? firstSeat.match(/^(\d+)-([ABEW])(\d)([01])([0-3])$/) : null;
  const zone = result.zone_id;
  const table = seatMatch ? Number(seatMatch[3]) : -1;
  const counts = { "1:A": 3, "1:B": 2, "2:A": 3, "2:B": 3, "3:East": 2, "3:West": 3 };
  const valid = seatMatch && Number(seatMatch[1]) === result.f && seatMatch[2] === zone?.[0] && table < (counts[`${result.f}:${zone}`] || 0);
  const upper = zone === "A" || zone === "East";
  const geometry = floorGeometry[result.f];
  const tableX = (upper ? geometry?.upperX : geometry?.lowerX)?.[table] ?? 0;
  const tableY = upper ? geometry?.upperY : geometry?.lowerY;
  const endX = tableX + 50;
  const endY = upper ? tableY + 60 : tableY - 15;
  const path = `M 795 202 L 750 202 L 750 380 L ${endX} 380 L ${endX} ${endY}`;
  return <dialog ref={dialogRef} className="locate-panel" aria-labelledby="locate-title" onCancel={(event) => { event.preventDefault(); onClose(); }} onClick={(event) => {
    if (event.target !== event.currentTarget) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) onClose();
  }}>
    <div className="locate-header"><div><h3 id="locate-title">Directions to your seats</h3><p>Floor {result.f} · {result.z}{valid ? ` · Table ${table + 1}` : ""}</p></div><button type="button" className="locate-close" aria-label="Close map" onClick={onClose}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" /></svg></button></div>
    <p className="locate-notice">Follow the blue route to your table. Seats are not reserved.</p>
    <div className="locate-map">
      <img src={`/maps/floor-${result.f}${theme === "dark" ? "-dark" : ""}.svg`} alt={`Floor ${result.f} map with zones and landmarks`} />
      {valid && <svg viewBox="0 0 1000 700" aria-hidden="true" className="locate-overlay">
        <defs><marker id="route-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#1676e8" /></marker></defs>
        <rect x={tableX - 5} y={tableY - 16} width="110" height="77" rx="10" fill="none" stroke="#1676e8" strokeWidth="4" />
        <path d={path} fill="none" stroke="#fff" strokeWidth="11" strokeLinecap="round" strokeLinejoin="round" />
        <path d={path} fill="none" stroke="#1676e8" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" markerEnd="url(#route-arrow)" />
      </svg>}
    </div>
    {valid ? <p className="locate-directions">Start at the lift on floor {result.f}. Follow the blue line along the corridor to {result.z}, table {table + 1}. Suggested seat IDs: {result.seat_ids.join(", ")}.</p> : <p role="status" className="locate-directions">Seat details are unavailable. Refresh the recommendation after restarting the updated backend.</p>}
  </dialog>;
}

function Student({ theme, onThemeChange, view, onViewChange }) {
  const request = useRef(null);
  const [phase, setPhase] = useState("ready");
  const [n, setN] = useState(4);
  const [preferQuiet, setPreferQuiet] = useState(false);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showLocate, setShowLocate] = useState(false);
  const [selectedChoice, setSelectedChoice] = useState(null);
  const displayRes = selectedChoice || res;
  useEffect(() => () => request.current?.abort(), []);

  async function find(refresh = false) {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    const timeout = setTimeout(() => controller.abort(), 10000);
    const startedAt = performance.now();
    setErr("");
    if (refresh) setIsRefreshing(true);
    else setPhase("asking");
    try {
      const result = await getRecommendation(n, preferQuiet, controller.signal);
      const remaining = 500 - (performance.now() - startedAt);
      if (remaining > 0) await new Promise((resolve) => setTimeout(resolve, remaining));
      setRes(result);
      setSelectedChoice(null);
      setShowLocate(false);
      setPhase("done");
    } catch (error) {
      const remaining = 500 - (performance.now() - startedAt);
      if (remaining > 0) await new Promise((resolve) => setTimeout(resolve, remaining));
      setErr(error.name === "AbortError"
        ? "The search timed out. Check your connection and try again."
        : "Cannot reach the library server. Please try again in a moment.");
      if (!refresh) setPhase("ready");
    } finally {
      clearTimeout(timeout);
      setIsRefreshing(false);
    }
  }

  return (
    <main className="phone">
      <header>
        <span className="mark">Lib<b>Edge</b></span>
        <div className="header-actions">
          <ViewToggle view={view} onChange={onViewChange} />
          <ThemeToggle theme={theme} onChange={onThemeChange} />
          <a className="nav-link" href="#admin">Staff view</a>
        </div>
      </header>

      {(phase === "ready" || phase === "asking") && (
        <section className="picker">
          <p className="eyebrow">Library seating</p>
          <h1>Find a place to study</h1>
          <p className="picker-intro">Choose your group size. We’ll find seats together and show you where to go.</p>
          <h2>How many people?</h2>
          <div className="stepper">
            <button onClick={() => setN(Math.max(1, n - 1))} disabled={n === 1 || phase === "asking"} aria-label="Fewer people">−</button>
            <output aria-live="polite">{n}<small>{n === 1 ? "person" : "people"}</small></output>
            <button onClick={() => setN(Math.min(12, n + 1))} disabled={n === 12 || phase === "asking"} aria-label="More people">+</button>
          </div>
          <label className={`preference${preferQuiet ? " active" : ""}`}>
            <input
              type="checkbox"
              disabled={phase === "asking"}
              checked={preferQuiet}
              onChange={(event) => setPreferQuiet(event.target.checked)}
            />
            <QuietPreferenceCopy />
            <QuietPreferenceCopy filled />
            <span className="quiet-icon-active" aria-hidden="true"><SpeakerIcon muted /></span>
          </label>
          <button className="primary" onClick={() => find()} disabled={phase === "asking"}>
            {phase === "asking" ? <LoadingLabel>Checking every floor…</LoadingLabel> : "Find seats"}
          </button>
        </section>
      )}

      {phase === "done" && res && (
        <section className="result">
          {res.ok ? (<>
            <div className="result-summary">
              <p className="eyebrow">{selectedChoice ? `Selected zone for ${res.g}` : res.p ? `Quieter match for ${res.g}` : `Best match for ${res.g}`}</p>
              <h2>Floor {displayRes.f}<span> · {displayRes.z}</span><small className="place-note">{ZONE_LOCATIONS[`${displayRes.f}:${displayRes.z}`]}</small></h2>
              <div className="chips">
                <span><b>{displayRes.n}</b> adjacent seats</span>
                <span><b>{displayRes.q}</b> noise</span>
                <span><b>~{displayRes.t}s</b> walk</span>
                <span><b>{displayRes.o}%</b> full</span>
              </div>
              <button type="button" className="secondary-button locate-button" aria-haspopup="dialog" aria-expanded={showLocate} onClick={() => setShowLocate(true)}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s7-6 7-12a7 7 0 1 0-14 0c0 6 7 12 7 12Z"/><circle cx="12" cy="9" r="2.5"/></svg>Locate seats</button>
            </div>
            <SeatMap map={displayRes.map} />
            <p className="legend"><i className="seat pick" /> suggested <i className="seat" /> available <i className="seat taken" /> occupied <i className="seat bag" /> item <i className="seat unknown" /> unknown</p>
            <ZoneOptions options={res.oz} need={res.g} bestFloor={res.f} bestZone={res.z} selectedFloor={displayRes.f} selectedZone={displayRes.z} choices={res.choices || []} onSelect={(choice) => { setSelectedChoice(choice); setShowLocate(false); }} preferQuiet={res.p === 1} />
          </>) : (<>
            <p className="eyebrow">No block of {res.g}</p>
            <h2>No zone has {res.g} seats together</h2>
            <p>The largest available block right now is <b>{res.best}</b>. Try a smaller group or split in two.</p>
            <ZoneOptions options={res.oz} need={res.g} preferQuiet={res.p === 1} />
          </>)}
          {res.ok && showLocate && <LocateMap result={displayRes} theme={theme} onClose={() => setShowLocate(false)} />}
          <button className="ghost" onClick={() => setPhase("ready")}>Change search</button>
          <button className="ghost" onClick={() => find(true)} disabled={isRefreshing}>
            {isRefreshing ? <LoadingLabel>Refreshing availability…</LoadingLabel> : "Refresh availability"}
          </button>
        </section>
      )}
      {err && <p className="err" role="alert">{err}</p>}
    </main>
  );
}

function CameraManagerPage({ view, onViewChange }) {
  const [available, setAvailable] = useState(null);
  useEffect(() => {
    const controller = new AbortController();
    fetch('/camera-manager/api/cameras', { signal: controller.signal }).then((response) => setAvailable(response.ok)).catch((error) => { if (error.name !== 'AbortError') setAvailable(false); });
    return () => controller.abort();
  }, []);
  return <main className="camera-manager-page"><header><span className="mark">Lib<b>Edge</b> <small>Camera manager</small></span><div className="header-actions"><ViewToggle view={view} onChange={onViewChange} /><a className="nav-link" href="#admin">← Staff dashboard</a></div></header>
    {available === null ? <p role="status">Connecting to camera manager…</p> : available ? <iframe title="Camera management" className="camera-manager-frame" src="/camera-manager/" /> : <div className="manager-offline" role="status"><h1>Camera manager is unavailable</h1><p>Check the backend startup log for camera manager errors, then reload this page.</p><a className="nav-link" href="#admin">Return to staff dashboard</a></div>}
  </main>;
}

export default function App() {
  const [route, setRoute] = useState(location.hash);
  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem("libedge-theme") === "dark" ? "dark" : "light"; }
    catch { return "light"; }
  });
  const [view, setView] = useState(() => {
    try { return localStorage.getItem("libedge-view") === "phone" ? "phone" : "desktop"; }
    catch { return "desktop"; }
  });
  useEffect(() => {
    const f = () => setRoute(location.hash);
    addEventListener("hashchange", f); return () => removeEventListener("hashchange", f);
  }, []);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("libedge-theme", theme); } catch { /* Theme still applies for this session. */ }
  }, [theme]);
  useEffect(() => {
    document.documentElement.dataset.view = view;
    try { localStorage.setItem("libedge-view", view); } catch { /* View still applies for this session. */ }
  }, [view]);
  const staff = route === "#admin" || route === "#cameras";
  const content = route === "#cameras" ? <CameraManagerPage view={view} onViewChange={setView} /> : staff ? <Admin theme={theme} onThemeChange={setTheme} view={view} onViewChange={setView} /> : <Student theme={theme} onThemeChange={setTheme} view={view} onViewChange={setView} />;
  return staff && view !== "phone" ? content : <div className="student-shell"><div className="phone-frame">{staff ? <div className="phone staff-phone">{content}</div> : content}</div></div>;
}
