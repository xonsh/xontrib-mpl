"""Matplotlib hooks, for what its worth."""

import shutil
from io import BytesIO

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from xonsh.built_ins import XSH
from xonsh.tools import ON_WINDOWS, print_color

try:
    # Use iterm2_tools as an indicator for the iterm2 terminal emulator
    from iterm2_tools.images import display_image_bytes
except ImportError:
    _use_iterm = False
else:
    _use_iterm = True

XONTRIB_MPL_MINIMAL_DEFAULT = True


def _get_buffer(fig, **kwargs):
    b = BytesIO()
    fig.savefig(b, **kwargs)
    b.seek(0)
    return b


def _physical_size(canvas):
    """Return ``(width, height)`` in physical pixels — the size of the buffer
    that ``savefig(format='raw')`` actually produces.

    matplotlib >= 3.7 split logical vs. physical pixels for HiDPI/Retina:
    ``get_width_height()`` returns logical, ``get_width_height(physical=True)``
    returns physical. On older matplotlib there is no such kwarg and the
    plain call already returns physical pixels.
    """
    try:
        return canvas.get_width_height(physical=True)
    except TypeError:
        return canvas.get_width_height()


def figure_to_rgb_array(fig, shape=None):
    """Converts figure to a numpy array

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        the figure to be plotted
    shape : iterable
        with the shape of the output array. by default this attempts to use the
        pixel height and width of the figure


    Returns
    -------
    array : np.ndarray
        An RGBA array of the image represented by the figure.

    Note: the method will throw an exception if the given shape is wrong.
    """
    array = np.frombuffer(
        _get_buffer(fig, dpi=fig.dpi, format="raw").read(), dtype="uint8"
    )
    if shape is None:
        w, h = _physical_size(fig.canvas)
        shape = (h, w, 4)
    return array.reshape(*shape)


def figure_to_tight_array(fig, width, height, minimal=True):
    """Converts figure to a numpy array of rgb values of tight value

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        the figure to be plotted
    width : int
        pixel width of the final array
    height : int
        pixel height of the final array
    minimal : bool
        whether or not to reduce the output array to minimized margins/whitespace
        text is also eliminated

    Returns
    -------
    array : np.ndarray
        An RGBA array of the image represented by the figure.
    """
    # Defensive clamp: terminals can report (0, 0) when stdout is piped or
    # detached, and show() further subtracts 1 row. Either case would later
    # hit ZeroDivisionError in `1/height` or in `width * dpi // w`.
    width = max(width, 2)
    height = max(height, 2)

    # store the properties of the figure in order to restore it. We capture
    # the size in *inches* rather than logical pixels: ``get_width_height()``
    # returns ``inches * dpi / device_pixel_ratio`` on HiDPI displays (mpl
    # ≥ 3.7), so ``w / dpi`` would be the original inches *divided by DPR*
    # — restoration would shrink the figure by the DPR factor on Retina.
    orig_size_inches = tuple(fig.get_size_inches())
    w, h = fig.canvas.get_width_height()
    if w <= 0 or h <= 0:
        raise ValueError(
            "matplotlib canvas has zero width or height; nothing to render"
        )
    dpi_fig = fig.dpi
    rc_overrides = {}
    if minimal:
        # perform reversible operations to produce an optimally tight layout
        dpi = dpi_fig
        subplotpars = {
            k: getattr(fig.subplotpars, k)
            for k in ["wspace", "hspace", "bottom", "top", "left", "right"]
        }

        # set the figure dimensions to the terminal size
        fig.set_size_inches(width / dpi, height / dpi, forward=True)
        width, height = _physical_size(fig.canvas)
        # ``_physical_size`` can still return a degenerate value on exotic
        # backends or tiny canvases — keep margin math safe.
        width = max(width, 1)
        height = max(height, 1)

        # remove all space between subplots
        fig.subplots_adjust(wspace=0, hspace=0)
        # Leave a one-pixel band for tick labels at top and bottom *if* the
        # canvas is tall enough for the strict inequality bottom < top to
        # hold. For height == 2 we'd compute bottom=top=0.5 which matplotlib
        # rejects with ``ValueError: bottom cannot be >= top``.
        if height >= 3:
            fig.subplots_adjust(bottom=1 / height, top=1 - 1 / height, left=0, right=1)
        else:
            fig.subplots_adjust(bottom=0, top=1, left=0, right=1)

        # Render with font.size=0 to suppress tick labels and other text. We
        # apply this via ``rc_context`` rather than mutating ``rcParams``
        # globally — the latter is process-wide state and a concurrent
        # render on another thread (xonsh background job, GUI mainloop)
        # would also see font.size=0. ``rc_context`` also restores on
        # exception, which the previous manual update did not.
        rc_overrides = {"font.size": 0}
    else:
        dpi = min([width * fig.dpi // w, height * fig.dpi // h])
        # Floor at a dpi high enough for freetype to compute a non-zero ppem
        # for the figure's text — at dpi=1 the AGG backend raises
        # ``invalid ppem value`` because ``font_size * dpi / 72`` rounds to 0.
        dpi = max(int(dpi), 10)
        fig.dpi = dpi
        width, height = _physical_size(fig.canvas)
        width = max(width, 1)
        height = max(height, 1)

    # Draw the renderer and get the RGB buffer from the figure
    with matplotlib.rc_context(rc_overrides):
        array = figure_to_rgb_array(fig, shape=(height, width, 4))

    if minimal:
        # reset the axis positions and figure dimensions
        fig.set_size_inches(*orig_size_inches, forward=True)
        fig.subplots_adjust(**subplotpars)
    else:
        fig.dpi = dpi_fig

    return array


def buf_to_color_str(buf):
    """Converts an RGB array to a xonsh color string."""
    space = " "
    pix = "{{bg#{0:02x}{1:02x}{2:02x}}} "
    pixels = []
    for h in range(buf.shape[0]):
        last = None
        for w in range(buf.shape[1]):
            rgb = buf[h, w]
            if last is not None and (last == rgb).all():
                pixels.append(space)
            else:
                pixels.append(pix.format(*rgb))
            last = rgb
        pixels.append("{RESET}\n")
    pixels[-1] = pixels[-1].rstrip()
    return "".join(pixels)


def display_figure_with_iterm2(fig):
    """Displays a matplotlib figure using iterm2 inline-image escape sequence.

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        the figure to be plotted
    """
    print(display_image_bytes(_get_buffer(fig, format="png", dpi=fig.dpi).read()))


def show():
    """Run the mpl display sequence by printing the most recent figure to console"""
    try:
        minimal = XSH.env["XONTRIB_MPL_MINIMAL"]
    except KeyError:
        minimal = XONTRIB_MPL_MINIMAL_DEFAULT
    fig = plt.gcf()
    if _use_iterm:
        display_figure_with_iterm2(fig)
    else:
        # Display the image using terminal characters to fit into the console
        w, h = shutil.get_terminal_size()
        if ON_WINDOWS:
            w -= 1  # @melund reports that win terminals are too thin
        h -= 1  # leave space for next prompt
        # If stdout is piped or the terminal mis-reports its size, clamp to a
        # sane minimum so figure_to_tight_array doesn't blow up downstream.
        w = max(w, 2)
        h = max(h, 2)
        buf = figure_to_tight_array(fig, w, h, minimal)
        s = buf_to_color_str(buf)
        print_color(s)
