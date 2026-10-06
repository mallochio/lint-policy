"""Shared lint policy hooks for agentic Python repositories.

The hooks reject explanatory comments, require docstrings in source roots,
cap file and function length, require suppression directives to carry a reason
and a baseline entry, and reject numeric isinstance guards that accept bool.
"""

__version__ = "0.2.0"
