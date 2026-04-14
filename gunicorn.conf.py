"""
Gunicorn configuration.

on_starting runs once in the arbiter (master) process before workers are forked,
so only one process ever binds port 8087 — workers never compete for the socket.
"""


def on_starting(server):
    """Register SAMCollector and start the Prometheus metrics HTTP server on port 8087."""
    import django
    django.setup()
    from django.conf import settings
    if not settings.PROMETHEUS_METRICS_ENABLED:
        return
    from prometheus_client import REGISTRY, start_http_server
    from core.metrics import SAMCollector
    REGISTRY.register(SAMCollector())
    start_http_server(8087)
