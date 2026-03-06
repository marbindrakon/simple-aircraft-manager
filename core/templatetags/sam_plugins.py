"""Template tags for SAM plugin sub-tab injection.

Usage in existing sub-tab templates::

    {% load sam_plugins %}

    <!-- Inside the toggle-group, after built-in buttons: -->
    {% plugin_sub_tab_buttons "consumables" %}

    <!-- After built-in content panels: -->
    {% plugin_sub_tab_panels "consumables" %}
"""

from django import template

register = template.Library()


@register.inclusion_tag('core/plugin_sub_tab_buttons.html')
def plugin_sub_tab_buttons(primary_group):
    """Render toggle-group buttons for plugin sub-tabs within *primary_group*."""
    from core.plugins import registry
    return {'tabs': registry.sub_tabs_for(primary_group)}


@register.inclusion_tag('core/plugin_sub_tab_panels.html')
def plugin_sub_tab_panels(primary_group):
    """Render content panels for plugin sub-tabs within *primary_group*."""
    from core.plugins import registry
    return {'tabs': registry.sub_tabs_for(primary_group)}
