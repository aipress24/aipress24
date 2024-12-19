from werkzeug.local import LocalProxy


def unproxy(obj):
    if isinstance(obj, LocalProxy):
        return obj._get_current_object()
    return obj
