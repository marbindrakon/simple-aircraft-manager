import threading

from django.apps import apps


def dispatch_import(task, fallback_target, fallback_args, fallback_kwargs=None, **defer_kwargs):
    """Dispatch an import via Procrastinate when available, otherwise a thread."""
    if apps.is_installed('procrastinate.contrib.django'):
        return task.defer(**defer_kwargs)

    thread = threading.Thread(
        target=fallback_target,
        args=fallback_args,
        kwargs=fallback_kwargs or {},
        daemon=True,
    )
    thread.start()
    return thread
