"""
Tests for the litellm provider in health/logbook_import.py.
Covers _call_litellm(), run_import() client creation, and view filtering.
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mock_openai_response(content_dict, finish_reason='stop', completion_tokens=50):
    """Build a mock openai ChatCompletion response."""
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].finish_reason = finish_reason
    mock_resp.choices[0].message.content = json.dumps(content_dict)
    mock_resp.usage.completion_tokens = completion_tokens
    return mock_resp


EMPTY_EXTRACTION = {'entries': [], 'non_logbook_pages': [], 'unparseable_pages': []}


# ---------------------------------------------------------------------------
# _call_litellm
# ---------------------------------------------------------------------------

class TestCallLitellm:
    def test_success_returns_parsed_data(self, tmp_path):
        from health.logbook_import import _call_litellm

        fake_image = tmp_path / "p0.jpg"
        fake_image.write_bytes(b'\xff\xd8\xff\xe0' + b'\x00' * 16)

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = make_mock_openai_response(EMPTY_EXTRACTION)

        with patch('health.logbook_import._get_image_bytes', return_value=b'\xff\xd8'):
            result = _call_litellm(mock_client, [fake_image], 'some-model')

        assert result['truncated'] is False
        assert result['output_tokens'] == 50
        assert result['data'] == EMPTY_EXTRACTION

    def test_truncated_when_finish_reason_length(self, tmp_path):
        from health.logbook_import import _call_litellm

        fake_image = tmp_path / "p0.jpg"
        fake_image.write_bytes(b'\xff\xd8\xff\xe0' + b'\x00' * 16)

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = make_mock_openai_response(
            EMPTY_EXTRACTION, finish_reason='length'
        )

        with patch('health.logbook_import._get_image_bytes', return_value=b'\xff\xd8'):
            result = _call_litellm(mock_client, [fake_image], 'some-model')

        assert result['truncated'] is True
        assert result['data'] == {}

    def test_system_prompt_is_first_message(self, tmp_path):
        from health.logbook_import import _call_litellm, EXTRACT_SYSTEM_PROMPT

        fake_image = tmp_path / "p0.jpg"
        fake_image.write_bytes(b'\xff\xd8\xff\xe0' + b'\x00' * 16)

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = make_mock_openai_response(EMPTY_EXTRACTION)

        with patch('health.logbook_import._get_image_bytes', return_value=b'\xff\xd8'):
            _call_litellm(mock_client, [fake_image], 'some-model')

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        messages = call_kwargs['messages']
        assert messages[0]['role'] == 'system'
        assert messages[0]['content'] == EXTRACT_SYSTEM_PROMPT

    def test_image_sent_as_image_url_type(self, tmp_path):
        from health.logbook_import import _call_litellm

        fake_image = tmp_path / "p0.jpg"
        fake_image.write_bytes(b'\xff\xd8\xff\xe0' + b'\x00' * 16)

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = make_mock_openai_response(EMPTY_EXTRACTION)

        with patch('health.logbook_import._get_image_bytes', return_value=b'\xff\xd8'):
            _call_litellm(mock_client, [fake_image], 'some-model')

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        user_content = call_kwargs['messages'][1]['content']
        image_blocks = [b for b in user_content if b.get('type') == 'image_url']
        assert len(image_blocks) == 1
        assert image_blocks[0]['image_url']['url'].startswith('data:image/jpeg;base64,')

    def test_prior_context_prepended_to_user_message(self, tmp_path):
        from health.logbook_import import _call_litellm

        fake_image = tmp_path / "p0.jpg"
        fake_image.write_bytes(b'\xff\xd8\xff\xe0' + b'\x00' * 16)

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = make_mock_openai_response(EMPTY_EXTRACTION)

        with patch('health.logbook_import._get_image_bytes', return_value=b'\xff\xd8'):
            _call_litellm(mock_client, [fake_image], 'some-model', prior_context_text='PRIOR CTX')

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        user_content = call_kwargs['messages'][1]['content']
        text_blocks = [b for b in user_content if b.get('type') == 'text']
        assert any('PRIOR CTX' in b['text'] for b in text_blocks)

    def test_json_object_response_format_requested(self, tmp_path):
        from health.logbook_import import _call_litellm

        fake_image = tmp_path / "p0.jpg"
        fake_image.write_bytes(b'\xff\xd8\xff\xe0' + b'\x00' * 16)

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = make_mock_openai_response(EMPTY_EXTRACTION)

        with patch('health.logbook_import._get_image_bytes', return_value=b'\xff\xd8'):
            _call_litellm(mock_client, [fake_image], 'some-model')

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs.get('response_format') == {'type': 'json_object'}


# ---------------------------------------------------------------------------
# run_import — litellm client creation
# ---------------------------------------------------------------------------

class TestRunImportLitellm:
    def test_error_when_litellm_base_url_not_set(self, aircraft):
        from health.logbook_import import run_import

        with patch('django.conf.settings') as mock_settings:
            mock_settings.LITELLM_BASE_URL = ''
            events = list(run_import(
                aircraft=aircraft,
                image_paths=[],
                collection_name='Test',
                doc_name='Test',
                provider='litellm',
                model='some-model',
            ))

        error_events = [e for e in events if e['type'] == 'error']
        assert any('LITELLM_BASE_URL' in e['message'] for e in error_events)

    def test_unknown_provider_yields_error(self, aircraft):
        from health.logbook_import import run_import

        events = list(run_import(
            aircraft=aircraft,
            image_paths=[],
            collection_name='Test',
            doc_name='Test',
            provider='nonexistent',
            model='some-model',
        ))

        error_events = [e for e in events if e['type'] == 'error']
        assert error_events


# ---------------------------------------------------------------------------
# LogbookImportView.get — litellm filtering
# ---------------------------------------------------------------------------

class TestLogbookImportViewFiltering:
    @pytest.fixture
    def session_owner(self, owner_user):
        from django.test import Client
        c = Client()
        c.force_login(owner_user)
        return c

    def test_litellm_models_hidden_when_base_url_not_set(self, session_owner):
        litellm_models = [
            {'id': 'claude-sonnet-4-6', 'name': 'Sonnet (proxy)', 'provider': 'litellm'}
        ]
        with patch('django.conf.settings.LOGBOOK_IMPORT_MODELS', litellm_models), \
             patch('django.conf.settings.LITELLM_BASE_URL', ''), \
             patch('django.conf.settings.LOGBOOK_IMPORT_DEFAULT_MODEL', 'claude-sonnet-4-6'):
            response = session_owner.get('/tools/import-logbook/')

        assert response.status_code == 200
        import_models = response.context['import_models']
        assert not any(m['provider'] == 'litellm' for m in import_models)

    def test_litellm_models_shown_when_base_url_set(self, session_owner):
        litellm_models = [
            {'id': 'claude-sonnet-4-6', 'name': 'Sonnet (proxy)', 'provider': 'litellm'}
        ]
        with patch('django.conf.settings.LOGBOOK_IMPORT_MODELS', litellm_models), \
             patch('django.conf.settings.LITELLM_BASE_URL', 'http://litellm:4000'), \
             patch('django.conf.settings.LOGBOOK_IMPORT_DEFAULT_MODEL', 'claude-sonnet-4-6'):
            response = session_owner.get('/tools/import-logbook/')

        assert response.status_code == 200
        import_models = response.context['import_models']
        assert any(m['provider'] == 'litellm' for m in import_models)
