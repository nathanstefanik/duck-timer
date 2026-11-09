# duck-timer

A shared duck race countdown timer at [timer.nathanstefanik.xyz](https://timer.nathanstefanik.xyz).

Make a timer (1 second to 99:99:99), share the short word code
(e.g. `misty-mallard`), and everyone watching sees the same countdown and
the same duck race. The winning duck is drawn server-side with `secrets`
when the timer starts, and the race animation is a pure function of elapsed
time and that shared seed, so every viewer sees the identical race.

No dependencies. Python stdlib server, plain HTML/CSS/JS client.

## Run locally

```sh
python3 server.py
```

Then open http://127.0.0.1:8000.

## Deploy

See [deploy/README.md](deploy/README.md).
