from unittest.mock import Mock, patch

from health.dispatch import dispatch_import


def test_dispatch_import_defers_when_procrastinate_installed():
    task = Mock()
    fallback_target = Mock()

    with patch('health.dispatch.apps.is_installed', return_value=True), \
            patch('health.dispatch.threading.Thread') as thread_cls:
        result = dispatch_import(
            task,
            fallback_target,
            ('fallback-job-id',),
            job_id='deferred-job-id',
        )

    task.defer.assert_called_once_with(job_id='deferred-job-id')
    thread_cls.assert_not_called()
    assert result == task.defer.return_value


def test_dispatch_import_starts_thread_when_procrastinate_not_installed():
    task = Mock()
    fallback_target = Mock()
    thread = Mock()

    with patch('health.dispatch.apps.is_installed', return_value=False), \
            patch('health.dispatch.threading.Thread', return_value=thread) as thread_cls:
        result = dispatch_import(
            task,
            fallback_target,
            ('job-id', 'path'),
            fallback_kwargs={'tail_number_override': 'N12345'},
            job_id='ignored-deferred-job-id',
        )

    task.defer.assert_not_called()
    thread_cls.assert_called_once_with(
        target=fallback_target,
        args=('job-id', 'path'),
        kwargs={'tail_number_override': 'N12345'},
        daemon=True,
    )
    thread.start.assert_called_once_with()
    assert result == thread
