import importlib.util
import socket
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "llama_cpp/rootfs/usr/lib/llama-app/healthcheck.py"
spec = importlib.util.spec_from_file_location("healthcheck", SCRIPT)
healthcheck = importlib.util.module_from_spec(spec)
spec.loader.exec_module(healthcheck)


def serve(status):
    """Start a server answering every GET with `status`; return its URL."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(status)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}/health"


class Check(unittest.TestCase):
    def check_status(self, status):
        server, url = serve(status)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return healthcheck.check(url, timeout=5)

    def test_serving_is_healthy(self):
        self.assertEqual(self.check_status(200), (True, "HTTP 200"))

    def test_loading_a_model_is_healthy(self):
        self.assertEqual(self.check_status(503), (True, "HTTP 503"))

    def test_other_error_statuses_are_unhealthy(self):
        for status in (500, 404):
            self.assertEqual(self.check_status(status), (False, f"HTTP {status}"))

    def test_not_listening_is_healthy(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        # Closed again, so the port now refuses connections.
        healthy, reason = healthcheck.check(f"http://127.0.0.1:{port}/health", timeout=5)
        self.assertEqual((healthy, reason), (True, "not listening yet"))

    def test_accepting_but_silent_is_unhealthy(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            sock.listen()
            port = sock.getsockname()[1]
            healthy, reason = healthcheck.check(f"http://127.0.0.1:{port}/health", timeout=0.3)
        self.assertFalse(healthy)
        self.assertIn("timed out", reason)

    def test_unresolvable_host_is_unhealthy(self):
        healthy, _ = healthcheck.check("http://host.invalid/health", timeout=5)
        self.assertFalse(healthy)


if __name__ == "__main__":
    unittest.main()
