# duck-timer

A shared duck race countdown timer at [timer.nathanstefanik.xyz](https://timer.nathanstefanik.xyz).

Make a timer (1 second to 99:99:99), share the short word code
(e.g. `misty-mallard`), and everyone watching sees the same countdown and
the same duck race. When the timer starts the server draws a seed with
`secrets`, and every viewer simulates the identical random-walk race from
it — the animation is a pure function of elapsed time and that seed.

Each step every duck draws a step length from the chosen distribution
(all have mean 1):

- **normal** — mean 1, sd 1.5: about a quarter of steps go backwards.
- **uniform** — 0 to 2: always forward, steady.
- **exponential** — mean 1: always forward, occasional lunges.

The first duck across the line wins, touching it exactly when the timer
hits zero — nobody gets there early. For the normal walk only, capital
letters in a name give a small edge: each A–Z (up to 10) nudges the mean
step up, so `AAAA AAAAAA` beats `duck` about 95% of the time head-to-head.

No dependencies. Python stdlib server, plain HTML/CSS/JS client.

## Run locally

```sh
python3 server.py
```

Then open http://127.0.0.1:8000.

## Test

```sh
node --test test/
python3 -m unittest discover -s test
```

## Deploy

See [deploy/README.md](deploy/README.md).
