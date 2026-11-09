import { useEffect, useRef, useState } from "react";
import ThemeToggle from "./ThemeToggle";
import { ZONE_LOCATIONS } from "./zoneLocations";

const SEAT_STATUS = {
  empty: "Available",
  occupied: "Occupied",
  object: "Item on seat",
  unknown: "Unknown",
};

function Header({ theme, onThemeChange, live }) {
  return (
    <header>
      <span className="mark">Lib<b>Edge</b> <small>Library staff</small></span>
      <div className="header-actions">
        <a className="nav-link" href="#">Student view</a>
        <ThemeToggle theme={theme} onChange={onThemeChange} />
        <span className={`pill ${live ? "on" : ""}`}><i />{live ? "Connected" : "Reconnecting"}</span>
      </div>
    </header>
  );
}

function ZoneMap({ floor, zone }) {
  const seats = zone.seats || [];
  const tables = [...new Set(seats.map((seat) => seat.table))].sort((a, b) => a - b);
  return (
    <article className="zone-map-card">
      <div className="zone-map-heading">
        <h3>{zone.label}</h3>
        <span>{zone.occ}% occupied</span>
      </div>
      <p className="zone-location">{ZONE_LOCATIONS[`${floor}:${zone.label}`]}</p>
      <p className="zone-metrics">
        <span><b>{zone.empty}</b> available</span>
        <span><b>{zone.max_group}</b> together</span>
        <span><b>{Math.round(zone.noise)}</b> dB</span>
      </p>
      {tables.length ? (
        <div className="zone-tables" aria-label={`Floor ${floor} ${zone.label} seat map`}>
          {tables.map((table) => (
            <section className="seat-table" key={table} aria-label={`Table ${table + 1}`}>
              <h4>Table {table + 1}</h4>
              {[0, 1].map((row) => (
                <ul className="seat-row" key={row} aria-label={`Row ${row + 1}`}>
                  {seats.filter((seat) => seat.table === table && seat.row === row)
                    .sort((a, b) => a.column - b.column)
                    .map((seat) => {
                      const status = SEAT_STATUS[seat.state] || SEAT_STATUS.unknown;
                      return <li
                        key={seat.id}
                        className={`seat-cell ${seat.state || "unknown"}`}
                        aria-label={`Seat ${seat.id}: ${status}`}
                        title={`${seat.id}: ${status}`}
                        tabIndex={0}
                      >{seat.row * 4 + seat.column + 1}</li>;
                    })}
                </ul>
              ))}
            </section>
          ))}
        </div>
      ) : <p className="map-pending">Seat details are unavailable. Check that the server is running the latest version.</p>}
    </article>
  );
}

function CameraDialog({ dialogRef, onClose }) {
  return (
    <dialog ref={dialogRef} className="camera-dialog" onClose={onClose} aria-labelledby="camera-title">
      <div className="camera-dialog-header">
        <h2 id="camera-title">Live camera feed</h2>
        <button className="icon-button" type="button" onClick={() => dialogRef.current?.close()} aria-label="Close">×</button>
      </div>
      <div className="camera-placeholder" role="img" aria-label="Camera feed is not connected">
        <span>Camera feed not connected</span>
      </div>
      <p>The camera feed will be available after camera integration is connected.</p>
      <button className="secondary-button" type="button" onClick={() => dialogRef.current?.close()}>Close</button>
    </dialog>
  );
}

export default function Admin({ theme, onThemeChange }) {
  const [s, setS] = useState(null);
  const [live, setLive] = useState(false);
  const [selectedFloor, setSelectedFloor] = useState(1);
  const [cameraOpen, setCameraOpen] = useState(false);
  const cameraDialog = useRef(null);

  useEffect(() => {
    let ws, t, dead = false;
    const open = () => {
      ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
      ws.onopen = () => setLive(true);
      ws.onmessage = (e) => {
        try {
          const next = JSON.parse(e.data);
          if (Array.isArray(next.floors)) setS(next);
        } catch { setLive(false); }
      };
      ws.onclose = () => { setLive(false); if (!dead) t = setTimeout(open, 2000); };
    };
    open(); return () => { dead = true; clearTimeout(t); ws?.close(); };
  }, []);

  useEffect(() => {
    if (cameraOpen && cameraDialog.current && !cameraDialog.current.open) cameraDialog.current.showModal();
  }, [cameraOpen]);

  const floors = s?.floors || [];
  const activeFloor = floors.find((floor) => floor.floor === selectedFloor) || floors[0];
  const activeNode = s?.nodes?.find((node) => node.floor === activeFloor?.floor);
  const dataFreshness = !activeNode ? "Source status unavailable"
    : activeNode.mode === "simulated" ? "Demo occupancy data"
      : activeNode.age_seconds === null ? "No seat update received yet"
        : `Floor data last reported ${activeNode.age_seconds}s ago`;

  if (!s) return <main className="admin">
    <Header theme={theme} onThemeChange={onThemeChange} live={live} />
    <h1 className="dashboard-title">Library overview</h1>
    <p className="dashboard-intro" role="status">Waiting for the library server. This page reconnects automatically.</p>
  </main>;

  return (
    <main className="admin">
      <Header theme={theme} onThemeChange={onThemeChange} live={live} />
      <h1 className="dashboard-title">Library overview</h1>
      <p className="dashboard-intro">Check occupancy, compare floors, and inspect seat availability by zone.</p>

      <section className="kpis" aria-label="Library summary">
        <div><small>Total occupancy</small><strong>{s.occupancy}%</strong></div>
        <div><small>Available seats</small><strong>{s.available}</strong></div>
        <div><small>Quietest zone</small><strong>{s.quietest}</strong></div>
        <div><small>Largest group available</small><strong>{s.largest}</strong><em>{s.largest_size} seats</em></div>
      </section>

      <section aria-labelledby="floor-overview-title">
        <h2 id="floor-overview-title" className="section-title">Floor overview</h2>
        <div className="grid">
          {floors.map((floor) => (
            <article key={floor.floor}>
              <h3>Floor {floor.floor}<span>{floor.occ}% occupied</span></h3>
              <div className="bar" aria-label={`${floor.occ}% occupied`}><div style={{ width: `${floor.occ}%` }} /></div>
              <table><thead><tr><th scope="col">Zone</th><th scope="col">Free</th><th scope="col">Block</th><th scope="col">dB</th></tr></thead>
                <tbody>{floor.zones.map((zone) => (
                  <tr key={zone.label}><th scope="row">{zone.label}</th><td>{zone.empty}</td><td>{zone.max_group}</td><td>{Math.round(zone.noise)}</td></tr>
                ))}</tbody>
              </table>
            </article>
          ))}
        </div>
      </section>

      <section className="floor-explorer" aria-labelledby="floor-explorer-title">
        <div className="explorer-header">
          <div>
            <h2 id="floor-explorer-title" className="section-title">Explore floor maps</h2>
            <p>Select a floor to inspect seat status, zone availability, and noise.</p>
            <div className="map-stream-status" aria-live="polite">
              <i className={live ? "connected" : "disconnected"} />
              <strong>{live ? "Receiving updates every 2 seconds" : "Connection lost · retrying"}</strong>
              <span>{dataFreshness}</span>
            </div>
          </div>
          <button className="secondary-button" type="button" onClick={() => setCameraOpen(true)}>Camera feed · preview</button>
        </div>
        <nav className="floor-picker" aria-label="Choose a floor">
          {floors.map((floor) => <button
            key={floor.floor}
            type="button"
            className={activeFloor?.floor === floor.floor ? "selected" : ""}
            aria-pressed={activeFloor?.floor === floor.floor}
            onClick={() => setSelectedFloor(floor.floor)}
          >Floor {floor.floor}</button>)}
        </nav>
        {activeFloor && <>
          <div className="floor-detail-heading">
            <h3>Floor {activeFloor.floor}</h3>
            <p>{activeFloor.empty} available · {activeFloor.occ}% occupied</p>
          </div>
          <div className="seat-legend" aria-label="Seat status legend">
            <span><i className="empty" />Available</span>
            <span><i className="occupied" />Occupied</span>
            <span><i className="object" />Item on seat</span>
            <span><i className="unknown" />Unknown</span>
          </div>
          <div className="zone-map-grid">
            {activeFloor.zones.map((zone) => <ZoneMap key={zone.label} floor={activeFloor.floor} zone={zone} />)}
          </div>
        </>}
        <p className="admin-help">Numbers run left to right within each table. Focus or hover over a seat for its ID and status.</p>
      </section>

      <section className="grid node-grid" aria-label="Edge node status">
        {s.nodes?.map((node) => {
          const age = node.age_seconds;
          const online = age !== null && age <= 15;
          const status = node.mode === "simulated" ? "Simulated" : online ? "Reporting" : age === null ? "Waiting for update" : "Stale";
          const source = node.mode === "simulated" ? "demo simulator" : node.mode === "mongo" ? "MongoDB snapshot" : "edge node";
          return <article key={`node-${node.floor}`}>
            <h3>Floor {node.floor} {source}<span>{status}</span></h3>
            <p>{node.mode === "simulated" ? "Occupancy is generated by the demo simulator." : age === null ? "No occupancy update received yet." : `Last update ${age}s ago.`}</p>
          </article>;
        })}
      </section>

      <footer>LibEdge · Library seating</footer>
      {cameraOpen && <CameraDialog dialogRef={cameraDialog} onClose={() => setCameraOpen(false)} />}
    </main>
  );
}
