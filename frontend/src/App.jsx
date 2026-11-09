import { useEffect, useRef, useState } from "react";
import { getRecommendation } from "./api";
import Admin from "./Admin";
import { ZONE_LOCATIONS } from "./zoneLocations";
import ThemeToggle from "./ThemeToggle";

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

function ZoneOptions({ options = [], need, bestFloor, bestZone, preferQuiet }) {
  const hasFit = options.some(([, , , max]) => max >= need);
  const visibleOptions = hasFit ? options.filter(([, , , max]) => max >= need) : options;
  return (
    <section className="zone-options">
      <h3>{hasFit ? `Zones that fit ${need} students` : "Zone capacity"}</h3>
      <ul className="floors">
        {visibleOptions.map(([floor, zone, empty, max, noise]) => {
          const isBest = floor === bestFloor && zone === bestZone;
          return <li key={`${floor}-${zone}`} className={`${max >= need ? "good" : "bad"}${isBest ? " best" : ""}`}>
            <b>Floor {floor} · {zone}<small>{ZONE_LOCATIONS[`${floor}:${zone}`]}</small></b><span>{empty} empty{Number.isFinite(noise) ? ` · ${noise} dB` : ""}</span>
            <em>{isBest ? "Best match" : max >= need ? `${max} together` : `max ${max} together`}</em>
          </li>;
        })}
      </ul>
      {preferQuiet && hasFit && <p className="note">Results give more weight to quieter zones.</p>}
      {!hasFit && <p className="note">No zone currently has {need} adjacent seats. The list shows each zone’s largest available group.</p>}
    </section>
  );
}

function Student({ theme, onThemeChange }) {
  const request = useRef(null);
  const [phase, setPhase] = useState("ready");
  const [n, setN] = useState(4);
  const [preferQuiet, setPreferQuiet] = useState(false);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => () => request.current?.abort(), []);

  async function find() {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    const timeout = setTimeout(() => controller.abort(), 10000);
    setErr("");
    setPhase("asking");
    try {
      const result = await getRecommendation(n, preferQuiet, controller.signal);
      setRes(result);
      setPhase("done");
    } catch (error) {
      setErr(error.name === "AbortError"
        ? "The search timed out. Check your connection and try again."
        : "Cannot reach the library server. Please try again in a moment.");
      setPhase("ready");
    } finally {
      clearTimeout(timeout);
    }
  }

  return (
    <main className="phone">
      <header>
        <span className="mark">Lib<b>Edge</b></span>
        <div className="header-actions">
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
          <label className="preference">
            <input type="checkbox" disabled={phase === "asking"} checked={preferQuiet} onChange={(event) => setPreferQuiet(event.target.checked)} />
            <span><b>Prefer a quieter place</b><small>Give quieter zones more priority.</small></span>
          </label>
          <button className="primary" onClick={find} disabled={phase === "asking"}>
            {phase === "asking" ? "Checking every floor…" : "Find seats"}
          </button>
        </section>
      )}

      {phase === "done" && res && (
        <section className="result">
          {res.ok ? (<>
            <p className="eyebrow">{res.p ? `Quieter match for ${res.g}` : `Best match for ${res.g}`}</p>
            <h2>Floor {res.f}<span> · {res.z}</span><small className="place-note">Example location: {ZONE_LOCATIONS[`${res.f}:${res.z}`]}</small></h2>
            <div className="chips">
              <span><b>{res.n}</b> adjacent seats</span>
              <span><b>{res.q}</b> noise</span>
              <span><b>~{res.t}s</b> walk</span>
              <span><b>{res.o}%</b> full</span>
            </div>
            <SeatMap map={res.map} />
            <p className="legend"><i className="seat pick" /> suggested <i className="seat" /> available <i className="seat taken" /> occupied <i className="seat bag" /> item <i className="seat unknown" /> unknown</p>
            <ZoneOptions options={res.oz} need={res.g} bestFloor={res.f} bestZone={res.z} preferQuiet={res.p === 1} />
          </>) : (<>
            <p className="eyebrow">No block of {res.g}</p>
            <h2>No zone has {res.g} seats together</h2>
            <p>The largest available block right now is <b>{res.best}</b>. Try a smaller group or split in two.</p>
            <ZoneOptions options={res.oz} need={res.g} preferQuiet={res.p === 1} />
          </>)}
          <button className="ghost" onClick={() => setPhase("ready")}>Change search</button>
          <button className="ghost" onClick={find}>Refresh availability</button>
        </section>
      )}
      {err && <p className="err" role="alert">{err}</p>}
    </main>
  );
}

export default function App() {
  const [admin, setAdmin] = useState(location.hash === "#admin");
  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem("libedge-theme") === "dark" ? "dark" : "light"; }
    catch { return "light"; }
  });
  useEffect(() => {
    const f = () => setAdmin(location.hash === "#admin");
    addEventListener("hashchange", f); return () => removeEventListener("hashchange", f);
  }, []);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("libedge-theme", theme); } catch { /* Theme still applies for this session. */ }
  }, [theme]);
  return admin
    ? <Admin theme={theme} onThemeChange={setTheme} />
    : <Student theme={theme} onThemeChange={setTheme} />;
}
