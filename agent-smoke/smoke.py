#!/usr/bin/env python3
"""Smoke-test a Zentinel agent binary behind a real Zentinel.

    python3 smoke.py --agent <agent-binary> --zentinel <zentinel-binary> [options]

Starts, in a scratch directory:

  * an upstream fixture that answers every request with 200 "upstream-ok"
    and records what it received;
  * the agent, listening on a Unix socket (default) or on gRPC;
  * a Zentinel with a generated config: one route to the upstream through
    an agent filter, with the agent, the filter and the route all
    `failure-mode "closed"`.

and then checks, in order:

  1. handshake + allow: the clean request is answered with --clean's expected
     status (default 200, served by the upstream). Fail-closed means this
     cannot pass unless the proxy completed the v2 handshake with the agent
     and got its decision back;
  2. every --case / --cases request gets its expected status, and reaches the
     upstream only if that status is 2xx (override with "reaches_upstream");
  3. kill: with the agent stopped, the clean request is no longer answered
     the way it was in 1., and does not reach the upstream. If it still is,
     the agent was never on the request path.

Request specs (--clean, --case and each entry of a --cases file) are JSON
objects:

    {"name": "missing API key", "method": "GET", "path": "/",
     "headers": {"X-API-Key": "k"}, "body": "...", "expect": 401,
     "reaches_upstream": false,
     "upstream_headers": {"X-User-Id": "smoke", "X-Added": null},
     "upstream_lacks_headers": ["X-Forged"]}

"upstream_headers" (value null = any value) and "upstream_lacks_headers"
check the request the upstream received, so a case can prove that the agent
added or stripped a header.

Only "expect" is required for a case; "path" defaults to "/smoke",
"method" to GET. --clean defaults to {"path": "/smoke", "expect": 200}.

Agent arguments: by default the transport arguments are added for you
(`--socket {socket}` for uds, `--grpc-address {grpc_address}` for grpc);
pass --transport-args to replace them. Any --agent-arg, --transport-args,
--agent-env value and the --agent-config text may use the placeholders
{socket}, {grpc_address}, {grpc_port}, {work} (the scratch directory) and
{cwd} (the directory the harness was started from).

Exit status: 0 pass; 2 usage; 10 agent did not start; 11 zentinel rejected
the config or did not start; 12 clean request failed (handshake or allow);
13 a case failed; 14 kill check failed. A one-line JSON summary is written to
--report if given.

Requires Python 3.8+ and nothing else (no curl, no third-party modules).
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

EXIT_USAGE = 2
EXIT_AGENT_START = 10
EXIT_ZENTINEL_START = 11
EXIT_CLEAN = 12
EXIT_CASE = 13
EXIT_KILL = 14

UPSTREAM_BODY = b"upstream-ok\n"


class SmokeFailure(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


# --- upstream fixture -----------------------------------------------------------


class Upstream:
    """In-process HTTP server that answers 200 and counts what it received."""

    def __init__(self) -> None:
        self.requests: list[str] = []
        self.last_headers: dict[str, str] = {}
        lock = threading.Lock()
        seen = self.requests
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def _ok(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                if length:
                    self.rfile.read(length)
                with lock:
                    seen.append(self.requestline)
                    outer.last_headers = {k.lower(): v for k, v in self.headers.items()}
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(UPSTREAM_BODY)))
                self.end_headers()
                self.wfile.write(UPSTREAM_BODY)

            do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = _ok

            def log_message(self, *args) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def count(self) -> int:
        return len(self.requests)

    def stop(self) -> None:
        self.server.shutdown()


# --- helpers --------------------------------------------------------------------


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def tcp_ready(port: int) -> bool:
    try:
        socket.create_connection(("127.0.0.1", port), 1).close()
        return True
    except OSError:
        return False


def kdl_string(value: str) -> str:
    return json.dumps(value)


def parse_spec(text: str, what: str, default_expect: int | None = None) -> dict:
    try:
        spec = json.loads(text)
    except json.JSONDecodeError as e:
        raise SmokeFailure(EXIT_USAGE, f"{what}: not valid JSON ({e}): {text}")
    if not isinstance(spec, dict):
        raise SmokeFailure(EXIT_USAGE, f"{what}: must be a JSON object: {text}")
    return normalize_spec(spec, what, default_expect)


def normalize_spec(spec: dict, what: str, default_expect: int | None = None) -> dict:
    spec = dict(spec)
    if "expect" not in spec:
        if default_expect is None:
            raise SmokeFailure(EXIT_USAGE, f"{what}: missing \"expect\" (the expected status)")
        spec["expect"] = default_expect
    spec["expect"] = int(spec["expect"])
    spec.setdefault("method", "GET")
    spec.setdefault("path", "/smoke")
    spec.setdefault("headers", {})
    spec.setdefault("name", f"{spec['method']} {spec['path']}")
    spec.setdefault("reaches_upstream", 200 <= spec["expect"] < 300)
    if not str(spec["path"]).startswith("/"):
        raise SmokeFailure(EXIT_USAGE, f"{what}: path must start with '/': {spec['path']}")
    return spec


class Harness:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.cwd = os.getcwd()
        self.agent_bin = str(Path(args.agent).resolve())
        self.zentinel_bin = str(Path(args.zentinel).resolve())
        self.work = Path(tempfile.mkdtemp(prefix="zentinel-smoke."))
        # Unix socket paths are limited to ~104 bytes and TMPDIR on macOS
        # runners is long, so the socket gets its own short directory.
        self.socket_dir = Path(tempfile.mkdtemp(prefix="zs.", dir=args.socket_dir))
        self.socket = str(self.socket_dir / "agent.sock")
        self.grpc_port = free_port()
        self.proxy_port = free_port()
        self.metrics_port = free_port()
        self.procs: dict[str, subprocess.Popen] = {}
        self.logs: dict[str, Path] = {}
        self.upstream: Upstream | None = None
        self.report: dict = {
            "agent": self.agent_bin,
            "zentinel": self.zentinel_bin,
            "transport": args.transport,
            "handshake": None,
            "clean": None,
            "cases": [],
            "kill": None,
            "result": "fail",
        }

    # placeholders --------------------------------------------------------------

    def subst(self, text: str) -> str:
        return (
            text.replace("{socket}", self.socket)
            .replace("{grpc_address}", f"127.0.0.1:{self.grpc_port}")
            .replace("{grpc_port}", str(self.grpc_port))
            .replace("{work}", str(self.work))
            .replace("{cwd}", self.cwd)
        )

    # processes -----------------------------------------------------------------

    def spawn(self, name: str, argv: list[str], env: dict | None = None) -> subprocess.Popen:
        log = self.work / f"{name}.log"
        self.logs[name] = log
        fh = open(log, "ab")
        proc = subprocess.Popen(
            argv,
            stdout=fh,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=env,
            cwd=self.cwd,
            start_new_session=True,
        )
        self.procs[name] = proc
        return proc

    def stop(self, name: str, grace: float = 5.0) -> None:
        proc = self.procs.get(name)
        if proc is None or proc.poll() is not None:
            return
        try:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        except ProcessLookupError:
            pass

    def cleanup(self) -> None:
        for name in list(self.procs):
            self.stop(name, grace=2.0)
        if self.upstream:
            self.upstream.stop()
        if not self.args.keep_work:
            shutil.rmtree(self.work, ignore_errors=True)
        shutil.rmtree(self.socket_dir, ignore_errors=True)

    def dump_logs(self) -> None:
        for name, path in self.logs.items():
            try:
                lines = path.read_text(errors="replace").splitlines()
            except OSError:
                continue
            print(f"----- {name} log (last 60 lines) -----", file=sys.stderr)
            for line in lines[-60:]:
                print(line, file=sys.stderr)
        if self.args.keep_work:
            print(f"(scratch directory kept: {self.work})", file=sys.stderr)

    def log_text(self, name: str) -> str:
        path = self.logs.get(name)
        try:
            return path.read_text(errors="replace") if path else ""
        except OSError:
            return ""

    # steps ---------------------------------------------------------------------

    def start_agent(self) -> None:
        a = self.args
        if a.transport_args is not None:
            transport = shlex.split(self.subst(a.transport_args))
        elif a.transport == "uds":
            transport = ["--socket", self.socket]
        else:
            transport = ["--grpc-address", f"127.0.0.1:{self.grpc_port}"]
        argv = [self.agent_bin, *transport, *[self.subst(x) for x in a.agent_arg]]
        env = dict(os.environ)
        env.setdefault("RUST_LOG", "info")
        for kv in a.agent_env:
            if "=" not in kv:
                raise SmokeFailure(EXIT_USAGE, f"--agent-env expects KEY=VALUE, got {kv}")
            k, v = kv.split("=", 1)
            env[k] = self.subst(v)
        print("agent argv: " + " ".join(shlex.quote(x) for x in argv))
        proc = self.spawn("agent", argv, env)

        deadline = time.monotonic() + a.startup_timeout
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise SmokeFailure(EXIT_AGENT_START, f"agent exited during startup (status {proc.returncode})")
            if a.transport == "uds" and os.path.exists(self.socket):
                return
            if a.transport == "grpc" and tcp_ready(self.grpc_port):
                return
            time.sleep(0.2)
        where = self.socket if a.transport == "uds" else f"127.0.0.1:{self.grpc_port}"
        raise SmokeFailure(EXIT_AGENT_START, f"agent did not listen on {where} within {a.startup_timeout}s")

    def zentinel_config(self) -> str:
        a = self.args
        if a.transport == "uds":
            transport = f"unix-socket path={kdl_string(self.socket)}"
        else:
            transport = f"grpc address={kdl_string(f'http://127.0.0.1:{self.grpc_port}')}"
        events = " ".join(kdl_string(e.strip()) for e in a.events.split(",") if e.strip())
        config_block = ""
        if a.agent_config:
            text = a.agent_config
            if text.startswith("@"):
                text = Path(text[1:]).read_text()
            body = textwrap.indent(self.subst(text).strip("\n"), " " * 12)
            config_block = f"\n        config {{\n{body}\n        }}"
        name = kdl_string(a.name)
        return f"""\
system {{
    worker-threads 1
    graceful-shutdown-timeout-secs 1
}}

listeners {{
    listener "http" {{
        address "127.0.0.1:{self.proxy_port}"
        protocol "http"
    }}
}}

routes {{
    route "protected" {{
        matches {{
            path-prefix "/"
        }}
        upstream "backend"
        filters {name}
        policies {{
            failure-mode "closed"
        }}
    }}
}}

agents {{
    agent {name} type={kdl_string(a.type)} {{
        {transport}
        events {events}
        timeout-ms {a.timeout_ms}
        failure-mode "closed"{config_block}
    }}
}}

filters {{
    filter {name} {{
        type "agent"
        agent {name}
        timeout-ms {a.timeout_ms}
        failure-mode "closed"
    }}
}}

upstreams {{
    upstream "backend" {{
        target "127.0.0.1:{self.upstream.port}"
    }}
}}

observability {{
    metrics {{
        address "127.0.0.1:{self.metrics_port}"
        path "/metrics"
    }}
}}
"""

    def start_zentinel(self) -> None:
        cfg = self.work / "zentinel.kdl"
        cfg.write_text(self.zentinel_config())
        test = subprocess.run(
            [self.zentinel_bin, "test", "--config", str(cfg)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=self.cwd,
        )
        (self.work / "zentinel-test.log").write_bytes(test.stdout)
        self.logs["zentinel-test"] = self.work / "zentinel-test.log"
        if test.returncode != 0:
            print(cfg.read_text(), file=sys.stderr)
            raise SmokeFailure(EXIT_ZENTINEL_START, "zentinel rejected the smoke-test config")
        self.spawn("zentinel", [self.zentinel_bin, "--config", str(cfg)])

    def request(self, spec: dict) -> tuple[int, bytes]:
        """Send one request; status 0 means no HTTP response at all."""
        body = spec.get("body")
        data = body.encode() if isinstance(body, str) else None
        headers = dict(spec.get("headers") or {})
        if data is not None:
            headers.setdefault("Content-Type", "application/octet-stream")
        conn = http.client.HTTPConnection("127.0.0.1", self.proxy_port, timeout=10)
        try:
            conn.request(spec["method"], spec["path"], body=data, headers=headers)
            resp = conn.getresponse()
            return resp.status, resp.read()
        except (OSError, http.client.HTTPException):
            return 0, b""
        finally:
            conn.close()

    def check(self, spec: dict, code_on_fail: int) -> dict:
        before = self.upstream.count()
        status, body = self.request(spec)
        reached = self.upstream.count() > before
        result = {"name": spec["name"], "expect": spec["expect"], "status": status, "reached_upstream": reached}
        if status != spec["expect"]:
            raise SmokeFailure(code_on_fail, f"{spec['name']}: expected {spec['expect']}, got {status or 'no response'}")
        if spec["reaches_upstream"] and not (reached and body == UPSTREAM_BODY):
            raise SmokeFailure(code_on_fail, f"{spec['name']}: {status} but the response did not come from the upstream")
        if not spec["reaches_upstream"] and reached:
            raise SmokeFailure(code_on_fail, f"{spec['name']}: the upstream received the request")
        got = self.upstream.last_headers if reached else {}
        for name, want in (spec.get("upstream_headers") or {}).items():
            have = got.get(name.lower())
            if have is None or (want is not None and have != want):
                raise SmokeFailure(
                    code_on_fail,
                    f"{spec['name']}: upstream header {name} is {have!r}, expected {'any value' if want is None else repr(want)}",
                )
        for name in spec.get("upstream_lacks_headers") or []:
            if name.lower() in got:
                raise SmokeFailure(
                    code_on_fail, f"{spec['name']}: the upstream received header {name}: {got[name.lower()]!r}"
                )
        return result

    def run(self, clean: dict, cases: list[dict]) -> None:
        a = self.args
        print(f"agent:    {self.agent_bin}")
        ver = subprocess.run([self.agent_bin, "--version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        print("          " + (ver.stdout.decode(errors="replace").strip() or f"(--version exited {ver.returncode})"))
        print(f"zentinel: {self.zentinel_bin}")
        zver = subprocess.run([self.zentinel_bin, "--version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        print("          " + zver.stdout.decode(errors="replace").strip())

        self.upstream = Upstream()
        self.start_agent()
        self.start_zentinel()

        # 1. Clean request, retried until the proxy is up and the agent
        #    connection is established.
        status = 0
        deadline = time.monotonic() + a.startup_timeout
        while time.monotonic() < deadline:
            zp = self.procs["zentinel"]
            if zp.poll() is not None:
                raise SmokeFailure(EXIT_ZENTINEL_START, f"zentinel exited during startup (status {zp.returncode})")
            before = self.upstream.count()
            status, body = self.request(clean)
            if status == clean["expect"]:
                break
            if status != 0 and before == self.upstream.count() and status not in (502, 503, 504, 500):
                # A definite answer that is not the expected one: no point retrying for a minute.
                time.sleep(1)
                status, body = self.request(clean)
                break
            time.sleep(0.5)
        time.sleep(0.2)
        self.report["handshake"] = "handshake successful" in self.log_text("zentinel").lower()
        try:
            self.report["clean"] = self.check(clean, EXIT_CLEAN)
        except SmokeFailure as e:
            self.report["clean"] = {"name": clean["name"], "expect": clean["expect"], "status": status}
            hs = "the proxy logged a successful handshake" if self.report["handshake"] else "the proxy never logged a successful handshake"
            raise SmokeFailure(e.code, f"{e} ({hs})")
        print(f"ok   handshake {'logged' if self.report['handshake'] else 'not logged'}; clean request answered {clean['expect']}")

        # 2. Per-agent cases.
        for spec in cases:
            self.report["cases"].append(self.check(spec, EXIT_CASE))
            print(f"ok   {spec['name']}: {spec['expect']}")
        if cases:
            self.check(clean, EXIT_CASE)
            print("ok   clean request still answered after the cases")

        # 3. Kill the agent: under fail-closed the clean request must stop
        #    being answered the same way.
        self.stop("agent", grace=5.0)
        deadline = time.monotonic() + 10
        status, reached = clean["expect"], True
        while time.monotonic() < deadline:
            before = self.upstream.count()
            status, _ = self.request(clean)
            reached = self.upstream.count() > before
            if status != clean["expect"] and not reached:
                break
            time.sleep(0.5)
        self.report["kill"] = {"status": status, "reached_upstream": reached}
        if status == clean["expect"] or reached:
            raise SmokeFailure(
                EXIT_KILL,
                f"with the agent stopped the clean request still got {status}"
                f"{' from the upstream' if reached else ''}: the agent was not on the request path",
            )
        print(f"ok   with the agent stopped the clean request is refused ({status or 'no response'})")
        self.report["result"] = "pass"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--agent", required=True, help="agent binary")
    p.add_argument("--zentinel", required=True, help="zentinel binary")
    p.add_argument("--name", help="agent and filter id in the generated config (default: from the binary name)")
    p.add_argument("--type", default="custom", help='agent type= in the config (default "custom")')
    p.add_argument("--transport", choices=["uds", "grpc"], default="uds")
    p.add_argument("--transport-args", help="replace the default transport arguments (shell-quoted string)")
    p.add_argument("--agent-arg", action="append", default=[], help="extra agent argument (repeatable)")
    p.add_argument("--agent-env", action="append", default=[], help="KEY=VALUE for the agent (repeatable)")
    p.add_argument("--agent-config", help="KDL body of the agent's config { } block, or @file")
    p.add_argument("--events", default="request_headers", help="comma-separated agent events (default request_headers)")
    p.add_argument("--timeout-ms", type=int, default=2000, help="agent and filter timeout-ms (default 2000)")
    p.add_argument("--clean", default='{"path": "/smoke"}', help='clean request spec (default {"path": "/smoke"}, expect 200)')
    p.add_argument("--case", action="append", default=[], help="request spec JSON (repeatable)")
    p.add_argument("--cases", action="append", default=[], help="JSON file with a list of request specs (repeatable)")
    p.add_argument("--startup-timeout", type=float, default=float(os.environ.get("SMOKE_STARTUP_TIMEOUT", 60)))
    p.add_argument("--socket-dir", default=os.environ.get("SMOKE_SOCKET_DIR", "/tmp"))
    p.add_argument("--keep-work", action="store_true", default=os.environ.get("KEEP_WORK") == "1")
    p.add_argument("--report", help="write a JSON summary here")
    a = p.parse_args(argv)

    if not a.name:
        base = Path(a.agent).name
        if base.startswith("zentinel-") and base.endswith("-agent"):
            a.name = base[len("zentinel-") : -len("-agent")]
        else:
            a.name = "agent"

    harness = None
    code = 0
    try:
        clean = parse_spec(a.clean, "--clean", default_expect=200)
        cases = [parse_spec(c, "--case") for c in a.case]
        for f in a.cases:
            data = json.loads(Path(f).read_text())
            if not isinstance(data, list):
                raise SmokeFailure(EXIT_USAGE, f"{f}: must contain a JSON list of request specs")
            cases += [normalize_spec(c, f"{f}[{i}]") for i, c in enumerate(data)]
        for path in (a.agent, a.zentinel):
            if not os.access(path, os.X_OK):
                raise SmokeFailure(EXIT_USAGE, f"not an executable: {path}")
        harness = Harness(a)
        harness.run(clean, cases)
        print(f"PASS: {a.name} agent smoke test")
    except SmokeFailure as e:
        code = e.code
        print(f"FAIL: {e}", file=sys.stderr)
        if harness:
            harness.dump_logs()
    except KeyboardInterrupt:
        code = 130
    finally:
        if harness:
            harness.cleanup()
            if a.report:
                harness.report["exit"] = code
                Path(a.report).write_text(json.dumps(harness.report) + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
