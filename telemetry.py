"""Serve a demonstration API and export correlated OTLP telemetry."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import secrets
import time
import urllib.error
import urllib.request

ENDPOINT = os.getenv("OTLP_ENDPOINT", "http://localhost:4318").rstrip("/")
METRICS_ENDPOINT = os.getenv("METRICS_OTLP_ENDPOINT", ENDPOINT).rstrip("/")
RESOURCE = {"attributes": [{"key": "service.name", "value": {"stringValue": "lgtm-demo"}}]}


def send(signal, body):
    request = urllib.request.Request(
        f"{METRICS_ENDPOINT if signal == 'metrics' else ENDPOINT}/v1/{signal}", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        result = json.load(response)
        if result.get("partialSuccess"):
            print(f"{signal}: partial success {result['partialSuccess']}", flush=True)


def emit(sequence, failed):
    now = time.time_ns()
    trace_id, span_id = secrets.token_hex(16), secrets.token_hex(8)
    send("traces", {"resourceSpans": [{"resource": RESOURCE, "scopeSpans": [{"spans": [{
        "traceId": trace_id, "spanId": span_id, "name": "process-order",
        "kind": 1, "startTimeUnixNano": str(now - 100_000_000),
        "endTimeUnixNano": str(now), "status": {"code": 2 if failed else 1},
        "attributes": [{"key": "demo.outcome", "value": {"stringValue": "error" if failed else "ok"}}],
    }]}]}]})
    send("logs", {"resourceLogs": [{"resource": RESOURCE, "scopeLogs": [{"logRecords": [{
        "timeUnixNano": str(now), "traceId": trace_id, "spanId": span_id,
        "severityText": "ERROR" if failed else "INFO", "severityNumber": 17 if failed else 9,
        "body": {"stringValue": "simulated order failed" if failed else "simulated order processed"},
    }]}]}]})
    send("metrics", {"resourceMetrics": [{"resource": RESOURCE, "scopeMetrics": [{"metrics": [{
        "name": "demo.orders", "unit": "{order}", "sum": {"aggregationTemporality": 2,
        "isMonotonic": True, "dataPoints": [{"startTimeUnixNano": str(START),
        "timeUnixNano": str(now), "asInt": str(sequence)}]},
    }]}]}]})
    print(f"sent sequence={sequence} trace_id={trace_id} outcome={'error' if failed else 'ok'}", flush=True)
    return trace_id


START = time.time_ns()
sequence = 0


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global sequence
        if self.path == "/health":
            self.respond(200, {"status": "ok"})
            return
        if self.path not in ("/order", "/order?fail=true"):
            self.respond(404, {"error": "not found"})
            return
        sequence += 1
        failed = self.path.endswith("fail=true")
        try:
            trace_id = emit(sequence, failed)
        except (OSError, urllib.error.URLError, ValueError) as exc:
            print(f"telemetry export failed: {exc}", flush=True)
            self.respond(503, {"error": "telemetry unavailable"})
            return
        self.respond(500 if failed else 200, {"result": "error" if failed else "ok", "trace_id": trace_id})

    def respond(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


print("demo API listening on :8080", flush=True)
HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
