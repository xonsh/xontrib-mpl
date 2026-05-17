"""Matplotlib xontribution.

Provides:

- the ``mpl`` alias, which prints the current matplotlib figure to the
  terminal;
- an import hook that puts ``matplotlib.pyplot`` into interactive mode and
  monkey-patches ``plt.show`` to be non-blocking, the first time pyplot is
  imported in an interactive xonsh session;
- an after-command hook that redraws the active matplotlib figure so its
  window stays responsive while the shell is busy.

This xontrib should be loaded before ``matplotlib`` is imported.
"""

import sys

from xonsh.built_ins import XSH
from xonsh.tools import unthreadable

__all__ = ()


@unthreadable
def mpl(args, stdin=None):
    """Print the current matplotlib figure to the terminal."""
    from xontrib.mplhooks import show

    show()


def interactive_pyplot(module=None, **kwargs):
    """Puts ``matplotlib.pyplot`` into interactive mode and monkey-patches
    ``plt.show()`` so it defaults to non-blocking. Idempotent across
    re-imports of pyplot — calling it twice for the same module is a no-op."""
    if module.__name__ != "matplotlib.pyplot" or not XSH.env.get("XONSH_INTERACTIVE"):
        return
    if getattr(module.show, "_xontrib_mpl_patched", False):
        return

    module.ion()
    plt_show = module.show

    def xonsh_show(*args, **kwargs):
        """Monkey-patched ``matplotlib.pyplot.show()`` for xonsh's interactive
        mode. Defaults to ``block=False`` so the shell prompt isn't frozen,
        but honors an explicit ``block=True`` from the caller."""
        kwargs.setdefault("block", False)
        return plt_show(*args, **kwargs)

    xonsh_show._xontrib_mpl_patched = True
    xonsh_show._xontrib_mpl_orig_show = plt_show
    module.show = xonsh_show


def redraw_mpl_figure(**kwargs):
    """Redraw the current matplotlib figure after each command.
    No-op until matplotlib has actually been imported by the user."""
    if not XSH.env.get("XONSH_INTERACTIVE"):
        return
    pylab_helpers = sys.modules.get("matplotlib._pylab_helpers")
    if pylab_helpers is not None:
        pylab_helpers.Gcf.draw_all()


def _restore_pyplot_show():
    """If we monkey-patched ``matplotlib.pyplot.show``, put the original
    back. Safe to call when matplotlib was never imported."""
    pyplot = sys.modules.get("matplotlib.pyplot")
    if pyplot is None:
        return
    show = getattr(pyplot, "show", None)
    if show is not None and getattr(show, "_xontrib_mpl_patched", False):
        orig = getattr(show, "_xontrib_mpl_orig_show", None)
        if orig is not None:
            pyplot.show = orig


def _load_xontrib_(xsh, **_):
    """Wire up the ``mpl`` alias and the matplotlib interactivity hooks."""
    xsh.env.register(
        "XONTRIB_MPL_MINIMAL",
        type="bool",
        default=True,
        doc=(
            "When True (the default), the ``mpl`` alias strips tick labels, "
            "axis text and inter-subplot gaps before rendering the figure "
            "to the terminal. Set to False to keep the figure's normal "
            "margins and labels at the cost of less plotting area."
        ),
    )
    xsh.aliases["mpl"] = mpl
    xsh.builtins.events.on_import_post_exec_module(interactive_pyplot)
    xsh.builtins.events.on_postcommand(redraw_mpl_figure)
    return {}


def _unload_xontrib_(xsh, **_):
    """Undo everything ``_load_xontrib_`` set up."""
    xsh.builtins.events.on_import_post_exec_module.discard(interactive_pyplot)
    xsh.builtins.events.on_postcommand.discard(redraw_mpl_figure)
    if "mpl" in xsh.aliases:
        del xsh.aliases["mpl"]
    _restore_pyplot_show()
    if "XONTRIB_MPL_MINIMAL" in xsh.env:
        xsh.env.deregister("XONTRIB_MPL_MINIMAL")
    return {}
