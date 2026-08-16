"""JSON-RPC / streamable-HTTP protocol behavior of the /mcp endpoint."""
import json

import pytest

from .conftest import MCP_URL, rpc

pytestmark = pytest.mark.urls('tests.mcp.urls')


def test_initialize(owner_mcp_client):
    body = rpc(owner_mcp_client, 'initialize', {
        'protocolVersion': '2025-06-18',
        'capabilities': {},
        'clientInfo': {'name': 'test', 'version': '0'},
    }).json()
    result = body['result']
    assert result['protocolVersion'] == '2025-06-18'
    assert result['capabilities'] == {'tools': {'listChanged': False}}
    assert result['serverInfo']['name'] == 'simple-aircraft-manager'


def test_initialize_older_supported_version_is_echoed(owner_mcp_client):
    body = rpc(owner_mcp_client, 'initialize', {'protocolVersion': '2025-03-26'}).json()
    assert body['result']['protocolVersion'] == '2025-03-26'


def test_initialize_unknown_version_falls_back_to_latest(owner_mcp_client):
    body = rpc(owner_mcp_client, 'initialize', {'protocolVersion': '1999-01-01'}).json()
    assert body['result']['protocolVersion'] == '2025-06-18'


def test_ping(owner_mcp_client):
    body = rpc(owner_mcp_client, 'ping').json()
    assert body == {'jsonrpc': '2.0', 'id': 1, 'result': {}}


def test_notification_returns_202(owner_mcp_client):
    response = owner_mcp_client.post(
        MCP_URL,
        data=json.dumps({'jsonrpc': '2.0', 'method': 'notifications/initialized'}),
        content_type='application/json',
    )
    assert response.status_code == 202
    assert response.content == b''


def test_tools_list_shape(owner_mcp_client):
    body = rpc(owner_mcp_client, 'tools/list').json()
    tools = body['result']['tools']
    names = {t['name'] for t in tools}
    assert 'get_aircraft_summary' in names
    assert 'update_aircraft_hours' in names
    for tool in tools:
        assert tool['description']
        assert tool['inputSchema']['type'] == 'object'


def test_unknown_method(owner_mcp_client):
    body = rpc(owner_mcp_client, 'resources/list').json()
    assert body['error']['code'] == -32601


def test_parse_error(owner_mcp_client):
    response = owner_mcp_client.post(MCP_URL, data='{not json', content_type='application/json')
    assert response.status_code == 400
    assert response.json()['error']['code'] == -32700


def test_invalid_envelope(owner_mcp_client):
    response = owner_mcp_client.post(
        MCP_URL, data=json.dumps({'id': 1, 'method': 'ping'}),
        content_type='application/json',
    )
    assert response.status_code == 400
    assert response.json()['error']['code'] == -32600


def test_batch_rejected(owner_mcp_client):
    response = owner_mcp_client.post(
        MCP_URL,
        data=json.dumps([{'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}]),
        content_type='application/json',
    )
    assert response.status_code == 400
    assert response.json()['error']['code'] == -32600


def test_get_is_405(owner_mcp_client):
    response = owner_mcp_client.get(MCP_URL)
    assert response.status_code == 405


def test_unknown_tool(owner_mcp_client):
    body = rpc(owner_mcp_client, 'tools/call', {'name': 'nope', 'arguments': {}}).json()
    assert body['error']['code'] == -32602


def test_missing_required_argument(owner_mcp_client):
    body = rpc(owner_mcp_client, 'tools/call',
               {'name': 'get_aircraft_summary', 'arguments': {}}).json()
    assert body['error']['code'] == -32602
    assert 'aircraft_id' in body['error']['message']


def test_unknown_argument_rejected(owner_mcp_client, aircraft):
    body = rpc(owner_mcp_client, 'tools/call', {
        'name': 'get_aircraft_summary',
        'arguments': {'aircraft_id': str(aircraft.id), 'bogus': 1},
    }).json()
    assert body['error']['code'] == -32602
    assert 'bogus' in body['error']['message']


@pytest.mark.urls('simple_aircraft_manager.urls')
def test_endpoint_not_mounted_when_disabled(owner_mcp_client):
    # The project URLconf only mounts /mcp when MCP_ENABLED is set, and it is
    # off in test settings.
    response = rpc(owner_mcp_client, 'ping')
    assert response.status_code == 404
