# Phase 7: Validation & Testing

## Objective

Verify the entire stack works correctly under real internet traffic, generate controlled test traffic for validation, and establish a dial escalation plan to move from pure monitoring to active blocking.

---

## 7.1 Validation Architecture

```mermaid
flowchart TD
    subgraph Validation["🧪 Validation Layers"]
        L1["Component Tests\n(each service works independently)"]
        L2["Integration Tests\n(full pipeline: HAProxy → JA4proxy → Caddy)"]
        L3["Traffic Generation\n(known clients with known fingerprints)"]
        L4["Real Traffic\n(natural internet scans and bots)"]
        L5["Stress Testing\n(connection floods, resource limits)"]
        L6["Dial Escalation\n(gradual move from monitor to block)"]
    end

    L1 --> L2 --> L3 --> L4 --> L5 --> L6

    style Validation fill:#27ae60,color:#fff
```

---

## 7.2 Component-Level Validation

### Step 1: Verify Each Component Independently

```bash
# ── HAProxy ──
echo "=== HAProxy ==="
docker exec ja4proxy-haproxy haproxy -c -f /usr/local/etc/haproxy/haproxy.cfg
curl -s http://127.0.0.1:8404/stats | head -1
echo ""

# ── Redis ──
echo "=== Redis ==="
docker exec ja4proxy-redis redis-cli -a "$(grep REDIS_PASSWORD /opt/ja4proxy-docker/.env | cut -d= -f2)" PING
echo ""

# ── Caddy ──
echo "=== Caddy ==="
curl -s http://127.0.0.1:8081/ | grep -o "RESEARCH HONEYPOT"
echo ""

# ── JA4proxy ──
echo "=== JA4proxy ==="
curl -s http://127.0.0.1:9090/health | jq .
curl -s http://127.0.0.1:9090/health/deep | jq .
echo ""

# ── Prometheus ──
echo "=== Prometheus ==="
curl -s http://127.0.0.1:9091/-/healthy
echo ""

# ── Grafana ──
echo "=== Grafana ==="
curl -s -u admin:$(grep GRAFANA_ADMIN_PASSWORD /opt/ja4proxy-docker/.env | cut -d= -f2) \
  http://127.0.0.1:3000/api/health | jq .
echo ""

# ── Loki ──
echo "=== Loki ==="
curl -s http://127.0.0.1:3100/ready
echo ""
```

### Expected Results

```mermaid
flowchart LR
    subgraph Expected["✅ Expected Component Status"]
        E1["HAProxy: config OK,\nstats page loads"]
        E2["Redis: PONG"]
        E3["Caddy: HTML contains\nRESEARCH HONEYPOT"]
        E4["JA4proxy: healthy,\nall deps OK"]
        E5["Prometheus: healthy"]
        E6["Grafana: {database: ok}"]
        E7["Loki: ready"]
    end

    style Expected fill:#27ae60,color:#fff
```

---

## 7.3 End-to-End Integration Test

```bash
# ── Test 1: Full pipeline via HTTPS ──
echo "=== Full HTTPS pipeline ==="
curl -vk https://127.0.0.1:443/ 2>&1

# Should see:
# - TLS handshake succeeds (via HAProxy passthrough → Caddy)
# - HTTP 200 with honeypot HTML
# - JA4proxy logs the connection fingerprint

# ── Test 2: Verify JA4proxy logged it ──
echo "=== JA4proxy logs ==="
sudo journalctl -u ja4proxy.service --since "2 min ago" | grep -i "JA4\|connection"

# ── Test 3: Verify Prometheus recorded it ──
echo "=== Prometheus metrics ==="
curl -s http://127.0.0.1:9090/metrics | grep "ja4proxy_connections_total"

# ── Test 4: Verify log shipping to Loki ──
echo "=== Loki logs ==="
curl -s 'http://127.0.0.1:3100/loki/api/v1/query?query={unit="ja4proxy.service"}&limit=5' \
  | jq '.data.result[0].values[0][1]'

# ── Test 5: Honeypot form submission ──
echo "=== Form submission ==="
curl -sk -X POST https://127.0.0.1:443/submit \
  -d "name=testbot&email=bot@test.com&message=testing"
# Should return: "Submission received and discarded for research."
```

---

## 7.4 Controlled Traffic Generation

### Test with Known Clients

```mermaid
flowchart TD
    subgraph KnownClients["🧪 Known Client Fingerprints"]
        K1["curl → Known JA4\n(curl's TLS signature)"]
        K2["wget → Known JA4\n(wget's TLS signature)"]
        K3["Firefox browser → Known JA4\n(Firefox's ClientHello)"]
        K4["Chrome browser → Known JA4\n(Chrome's ClientHello)"]
        K5["Python requests → Known JA4\n(Python's TLS stack)"]
        K6["nmap SSL scan → Known JA4\n(scanner fingerprint)"]
        K7["openssl s_client → Known JA4\n(raw TLS client hello)"]
    end

    subgraph Baseline["📊 Establish Baseline"]
        B1["Record expected JA4\nfor each client type"]
        B2["Verify correct action\n(all should be ALLOW at dial=0)"]
        B3["Verify risk scores\nmake sense for each client"]
        B4["Verify GeoIP,\nASN data accuracy"]
    end

    KnownClients --> Baseline

    style KnownClients fill:#2980b9,color:#fff
    style Baseline fill:#27ae60,color:#fff
```

### Generate known traffic:

```bash
# ── curl ──
curl -vk https://127.0.0.1:443/ > /dev/null 2>&1
echo "curl connection made"

# ── wget ──
wget --no-check-certificate -q -O /dev/null https://127.0.0.1:443/
echo "wget connection made"

# ── openssl s_client (raw TLS) ──
echo | openssl s_client -connect 127.0.0.1:443 -tls1_3 2>/dev/null | head -5
echo "openssl TLS 1.3 connection made"

echo | openssl s_client -connect 127.0.0.1:443 -tls1_2 2>/dev/null | head -5
echo "openssl TLS 1.2 connection made"

# ── nmap scan (scanner behavior) ──
nmap -sV --script ssl-enum-ciphers -p 443 127.0.0.1 2>/dev/null | head -20
echo "nmap scan completed"

# ── Python requests ──
python3 -c "
import requests
import urllib3
urllib3.disable_warnings()
r = requests.get('https://127.0.0.1:443/', verify=False)
print(f'Python requests: status={r.status_code}')
"

# ── Go net/http ──
# (if Go is available on admin machine)
# This gives a different JA4 than curl/wget
```

### Record Baseline Fingerprints

After running the above, check what JA4proxy recorded:

```bash
# Get all fingerprints from last 10 minutes
sudo journalctl -u ja4proxy.service --since "10 min ago" | \
  grep -oP 'JA4[a-z]*=[^ ,]+' | sort -u

# Or from Prometheus
curl -s 'http://127.0.0.1:9091/api/v1/query?query=ja4proxy_connections_total' | \
  jq '.data.result[] | .metric'
```

Document the results:

| Client | JA4 Fingerprint | Risk Score | Action | Notes |
|--------|----------------|------------|--------|-------|
| curl | `t13d...` | ~20 | allow | Known CLI tool |
| wget | `t13d...` | ~25 | allow | Known CLI tool |
| Firefox | `t13d...` | ~10 | allow | Legitimate browser |
| Chrome | `t13d...` | ~10 | allow | Legitimate browser |
| nmap | `t13d...` | ~60 | flag/tarpit | Scanner |
| openssl | `t13d...` | ~40 | flag | Raw TLS client |
| Python requests | `t13d...` | ~35 | flag | HTTP library |

> **Note**: Actual JA4 values depend on the specific client versions. Record these from your own test runs.

---

## 7.5 Real Traffic Observation

```mermaid
flowchart TD
    subgraph RealTraffic["🌐 Natural Internet Traffic"]
        R1["Search engine crawlers\n(Googlebot, Bingbot)"]
        R2["Vulnerability scanners\n(Shodan, Censys, ZoomEye)"]
        R3["Malware C2 check-ins\n(if domain gets discovered)"]
        R4["Mass internet scans\n(botnets scanning port 443)"]
        R5["Security researchers\n(who discover the honeypot)"]
        R6["Legitimate users\n(who accidentally visit)"]
    end

    subgraph Observe["👀 What to Watch"]
        O1["Connection rate\n(conns/hour, conns/day)"]
        O2["Fingerprint diversity\n(unique JA4s seen)"]
        O3["Geographic spread\n(countries, ASNs)"]
        O4["Risk score distribution\n(how many high-score)"]
        O5["Behavioral patterns\n(beaconing, bursts, sweeps)"]
        O6["Honeypot interactions\n(who fills out the form)"]
    end

    RealTraffic --> Observe

    style RealTraffic fill:#2980b9,color:#fff
    style Observe fill:#f39c12,color:#fff
```

### Monitor real traffic patterns:

```bash
# Connection rate (per minute, last hour)
curl -s 'http://127.0.0.1:9091/api/v1/query_range?query=rate(ja4proxy_connections_total%5B1m%5D)&start=-1h&end=now&step=60' \
  | jq '.data.result[0].values'

# Top countries
curl -s 'http://127.0.0.1:9091/api/v1/query?query=topk(10,%20sum%20by(country)(increase(ja4proxy_connections_total%5B24h%5D)))' \
  | jq '.data.result[] | {country: .metric.country, count: .value[1]}' | sort -t: -k3 -rn

# Top JA4 fingerprints
curl -s 'http://127.0.0.1:9091/api/v1/query?query=topk(15,%20sum%20by(ja4)(increase(ja4proxy_connections_total%5B24h%5D)))' \
  | jq '.data.result[] | {ja4: .metric.ja4, count: .value[1]}' | sort -t: -k3 -rn

# Risk score distribution
curl -s 'http://127.0.0.1:9091/api/v1/query?query=histogram_quantile(0.50,%20rate(ja4proxy_risk_score_bucket%5B1h%5D))' \
  | jq '.data.result[0].value'

# Honeypot form submissions
docker logs ja4proxy-honeypot 2>&1 | grep "POST" | wc -l
```

---

## 7.6 Stress Testing

```mermaid
flowchart TD
    subgraph Stress["💪 Stress Tests"]
        S1["Connection flood\n(10,000 rapid connections)"]
        S2["Large payload\n(max-size TLS ClientHello)"]
        S3["Slow connections\n(open but don't send)"]
        S4["Invalid TLS\n(malformed ClientHello)"]
        S5["SSLv3 attempt\n(legacy protocol)"]
    end

    subgraph Expected["✅ Expected Behavior"]
        E1["Proxy stays responsive\n(p50 < 1ms)"]
        E2["No crashes or panics"]
        E3["Redis handles load\n(no OOM, no timeouts)"]
        E4["Tarpit activates\n(if dial > 55)"]
        E5["Logs remain accurate\n(no dropped entries)"]
    end

    Stress --> Expected

    style Stress fill:#e74c3c,color:#fff
    style Expected fill:#27ae60,color:#fff
```

### Connection flood test (from admin machine, NOT through the proxy):

```bash
# Simple parallel curl — no extra tools needed
for i in $(seq 1 100); do
  curl -sk https://127.0.0.1:443/ > /dev/null 2>&1 &
done
wait
echo "100 parallel connections completed"

# Monitor during test
watch -n1 'curl -s http://127.0.0.1:9090/metrics | grep -E "ja4proxy_active_connections|ja4proxy_connections_total|pipeline_duration"'
```

> **For heavier load testing**, consider installing [vegeta](https://github.com/tsenart/vegeta) or using the upstream JA4proxy traffic generator (`cd JA4proxy && make traffic-gen`).

### Resource monitoring during stress:

```bash
# Watch JA4proxy memory
systemctl status ja4proxy.service | grep Memory

# Watch Docker containers
docker stats --no-stream

# Watch system resources
htop
```

---

## 7.7 Dial Escalation Plan

```mermaid
flowchart TD
    subgraph Dial["🎚️ Dial Escalation Strategy"]
        D0["Dial 0: MONITOR\n(Log everything, block nothing)\n— Baseline data collection"]
        D1["Dial 20: FLAG\n(Log + flag suspicious)\n— Identify false positives"]
        D2["Dial 40: RATE LIMIT\n(Slow down suspicious)\n— Test rate limiting"]
        D3["Dial 55: TARPIT\n(Waste bot resources)\n— Observe tarpit effectiveness"]
        D4["Dial 70: BLOCK\n(Drop blacklisted)\n— Active blocking begins"]
        D5["Dial 85: BAN\n(Temp ban repeat offenders)\n— 5-min auto-expiring bans"]
        D6["Dial 100: MAXIMUM\n(Block all high-risk)\n— Full enforcement"]
    end

    D0 -. "Week 1-2\n(validate data)" .-> D1
    D1 -. "Week 2-3\n(check FPs)" .-> D2
    D2 -. "Week 3-4\n(test limits)" .-> D3
    D3 -. "Week 4-5\n(assess impact)" .-> D4
    D4 -. "Week 5-6\n(full blocking)" .-> D5
    D5 -. "Week 6+\n(max protection)" .-> D6

    style Dial fill:#2980b9,color:#fff
```

### Escalation Procedure

```bash
# ── Current dial check ──
curl -s http://127.0.0.1:9090/metrics | grep "ja4proxy_dial_current"

# ── Change dial (Method 1: Edit config + hot-reload) ──
sudo sed -i 's/dial: [0-9]*/dial: 20/' /opt/ja4proxy/config/proxy.yml
sudo kill -SIGHUP $(pidof ja4proxy)

# Verify change
sudo journalctl -u ja4proxy.service --since "30 sec ago" | grep -i "reload\|dial"
curl -s http://127.0.0.1:9090/metrics | grep "ja4proxy_dial_current"

# ── Change dial (Method 2: Redis command) ──
docker exec ja4proxy-redis redis-cli -a "$(grep REDIS_PASSWORD /opt/ja4proxy-docker/.env | cut -d= -f2)" \
  SET ja4proxy:dial 20

# ── Change dial (Method 3: API if management API is enabled) ──
curl -X POST http://127.0.0.1:8090/api/v1/dial -d '{"dial": 20}'

# ── Always verify after change ──
sleep 5
curl -s http://127.0.0.1:9090/metrics | grep "ja4proxy_dial_current"
```

### Counterfactual Analysis

At each dial level, analyze the counterfactual logs:

```bash
# At dial=0, check what WOULD have been flagged
sudo journalctl -u ja4proxy.service --since "24 hours ago" | \
  grep "counterfactual" | grep -E "flag|rate_limit|tarpit|block|ban" | \
  awk '{print $NF}' | sort | uniq -c | sort -rn

# At dial=20, check what WOULD have been tarpitted
sudo journalctl -u ja4proxy.service --since "24 hours ago" | \
  grep "counterfactual_action=tarpit" | wc -l

# Compare connection actions before/after dial change
curl -s 'http://127.0.0.1:9091/api/v1/query?query=sum%20by(action)(ja4proxy_connections_total)' \
  | jq '.data.result[] | {action: .metric.action, count: .value[1]}'
```

---

## 7.8 Go Proxy Reliability Assessment

```mermaid
flowchart TD
    subgraph Reliability["⚡ Reliability Metrics"]
        R1["Uptime\n(systemd restart count)"]
        R2["p50/p95/p99 latency\n(pipeline duration)"]
        R3["Error rate\n(connection errors / total)"]
        R4["Memory usage\n(RSS over time)"]
        R5["Goroutine count\n(stable vs growing)"]
        R6["Connection throughput\n(conns/sec at peak)"]
        R7["Config reload success\n(reloads without restart)"]
    end

    subgraph Targets["🎯 Target Values"]
        T1["Uptime: > 99.9%\n(max 1 restart/month)"]
        T2["p50: < 0.5ms\np99: < 2ms"]
        T3["Error rate: < 1%"]
        T4["Memory: stable\n(no growth > 10%/week)"]
        T5["Goroutines: stable\n(< 1000 at idle)"]
        T6["Throughput: > 5000 conns/sec"]
        T7["Reload: 100% success\n(no restarts needed)"]
    end

    Reliability --> Targets

    style Reliability fill:#2980b9,color:#fff
    style Targets fill:#27ae60,color:#fff
```

### Collect reliability data:

```bash
# Uptime info
systemctl show ja4proxy.service -p ActiveEnterTimestamp,ActiveState,NActiveEntersPerSec

# Latency (p50, p95, p99)
curl -s 'http://127.0.0.1:9091/api/v1/query?query=histogram_quantile(0.50,%20rate(ja4proxy_pipeline_duration_seconds_bucket%5B1h%5D))' \
  | jq '.data.result[0].value'
curl -s 'http://127.0.0.1:9091/api/v1/query?query=histogram_quantile(0.95,%20rate(ja4proxy_pipeline_duration_seconds_bucket%5B1h%5D))' \
  | jq '.data.result[0].value'
curl -s 'http://127.0.0.1:9091/api/v1/query?query=histogram_quantile(0.99,%20rate(ja4proxy_pipeline_duration_seconds_bucket%5B1h%5D))' \
  | jq '.data.result[0].value'

# Memory
systemctl show ja4proxy.service -p MemoryCurrent

# Goroutines (from /metrics)
curl -s http://127.0.0.1:9090/metrics | grep "go_goroutines"

# Error rate
TOTAL=$(curl -s http://127.0.0.1:9090/metrics | grep "ja4proxy_connections_total" | awk '{sum += $2} END {print sum}')
ERRORS=$(curl -s http://127.0.0.1:9090/metrics | grep "ja4proxy_connection_errors_total" | awk '{sum += $2} END {print sum}')
echo "Error rate: $ERRORS / $TOTAL = $(echo "scale=4; $ERRORS / $TOTAL * 100" | bc)%"
```

---

## 7.9 Verification Checklist

```mermaid
flowchart LR
    subgraph Done["✅ Phase 7 Verification"]
        D1["✅ All components pass health checks"]
        D2["✅ End-to-end: curl :443 returns honeypot"]
        D3["✅ JA4 fingerprint in logs for each client type"]
        D4["✅ Baseline fingerprints documented"]
        D5["✅ Prometheus metrics incrementing"]
        D6["✅ Logs shipping to Loki"]
        D7["✅ Grafana dashboards loading"]
        D8["✅ Stress test: 100 parallel conns handled"]
        D9["✅ Dial escalation tested (0→20→0)"]
        D10["✅ Counterfactual logs working"]
        D11["✅ Reliability metrics within targets"]
        D12["✅ Honeypot form submission works"]
    end

    style Done fill:#27ae60,color:#fff
```

---

## 7.10 Ongoing Research Workflow

```mermaid
flowchart TD
    subgraph Workflow["📋 Daily/Weekly/Monthly Workflow"]
        Daily["📅 Daily (5 min)"]
        Daily -->|"1. Check service status"| D1
        Daily -->|"2. Review error logs"| D2
        Daily -->|"3. Note connection rate"| D3
        Daily -->|"4. Check disk space"| D4

        Weekly["📅 Weekly (30 min)"]
        Weekly -->|"1. Export metrics data"| W1
        Weekly -->|"2. Review top JA4 fingerprints"| W2
        Weekly -->|"3. Analyze geographic trends"| W3
        Weekly -->|"4. Update Grafana dashboards"| W4
        Weekly -->|"5. Review dial setting"| W5

        Monthly["📅 Monthly (2 hours)"]
        Monthly -->|"1. Security audit"| M1
        Monthly -->|"2. Compile research report"| M2
        Monthly -->|"3. Assess Go proxy reliability"| M3
        Monthly -->|"4. Plan dial escalation step"| M4
        Monthly -->|"5. Consider enabling feeds"| M5
    end

    style Daily fill:#2980b9,color:#fff
    style Weekly fill:#f39c12,color:#fff
    style Monthly fill:#27ae60,color:#fff
```

---

## Dependencies

- **Phase 1-6**: All prior phases must be complete and verified
- **→ Ongoing**: This phase transitions into the continuous research workflow

---

## Notes & Decisions

| Decision | Rationale |
|----------|-----------|
| Start with dial=0 | Zero risk of false positives. Build confidence in data before any blocking. |
| Weekly dial review | Ensures we don't escalate blindly. Each step needs data validation. |
| Counterfactuals always on | Even at dial=0, we learn "what would happen" — critical for research. |
| Stress test at 100 conns | Realistic for a honeypot. Production needs much higher. |
| Reliability targets documented | Concrete numbers to validate the Go proxy against. Not subjective. |
| No automated alerting initially | Manual daily checks are sufficient for research. Add automation when moving to production. |
