from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"


class AircraftDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'aircraft_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['aircraft_id'] = self.kwargs['pk']
        context['base_template'] = 'base.html'
        import_models = list(settings.LOGBOOK_IMPORT_MODELS)
        extra = getattr(settings, 'LOGBOOK_IMPORT_EXTRA_MODELS', None)
        if extra:
            import json as _json
            try:
                import_models = import_models + _json.loads(extra)
            except (ValueError, TypeError):
                pass
        context['import_models'] = import_models
        context['import_default_model'] = getattr(settings, 'LOGBOOK_IMPORT_DEFAULT_MODEL', 'claude-sonnet-4-6')
        return context


class SquawkHistoryView(LoginRequiredMixin, TemplateView):
    template_name = 'squawk_history.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['aircraft_id'] = self.kwargs['pk']
        return context

