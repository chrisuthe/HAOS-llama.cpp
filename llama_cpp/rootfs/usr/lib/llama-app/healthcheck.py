#!/usr/bin/env python3
"""Container health check: unhealthy only when the server is up but not answering."""

import sys
import urllib.error
import urllib.request

URL = "http://127.0.0.1:8080/health"
# Shorter than the HEALTHCHECK timeout in the Dockerfile, so a hang is reported
# here with a reason rather than by Docker killing the check.
TIMEOUT = 10


def check(url=URL, timeout=TIMEOUT):
    """Return (healthy, reason)."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return True, f"HTTP {response.status}"
    except urllib.error.HTTPError as err:
        # 503 is llama-server saying a model is still loading.
        return err.code == 503, f"HTTP {err.code}"
    except urllib.error.URLError as err:
        # Nothing listens while a model downloads, which can run for hours. A
        # server that died would have taken the container with it, so a refused
        # connection can only mean it has not started serving yet.
        if isinstance(err.reason, ConnectionRefusedError):
            return True, "not listening yet"
        return False, str(err.reason)
    except OSError as err:
        return False, str(err) or type(err).__name__


def main():
    healthy, reason = check()
    print(reason)
    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main())
