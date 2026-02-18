<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://zentinelproxy.io/logo-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://zentinelproxy.io/logo-light.svg">
    <img alt="Zentinel" src="https://zentinelproxy.io/logo-light.svg" width="320">
  </picture>
</p>

<h3 align="center">A security-first reverse proxy built to guard the free web</h3>

<p align="center">
  <a href="https://zentinelproxy.io">Website</a> ·
  <a href="https://zentinelproxy.io/docs/">Docs</a> ·
  <a href="https://github.com/zentinelproxy/zentinel">Source</a> ·
  <a href="https://zentinelproxy.io/agents/">Agent Registry</a>
</p>

---

**Zentinel** is a high-performance reverse proxy written in Rust, built on [Cloudflare Pingora](https://github.com/cloudflare/pingora). It uses a pluggable **agent** architecture — each security or middleware concern is an isolated, composable module that you can mix, match, and extend.

### Core

| Repo | Description |
|------|-------------|
| [`zentinel`](https://github.com/zentinelproxy/zentinel) | The proxy core — routing, TLS, load balancing, agent pipeline |
| [`zentinel-modsec`](https://github.com/zentinelproxy/zentinel-modsec) | Pure Rust ModSecurity engine with OWASP CRS compatibility |
| [`zentinel-convert`](https://github.com/zentinelproxy/zentinel-convert) | Convert nginx / HAProxy / Envoy / Traefik / Caddy configs to Zentinel |

### Security Agents

| Agent | What it does |
|-------|-------------|
| [`auth`](https://github.com/zentinelproxy/zentinel-agent-auth) | JWT, API keys, OIDC, mTLS, SAML |
| [`waf`](https://github.com/zentinelproxy/zentinel-agent-waf) | OWASP CRS web application firewall |
| [`zentinelsec`](https://github.com/zentinelproxy/zentinel-agent-zentinelsec) | Pure Rust ModSecurity WAF (no C deps) |
| [`modsec`](https://github.com/zentinelproxy/zentinel-agent-modsec) | ModSecurity via libmodsecurity bindings |
| [`denylist`](https://github.com/zentinelproxy/zentinel-agent-denylist) | IP and pattern-based blocking |
| [`ratelimit`](https://github.com/zentinelproxy/zentinel-agent-ratelimit) | Token bucket rate limiting |
| [`bot-management`](https://github.com/zentinelproxy/zentinel-agent-bot-management) | Bot detection and management |
| [`ip-reputation`](https://github.com/zentinelproxy/zentinel-agent-ip-reputation) | Threat intelligence and blocklist checks |
| [`ai-gateway`](https://github.com/zentinelproxy/zentinel-agent-ai-gateway) | LLM proxy — prompt injection, PII, jailbreak detection |
| [`graphql-security`](https://github.com/zentinelproxy/zentinel-agent-graphql-security) | Query depth, complexity, and introspection control |
| [`grpc-inspector`](https://github.com/zentinelproxy/zentinel-agent-grpc-inspector) | gRPC authz, rate limiting, metadata inspection |
| [`websocket-inspector`](https://github.com/zentinelproxy/zentinel-agent-websocket-inspector) | WebSocket content filtering and schema validation |
| [`content-scanner`](https://github.com/zentinelproxy/zentinel-agent-content-scanner) | Malware scanning with ClamAV |
| [`spiffe`](https://github.com/zentinelproxy/zentinel-agent-spiffe) | SPIFFE / SPIRE workload identity |
| [`policy`](https://github.com/zentinelproxy/zentinel-agent-policy) | Policy evaluation — Rego/OPA + Cedar |
| [`soap`](https://github.com/zentinelproxy/zentinel-agent-soap) | SOAP envelope validation and WS-Security |
| [`audit-logger`](https://github.com/zentinelproxy/zentinel-agent-audit-logger) | Compliance logging with PII redaction |
| [`api-deprecation`](https://github.com/zentinelproxy/zentinel-agent-api-deprecation) | API lifecycle and deprecation management |

### Extensibility Agents

| Agent | What it does |
|-------|-------------|
| [`lua`](https://github.com/zentinelproxy/zentinel-agent-lua) | Custom logic via Lua scripts |
| [`js`](https://github.com/zentinelproxy/zentinel-agent-js) | Custom logic via JavaScript |
| [`wasm`](https://github.com/zentinelproxy/zentinel-agent-wasm) | Run WebAssembly modules in the request pipeline |
| [`transform`](https://github.com/zentinelproxy/zentinel-agent-transform) | Request / response header and body transforms |
| [`mock-server`](https://github.com/zentinelproxy/zentinel-agent-mock-server) | Stub responses for testing |
| [`chaos`](https://github.com/zentinelproxy/zentinel-agent-chaos) | Fault injection for resilience testing |
| [`mqtt-gateway`](https://github.com/zentinelproxy/zentinel-agent-mqtt-gateway) | MQTT protocol gateway |

### Agent SDKs

Build your own agents in your language of choice.

| Language | Repo |
|----------|------|
| Rust | [`zentinel-agent-rust-sdk`](https://github.com/zentinelproxy/zentinel-agent-rust-sdk) |
| Python | [`zentinel-agent-python-sdk`](https://github.com/zentinelproxy/zentinel-agent-python-sdk) |
| Go | [`zentinel-agent-go-sdk`](https://github.com/zentinelproxy/zentinel-agent-go-sdk) |
| TypeScript | [`zentinel-agent-typescript-sdk`](https://github.com/zentinelproxy/zentinel-agent-typescript-sdk) |
| Kotlin | [`zentinel-agent-kotlin-sdk`](https://github.com/zentinelproxy/zentinel-agent-kotlin-sdk) |
| Elixir | [`zentinel-agent-elixir-sdk`](https://github.com/zentinelproxy/zentinel-agent-elixir-sdk) |
| Haskell | [`zentinel-agent-haskell-sdk`](https://github.com/zentinelproxy/zentinel-agent-haskell-sdk) |

### Infrastructure

| Repo | Description |
|------|-------------|
| [`zentinel-helm`](https://github.com/zentinelproxy/zentinel-helm) | Helm chart for Kubernetes |
| [`zentinel-hub`](https://github.com/zentinelproxy/zentinel-hub) | Fleet management control plane (Go) |
| [`zentinel-control-plane`](https://github.com/zentinelproxy/zentinel-control-plane) | Fleet management control plane (Elixir/Phoenix) |
| [`zentinel-bench`](https://github.com/zentinelproxy/zentinel-bench) | Benchmarks vs Envoy, HAProxy, Nginx |

---

<p align="center">
  <sub>Built with Rust and Pingora. Based in Switzerland.</sub>
</p>
