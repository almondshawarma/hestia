# deploy/ : Hestia services on the Obelisk

Joins the Helios stack, bring it up incrementally.

```bash
# 1. broker only then flash a puck at it and watch topics
docker compose -f deploy/docker-compose.yml up -d hestia-mqtt
docker exec -it hestia-hestia-mqtt-1 mosquitto_sub -t 'hestia/#' -v

# 2. add the puck IOC (edit ioc/puck_ioc.py PUCKS first)
docker compose -f deploy/docker-compose.yml up -d --build hestia-ioc-puck

# 3. verify Channel Access from anywhere on the tailnet
caproto-monitor HES:LR:BME1:TEMP

# 4. later: uncomment hestia-ca2influx for Grafana history
```

## Networking notes
- **MQTT `1883`** is published, so scope it to Hestia contributors with a **Tailscale ACL** but
  never expose the personal Helios services to others (see `../docs/ARCHITECTURE.md`).
- The **IOC uses `network_mode: host`** so Channel Access UDP broadcasts (5064/5065) reach
  clients on the LAN/Tailscale.
- **Access-security** (`access_security.acf`, TODO): per-room read/write rules keyed on the
  `HES:RM<x>:` prefixes. This is where others get scoped control.
