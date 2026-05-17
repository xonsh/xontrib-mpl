"""Matplotlib xontribution. This xontrib should be loaded before matplotlib
is imported.
"""
import sys

from xonsh.built_ins import XSH
from xonsh.tools import unthreadable

__all__ = ()


@unthreadable
def mpl(args, stdin=None):
    """Hooks to matplotlib"""
    from xontrib.mplhooks import show

    show()


XSH.aliases["mpl"] = mpl


@XSH.builtins.events.on_import_post_exec_module
def interactive_pyplot(module=None, **kwargs):
    """Puts matplotlib.pyplot into interactive mode and monkey-patches
    plt.show() to default to non-blocking. Idempotent across re-imports."""
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
    module.show = xonsh_show


@XSH.builtins.events.on_postcommand
def redraw_mpl_figure(**kwargs):
    """Redraws the current matplotlib figure after each command.
    No-op until matplotlib has actually been imported by the user."""
    if not XSH.env.get("XONSH_INTERACTIVE"):
        return
    pylab_helpers = sys.modules.get("matplotlib._pylab_helpers")
    if pylab_helpers is not None:
        pylab_helpers.Gcf.draw_all()
