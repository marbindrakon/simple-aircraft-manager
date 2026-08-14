import datetime
import json

import pytest
from django.utils import timezone
from oauth2_provider.models import AccessToken, Application
from rest_framework.test import APIClient

MCP_URL = '/mcp'


@pytest.fixture
def oauth_application(db):
    return Application.objects.create(
        name='test-mcp-client',
        client_type=Application.CLIENT_CONFIDENTIAL,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris='https://claude.ai/api/mcp/auth_callback',
    )


@pytest.fixture
def mcp_token_factory(oauth_application):
    counter = {'n': 0}

    def _make(user, scope='read write', expired=False):
        counter['n'] += 1
        delta = datetime.timedelta(hours=-1 if expired else 1)
        return AccessToken.objects.create(
            user=user,
            application=oauth_application,
            token=f'test-token-{counter["n"]}',
            scope=scope,
            expires=timezone.now() + delta,
        )

    return _make


@pytest.fixture
def mcp_client_factory(mcp_token_factory):
    def _make(user, scope='read write', expired=False):
        token = mcp_token_factory(user, scope=scope, expired=expired)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.token}')
        return client

    return _make


@pytest.fixture
def owner_mcp_client(mcp_client_factory, owner_user):
    return mcp_client_factory(owner_user)


@pytest.fixture
def pilot_mcp_client(mcp_client_factory, pilot_user):
    return mcp_client_factory(pilot_user)


@pytest.fixture
def other_mcp_client(mcp_client_factory, other_user):
    return mcp_client_factory(other_user)


def rpc(client, method, params=None, request_id=1):
    body = {'jsonrpc': '2.0', 'id': request_id, 'method': method}
    if params is not None:
        body['params'] = params
    return client.post(MCP_URL, data=json.dumps(body), content_type='application/json')


def call_tool(client, name, arguments=None):
    """POST a tools/call and return the JSON-RPC response body."""
    response = rpc(client, 'tools/call', {'name': name, 'arguments': arguments or {}})
    assert response.status_code == 200, response.content
    return response.json()


def tool_payload(client, name, arguments=None):
    """Call a tool expecting success; return its structuredContent."""
    body = call_tool(client, name, arguments)
    assert 'result' in body, body
    result = body['result']
    assert result.get('isError') is False, result
    return result['structuredContent']


def tool_error(client, name, arguments=None):
    """Call a tool expecting an in-band failure; return its message text."""
    body = call_tool(client, name, arguments)
    assert 'result' in body, body
    result = body['result']
    assert result.get('isError') is True, result
    return result['content'][0]['text']
