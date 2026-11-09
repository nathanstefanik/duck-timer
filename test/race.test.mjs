import { test } from "node:test";
import assert from "node:assert/strict";
import { simulateRace, positionsAt } from "../static/race.js";

const DISTS = ["normal", "uniform", "exponential"];
const SIZES = [2, 6, 12];
const SEEDS = 200;
const FRACS = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.99, 0.999];

const names = (n) => Array.from({ length: n }, (_, i) => `duck ${i + 1}`);

test("same seed, names, and dist give an identical race", () => {
  for (const dist of DISTS) {
    const a = simulateRace(12345, names(6), dist);
    const b = simulateRace(12345, names(6), dist);
    assert.deepEqual(a, b);
  }
});

test("winner finishes exactly at frac 1; nobody touches the line before", () => {
  for (const dist of DISTS) {
    for (const n of SIZES) {
      for (let seed = 0; seed < SEEDS; seed++) {
        const race = simulateRace(seed, names(n), dist);
        const final = positionsAt(race, 1);
        final.forEach((p, i) => {
          assert.ok(p >= 0 && p <= 1, `${dist} seed ${seed} duck ${i}: pos ${p} out of [0,1]`);
          if (i === race.winner) {
            assert.ok(Math.abs(p - 1) < 1e-9, `winner pos ${p} not ~1`);
          } else {
            assert.ok(p < final[race.winner], `duck ${i} ties or beats winner`);
          }
        });
        assert.deepEqual(positionsAt(race, 0), Array(n).fill(0));
        for (const frac of FRACS) {
          for (const p of positionsAt(race, frac)) {
            assert.ok(p >= 0 && p <= 1, `frac ${frac}: pos ${p} out of [0,1]`);
            assert.ok(p < 1, `frac ${frac}: pos ${p} crossed early`);
          }
        }
      }
    }
  }
});

test("only the normal walk steps backwards", () => {
  const backward = (race) =>
    race.paths.some((p) => p.some((v, k) => k > 0 && v < p[k - 1]));
  const seen = {};
  for (const dist of DISTS) {
    seen[dist] = false;
    for (let seed = 0; seed < SEEDS; seed++) {
      if (backward(simulateRace(seed, names(6), dist))) seen[dist] = true;
    }
  }
  assert.equal(seen.normal, true, "normal should step backwards sometimes");
  assert.equal(seen.uniform, false, "uniform must never step backwards");
  assert.equal(seen.exponential, false, "exponential must never step backwards");
});
