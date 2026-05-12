"""Entry module for the ``dramatiq`` CLI.

Importing this module creates the Flask app and initializes the
Dramatiq broker as side effects, so by the time ``dramatiq``'s worker
loop starts iterating ``dramatiq.get_broker().actors``, every actor
registered via ``@job()`` or ``@crontab()`` is bound to a broker that
talks to Postgres.

Use as::

    dramatiq app.dramatiq.worker_entry --processes 1 --threads 4

The Procfile and the ``flask queue worker`` convenience wrapper both
target this module.
"""

from __future__ import annotations

from app.dramatiq.setup import init_dramatiq
from app.flask.main import create_app

_app = create_app()
init_dramatiq(_app)

# Push an app context for the lifetime of the worker so that code
# touching ``current_app`` / ``g`` works even outside the per-message
# context that ``AppContextMiddleware`` already installs. The middleware
# scopes its context per message, so this top-level push is just a
# safety net for non-actor code paths (e.g. broker callbacks).
_app.app_context().push()
