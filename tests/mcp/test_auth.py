"""OAuth bearer auth, scopes, and discovery metadata for the MCP endpoint."""
import json

import pytest
from rest_framework.test import APIClient

from .conftest import MCP_URL, rpc, tool_payload

pytestmark = pytest.mark.urls('tests.mcp.urls')


def _anon_rpc(method='ping'):
    client = APIClient()
    return client.post(
        MCP_URL,
        data=json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method}),
        content_type='application/json',
    )


def test_unauthenticated_gets_401_with_resource_metadata_challenge(db):
    response = _anon_rpc()
    assert response.status_code == 401
    challenge = response.headers['WWW-Authenticate']
    assert challenge.startswith('Bearer')
    assert 'resource_metadata=' in challenge
    assert '/.well-known/oauth-protected-resource/mcp' in challenge


def test_expired_token_rejected(mcp_client_factory, owner_user):
    client = mcp_client_factory(owner_user, expired=True)
    assert rpc(client, 'ping').status_code == 401


def test_garbage_token_rejected(db):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION='Bearer not-a-real-token')
    response = client.post(
        MCP_URL,
        data=json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}),
        content_type='application/json',
    )
    assert response.status_code == 401


def test_read_scope_hides_write_tools(mcp_client_factory, owner_user):
    client = mcp_client_factory(owner_user, scope='read')
    tools = rpc(client, 'tools/list').json()['result']['tools']
    names = {t['name'] for t in tools}
    assert 'get_aircraft_summary' in names
    assert 'update_aircraft_hours' not in names
    assert 'create_squawk' not in names


def test_read_scope_blocks_write_tool_call(mcp_client_factory, owner_user, aircraft):
    client = mcp_client_factory(owner_user, scope='read')
    body = rpc(client, 'tools/call', {
        'name': 'update_aircraft_hours',
        'arguments': {'aircraft_id': str(aircraft.id), 'new_tach_time': 101.0},
    }).json()
    result = body['result']
    assert result['isError'] is True
    assert 'write' in result['content'][0]['text']
    aircraft.refresh_from_db()
    assert float(aircraft.tach_time) == 100.0


def test_write_scope_allows_write_tools(owner_mcp_client, aircraft):
    payload = tool_payload(owner_mcp_client, 'update_aircraft_hours', {
        'aircraft_id': str(aircraft.id), 'new_tach_time': 101.5,
    })
    assert payload['success'] is True


def test_protected_resource_metadata(client, db):
    response = client.get('/.well-known/oauth-protected-resource/mcp')
    assert response.status_code == 200
    data = response.json()
    assert data['resource'].endswith('/mcp')
    assert set(data['scopes_supported']) == {'read', 'write'}
    assert data['bearer_methods_supported'] == ['header']
    assert data['authorization_servers']


def test_metadata_does_not_advertise_risky_grants(client, db):
    data = client.get('/.well-known/oauth-authorization-server').json()
    assert data['grant_types_supported'] == ['authorization_code', 'refresh_token']
    assert data['response_types_supported'] == ['code']
    assert 'password' not in data['grant_types_supported']
    assert 'token' not in data['response_types_supported']  # no implicit


def test_password_grant_rejected(client, db, owner_user):
    # Even with a public application explicitly set to the password grant (so
    # client auth is not the blocker), the RFC 9700 gate must reject the grant
    # at the token endpoint — no credential-testing oracle against local users.
    from oauth2_provider.models import Application
    app = Application.objects.create(
        name='password-client',
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_PASSWORD,
    )
    owner_user.set_password('supersecret')
    owner_user.save()
    response = client.post('/o/token/', data={
        'grant_type': 'password',
        'username': owner_user.username,
        'password': 'supersecret',
        'client_id': app.client_id,
        'scope': 'read write',
    })
    assert response.status_code == 400
    assert b'access_token' not in response.content
    assert response.json()['error'] in ('unauthorized_client', 'unsupported_grant_type')


def test_authorization_server_metadata(client, db):
    prm = client.get('/.well-known/oauth-protected-resource/mcp').json()
    issuer = prm['authorization_servers'][0]
    # RFC 8414: for an issuer with a path component the metadata lives at
    # /.well-known/oauth-authorization-server/<path>.
    path = issuer.split('://', 1)[1].split('/', 1)
    suffix = f"/{path[1]}" if len(path) > 1 else ''
    response = client.get(f'/.well-known/oauth-authorization-server{suffix}')
    assert response.status_code == 200
    data = response.json()
    assert data['issuer'] == issuer
    assert data['authorization_endpoint'].endswith('/o/authorize/')
    assert data['token_endpoint'].endswith('/o/token/')
    assert 'registration_endpoint' in data  # DCR advertised
    assert 'S256' in data['code_challenge_methods_supported']
    assert set(data['scopes_supported']) >= {'read', 'write'}


def test_dynamic_client_registration(client, db):
    response = client.post(
        '/o/register/',
        data=json.dumps({
            'client_name': 'Claude',
            'redirect_uris': ['https://claude.ai/api/mcp/auth_callback'],
            'grant_types': ['authorization_code', 'refresh_token'],
            'token_endpoint_auth_method': 'client_secret_basic',
        }),
        content_type='application/json',
    )
    assert response.status_code == 201, response.content
    data = response.json()
    assert data['client_id']
    assert data['redirect_uris'] == ['https://claude.ai/api/mcp/auth_callback']
