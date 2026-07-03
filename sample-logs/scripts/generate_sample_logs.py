"""Generates large, realistic multi-thousand-line sample logs for the three
supported domains (kubernetes, nginx, system). Each file is mostly routine
noise with one real incident buried inside, so it exercises log_processor.py's
error-context extraction on a non-trivial volume of input.

Usage: python3 generate_sample_logs.py [--lines N] [--seed N]
"""
import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent

PODS = ["checkout-api", "cart-svc", "catalog-svc", "auth-svc", "search-svc", "recommend-svc"]
NODES = [f"node-worker-{i}" for i in range(1, 7)]
ROUTES = ["/api/cart/summary", "/api/products", "/api/checkout/session",
          "/api/search?q=shoes", "/api/recommend", "/api/user/profile"]
CLIENTS = [f"192.168.1.{i}" for i in range(10, 240)]
UAS = ["Mozilla/5.0", "okhttp/4.9.3", "curl/8.4.0", "Go-http-client/2.0"]
UPSTREAM_HOSTS = [f"10.0.2.{i}" for i in range(10, 30)]


def ts(base, offset_s):
    return (base + timedelta(seconds=offset_s)).strftime("%Y-%m-%dT%H:%M:%SZ")


def gen_kubernetes(n_lines: int, base: datetime, rng: random.Random) -> str:
    lines = []
    t = 0
    incident_at = int(n_lines * rng.uniform(0.55, 0.7))
    for i in range(n_lines):
        t += rng.randint(1, 4)
        pod = rng.choice(PODS)
        node = rng.choice(NODES)
        pod_id = f"{pod}-7f6d9c8b5f-{rng.randrange(1000,9999):x}"

        if i == incident_at:
            # Inject the real incident: memory climb -> OOMKill -> CrashLoopBackOff
            target_pod = f"checkout-api-7f6d9c8b5f-x2n4q"
            for pct, mib in [(82, 410), (89, 445), (94, 470), (98, 490)]:
                t += rng.randint(3, 8)
                lines.append(f"{ts(base,t)} WARN  checkout-api[x2n4q]: memory usage at {pct}% of limit ({mib}Mi/500Mi)")
            t += 2
            lines.append(f"{ts(base,t)} INFO  checkout-api[x2n4q]: cache warm-up job started (promo-catalog-sync)")
            t += 3
            lines.append(f"{ts(base,t)} ERROR checkout-api[x2n4q]: java.lang.OutOfMemoryError: Java heap space")
            lines.append(f"{ts(base,t)} ERROR checkout-api[x2n4q]:   at com.acme.catalog.PromoCatalogSync.loadFullCatalog(PromoCatalogSync.java:88)")
            lines.append(f"{ts(base,t)} ERROR checkout-api[x2n4q]:   at com.acme.catalog.PromoCatalogSync.run(PromoCatalogSync.java:41)")
            t += 1
            lines.append(f"{ts(base,t)} CRITICAL kubelet[node-worker-3]: Memory cgroup out of memory: Killed process 18422 (java) total-vm:2145332kB, anon-rss:512000kB")
            lines.append(f"{ts(base,t)} CRITICAL kubelet[node-worker-3]: Container checkout-api in pod {target_pod} terminated with reason OOMKilled, exit code 137")
            t += 1
            lines.append(f"{ts(base,t)} WARN  kubelet[node-worker-3]: Back-off restarting failed container checkout-api in pod {target_pod}")
            t += 12
            lines.append(f"{ts(base,t)} INFO  kube-scheduler: Pod {target_pod} rescheduled, restartCount=1")
            # repeat twice more, escalating
            for restart in (2, 3):
                t += rng.randint(280, 320)
                lines.append(f"{ts(base,t)} WARN  checkout-api[x2n4q]: memory usage at 88% of limit (440Mi/500Mi)")
                t += 3
                lines.append(f"{ts(base,t)} INFO  checkout-api[x2n4q]: cache warm-up job started (promo-catalog-sync)")
                t += 30
                lines.append(f"{ts(base,t)} ERROR checkout-api[x2n4q]: java.lang.OutOfMemoryError: Java heap space")
                t += 1
                lines.append(f"{ts(base,t)} CRITICAL kubelet[node-worker-3]: Container checkout-api in pod {target_pod} terminated with reason OOMKilled, exit code 137")
                lines.append(f"{ts(base,t)} WARN  kubelet[node-worker-3]: Back-off restarting failed container checkout-api in pod {target_pod}, restartCount={restart}")
            t += 2
            lines.append(f"{ts(base,t)} CRITICAL kube-scheduler: Pod {target_pod} has restarted 3 times in 10 minutes, marked CrashLoopBackOff")
            lines.append(f"{ts(base,t)} ERROR ingress-nginx: upstream {target_pod} unavailable, returning 503 to client")
            t += 8
            lines.append(f"{ts(base,t)} ERROR ingress-nginx: upstream {target_pod} unavailable, returning 503 to client")
            t += 20
            lines.append(f"{ts(base,t)} WARN  alertmanager: Alert firing - CheckoutAPICrashLoopBackOff (severity=critical, namespace=prod)")
            continue

        # routine noise
        kind = rng.choices(
            ["req", "probe", "sync", "scale"],
            weights=[70, 20, 8, 2],
        )[0]
        if kind == "req":
            route = rng.choice(ROUTES)
            latency = rng.randint(15, 140)
            lines.append(f"{ts(base,t)} INFO  {pod}[{pod_id[-5:]}]: GET {route} 200 {latency}ms")
        elif kind == "probe":
            lines.append(f"{ts(base,t)} INFO  kubelet[{node}]: Readiness probe succeeded for pod {pod_id}")
        elif kind == "sync":
            lines.append(f"{ts(base,t)} INFO  kubelet[{node}]: SyncLoop (ADD): \"{pod_id}_prod({rng.randrange(0x1000,0xffff):x})\"")
        else:
            lines.append(f"{ts(base,t)} INFO  kube-scheduler: HorizontalPodAutoscaler {pod} scaled to {rng.randint(3,10)} replicas")

    return "\n".join(lines) + "\n"


def nginx_clf_ts(base, offset_s):
    return (base + timedelta(seconds=offset_s)).strftime("%d/%b/%Y:%H:%M:%S +0000")


def nginx_err_ts(base, offset_s):
    return (base + timedelta(seconds=offset_s)).strftime("%Y/%m/%d %H:%M:%S")


def gen_nginx(n_lines: int, base: datetime, rng: random.Random) -> str:
    lines = []
    t = 0
    incident_at = int(n_lines * rng.uniform(0.5, 0.65))
    incident_len = 0
    in_incident = False
    incident_upstream_down = set()

    while len(lines) < n_lines:
        t += rng.randint(1, 3)
        client = rng.choice(CLIENTS)
        ua = rng.choice(UAS)

        if len(lines) == incident_at and not in_incident:
            in_incident = True
            incident_len = rng.randint(30, 45)
            incident_upstream_down = {rng.choice(UPSTREAM_HOSTS), rng.choice(UPSTREAM_HOSTS)}

        if in_incident and incident_len > 0:
            phase = rng.choices(["refused", "no_live", "recovered", "client502"], weights=[45, 15, 10, 30])[0]
            host = rng.choice(list(incident_upstream_down))
            if phase == "refused":
                lines.append(f"{nginx_err_ts(base,t)} [error] 2891#2891: *{4000+len(lines)} connect() failed (111: Connection refused) while connecting to upstream, client: {client}, server: api.acme.internal, request: \"GET /api/orders/{889200+len(lines)} HTTP/1.1\", upstream: \"http://{host}:8080/api/orders\", host: \"api.acme.internal\"")
            elif phase == "no_live":
                lines.append(f"{nginx_err_ts(base,t)} [alert] 2891#2891: *{4000+len(lines)} all upstream servers in group orders_backend are marked down, retrying in 5s")
            elif phase == "recovered" and incident_len < 5:
                lines.append(f"{nginx_err_ts(base,t)} [warn] 2891#2891: *{4000+len(lines)} upstream server orders_backend/{host}:8080 restored, resuming health checks")
            else:
                lines.append(f"{client} - - [{nginx_clf_ts(base,t)}] \"GET /api/orders/{889200+len(lines)} HTTP/1.1\" 502 559 \"-\" \"{ua}\"")
            incident_len -= 1
            if incident_len <= 0:
                in_incident = False
            continue

        # routine noise: normal 200s across a handful of routes
        route = rng.choice(["/api/products?page=1", "/api/products?page=2", "/api/orders", "/api/cart", "/api/search?q=laptop"])
        status = rng.choices([200, 200, 200, 201, 304], weights=[60, 20, 10, 5, 5])[0]
        size = rng.randint(300, 3500)
        method = "POST" if route == "/api/orders" and rng.random() < 0.4 else "GET"
        lines.append(f"{client} - - [{nginx_clf_ts(base,t)}] \"{method} {route} HTTP/1.1\" {status} {size} \"-\" \"{ua}\"")

    return "\n".join(lines[:n_lines]) + "\n"


def gen_system(n_lines: int, base: datetime, rng: random.Random) -> str:
    lines = []
    t = 0
    host = "db-primary-01"
    incident_at = int(n_lines * rng.uniform(0.6, 0.75))

    for i in range(n_lines):
        t += rng.randint(20, 90)

        if i == incident_at:
            for pct, gb in [(89, 178), (93, 186), (100, 200)]:
                t += rng.randint(300, 900)
                lines.append(f"{ts(base,t)} {host} monitoring-agent[771]: disk usage /var {pct}% ({gb}G/200G)")
            t += 60
            lines.append(f"{ts(base,t)} {host} postgres[8890]: WARNING:  could not write to file \"pg_wal/000000010000000000000091\": No space left on device")
            lines.append(f"{ts(base,t)} {host} postgres[8890]: ERROR:  could not extend file \"base/16401/16789\": No space left on device")
            lines.append(f"{ts(base,t)} {host} postgres[8890]: HINT:  Check free disk space.")
            t += 1
            lines.append(f"{ts(base,t)} {host} kernel: EXT4-fs error (device nvme0n1p1): ext4_do_update_inode:4886: comm postgres: corrupted inode")
            lines.append(f"{ts(base,t)} {host} postgres[512]: FATAL:  the database system is in recovery mode")
            lines.append(f"{ts(base,t)} {host} postgres[512]: LOG:  server process (PID 8890) exited with exit code 1")
            lines.append(f"{ts(base,t)} {host} postgres[512]: LOG:  terminating any other active server processes")
            t += 1
            for _ in range(3):
                lines.append(f"{ts(base,t)} {host} app-orders-svc[2201]: ERROR: could not connect to database: connection refused")
            lines.append(f"{ts(base,t)} {host} monitoring-agent[771]: disk usage /var 100% (200G/200G)")
            lines.append(f"{ts(base,t)} {host} monitoring-agent[771]: CRITICAL: filesystem /var is full, no space left on device")
            t += 6
            lines.append(f"{ts(base,t)} {host} systemd[1]: postgresql.service: Main process exited, code=exited, status=1/FAILURE")
            lines.append(f"{ts(base,t)} {host} systemd[1]: postgresql.service: Failed with result 'exit-code'.")
            for restart in (1, 2, 3):
                t += 5
                lines.append(f"{ts(base,t)} {host} systemd[1]: postgresql.service: Scheduled restart job, restart counter is at {restart}.")
                t += 2
                lines.append(f"{ts(base,t)} {host} postgres[{9100+restart}]: FATAL:  could not create lock file \"postmaster.pid\": No space left on device")
                lines.append(f"{ts(base,t)} {host} systemd[1]: postgresql.service: Main process exited, code=exited, status=1/FAILURE")
            t += 5
            lines.append(f"{ts(base,t)} {host} alertmanager: Alert firing - DatabaseDown (severity=critical, host={host})")
            lines.append(f"{ts(base,t)} {host} alertmanager: Alert firing - DiskSpaceCritical (severity=critical, host={host}, mount=/var)")
            continue

        kind = rng.choices(["checkpoint", "disk", "cron", "conn"], weights=[15, 40, 10, 35])[0]
        if kind == "checkpoint":
            lines.append(f"{ts(base,t)} {host} postgres[512]: LOG:  checkpoint complete: wrote {rng.randint(2000,4500)} buffers ({rng.uniform(10,30):.1f}%)")
        elif kind == "disk":
            pct = rng.randint(60, 80)
            gb = int(pct * 2)
            lines.append(f"{ts(base,t)} {host} monitoring-agent[771]: disk usage /var {pct}% ({gb}G/200G)")
        elif kind == "cron":
            lines.append(f"{ts(base,t)} {host} cron[512]: (root) CMD (/usr/lib/php/sessionclean)")
        else:
            lines.append(f"{ts(base,t)} {host} postgres[{rng.randint(500,900)}]: LOG:  connection received: host=10.0.2.{rng.randint(10,30)} port={rng.randint(40000,60000)}")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lines", type=int, default=4000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    base = datetime(2026, 7, 3, 8, 0, 0)

    specs = [
        ("kubernetes-oom-crash-large.log", gen_kubernetes),
        ("nginx-502-upstream-large.log", gen_nginx),
        ("system-disk-full-large.log", gen_system),
    ]
    for filename, generator in specs:
        content = generator(args.lines, base, rng)
        out_path = OUT_DIR / filename
        out_path.write_text(content)
        n = content.count("\n")
        print(f"wrote {out_path} ({n} lines, {len(content)} bytes)")


if __name__ == "__main__":
    main()
