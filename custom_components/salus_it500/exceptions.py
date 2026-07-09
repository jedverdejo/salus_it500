"""Exceptions for Salus iT500 smart devices."""


class IT500Error(Exception):
    """Salus iT500 exception."""

    pass


class IT500AuthenticationError(IT500Error):
    """Salus iT500 authentication exception."""

    pass


class IT500CommandError(IT500Error):
    """Salus iT500 command exception."""

    pass


class IT500ConnectionError(IT500Error):
    """Salus iT600 connection exception."""

    pass

class IT500InvalidParameter(IT500Error):
    pass