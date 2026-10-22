# Agent release pipeline and smoke harness

One release pipeline for every Zentinel agent repository, so that a release is
always built from its tag, run behind a real Zentinel on every platform, and
published under exactly the asset names `zentinel bundle install` downloads.

- [`.github/workflows/agent-release.yml`](../.github/workflows/agent-release.yml):
  reusable workflow (`on: workflow_call`) that checks, builds, smoke-tests and
  publishes.
- [`agent-smoke/smoke.py`](smoke.py): the smoke harness the workflow runs
  (Python 3.8+, standard library only). It also runs locally.

Both are versioned together by tag. Callers pin `@v1`; `v1` moves forward only
for compatible changes.

## What a release does

1. **plan**: the tag must equal `v` + the version of the package that owns
   `binary` (read with `cargo metadata`), and a release for that tag must not
   exist yet. Resolves the Zentinel release to test against (default: the
   latest).
2. **build**, one job per platform on a native runner (no cross-compiling):
   `cargo build --release --locked --bin <binary>` from the tag; strip;
   `<binary> --version` must print exactly `<binary> <version>`; download that
   Zentinel release for the platform and check its `.sha256`; run your
   `smoke-command`; package `<binary>-<version>-<platform>.tar.gz` (the binary
   at the archive root) and `<...>.tar.gz.sha256`.
3. **publish**, only on a tag push and only after every platform passed: check
   every asset and checksum is there, then `gh release create --verify-tag`.
   That fails if the release exists, so a published release is never replaced.

Any other trigger (manual dispatch, a branch push, a pull request) is a dry run
that does everything except publish.

The asset URL is the one `crates/proxy/src/bundle/lock.rs` in
zentinelproxy/zentinel builds, and that `scripts/check-bundle-lock.py` checks:

```
https://github.com/<repo>/releases/download/v<version>/<binary>-<version>-<platform>.tar.gz
```

| Platform | Runner | Rust target | Zentinel asset |
|---|---|---|---|
| `linux-x86_64` | `ubuntu-24.04` | `x86_64-unknown-linux-gnu` | `linux-amd64` |
| `linux-aarch64` | `ubuntu-24.04-arm` | `aarch64-unknown-linux-gnu` | `linux-arm64` |
| `darwin-aarch64` | `macos-14` | `aarch64-apple-darwin` | `darwin-arm64` |
| `darwin-x86_64` | `macos-13` | `x86_64-apple-darwin` | `darwin-amd64` |

The default is the first three, which is what `bundle-versions.lock` lists.

## Using it

`release.yml` in the agent repository:

```yaml
name: Release

on:
  push:
    tags: ['v*']
  workflow_dispatch:   # dry run

permissions:
  contents: write      # only the publish job uses it

jobs:
  release:
    uses: zentinelproxy/.github/.github/workflows/agent-release.yml@v1
    with:
      binary: zentinel-foo-agent
      smoke-command: scripts/smoke-test.sh
```

The smoke job in `ci.yml` is the same pipeline on one platform. It never
publishes, so it can stay read-only:

```yaml
  smoke:
    name: Smoke
    uses: zentinelproxy/.github/.github/workflows/agent-release.yml@v1
    permissions:
      contents: read
    with:
      binary: zentinel-foo-agent
      smoke-command: scripts/smoke-test.sh
      platforms: '["linux-x86_64"]'
      cache: true
```

To release: bump `version` in `Cargo.toml`, commit it together with the
updated `Cargo.lock`, merge, then tag that commit:

```bash
git tag -a v0.4.0 -m "v0.4.0" && git push origin v0.4.0
```

### Inputs

| Input | Default | Meaning |
|---|---|---|
| `binary` | required | The `[[bin]]` name, e.g. `zentinel-waf-agent` |
| `smoke-command` | required | Shell command run in the repository root on every platform; must exit 0 |
| `platforms` | `["linux-x86_64", "linux-aarch64", "darwin-aarch64"]` | JSON list from the table above |
| `zentinel-version` | `latest` | Zentinel release tag to smoke-test against, e.g. `26.10_7` |
| `cargo-features` | empty | `--features` value |
| `cargo-no-default-features` | `false` | Build with `--no-default-features` |
| `apt-packages` | `protobuf-compiler` | Installed on Linux before the build |
| `brew-packages` | `protobuf` | Installed on macOS before the build |
| `setup-linux` / `setup-macos` | empty | Extra shell before the build (e.g. build libmodsecurity, install ClamAV); may write `$GITHUB_ENV` |
| `siblings` | empty | Path dependencies: one `owner/repo@ref` per line, cloned to `../<repo>`. Pin a SHA or tag |
| `rust-toolchain` | `stable` | For `dtolnay/rust-toolchain` |
| `harness-ref` | `v1` | Ref of this repository to take `smoke.py` from; keep it equal to the `@ref` you call |
| `publish` | `true` | `false` turns tag pushes into dry runs too |
| `cache` | `false` | `Swatinem/rust-cache` (for CI callers; releases build clean) |

Outputs: `version`, `zentinel-release`.

The smoke command gets in its environment: `AGENT_BIN` (the stripped release
binary), `ZENTINEL_BIN`, `AGENT_SMOKE` (path to `smoke.py`), `AGENT_VERSION`,
`PLATFORM`, `ZENTINEL_RELEASE`.

Example of extra build dependencies (the modsec agent):

```yaml
    with:
      binary: zentinel-modsec-agent
      apt-packages: >-
        protobuf-compiler build-essential libtool autoconf automake pkg-config
        libcurl4-openssl-dev libpcre3-dev libpcre2-dev libyajl-dev libxml2-dev
      brew-packages: protobuf modsecurity
      setup-linux: |
        git clone --depth 1 --branch v3.0.14 https://github.com/owasp-modsecurity/ModSecurity.git /tmp/modsecurity
        cd /tmp/modsecurity && git submodule update --init && ./build.sh
        ./configure --prefix=/usr/local --without-lmdb && make -j"$(nproc)" && sudo make install
        sudo ldconfig
        echo "PKG_CONFIG_PATH=/usr/local/lib/pkgconfig" >> "$GITHUB_ENV"
      smoke-command: scripts/smoke-test.sh
```

## The smoke harness

```
python3 smoke.py --agent <agent-binary> --zentinel <zentinel-binary> [options]
```

It starts an upstream fixture (200 `upstream-ok`, records what it got), the
agent (Unix socket by default, `--transport grpc` for gRPC), and a Zentinel
whose generated config puts the agent on one route with the agent, the filter
and the route all `failure-mode "closed"`. Then:

1. **handshake + allow**: the clean request (`--clean`, default `GET /smoke`
   expecting 200 from the upstream) gets its expected answer. Under
   fail-closed this needs a completed v2 handshake and the agent's decision.
   The report also says whether the proxy logged `handshake successful`.
2. **cases**: each `--case` / `--cases` request gets its expected status, and
   reaches the upstream only when that status is 2xx.
3. **kill**: the agent is stopped; the clean request must stop getting its
   answer and must not reach the upstream. If it still does, the agent was
   never on the request path.

Request specs are JSON:

```json
{"name": "missing API key", "method": "GET", "path": "/smoke",
 "headers": {"X-API-Key": "k"}, "body": "...", "expect": 401,
 "reaches_upstream": false,
 "upstream_headers": {"X-User-Id": "smoke", "X-Auth-Method": null},
 "upstream_lacks_headers": ["X-SPIFFE-Id"]}
```

Only `expect` is required for a case (`--clean` defaults it to 200).
`upstream_headers` (`null` = any value) and `upstream_lacks_headers` check the
request the upstream received, to prove the agent added or removed a header.

Main options: `--agent-arg ARG` (repeatable), `--agent-env K=V`,
`--transport-args` (replace the default `--socket {socket}` /
`--grpc-address {grpc_address}`), `--agent-config` (KDL body of the agent's
`config { }` block, or `@file`), `--events`, `--name`, `--type`,
`--timeout-ms`, `--report out.json`, `--keep-work`. Arguments may use
`{socket}`, `{grpc_address}`, `{grpc_port}`, `{work}` and `{cwd}`.

Exit status: 0 pass, 2 usage, 10 the agent did not start, 11 Zentinel rejected
the config or did not start, 12 the clean request failed, 13 a case failed,
14 the kill check failed.

An agent's `scripts/smoke-test.sh` usually is just the call with its cases:

```bash
python3 "$AGENT_SMOKE" --agent "$AGENT_BIN" --zentinel "$ZENTINEL_BIN" \
    --agent-arg=--api-keys --agent-arg "$KEY:smoke" \
    --clean "{\"headers\": {\"X-API-Key\": \"$KEY\"}}" \
    --case '{"name": "missing API key", "expect": 401}'
```

`config { }` blocks are delivered to agents only by Zentinel builds that
include zentinelproxy/zentinel#603 (after 26.10_7). Against older releases,
configure the agent through its command line.

Locally:

```bash
gh release download 26.10_7 --repo zentinelproxy/zentinel \
  --pattern 'zentinel-26.10_7-darwin-arm64.tar.gz*'
shasum -a 256 -c zentinel-26.10_7-darwin-arm64.tar.gz.sha256 && tar xzf zentinel-26.10_7-darwin-arm64.tar.gz
cargo build --release --locked
AGENT_SMOKE=../.github/agent-smoke/smoke.py scripts/smoke-test.sh target/release/zentinel-foo-agent ./zentinel
```

## Versioning

Tag this repository `v1.0.0` and move `v1` with it for every compatible
change; a breaking change to an input, an output or the harness interface is
`v2`. While the pipeline is being piloted, callers pin the branch
(`@ci/agent-release`, with `harness-ref: ci/agent-release`).
