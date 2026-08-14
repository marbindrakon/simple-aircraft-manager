"""
Stateless MCP streamable-HTTP endpoint.

Implements the tools-only subset of the Model Context Protocol over plain
JSON-RPC POSTs (spec 2025-06-18). The server is stateless: no Mcp-Session-Id
is issued and every POST is answered with a single application/json body, which
the streamable-HTTP transport permits and which keeps the endpoint compatible
with the WSGI deployment.

Auth is OAuth 2.1 bearer tokens issued by this instance's django-oauth-toolkit
authorization server; unauthenticated requests get a 401 whose WWW-Authenticate
challenge advertises the RFC 9728 protected-resource metadata for /mcp.
"""
import json
import logging

from django.http import HttpResponse, JsonResponse
from oauth2_provider.contrib.rest_framework.authentication import (
    OAuth2ProtectedResourceAuthentication,
)
from rest_framework.exceptions import ParseError
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from mcp_server import protocol, registry
from mcp_server.access import ToolError

logger = logging.getLogger(__name__)

SERVER_INFO = {'name': 'simple-aircraft-manager', 'version': '1.0.0'}


class McpAuthentication(OAuth2ProtectedResourceAuthentication):
    def get_resource_metadata_url(self, request):
        # Advertise the RFC 9728 path-component document for the /mcp resource.
        return request.build_absolute_uri('/.well-known/oauth-protected-resource/mcp')


def _tool_success(payload):
    # Compact JSON, and no structuredContent duplicate: the client feeds
    # content.text to the model, so pretty-printing plus a second serialized
    # copy of the payload roughly doubled every response for no benefit
    # (structuredContent is optional when no outputSchema is declared).
    return {
        'content': [{'type': 'text', 'text': json.dumps(payload, separators=(',', ':'), default=str)}],
        'isError': False,
    }


def _tool_failure(message):
    return {
        'content': [{'type': 'text', 'text': message}],
        'isError': True,
    }


def _format_validation_errors(detail):
    """Flatten DRF serializer errors into a readable one-line-per-field string."""
    if isinstance(detail, dict):
        parts = []
        for field, errors in detail.items():
            if isinstance(errors, (list, tuple)):
                msg = '; '.join(str(e) for e in errors)
            else:
                msg = str(errors)
            parts.append(f"{field}: {msg}")
        return 'Validation failed — ' + ' | '.join(parts)
    return f'Validation failed — {detail}'


class McpEndpointView(APIView):
    authentication_classes = [McpAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Stateless server: no server-initiated SSE stream is offered.
        return HttpResponse(status=405, headers={'Allow': 'POST'})

    def handle_exception(self, exc):
        # Malformed JSON surfaces as a DRF ParseError (the OAuth authentication
        # layer touches request.POST, which runs the parsers before post()
        # executes) — answer with the JSON-RPC parse-error shape.
        if isinstance(exc, ParseError):
            return JsonResponse(
                protocol.rpc_error(None, protocol.PARSE_ERROR, 'Invalid JSON'),
                status=400,
            )
        return super().handle_exception(exc)

    def post(self, request):
        message = request.data

        envelope_error = protocol.validate_envelope(message)
        if envelope_error:
            request_id = message.get('id') if isinstance(message, dict) else None
            return JsonResponse(
                protocol.rpc_error(request_id, protocol.INVALID_REQUEST, envelope_error),
                status=400,
            )

        if protocol.is_notification(message):
            return HttpResponse(status=202)

        request_id = message['id']
        method = message['method']
        params = message.get('params') or {}

        if method == 'initialize':
            return JsonResponse(protocol.rpc_result(request_id, self._initialize(params)))
        if method == 'ping':
            return JsonResponse(protocol.rpc_result(request_id, {}))
        if method == 'tools/list':
            return JsonResponse(protocol.rpc_result(request_id, self._tools_list(request)))
        if method == 'tools/call':
            return JsonResponse(self._tools_call(request, request_id, params))

        return JsonResponse(
            protocol.rpc_error(request_id, protocol.METHOD_NOT_FOUND, f"Method not found: {method}")
        )

    def _initialize(self, params):
        client_version = params.get('protocolVersion')
        version = (
            client_version
            if client_version in protocol.SUPPORTED_PROTOCOL_VERSIONS
            else protocol.DEFAULT_PROTOCOL_VERSION
        )
        return {
            'protocolVersion': version,
            'capabilities': {'tools': {'listChanged': False}},
            'serverInfo': SERVER_INFO,
        }

    @staticmethod
    def _token_scopes(request):
        token = request.auth
        if token is None or not getattr(token, 'scope', ''):
            return set()
        return set(token.scope.split())

    def _tools_list(self, request):
        scopes = self._token_scopes(request)
        return {'tools': [t.descriptor() for t in registry.list_tools(scopes)]}

    def _tools_call(self, request, request_id, params):
        name = params.get('name')
        the_tool = registry.get_tool(name) if isinstance(name, str) else None
        if the_tool is None:
            return protocol.rpc_error(request_id, protocol.INVALID_PARAMS, f"Unknown tool: {name}")

        args = params.get('arguments') or {}
        if not isinstance(args, dict):
            return protocol.rpc_error(request_id, protocol.INVALID_PARAMS, "'arguments' must be an object")

        if the_tool.required_scope not in self._token_scopes(request):
            return protocol.rpc_result(request_id, _tool_failure(
                f"This token lacks the '{the_tool.required_scope}' scope required by {name}"
            ))

        schema_errors = registry.validate_args(the_tool, args)
        if schema_errors:
            return protocol.rpc_error(
                request_id, protocol.INVALID_PARAMS, '; '.join(schema_errors)
            )

        try:
            payload = the_tool.handler(request, args)
        except ToolError as e:
            return protocol.rpc_result(request_id, _tool_failure(str(e)))
        except DRFValidationError as e:
            return protocol.rpc_result(request_id, _tool_failure(_format_validation_errors(e.detail)))
        except Exception:
            logger.exception("MCP tool %s failed", name)
            return protocol.rpc_result(request_id, _tool_failure(
                f"Internal error while executing {name}"
            ))

        return protocol.rpc_result(request_id, _tool_success(payload))
