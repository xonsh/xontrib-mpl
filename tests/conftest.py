"""Force matplotlib to use the headless Agg backend for tests.

The tests never display figures on a real screen — they only render to
in-memory buffers via ``savefig`` / ``figure_to_rgb_array``, which work
identically on any rasterising backend. Agg is:

- available on every platform without GUI dependencies;
- identical on Linux / macOS / Windows runners (avoiding ``TkAgg`` on
  Windows-hosted CI, where Python's bundled Tcl/Tk install may be missing
  ``init.tcl`` — see
  https://github.com/xonsh/xontrib-mpl/actions/runs/26001791970);
- the fastest backend (no event-loop spin-up).

``conftest.py`` is loaded by pytest before collecting any test module, so
the ``use`` call lands before ``matplotlib.pyplot`` is imported anywhere.
"""
import matplotlib

matplotlib.use("Agg")
