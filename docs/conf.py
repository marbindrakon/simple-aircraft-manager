# Configuration file for the Sphinx documentation builder.

project = 'Simple Aircraft Manager'
copyright = ''
author = 'Simple Aircraft Manager'

extensions = [
    'myst_parser',
]

source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}

exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

html_theme = 'furo'
html_title = 'Simple Aircraft Manager'
html_static_path = []
