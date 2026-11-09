# Deploy runbook

Target: the timer runs in the joplin LXC (container 104, 192.168.1.236),
bound to 0.0.0.0:8000 so the Caddy host (192.168.1.220) can reach it over
the LAN. Caddy terminates TLS and is the only public face.

## 1. App (in container 104)

```sh
apt update && apt install -y git python3
git clone https://github.com/nathanstefanik/duck-timer /opt/duck-timer
cp /opt/duck-timer/deploy/duck-timer.service /etc/systemd/system/
systemctl enable --now duck-timer
curl -s 127.0.0.1:8000/ | head -3   # should print the create page
```

## 2. Caddy (on 192.168.1.220)

```sh
curl -s http://192.168.1.236:8000/ | head -3   # reachable over the LAN?
```

Append the block from `Caddyfile` in this directory to `/etc/caddy/Caddyfile`,
then:

```sh
systemctl reload caddy
```

Caddy obtains and renews the Let's Encrypt certificate on its own once DNS
is in place.

## 3. DNS

Add an `A` record `timer.nathanstefanik.xyz -> <public IP>` (same target as
vault/files/sync/joplin). Ports 80/443 already reach Caddy, so nothing new
to forward.

## 4. Update

```sh
cd /opt/duck-timer && git pull && systemctl restart duck-timer
```

Note: timer state is in-memory, so a restart drops live timers.
