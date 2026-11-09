// a race is a random walk: every step each duck draws its step length from
// the chosen distribution (all three have mean 1), and the first duck to
// cross FINISH wins. the crossing is interpolated within the step, and the
// timer's whole duration is mapped onto [0, end], so the winner touches the
// line exactly at zero and nobody touches it before.
export const FINISH = 60;
const SIGMA = 1.5;  // normal step sd: about a quarter of steps go backwards
// capital-letter edge (normal only): each A-Z adds MU_PER_CAP to the mean
// step, capped at 10 capitals. 10 capitals vs none wins head-to-head about
// 95% of the time (measured by simulation, 100k races).
const MU_PER_CAP = 0.05;

export function mulberry32(seed) {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const STEP = {
  normal: (rand, mu) => mu + SIGMA * Math.sqrt(-2 * Math.log(1 - rand())) * Math.cos(2 * Math.PI * rand()),
  uniform: (rand) => 2 * rand(),
  exponential: (rand) => -Math.log(1 - rand()),
};

// returns { paths, end, winner }: paths[i][k] is duck i's position after k
// steps, end is the fractional step at which the winner crosses FINISH.
export function simulateRace(seed, names, dist) {
  const rand = mulberry32(seed);
  const step = STEP[dist];
  const mus = names.map(
    (name) => 1 + MU_PER_CAP * Math.min((name.match(/[A-Z]/g) || []).length, 10));
  const paths = names.map(() => [0]);
  for (let k = 1; ; k++) {
    let end = Infinity, winner = -1;
    paths.forEach((p, i) => {
      const prev = p[k - 1], next = prev + step(rand, mus[i]);
      p.push(next);
      if (next >= FINISH) {
        const t = k - 1 + (FINISH - prev) / (next - prev);
        if (t < end) { end = t; winner = i; }
      }
    });
    if (winner >= 0) return { paths, end, winner };
  }
}

// on-screen positions in [0, 1] at fraction frac of the timer, linearly
// interpolated between steps. ducks that stepped behind the start sit at 0.
export function positionsAt({ paths, end }, frac) {
  const t = frac * end;
  const k = Math.min(Math.floor(t), paths[0].length - 2);  // guard t == last step exactly
  return paths.map(
    (p) => Math.max(0, Math.min(1, (p[k] + (p[k + 1] - p[k]) * (t - k)) / FINISH)));
}
