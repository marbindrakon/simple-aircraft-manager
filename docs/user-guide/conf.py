# Configuration file for the Sphinx documentation builder.

project = 'Simple Aircraft Manager'
copyright = '2026, Simple Aircraft Manager'
author = 'Simple Aircraft Manager'

extensions = []

templates_path = ['_templates']
exclude_patterns = ['_build']

html_theme = 'alabaster'
html_theme_options = {
    'description': 'Aircraft maintenance tracking and compliance management',
    'fixed_sidebar': True,
    'sidebar_collapse': True,
    'page_width': '960px',
}
html_static_path = []
html_favicon = None
html_title = 'Simple Aircraft Manager User Guide'
