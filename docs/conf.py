# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys

bd_warehouse_path = os.path.dirname(os.path.abspath(os.getcwd()))
source_files_path = os.path.join(bd_warehouse_path, "src", "bd_warehouse")
sys.path.insert(0, source_files_path)
sys.path.append(os.path.abspath("sphinxext"))
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("../"))

# -- Project information -----------------------------------------------------

project = 'bd_warehouse'
copyright = '2023, Gumyr'
author = 'Gumyr'


# The full version, including alpha/beta/rc tags
with open(os.path.join(bd_warehouse_path, "pyproject.toml")) as f:
    pyproject_toml = f.readlines()
for line in pyproject_toml:
    if "version =" in line:
        release = line.split("=")[1].strip()

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.napoleon",
    "sphinx.ext.autodoc",
    "sphinx_autodoc_typehints",
    "sphinx.ext.doctest",
    "sphinx.ext.graphviz",
    "sphinx.ext.inheritance_diagram",
    "sphinx.ext.viewcode",
    "sphinx_design",
    "sphinx_copybutton",
    "hoverxref.extension",
]

# Napoleon settings
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = False
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = True
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_use_keyword = True
napoleon_custom_sections = None

autodoc_typehints = ["signature"]
# autodoc_typehints = ["description"]
# autodoc_typehints = ["both"]

autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "member-order": "alphabetical",
}
# Sphinx settings
add_module_names = False
python_use_unqualified_type_names = True

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

root_doc = 'index'


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

# html_theme = 'alabaster'
html_theme = "sphinx_rtd_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
# html_static_path = ["_static"]

# -- Options for hoverxref -------------------------------------------------
hoverxref_role_types = {
    "hoverxref": "tooltip",
    "ref": "tooltip",  # for hoverxref_auto_ref config
    "confval": "tooltip",  # for custom object
    "mod": "tooltip",  # for Python Sphinx Domain
    "class": "tooltip",  # for Python Sphinx Domain
    "meth": "tooltip",  # for Python Sphinx Domain
    "func": "tooltip", # for Python Sphinx Domain
}

hoverxref_roles = [
    "class",
    "meth",
]

hoverxref_domains = [
    "py",
]

