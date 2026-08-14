"""
Tool registry for the MCP server.

Tools register at import time via the @tool decorator (tool modules are
imported from McpServerConfig.ready()). Each handler is called as
handler(request, args) where request is the authenticated DRF request and args
is the validated arguments dict; it returns a JSON-serializable dict.
"""
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

SCOPE_READ = 'read'
SCOPE_WRITE = 'write'

_JSON_TYPES = {
    'string': str,
    'integer': int,
    'number': (int, float),
    'boolean': bool,
    'object': dict,
    'array': list,
}


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: Dict[str, Any]
    required_scope: str
    handler: Callable

    def descriptor(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'inputSchema': self.input_schema,
        }


_REGISTRY: Dict[str, Tool] = {}


def tool(name: str, description: str, input_schema: Dict[str, Any],
         required_scope: str = SCOPE_READ):
    def decorator(fn):
        _REGISTRY[name] = Tool(
            name=name,
            description=description,
            input_schema=input_schema,
            required_scope=required_scope,
            handler=fn,
        )
        return fn
    return decorator


def get_tool(name: str):
    return _REGISTRY.get(name)


def list_tools(scopes) -> List[Tool]:
    """Tools available to a token with the given scopes (write tools are
    hidden from read-only tokens)."""
    return [t for t in _REGISTRY.values() if t.required_scope in scopes]


def validate_args(a_tool: Tool, args: Dict[str, Any]) -> List[str]:
    """
    Lightweight JSON-Schema check: required properties present, no unknown
    properties, and primitive types match. Value-level validation is left to
    the serializers behind each tool.
    """
    errors = []
    schema = a_tool.input_schema
    properties = schema.get('properties', {})

    for required in schema.get('required', []):
        if required not in args:
            errors.append(f"Missing required argument '{required}'")

    for key, value in args.items():
        if key not in properties:
            errors.append(f"Unknown argument '{key}'")
            continue
        expected = properties[key].get('type')
        py_type = _JSON_TYPES.get(expected)
        if value is None or py_type is None:
            continue
        if expected in ('integer', 'number') and isinstance(value, bool):
            errors.append(f"Argument '{key}' must be a {expected}")
        elif not isinstance(value, py_type):
            errors.append(f"Argument '{key}' must be a {expected}")

    return errors
