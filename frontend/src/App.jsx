import { useEffect, useRef, useState } from "react";
import { BluetoothLink, DemoLink, bluetoothSupported } from "./ble";
import Admin from "./Admin";

const CELL = { e: "seat", o: "seat taken", b: "seat bag", "*": "seat pick" };

function SeatMap({ map }) {
  return (
    <div className="map" aria-label="Seat map of your zone">
      {map.split("|").map((t, i) => (
        <div className="table" key={i}>
          {[0, 1].map((r) => (
            <div className="row" key={r}>
              {[...t.slice(r * 4, r * 4 + 4)].map((c, j) => <i key={j} className={CELL[c]} />)}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

function Floors({ fl, need }) {
  return (
    <ul className="floors">
      {fl.map(([f, empty, max]) => (
        <li key={f} className={max >= need ? "good" : "bad"}>
          <b>Floor {f}</b><span>{empty} empty</span>
          <em>{max >= need ? `${max} together` : `max ${max} together`}</em>
        </li>
      ))}
    </ul>
  );
}

function Student() {
  const link = useRef(null);
  const connectAttempt = useRef(0);
  const [phase, setPhase] = useState("idle");   // idle | linking | linked | asking | done
  const [n, setN] = useState(4);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const useDemo = new URLSearchParams(location.search).has("demo") || !bluetoothSupported();

  async function connect() {
    const attempt = ++connectAttempt.current;
    setErr(""); setPhase("linking");
    try {
      link.current = useDemo ? new DemoLink() : new BluetoothLink();
      await link.current.connect(() => { setPhase("idle"); setErr("Bluetooth link lost."); });
      if (attempt !== connectAttempt.current) return;
      setPhase("linked");
    } catch (e) {
      if (attempt !== connectAttempt.current) return;
      setPhase("idle"); if (e.name !== "NotFoundError") setErr(e.message);
    }
  }
  function continueWithoutBluetooth() {
    connectAttempt.current += 1;
    setErr("");
    link.current = new DemoLink();
    link.current.connect().then(() => setPhase("linked"));
  }
  async function find() {
    setErr(""); setPhase("asking");
    try { setRes(await link.current.ask(n)); setPhase("done"); }
    catch (e) { setErr(e.message); setPhase("linked"); }
  }

  const linked = phase !== "idle" && phase !== "linking";
  return (
    <main className="phone">
      <header>
        <span className="mark">Lib<b>Edge</b></span>
        <span className={`pill ${linked ? "on" : ""}`}>
          <i />{linked ? link.current.name : "Not connected"}
        </span>
      </header>

      {!linked && (
        <section className="hero">
          <h1>Find seats <br />for your group.</h1>
          <p>Connect to the library beacon by Bluetooth. Nothing is sent over mobile data and your location is never tracked.</p>
          <button className="primary" onClick={connect} disabled={phase === "linking"}>
            {phase === "linking" ? "Looking for beacon…" : useDemo ? "Connect (demo link)" : "Connect to library"}
          </button>
          {!useDemo && <button className="ghost" onClick={continueWithoutBluetooth}>
            Continue without Bluetooth
          </button>}
          {!useDemo && <small>Use the web preview with current backend data. Bluetooth recommendations require a nearby library beacon.</small>}
          {!bluetoothSupported() && <small>{navigator.bluetooth
            ? "Bluetooth requires this page to be served securely over HTTPS."
            : "This browser does not support Web Bluetooth. Open in Chrome on Android for the real connection."}</small>}
        </section>
      )}

      {(phase === "linked" || phase === "asking") && (
        <section className="picker">
          <h2>How many students?</h2>
          <div className="stepper">
            <button onClick={() => setN(Math.max(1, n - 1))} aria-label="fewer">−</button>
            <output>{n}</output>
            <button onClick={() => setN(Math.min(12, n + 1))} aria-label="more">+</button>
          </div>
          <button className="primary" onClick={find} disabled={phase === "asking"}>
            {phase === "asking" ? "Checking every floor…" : "Find our seats"}
          </button>
        </section>
      )}

      {phase === "done" && res && (
        <section className="result">
          {res.ok ? (<>
            <p className="eyebrow">Best match for {res.g}</p>
            <h2>Floor {res.f}<span> · {res.z}</span></h2>
            <div className="chips">
              <span><b>{res.n}</b> adjacent seats</span>
              <span><b>{res.q}</b> noise</span>
              <span><b>~{res.t}s</b> walk</span>
              <span><b>{res.o}%</b> full</span>
            </div>
            <SeatMap map={res.map} />
            <p className="legend"><i className="seat pick" /> your seats <i className="seat" /> free <i className="seat taken" /> taken</p>
            <Floors fl={res.fl} need={res.g} />
            <p className="note">Seats are not held for you. Head over now, availability changes live.</p>
          </>) : (<>
            <p className="eyebrow">No block of {res.g}</p>
            <h2>No zone has {res.g} seats together</h2>
            <p>The largest free block right now is <b>{res.best}</b>. Try a smaller group or split in two.</p>
            <Floors fl={res.fl} need={res.g} />
          </>)}
          <button className="ghost" onClick={() => setPhase("linked")}>Search again</button>
        </section>
      )}
      {err && <p className="err" role="alert">{err}</p>}
    </main>
  );
}

export default function App() {
  const [admin, setAdmin] = useState(location.hash === "#admin");
  useEffect(() => {
    const f = () => setAdmin(location.hash === "#admin");
    addEventListener("hashchange", f); return () => removeEventListener("hashchange", f);
  }, []);
  return admin ? <Admin /> : <Student />;
}
