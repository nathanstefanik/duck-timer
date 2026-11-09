import { mulberry32, simulateRace, positionsAt } from "./race.js";

const code = location.pathname.split("/").pop();

let state = null;
let offset = 0;  // server clock minus local clock, in seconds
let ducks = [];  // built once the first state arrives and names are known
let race = null;      // memoized simulateRace result
let raceSeed = null;  // seed race was simulated for

const clock = document.getElementById("clock");
const pond = document.getElementById("pond");
const banner = document.getElementById("banner");
document.getElementById("code").textContent = code;
document.title = `${code} — duck race timer`;

const BODIES = ["#f5d442", "#fdfdf2", "#b07b3f", "#7fb069", "#d96c8e", "#8ab6d6", "#c9b1ff", "#f2a65a"];

// hand-drawn, public domain by construction. derpiness is seeded:
// independently sized googly eyes with independently wandering pupils.
function duckSvg(rand) {
  const body = BODIES[Math.floor(rand() * BODIES.length)];
  const eye = (cx) => {
    const r = 2.6 + 2.2 * rand();
    const dx = (rand() - 0.5) * 2.6;
    const dy = (rand() - 0.5) * 2.6;
    return `<circle cx="${cx}" cy="13" r="${r.toFixed(1)}" fill="#fff" stroke="#333" stroke-width="0.6"/>
      <circle cx="${(cx + dx).toFixed(1)}" cy="${(13 + dy).toFixed(1)}" r="1.7" fill="#222"/>`;
  };
  return `<svg viewBox="0 0 72 48" width="48" height="32">
    <polygon points="2,26 16,30 6,38" fill="${body}"/>
    <ellipse cx="28" cy="33" rx="22" ry="12" fill="${body}"/>
    <ellipse cx="25" cy="35" rx="11" ry="6" fill="rgba(0,0,0,0.12)"/>
    <circle cx="46" cy="16" r="11" fill="${body}"/>
    <polygon points="55,13 70,17 55,21" fill="#f28c28"/>
    ${eye(43)}${eye(50)}
  </svg>`;
}

function buildPond(names, lookSeed) {
  const rand = mulberry32(lookSeed);
  ducks = names.map((name) => {
    const lane = document.createElement("div");
    lane.className = "lane";
    const rank = document.createElement("span");
    rank.className = "rank";
    const water = document.createElement("div");
    water.className = "water";
    const duck = document.createElement("span");
    duck.className = "duck";
    duck.innerHTML = duckSvg(rand);
    const label = document.createElement("span");
    label.className = "duck-name";
    label.textContent = name;  // textContent, not innerHTML: names are user input
    duck.prepend(label);
    water.appendChild(duck);
    lane.append(rank, water);
    pond.appendChild(lane);
    return { duck, rank, lane };
  });
}

function ordinal(n) {
  const suffix = n % 10 === 1 && n % 100 !== 11 ? "st"
    : n % 10 === 2 && n % 100 !== 12 ? "nd"
    : n % 10 === 3 && n % 100 !== 13 ? "rd" : "th";
  return `${n}${suffix}`;
}

function fmt(totalS) {
  const t = Math.max(0, totalS);
  const d = Math.floor(t / 86400);
  const h = Math.floor((t % 86400) / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = Math.floor(t % 60);
  const pad = (v) => String(v).padStart(2, "0");
  if (d) return `${d}d ${pad(h)}:${pad(m)}:${pad(s)}`;
  if (h) return `${h}:${pad(m)}:${pad(s)}`;
  return `${m}:${pad(s)}`;
}

function render() {
  if (state) {
    if (state.started_at === null) {
      clock.textContent = fmt(state.duration_s);
      banner.textContent = "";
      ducks.forEach((d) => {
        d.duck.style.setProperty("--pos", 0);
        d.rank.textContent = "";
        d.lane.classList.remove("leader");
      });
    } else {
      const elapsed = Math.min(Date.now() / 1000 + offset - state.started_at, state.duration_s);
      const frac = Math.max(0, elapsed) / state.duration_s;
      clock.textContent = fmt(Math.ceil(state.duration_s - elapsed));
      // the race is a pure function of the seed, so simulate once per start
      // and every viewer replays the identical walk, join-time aside.
      if (state.seed !== raceSeed) {
        race = simulateRace(state.seed, state.names, state.dist);
        raceSeed = state.seed;
      }
      const positions = positionsAt(race, frac);
      // ranks come from on-screen position: they flicker when ducks trade
      // places, and reveal nothing the eye can't see.
      const order = positions.map((p, i) => [p, i]).sort((a, b) => b[0] - a[0]);
      order.forEach(([, i], place) => {
        ducks[i].rank.textContent = ordinal(place + 1);
        ducks[i].lane.classList.toggle("leader", place === 0);
      });
      positions.forEach((p, i) => ducks[i].duck.style.setProperty("--pos", p));
      banner.textContent = frac >= 1 ? `${state.names[race.winner]} wins!` : "";
    }
  }
  requestAnimationFrame(render);
}

function adopt(data) {
  if (!ducks.length) buildPond(data.names, data.look_seed);
  if (data.title) {
    const title = document.getElementById("title");
    title.textContent = data.title;
    title.hidden = false;
    document.title = `${data.title} — duck race timer`;
  }
  state = data;
  offset = data.server_now - Date.now() / 1000;
}

async function act(action) {
  const resp = await fetch(`/api/t/${code}/${action}`, { method: "POST" });
  if (resp.ok) adopt(await resp.json());
}

document.getElementById("start").addEventListener("click", (e) => {
  e.preventDefault();
  act("start");
});
document.getElementById("reset").addEventListener("click", (e) => {
  e.preventDefault();
  act("reset");
});

// the SSE stream sends state immediately on connect, so no initial fetch.
// the browser auto-reconnects on network errors; a non-200 (e.g. 404 after
// the timer expired or the server restarted) closes it for good.
const es = new EventSource(`/api/t/${code}/stream`);
es.onmessage = (e) => adopt(JSON.parse(e.data));
es.onerror = () => {
  if (es.readyState === EventSource.CLOSED) clock.textContent = "no such timer";
};

requestAnimationFrame(render);
