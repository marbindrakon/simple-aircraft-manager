"""
Minimal JSON-RPC 2.0 helpers for the stateless MCP streamable-HTTP endpoint.
"""

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# Protocol versions this server accepts; the newest is offered by default.
SUPPORTED_PROTOCOL_VERSIONS = ['2025-06-18', '2025-03-26']
DEFAULT_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[0]


def rpc_result(request_id, result):
    return {'jsonrpc': '2.0', 'id': request_id, 'result': result}


def rpc_error(request_id, code, message):
    return {'jsonrpc': '2.0', 'id': request_id, 'error': {'code': code, 'message': message}}


def is_notification(message):
    """A JSON-RPC message without an id is a notification — no response body."""
    return isinstance(message, dict) and 'id' not in message


def validate_envelope(message):
    """Return an error string for a malformed JSON-RPC request, else None."""
    if not isinstance(message, dict):
        return 'Request must be a JSON object (batching is not supported)'
    if message.get('jsonrpc') != '2.0':
        return "Missing or invalid 'jsonrpc' version (expected '2.0')"
    if not isinstance(message.get('method'), str):
        return "Missing or invalid 'method'"
    params = message.get('params')
    if params is not None and not isinstance(params, dict):
        return "'params' must be an object"
    return None
