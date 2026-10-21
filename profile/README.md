<p align="center">
  <a href="https://zentinelproxy.io">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/zentinelproxy/design/main/marks/lockup/zentinel-lockup-dark.svg">
      <img alt="Zentinel" src="https://raw.githubusercontent.com/zentinelproxy/design/main/marks/lockup/zentinel-lockup-light.svg" height="52">
    </picture>
  </a>
</p>

<h3 align="center">A security-first reverse proxy built to guard the free web</h3>

<p align="center">
  <a href="https://zentinelproxy.io">Website</a> &middot;
  <a href="https://docs.zentinelproxy.io">Docs</a> &middot;
  <a href="https://registry.zentinelproxy.io">Agent registry</a> &middot;
  <a href="https://github.com/zentinelproxy/zentinel">GitHub</a>
</p>

Zentinel is a reverse proxy written in Rust on [Pingora](https://github.com/zentinelproxy/pingora).
The core does routing, TLS, load balancing and caching, and stays small.
Security and middleware concerns run as **agents**: separate processes the
proxy talks to over agent protocol v2, each with its own timeout and failure
mode, so a crashing or slow agent is bounded instead of taking the proxy down.

### Core

| Repository | What it does |
|---|---|
| [`zentinel`](https://github.com/zentinelproxy/zentinel) | The proxy: routing, TLS, load balancing, caching and the agent pipeline |
| [`zentinel-modsec`](https://github.com/zentinelproxy/zentinel-modsec) | Pure Rust ModSecurity rule engine with OWASP CRS compatibility |
| [`zentinel-convert`](https://github.com/zentinelproxy/zentinel-convert) | Converts nginx, HAProxy, Traefik, Caddy and Envoy configs to Zentinel KDL ([online](https://zentinelproxy.io/converter/)) |
| [`zentinel-control-plane`](https://github.com/zentinelproxy/zentinel-control-plane) | Fleet management for Zentinel proxies (Elixir/Phoenix) |
| [`zentinel-helm`](https://github.com/zentinelproxy/zentinel-helm) | Helm chart for running Zentinel on Kubernetes |
| [`pingora`](https://github.com/zentinelproxy/pingora) | Zentinel's Pingora fork, published as the `zentinel-pingora-*` crates |
| [`zentinel-hub`](https://github.com/zentinelproxy/zentinel-hub) | Deprecated Go fleet manager, superseded by `zentinel-control-plane` |

### Security agents

| Agent | What it does |
|---|---|
| [`auth`](https://github.com/zentinelproxy/zentinel-agent-auth) | JWT, API keys, Basic, OIDC, SAML, mTLS client certificates, Cedar authorization |
| [`waf`](https://github.com/zentinelproxy/zentinel-agent-waf) | Pure Rust WAF with its own detection rules and anomaly scoring |
| [`zentinelsec`](https://github.com/zentinelproxy/zentinel-agent-zentinelsec) | ModSecurity-compatible WAF that loads the OWASP CRS, built on `zentinel-modsec` (no C dependencies) |
| [`modsec`](https://github.com/zentinelproxy/zentinel-agent-modsec) | ModSecurity WAF through libmodsecurity bindings |
| [`denylist`](https://github.com/zentinelproxy/zentinel-agent-denylist) | Blocks requests by IP, CIDR range and pattern |
| [`ratelimit`](https://github.com/zentinelproxy/zentinel-agent-ratelimit) | Token bucket rate limiting |
| [`bot-management`](https://github.com/zentinelproxy/zentinel-agent-bot-management) | Bot detection and management |
| [`ip-reputation`](https://github.com/zentinelproxy/zentinel-agent-ip-reputation) | Checks client IPs against threat intelligence feeds and blocklists |
| [`ai-gateway`](https://github.com/zentinelproxy/zentinel-agent-ai-gateway) | Pattern-based prompt injection, jailbreak and PII checks for LLM API traffic |
| [`graphql-security`](https://github.com/zentinelproxy/zentinel-agent-graphql-security) | GraphQL query depth, complexity and introspection control |
| [`grpc-inspector`](https://github.com/zentinelproxy/zentinel-agent-grpc-inspector) | gRPC authorization, rate limiting and metadata inspection |
| [`websocket-inspector`](https://github.com/zentinelproxy/zentinel-agent-websocket-inspector) | WebSocket content filtering, schema validation and rate limiting |
| [`soap`](https://github.com/zentinelproxy/zentinel-agent-soap) | SOAP/XML validation, WSDL enforcement and XXE protection |
| [`mqtt-gateway`](https://github.com/zentinelproxy/zentinel-agent-mqtt-gateway) | Topic ACLs, client auth and payload inspection for MQTT over WebSocket |
| [`content-scanner`](https://github.com/zentinelproxy/zentinel-agent-content-scanner) | Malware scanning of request bodies with ClamAV |
| [`spiffe`](https://github.com/zentinelproxy/zentinel-agent-spiffe) | SPIFFE/SPIRE workload identity |
| [`policy`](https://github.com/zentinelproxy/zentinel-agent-policy) | Policy evaluation with Rego (OPA) and Cedar |
| [`audit-logger`](https://github.com/zentinelproxy/zentinel-agent-audit-logger) | Structured audit logging with PII redaction |

### Extensibility and other agents

| Agent | What it does |
|---|---|
| [`lua`](https://github.com/zentinelproxy/zentinel-agent-lua) | Custom request/response logic in Lua |
| [`js`](https://github.com/zentinelproxy/zentinel-agent-js) | Custom request/response logic in JavaScript (QuickJS) |
| [`wasm`](https://github.com/zentinelproxy/zentinel-agent-wasm) | Runs WebAssembly modules in the request pipeline (wasmtime) |
| [`transform`](https://github.com/zentinelproxy/zentinel-agent-transform) | URL rewrites, header changes and JSON body transforms |
| [`image-optimization`](https://github.com/zentinelproxy/zentinel-agent-image-optimization) | On-the-fly JPEG/PNG to WebP/AVIF conversion with caching |
| [`api-deprecation`](https://github.com/zentinelproxy/zentinel-agent-api-deprecation) | `Deprecation`/`Sunset` headers, redirects and blocking for retired endpoints |
| [`mock-server`](https://github.com/zentinelproxy/zentinel-agent-mock-server) | Configurable stub responses for testing |
| [`chaos`](https://github.com/zentinelproxy/zentinel-agent-chaos) | Controlled fault injection for resilience testing |

Every agent has a page in the [agent registry](https://registry.zentinelproxy.io).

### SDKs

Build your own agent against agent protocol v2 ([protocol docs](https://docs.zentinelproxy.io/agents/v2/)).

| Language | Repository |
|---|---|
| Rust | [`zentinel-agent-rust-sdk`](https://github.com/zentinelproxy/zentinel-agent-rust-sdk) |
| Go | [`zentinel-agent-go-sdk`](https://github.com/zentinelproxy/zentinel-agent-go-sdk) |
| Python | [`zentinel-agent-python-sdk`](https://github.com/zentinelproxy/zentinel-agent-python-sdk) (install from the repository; not on PyPI) |
| TypeScript | [`zentinel-agent-typescript-sdk`](https://github.com/zentinelproxy/zentinel-agent-typescript-sdk) |
| Kotlin | [`zentinel-agent-kotlin-sdk`](https://github.com/zentinelproxy/zentinel-agent-kotlin-sdk) |
| Elixir | [`zentinel-agent-elixir-sdk`](https://github.com/zentinelproxy/zentinel-agent-elixir-sdk) |
| Haskell | [`zentinel-agent-haskell-sdk`](https://github.com/zentinelproxy/zentinel-agent-haskell-sdk) |

### Sites and tooling

| Repository | What it does |
|---|---|
| [`zentinelproxy.io`](https://github.com/zentinelproxy/zentinelproxy.io) | The website, [zentinelproxy.io](https://zentinelproxy.io) |
| [`zentinelproxy.io-docs`](https://github.com/zentinelproxy/zentinelproxy.io-docs) | Versioned documentation, [docs.zentinelproxy.io](https://docs.zentinelproxy.io) |
| [`registry.zentinelproxy.io`](https://github.com/zentinelproxy/registry.zentinelproxy.io) | The agent registry, [registry.zentinelproxy.io](https://registry.zentinelproxy.io) |
| [`api.zentinelproxy.io`](https://github.com/zentinelproxy/api.zentinelproxy.io) | Static JSON API for agent registry and bundle metadata, used by `zentinel bundle` |
| [`design`](https://github.com/zentinelproxy/design) | Design tokens and marks shared by the sites |
| [`zentinel-bench`](https://github.com/zentinelproxy/zentinel-bench) | Benchmarks against Envoy, HAProxy and nginx ([results](https://zentinelproxy.io/benchmarks/)) |
| [`wafworth`](https://github.com/zentinelproxy/wafworth) | WAF-agnostic test suite with confusion-matrix metrics and multi-WAF comparison |
| [`.github`](https://github.com/zentinelproxy/.github) | This organization profile |

---

<p align="center">
  <sub>Part of <a href="https://zentinelproxy.io">Zentinel</a>, the security-first reverse proxy. The shisa guards the gate.</sub>
</p>
