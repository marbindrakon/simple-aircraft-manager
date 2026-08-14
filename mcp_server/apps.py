from django.apps import AppConfig


class McpServerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mcp_server'

    def ready(self):
        # Import tool modules so their @tool decorators register with the
        # registry before the first tools/list request.
        from mcp_server.tools import read, write  # noqa: F401
