# JA4proxy Real-World Testing Deployment Plan

## Executive Summary

This document provides a comprehensive, phase-by-phase implementation plan for deploying JA4proxy in front of a honeypot HTTPS form to collect real-world bot attack data and validate JA4 fingerprinting effectiveness in production-like conditions.

**Critical Constraints:**
- System MUST be clearly marked as test environment with impossible-to-miss warnings
- NO real PII collection or persistence
- Isolated from production infrastructure
- Monitor-first approach (no blocking initially)
- Full legal compliance with clear disclaimers

---

## Phase 1: Infrastructure Setup (Week 1-2)

### 1.1 Server Provisioning

#### Hardware/VM Specifications
- **CPU:** 2 vCPU minimum (4 vCPU recommended for high traffic)
- **RAM:** 4GB minimum (8GB recommended)
- **Storage:** 20GB SSD minimum (50GB recommended for extended logging)
- **Network:** Public IP with dedicated domain/subdomain
- **OS:** Ubuntu 22.04 LTS or Debian 12 (minimal install)

#### Network Architecture
```
Internet (Encrypted) -> [JA4proxy: L4 Interceptor] -> [HAProxy: TLS Termination] -> [Honeypot Backend]
                              |
                         [Redis: State Store]
                              |
                    [Observability Stack]
```

**Component Roles:**

1. **JA4proxy (The Gatekeeper)**
   - Listens on public ports 80/443
   - Intercepts raw TCP stream before TLS handshake completes
   - Parses Client Hello to generate JA4 fingerprint
   - Compares against blocklists/scoring thresholds
   - **Action:** If blocked → sends TCP RST immediately; If allowed → proxies raw bytes to HAProxy
   - *Critical:* Never terminates TLS itself; transparent TCP proxy with inspection capabilities

2. **HAProxy (The Traffic Manager)**
   - Receives proxied stream from JA4proxy
   - Performs **TLS Termination** (decrypts traffic)
   - Enforces Layer 7 rate limiting (requests per second)
   - Routes valid traffic to Honeypot Backend
   - Serves 503/403 if JA4proxy missed something (defense in depth)

3. **Honeypot Backend (The Bait)**
   - Simple HTTP server (Python/Flask or Node/Express)
   - Serves fake form with massive warnings
   - Logs submission metadata (IP, JA4 hash from headers, timestamp)
   - **Discards form payload entirely**

4. **Redis (The State Store)**
   - Stores dynamic ban lists shared between JA4proxy and HAProxy
   - Holds counters for rate limiting

5. **Observability Stack**
   - Prometheus: Scrapes metrics from JA4proxy and HAProxy
   - Grafana: Visualizes attack vectors and JA4 distributions
   - Loki: Aggregates logs for forensic analysis

#### Domain Configuration
- Register dedicated test domain (e.g., `test-dont-submit.example.com`)
- DNS A record pointing to server IP
- DNS TXT record with contact information and purpose statement
- SSL certificate via Let's Encrypt (automated renewal)

### 1.3 Base System Hardening

#### OS-Level Security Commands
```bash
apt update && apt upgrade -y
apt install -y ufw fail2ban docker.io docker-compose curl git
ufw default deny incoming
ufw default allow outgoing
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow from <ADMIN_IP> to any port 22
ufw enable
```

---

## Phase 2: Honeypot Form Development (Week 2-3)

### 2.1 Warning Design Requirements

#### Visual Warning Specifications
- **Size:** Minimum 30% of viewport height on initial load
- **Color:** High contrast (red/yellow on black or white)
- **Text Size:** Minimum 24px for main warning, 18px for secondary
- **Position:** Fixed overlay that must be acknowledged before form access

#### Warning Content
```
⚠️ SECURITY TEST ENVIRONMENT ⚠️
THIS IS NOT A REAL WEBSITE
DO NOT ENTER REAL INFORMATION
This is a security research project testing bot detection technology.
Any data submitted will be logged as TEST DATA ONLY and immediately discarded.
We do NOT collect, store, or use any personal information.
By continuing, you acknowledge this is a TEST SYSTEM.
[ I UNDERSTAND - CONTINUE TO TEST FORM ]
```

### 2.2 Backend Application Key Points

File: `/workspace/honeypot/app.py`

**Critical Rules (Enforced in Code):**
1. NEVER log actual form field values
2. NEVER store submissions in database
3. ONLY log metadata (JA4 signature, IP, timestamp, field count)
4. ALWAYS include "TEST DATA" marker in logs
5. AUTOMATICALLY purge logs after 30 days

**Metadata Logged:**
- Timestamp, JA4 signature, JA4 hash, IP address
- User agent (truncated to 200 chars)
- Referer (truncated to 200 chars)
- HTTP method, Request path, Content type
- Form field count (NOT values)
- JavaScript detection flag

### 2.3 Frontend Template Features

File: `/workspace/honeypot/templates/index.html`

- Full-screen warning overlay requiring acknowledgment
- Large, impossible-to-miss warning banners
- Form fields: name, address, city, phone, email (all marked TEST DATA ONLY)
- Persistent reminder headers on form page
- Footer with contact information and legal links
- JavaScript intercepts submission to show confirmation alert

### 2.4 CSS Styling for Maximum Visibility

File: `/workspace/honeypot/static/css/style.css`

**Design Elements:**
- Warning overlay: 95% black background, fixed position, z-index 9999
- Warning box: White background, 8px red border, pulsing animation on header
- Header text: 48px, red, uppercase, animated pulse
- Large warnings: 32px, bold, black
- Acknowledge button: Red background, 24px bold text
- Form header: Yellow warning background with amber border
- Footer warning: Pink background with dark red text
- Mobile responsive design for all screen sizes

---

## Phase 3: JA4proxy Configuration (Week 3-4)

### 3.1 JA4proxy Overview

JA4proxy sits between HAProxy (TLS termination) and the backend, analyzing TLS fingerprints and making routing/blocking decisions based on JA4 scores.

**Key Configuration Parameters:**
- `dial`: Blocking threshold (0 = monitor only, 1-10 = increasing strictness)
- `browser_bypass`: Allow known good browser signatures
- `log_level`: Detail level for logging
- `redis_host`: Connection to shared state

### 3.2 Initial Configuration (Monitor Mode)

File: `/workspace/configs/ja4proxy/ja4proxy.yaml`

**Critical Settings for Initial Deployment:**
- `dial: 0` - Monitor only, NO blocking
- `browser_bypass: false` - Disabled for testing to see all traffic
- `log_threshold: 30` - Log anything above score 30
- `logging.level: debug` - Maximum detail for initial analysis
- `logging.include_fingerprint: true` - Full JA4 details in logs
- `headers.inject_*: true` - Inject JA4 headers to backend

### 3.3 Graduated Rollout Strategy

| Period | Dial Setting | Browser Bypass | Action |
|--------|-------------|----------------|--------|
| Week 1-2 | 0 | false | Pure monitoring, all traffic passes |
| Week 3-4 | 2 | true | Soft blocking (score > 90 only) |
| Month 2 | 4 | true | Moderate blocking (score > 70) |
| Month 3+ | 5-7 | true | Production tuning based on data |

---

## Phase 4: Security Hardening (Week 4-5)

### 4.1 HAProxy Configuration

File: `/workspace/configs/haproxy/haproxy.cfg`

**Security Features:**
- TLS 1.2 minimum with strong cipher suites
- HTTP to HTTPS redirect
- Rate limiting: 100 requests per 10 seconds per IP
- Security headers: HSTS, X-Content-Type-Options, X-Frame-Options, X-XSS-Protection
- Health check endpoint on port 8404
- Backend routing through JA4proxy

### 4.2 Fail2Ban Configuration

Files:
- `/etc/fail2ban/jail.local`
- `/etc/fail2ban/filter.d/ja4proxy-highscore.conf`

**Jails Configured:**
- `ja4proxy-highscore`: Ban IPs with JA4 score > 80 for 24 hours after 3 strikes
- `honeypot-submission-flood`: Ban IPs submitting more than 20 times in 10 minutes

### 4.3 Log Rotation and Retention

File: `/etc/logrotate.d/ja4proxy-testing`

**Policy:**
- Daily rotation
- Keep 30 days of logs
- Compress old logs
- Auto-delete after 30 days

### 4.4 Container Security

**Docker Security Options:**
- `no-new-privileges:true`
- Read-only root filesystem
- tmpfs for /tmp
- Drop all capabilities except NET_BIND_SERVICE

---

## Phase 5: Observability & Analysis (Week 5-6)

### 5.1 Prometheus Configuration

File: `/workspace/configs/prometheus/prometheus.yml`

**Scrape Targets:**
- JA4proxy metrics on port 9090
- HAProxy stats on port 8404
- Honeypot health on port 5000

### 5.2 Key Metrics to Track

**JA4proxy Metrics:**
- Connections by JA4 score bucket (0-20, 21-40, 41-60, 61-80, 81-100)
- Unique fingerprints over time
- Blocking decisions (allow vs block)
- Request duration percentiles

**Honeypot Metrics:**
- Total submission attempts
- Submissions by JA4 score bucket
- Suspicious field manipulation attempts

### 5.3 Grafana Dashboards

**Dashboard 1: JA4 Overview**
- Connections by JA4 score distribution (histogram)
- Top 10 most common JA4 signatures
- Unique fingerprints over time (line graph)
- Geographic distribution of IPs (map)
- User agent breakdown (pie chart)
- High-score events timeline

**Dashboard 2: Attack Patterns**
- Submission attempts per hour
- Correlation between JA4 score and submissions
- Repeated offenders (IP + JA4 combo)
- Bot signature clusters
- Time-based attack patterns (heatmap)

**Dashboard 3: System Health**
- Request rate (RPS)
- Error rates by component
- Memory/CPU usage
- Redis connection pool
- Log volume

### 5.4 Loki Log Queries

**Example Queries:**
```
Find all high-score submissions: {job="honeypot"} | json | ja4_score > 70
Count submissions by JA4 signature: {job="honeypot"} | json | stats count() by ja4_signature
Find repeated IPs with different fingerprints: {job="honeypot"} | json | stats count_distinct(ja4_signature) by ip_address | count_distinct > 3
Detect rapid-fire submissions: {job="honeypot"} | json | rate(count) > 10 | stats sum() by ip_address
```

---

## Phase 6: Deployment & Operations (Week 6-7)

### 6.1 One-Click Deployment Script

File: `/workspace/scripts/deploy.sh`

**Steps:**
1. Check prerequisites (docker, docker-compose)
2. Create log directories
3. Generate self-signed SSL certificate
4. Deploy Docker Compose stack
5. Wait for services to start
6. Run health checks
7. Display access information and next steps

### 6.2 Docker Compose File

File: `/workspace/docker/docker-compose.yml`

**Services:**
- **haproxy**: Reverse proxy with TLS termination
- **ja4proxy**: JA4 fingerprint analysis
- **honeypot**: Flask backend with fake form
- **redis**: Shared state storage
- **prometheus**: Metrics collection
- **grafana**: Visualization dashboards
- **loki**: Log aggregation

All services on isolated bridge network `ja4net`.

### 6.3 Operations Runbook

**Daily Tasks (15-20 minutes):**
1. Check dashboards (5 min) - Review JA4 score distribution, traffic spikes, system health
2. Review high-score logs (10 min) - grep for scores 80-100
3. Verify log rotation (2 min) - check log file sizes and dates

**Weekly Tasks (1 hour):**
1. Pattern analysis (30 min) - Export top 20 JA4 signatures, identify new bot patterns
2. Security scan (15 min) - Run vulnerability assessment
3. Backup metrics (10 min) - Export weekly statistics

**Monthly Tasks (Half day):**
1. Configuration review - Assess dial setting, review bypass list, update rate limits
2. Security assessment - External penetration test, firewall review
3. Report generation - Compile statistics, document findings, share with team

---

## Phase 7: Research & Iteration (Ongoing)

### 7.1 Baseline Establishment (Month 1)

**Data Collection Goals:**
- Collect 1000+ unique JA4 fingerprints
- Document benign traffic patterns
- Identify common bot signatures
- Establish score distribution baseline

### 7.2 Bot Categorization Framework

**Categories to Track:**
1. **Headless Browsers** (Puppeteer, Playwright, Selenium) - Distinct JA4 signatures, missing TLS extensions
2. **HTTP Libraries** (curl, wget, Python requests) - Very low JA4 scores, minimal TLS handshake
3. **Mobile Automation** (Appium, mobile bots) - Mobile JA4 patterns, inconsistent user agents
4. **Known Malicious Tools** - Match against threat intelligence feeds
5. **Custom Bots** - Unusual fingerprint combinations, behavioral anomalies

### 7.3 Effectiveness Measurement

**Key Performance Indicators:**
- Detection Rate: % of known bots correctly identified (score > 70)
- False Positive Rate: % of legitimate traffic incorrectly flagged
- Blocking Efficiency: Reduction in malicious submissions after enabling blocking
- Fingerprint Stability: How often bots change JA4 signatures

### 7.4 Signature Database Building

**Output Format:**
```json
{
  "signature": "t13d1516h2_8daaf6152771_02713d6af862",
  "first_seen": "2024-01-15T10:30:00Z",
  "last_seen": "2024-01-20T15:45:00Z",
  "occurrence_count": 1247,
  "average_score": 87,
  "classification": "headless_browser",
  "tool_identified": "puppeteer",
  "associated_ips": 3,
  "behavioral_notes": "Rapid form submissions, no mouse movement"
}
```

---

## Risk Mitigation Strategies

### R1: Accidental PII Collection
**Probability:** Low | **Impact:** High

**Mitigations:**
- Code review enforcing no field value logging
- Automated tests checking log contents
- Clear visual warnings preventing honest users
- Legal disclaimers on all pages
- Automatic log purging after 30 days

**Monitoring:**
Daily scan for potential PII in logs (should return zero results):
```bash
grep -E '\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b' /var/log/honeypot/*.log
```

### R2: False Positive Blocking
**Probability:** Medium | **Impact:** Medium

**Mitigations:**
- Start with dial=0 (monitor only)
- Gradual threshold increases
- Browser bypass enabled
- Easy unban mechanism
- Clear contact method for false positives

**Response Plan:**
1. Immediate dial reduction if FP rate > 1%
2. Manual review of blocked signatures
3. Update bypass list within 24 hours
4. Communicate with affected parties

### R3: Server Compromise
**Probability:** Low | **Impact:** High

**Mitigations:**
- Minimal OS installation
- Regular security updates
- Container isolation
- Read-only filesystems where possible
- Network segmentation
- No sensitive data stored

**Response Plan:**
1. Isolate server immediately
2. Preserve logs for forensics
3. Rebuild from clean image
4. Rotate all credentials
5. Post-mortem analysis

### R4: Legal/Compliance Issues
**Probability:** Low | **Impact:** High

**Mitigations:**
- Clear public disclaimers
- No real data collection
- Contact information prominently displayed
- Terms of use explicitly stating research purpose
- Compliance with local laws (GDPR, CCPA, etc.)

**Required Documentation:**
- `/workspace/legal/DISCLAIMER.md` - Public disclaimer
- `/workspace/legal/TERMS.md` - Terms of use
- `/workspace/legal/PRIVACY.md` - Privacy policy (no data collection)

---

## Success Metrics (90-Day Targets)

### Quantitative Goals
- 1000+ unique JA4 fingerprints collected
- 100+ confirmed bot attacks logged and categorized
- 99.9% uptime (less than 2 hours downtime in 90 days)
- Zero security incidents
- Zero accidental PII collections
- False positive rate < 1%

### Qualitative Goals
- Documented top 20 malicious JA4 signatures
- Validated JA4 scoring accuracy against known tools
- Established baseline for "normal" traffic patterns
- Created repeatable deployment process
- Developed operational runbook
- Built signature database for community sharing

### Research Outputs
- Technical report on JA4 effectiveness in real-world conditions
- Catalog of bot signatures encountered
- Recommendations for JA4proxy configuration tuning
- Case studies of interesting attack patterns
- Open-source contributions back to JA4proxy project

---

## Appendix A: Quick Reference Commands

**View Live Logs:**
```bash
tail -f /var/log/ja4proxy/ja4proxy.log | jq .
tail -f /var/log/honeypot/submissions.log | jq .
```

**Check Service Status:**
```bash
docker-compose ps
docker stats
```

**Extract Metrics:**
```bash
# Top 10 JA4 signatures
cat /var/log/ja4proxy/ja4proxy.log | jq -r '.ja4_signature' | sort | uniq -c | sort -rn | head -10

# Score distribution
cat /var/log/ja4proxy/ja4proxy.log | jq -r '.ja4_score' | awk '{s[$1]++} END {for (i in s) print i, s[i]}' | sort -n

# Unique IPs today
cat /var/log/ja4proxy/ja4proxy.log | jq -r '.ip_address' | sort -u | wc -l
```

**Emergency Actions:**
```bash
docker-compose down          # Stop all services
docker-compose restart ja4proxy  # Restart specific service
docker-compose exec redis redis-cli FLUSHALL  # Clear ban lists
```

---

## Appendix B: Timeline Summary

| Week | Phase | Key Deliverables |
|------|-------|------------------|
| 1-2 | Infrastructure | Server provisioned, repo structure created, base hardening complete |
| 2-3 | Honeypot Dev | Form with warnings deployed, logging implemented, tested |
| 3-4 | JA4proxy Config | Monitor mode configuration, Docker integration |
| 4-5 | Security | HAProxy configured, Fail2Ban active, log rotation working |
| 5-6 | Observability | Prometheus/Grafana/Loki deployed, dashboards built |
| 6-7 | Deployment | Full stack deployed, runbook tested, monitoring active |
| 7+ | Research | Data collection ongoing, analysis performed, reports generated |

---

## Appendix C: Contact and Escalation

**Primary Contacts:**
- Technical Lead: [NAME] - [EMAIL]
- Security Officer: [NAME] - [EMAIL]
- Legal Counsel: [NAME] - [EMAIL]

**Escalation Matrix:**

| Issue Type | Severity | Response Time | Escalation Path |
|------------|----------|---------------|-----------------|
| Security breach | Critical | 15 minutes | Tech Lead -> Security -> Legal |
| False positive wave | High | 1 hour | Tech Lead -> Dial adjustment |
| Service outage | High | 30 minutes | Tech Lead -> Infra team |
| Legal inquiry | Critical | 1 hour | Legal -> Security -> Tech Lead |
| Data concern | High | 2 hours | Security -> Legal -> Tech Lead |

**Public Contact:**
- Email: security-test@example.com
- Web form: /contact (on honeypot site)
- Response SLA: 48 hours for non-critical inquiries
