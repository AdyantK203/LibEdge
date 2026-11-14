// Requests use the same host as the page; Vite proxies them during development.
const WALK = { "1:Zone A": 15, "1:Zone B": 25, "2:Zone A": 45, "2:Zone B": 40, "3:East": 75, "3:West": 70 };

function choicesFromState(state, recommendation) {
  const choices = [];
  for (const floor of state.floors || []) for (const zone of floor.zones || []) {
    if (!Array.isArray(zone.seats)) continue;
    const seats = zone.seats;
    const available = new Map(seats.filter((seat) => seat.state === "empty").map((seat) => [`${seat.table}:${seat.row}:${seat.column}`, seat]));
    const groups = [];
    while (available.size) {
      const queue = [available.keys().next().value];
      const group = [];
      while (queue.length) {
        const key = queue.shift();
        const seat = available.get(key);
        if (!seat) continue;
        available.delete(key);
        group.push(seat);
        for (const [r, c] of [[seat.row, seat.column + 1], [seat.row, seat.column - 1], [seat.row + 1, seat.column], [seat.row - 1, seat.column]]) queue.push(`${seat.table}:${r}:${c}`);
      }
      if (group.length >= recommendation.g) groups.push(group);
    }
    if (!groups.length) continue;
    groups.sort((a, b) => a.length - b.length);
    const selected = groups[0].slice(0, recommendation.g);
    const selectedIds = new Set(selected.map((seat) => seat.id));
    const tables = [...new Set(seats.map((seat) => seat.table))].sort((a, b) => a - b);
    const map = tables.map((table) => [0, 1].map((row) => [0, 1, 2, 3].map((column) => {
      const seat = seats.find((item) => item.table === table && item.row === row && item.column === column);
      return selectedIds.has(seat?.id) ? "*" : ({ empty: "e", occupied: "o", object: "b", unknown: "u" }[seat?.state] || "u");
    }).join("")).join("")).join("|");
    const noise = zone.noise;
    choices.push({ ...recommendation, f: floor.floor, z: zone.label, zone_id: zone.label.replace(/^Zone /, ""), seat_ids: selected.map((seat) => seat.id), n: zone.max_group, q: noise < 36 ? "low" : noise < 46 ? "moderate" : "high", t: WALK[`${floor.floor}:${zone.label}`], o: zone.occ, map });
  }
  return choices;
}

export async function getRecommendation(group, quiet, signal) {
  const query = new URLSearchParams({ group, quiet });
  const response = await fetch(`/api/recommend?${query}`, { signal });
  if (!response.ok) throw new Error("The library server could not complete the search. Please try again.");
  const recommendation = await response.json();
  if (recommendation.ok && !Array.isArray(recommendation.choices)) {
    const stateResponse = await fetch("/api/state", { signal });
    if (!stateResponse.ok) throw new Error("Could not load zone seat maps.");
    recommendation.choices = choicesFromState(await stateResponse.json(), recommendation);
    const current = recommendation.choices.find((choice) => choice.f === recommendation.f && choice.z === recommendation.z);
    if (current) Object.assign(recommendation, current, { choices: recommendation.choices });
  }
  return recommendation;
}
