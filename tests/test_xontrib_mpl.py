"""Tests for ``xontrib/mpl.py`` — alias registration, event handlers,
and idempotency of pyplot monkey-patching.

These tests don't require ``matplotlib`` / ``numpy`` to be installed:
they stub ``matplotlib._pylab_helpers`` via ``sys.modules`` and inject
a fake ``XSH`` session before importing the xontrib.
"""

import sys
import types
from unittest.mock import MagicMock

import pytest


def _make_recording_show():
    """A plain function that records its call args — but, crucially, has no
    autovivifying attribute access. Using a ``MagicMock`` here would silently
    return a truthy mock for ``getattr(show, '_xontrib_mpl_patched', False)``
    and short-circuit the idempotency guard inside ``interactive_pyplot``."""

    def show(*args, **kwargs):
        show.call_args_list.append((args, kwargs))

    show.call_args_list = []
    return show


def _fake_pyplot():
    mod = types.ModuleType("matplotlib.pyplot")
    mod.ion = MagicMock()
    mod.show = _make_recording_show()
    return mod


def _fake_pylab_helpers(active_manager=None):
    mod = types.ModuleType("matplotlib._pylab_helpers")
    gcf = MagicMock()
    gcf.get_active = MagicMock(return_value=active_manager)
    gcf.draw_all = MagicMock()
    mod.Gcf = gcf
    return mod


@pytest.fixture
def mpl_xontrib(monkeypatch):
    """Replace ``XSH`` with a stub, freshly import ``xontrib.mpl``, and
    expose the recorded event-handler registrations to the test."""
    post_command_handlers = []
    import_post_handlers = []

    def register_postcommand(fn):
        post_command_handlers.append(fn)
        return fn

    def register_import_post(fn):
        import_post_handlers.append(fn)
        return fn

    events = types.SimpleNamespace(
        on_postcommand=register_postcommand,
        on_import_post_exec_module=register_import_post,
    )
    fake_xsh = types.SimpleNamespace(
        aliases={},
        env={"XONSH_INTERACTIVE": True},
        builtins=types.SimpleNamespace(events=events),
    )

    monkeypatch.setattr("xonsh.built_ins.XSH", fake_xsh)
    # Force a fresh import so the module body runs against our stub.
    sys.modules.pop("xontrib.mpl", None)

    import xontrib.mpl as mpl_module

    yield types.SimpleNamespace(
        xsh=fake_xsh,
        module=mpl_module,
        post_command_handlers=post_command_handlers,
        import_post_handlers=import_post_handlers,
    )

    # Clean up so subsequent imports re-pick up the real XSH.
    sys.modules.pop("xontrib.mpl", None)
    sys.modules.pop("matplotlib._pylab_helpers", None)


# ---------------------------------------------------------------------------
# Module-load side effects
# ---------------------------------------------------------------------------


def test_alias_registered(mpl_xontrib):
    """xontrib must register the ``mpl`` alias on import."""
    assert "mpl" in mpl_xontrib.xsh.aliases


def test_redraw_registered_once_at_module_load(mpl_xontrib):
    """``redraw_mpl_figure`` must be registered exactly once at xontrib
    load — NOT inside ``interactive_pyplot``. This is the structural
    invariant that prevents the historical handler-leak bug."""
    handlers = mpl_xontrib.post_command_handlers
    assert mpl_xontrib.module.redraw_mpl_figure in handlers
    assert handlers.count(mpl_xontrib.module.redraw_mpl_figure) == 1


def test_import_post_handler_registered_once(mpl_xontrib):
    handlers = mpl_xontrib.import_post_handlers
    assert mpl_xontrib.module.interactive_pyplot in handlers
    assert handlers.count(mpl_xontrib.module.interactive_pyplot) == 1


# ---------------------------------------------------------------------------
# redraw_mpl_figure
# ---------------------------------------------------------------------------


def test_redraw_is_noop_without_matplotlib(mpl_xontrib, monkeypatch):
    """If matplotlib has never been imported, redraw must silently do
    nothing — no ImportError, no attribute errors."""
    monkeypatch.delitem(sys.modules, "matplotlib._pylab_helpers", raising=False)
    mpl_xontrib.module.redraw_mpl_figure()  # must not raise


def test_redraw_calls_draw_all_when_matplotlib_loaded(mpl_xontrib, monkeypatch):
    helpers = _fake_pylab_helpers()
    monkeypatch.setitem(sys.modules, "matplotlib._pylab_helpers", helpers)
    mpl_xontrib.module.redraw_mpl_figure()
    helpers.Gcf.draw_all.assert_called_once()


def test_redraw_is_noop_in_non_interactive_mode(mpl_xontrib, monkeypatch):
    helpers = _fake_pylab_helpers()
    monkeypatch.setitem(sys.modules, "matplotlib._pylab_helpers", helpers)
    mpl_xontrib.xsh.env["XONSH_INTERACTIVE"] = False
    mpl_xontrib.module.redraw_mpl_figure()
    helpers.Gcf.draw_all.assert_not_called()


# ---------------------------------------------------------------------------
# interactive_pyplot
# ---------------------------------------------------------------------------


def test_interactive_pyplot_ignores_non_pyplot_modules(mpl_xontrib):
    other = types.ModuleType("some.unrelated.module")
    other.show = "sentinel"
    mpl_xontrib.module.interactive_pyplot(module=other)
    assert other.show == "sentinel"


def test_interactive_pyplot_skips_when_not_interactive(mpl_xontrib, monkeypatch):
    monkeypatch.setitem(
        sys.modules, "matplotlib._pylab_helpers", _fake_pylab_helpers()
    )
    pyplot = _fake_pyplot()
    original_show = pyplot.show
    mpl_xontrib.xsh.env["XONSH_INTERACTIVE"] = False

    mpl_xontrib.module.interactive_pyplot(module=pyplot)

    assert pyplot.show is original_show
    pyplot.ion.assert_not_called()


def test_interactive_pyplot_patches_show(mpl_xontrib, monkeypatch):
    monkeypatch.setitem(
        sys.modules, "matplotlib._pylab_helpers", _fake_pylab_helpers()
    )
    pyplot = _fake_pyplot()
    original_show = pyplot.show

    mpl_xontrib.module.interactive_pyplot(module=pyplot)

    assert pyplot.show is not original_show
    assert getattr(pyplot.show, "_xontrib_mpl_patched", False) is True
    pyplot.ion.assert_called_once()


def test_interactive_pyplot_is_idempotent(mpl_xontrib, monkeypatch):
    """Calling ``interactive_pyplot`` twice for the same pyplot module must
    NOT re-wrap ``module.show`` — the second call is a no-op. Otherwise we
    would stack wrappers on every re-import."""
    monkeypatch.setitem(
        sys.modules, "matplotlib._pylab_helpers", _fake_pylab_helpers()
    )
    pyplot = _fake_pyplot()

    mpl_xontrib.module.interactive_pyplot(module=pyplot)
    show_after_first = pyplot.show

    mpl_xontrib.module.interactive_pyplot(module=pyplot)
    show_after_second = pyplot.show

    assert show_after_second is show_after_first
    pyplot.ion.assert_called_once()


def test_no_postcommand_handler_leak_on_repeated_imports(mpl_xontrib, monkeypatch):
    """REGRESSION test for the historical bug: ``interactive_pyplot`` used
    to contain an inner ``@on_postcommand`` decorator, so every re-import
    of ``matplotlib.pyplot`` (importlib.reload, manual sys.modules
    eviction, Jupyter kernel restart, …) would register one more identical
    handler. The handler-list must stay stable across N re-imports."""
    monkeypatch.setitem(
        sys.modules, "matplotlib._pylab_helpers", _fake_pylab_helpers()
    )

    handlers_before = list(mpl_xontrib.post_command_handlers)
    for _ in range(5):
        mpl_xontrib.module.interactive_pyplot(module=_fake_pyplot())
    handlers_after = list(mpl_xontrib.post_command_handlers)

    assert handlers_before == handlers_after, (
        "interactive_pyplot must not register additional on_postcommand "
        "handlers; instead, redraw_mpl_figure is registered once at "
        "xontrib load time."
    )


# ---------------------------------------------------------------------------
# xonsh_show monkey-patched wrapper
# ---------------------------------------------------------------------------


def test_xonsh_show_defaults_to_non_blocking(mpl_xontrib, monkeypatch):
    """The wrapper calls the underlying ``plt.show`` exactly once with
    ``block=False`` when the user passes no ``block`` kwarg."""
    monkeypatch.setitem(
        sys.modules, "matplotlib._pylab_helpers", _fake_pylab_helpers()
    )
    pyplot = _fake_pyplot()
    original = pyplot.show

    mpl_xontrib.module.interactive_pyplot(module=pyplot)
    pyplot.show()  # invoke the wrapped version

    assert len(original.call_args_list) == 1
    _, kwargs = original.call_args_list[0]
    assert kwargs["block"] is False


def test_xonsh_show_does_not_retry_when_figure_active(mpl_xontrib, monkeypatch):
    """REGRESSION test for the historical bug: the wrapper used to inspect
    ``Gcf.get_active()`` after the non-blocking show and re-invoke
    ``plt.show(block=True)`` whenever a figure manager was still active —
    which is the normal case, so the shell got blocked unconditionally
    (see GitHub issue #1). The wrapper must NOT call the underlying show
    more than once."""
    sentinel = object()
    helpers = _fake_pylab_helpers(active_manager=sentinel)
    monkeypatch.setitem(sys.modules, "matplotlib._pylab_helpers", helpers)
    pyplot = _fake_pyplot()
    original = pyplot.show

    mpl_xontrib.module.interactive_pyplot(module=pyplot)
    pyplot.show()

    assert len(original.call_args_list) == 1, (
        "xonsh_show must not retry with block=True just because there is "
        "an active figure manager — that re-blocks the shell."
    )
    assert original.call_args_list[0][1]["block"] is False


def test_xonsh_show_respects_explicit_block_true(mpl_xontrib, monkeypatch):
    """If the caller explicitly passes ``block=True``, the wrapper must
    honor it instead of forcing non-blocking. Only the default is overridden."""
    monkeypatch.setitem(
        sys.modules, "matplotlib._pylab_helpers", _fake_pylab_helpers()
    )
    pyplot = _fake_pyplot()
    original = pyplot.show

    mpl_xontrib.module.interactive_pyplot(module=pyplot)
    pyplot.show(block=True)

    assert len(original.call_args_list) == 1
    assert original.call_args_list[0][1]["block"] is True
