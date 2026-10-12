"""NEXUS retains the exact manifest route instead of inventing a product/local route."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from logos.app import create_app
from logos.config import LogosConfig


@pytest.fixture
def gateway(monkeypatch, tmp_path):
    monkeypatch.delenv('LOGOS_API_TOKEN', raising=False)
    route = {'product_id': 'prod-logos', 'capability_id': 'logos.federation.summary@v1',
             'source_hub': 'https://logos.example', 'description': 'Public summary',
             'price_per_call_usd': 0, 'routed_price_usd': 0}
    state = {'tools': [route], 'calls': [], 'status': 200,
             'result': {'output': {'ok': True, 'hubs_seen': 18}, 'price_usd': 0},
             'manifest_down': False}

    def hub(request):
        if request.url.path.endswith('/manifest'):
            return httpx.Response(503 if state['manifest_down'] else 200,
                                  json={'tools': state['tools']})
        assert str(request.url) == 'https://hub.example/ai-market/v2/invoke'
        state['calls'].append(json.loads(request.content))
        return httpx.Response(state['status'], json=state['result'])

    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: real_client(
        transport=httpx.MockTransport(hub), **kw))
    cfg = LogosConfig(data_dir=tmp_path, hub_url='https://hub.example')
    # These routes have no store/background-poller dependency.
    client = TestClient(create_app(cfg))
    yield client, state, route
    client.close()


def test_catalog_retains_full_route_identity(gateway):
    client, state, route = gateway
    state['tools'].append({**route, 'product_id': 'another-product', 'source_hub': 'https://other.example'})
    data = client.get('/api/v1/federation/capabilities').json()['capabilities']
    assert [(x['product_id'], x['source_hub']) for x in data] == [
        ('prod-logos', 'https://logos.example'), ('another-product', 'https://other.example')]
    assert data[0]['price_per_call_usd'] == 0


def test_unique_legacy_request_resolves_manifest_not_invented_id(gateway):
    client, state, route = gateway
    response = client.post('/api/v1/federation/invoke', json={'capability_id': route['capability_id'], 'input': {}})
    assert response.status_code == 200
    assert response.json()['result']['hubs_seen'] == 18
    assert state['calls'] == [{'product_id': 'prod-logos', 'capability_id': route['capability_id'],
                               'source_hub': 'https://logos.example', 'input': {}}]


def test_duplicate_name_uses_selected_provider_and_price_ceiling(gateway):
    client, state, route = gateway
    state['tools'].append({**route, 'source_hub': 'https://other.example'})
    response = client.post('/api/v1/federation/invoke', json={
        'product_id': 'prod-logos', 'capability_id': route['capability_id'],
        'source_hub': 'https://other.example', 'input': {}, 'max_price_usd': 0})
    assert response.status_code == 200
    assert state['calls'][0]['source_hub'] == 'https://other.example'
    assert state['calls'][0]['max_price_usd'] == 0


def test_ambiguous_legacy_request_does_not_pick_first_provider(gateway):
    client, state, route = gateway
    state['tools'].append({**route, 'source_hub': 'https://other.example'})
    response = client.post('/api/v1/federation/invoke', json={'capability_id': route['capability_id']})
    assert response.status_code == 409
    assert not state['calls']


@pytest.mark.parametrize('override', [{'product_id': 'missing'}, {'source_hub': 'http://127.0.0.1/private'}])
def test_unknown_or_stale_route_is_not_invoked(gateway, override):
    client, state, route = gateway
    response = client.post('/api/v1/federation/invoke', json={'capability_id': route['capability_id'], **override})
    assert response.status_code == 404
    assert not state['calls']


def test_local_route_remains_local(gateway):
    client, state, route = gateway
    state['tools'][0].pop('source_hub')
    response = client.post('/api/v1/federation/invoke', json={'capability_id': route['capability_id']})
    assert response.status_code == 200
    assert state['calls'][0]['source_hub'] == 'local'


def test_mutation_guard_still_refuses_before_hub_invoke(gateway):
    client, state, _ = gateway
    response = client.post('/api/v1/federation/invoke', json={'capability_id': 'treasury.payout.execute'})
    assert response.status_code == 403
    assert not state['calls']


@pytest.mark.parametrize('body', [[], {'capability_id': 7},
    {'capability_id': 'read@v1', 'input': []}, {'capability_id': 'read@v1', 'source_hub': []},
    {'capability_id': 'read@v1', 'max_price_usd': -1}, {'capability_id': 'read@v1', 'max_price_usd': True}])
def test_invalid_input_is_reported_without_invocation(gateway, body):
    client, state, _ = gateway
    assert client.post('/api/v1/federation/invoke', json=body).status_code == 400
    assert not state['calls']


def test_hub_error_explains_refusal_and_preserves_status(gateway):
    client, state, route = gateway
    state.update(status=402, result={'detail': 'Payment is required for this capability'})
    response = client.post('/api/v1/federation/invoke', json={'capability_id': route['capability_id']})
    assert response.status_code == 402
    assert response.json()['status'] == 'error'
    assert response.json()['error'] == 'Payment is required for this capability'


def test_catalog_failure_is_not_a_success_or_empty_invoke(gateway):
    client, state, route = gateway
    state['manifest_down'] = True
    response = client.post('/api/v1/federation/invoke', json={'capability_id': route['capability_id']})
    assert response.status_code == 502
    assert response.json()['status'] == 'error'
    assert not state['calls']
