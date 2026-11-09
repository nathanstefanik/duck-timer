# duck-timer

Shared duck-race countdown timer. No dependencies: Python stdlib server
(`server.py`, `words.py`), plain HTML/CSS/JS client (`static/`). Production
runs Python 3.13 on CT 104 — avoid anything newer.

## Test

```sh
node --test test/                            # race simulation (race.test.mjs)
python3 -m unittest discover -s test         # HTTP API (test_server.py)
```

## Deploy

`./deploy.sh` (gitignored, local only): rsyncs the working tree to CT 104
`/opt/duck-timer`, installs `deploy/duck-timer.service`, restarts
`duck-timer`, and verifies https://timer.nathanstefanik.xyz.

## Commits

Imperative, sentence-case subject, no prefixes; details in the user's
global rules.
