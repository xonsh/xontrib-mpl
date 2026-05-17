<p align="center">
Matplotlib hooks for xonsh, including the new 'mpl' alias that displays the current figure on the screen.
</p>

<p align="center">
If you like the idea click ⭐ on the repo and <a href="https://twitter.com/intent/tweet?text=Nice%20xontrib%20for%20the%20xonsh%20shell!&url=https://github.com/xonsh/xontrib-mpl" target="_blank">tweet</a>.
</p>


## Installation

To install use pip:

```bash
xpip install xontrib-mpl
# or: xpip install -U git+https://github.com/xonsh/xontrib-mpl
```

## Usage

```bash
xontrib load mpl
```
Examples: https://youtu.be/uaje5I22kgE?t=1362

### Example: poll CPU 10 times and plot inline

Sample CPU utilisation once per second for 10 seconds, build a line chart,
and render it right in the terminal — no GUI window needed:

```bash
xpip install psutil
xontrib load mpl

import psutil
import matplotlib.pyplot as plt

samples = []
N = 10
for i in range(N):
    perc = psutil.cpu_percent(interval=1)
    samples.append(perc)
    print(f'CPU {i+1}/{N}: {perc}%')

plt.close('all')   # discard previous figures so re-runs don't overlay
plt.plot(samples)
plt.ylim(0, 100)   # fixed 0–100% so re-runs are visually comparable

mpl
```

The figure is rasterised into coloured terminal cells and printed inline
below your prompt.

> Tip: `mpl` defaults to `$XONTRIB_MPL_MINIMAL = True`, which hides tick
> labels, axes text and inter-subplot gaps so the plot uses the full
> terminal. Set it to `False` (`$XONTRIB_MPL_MINIMAL = False`) to keep
> the title / xlabel / ylabel you'd normally pass to matplotlib.

## Day to day usage

If you want to use matplotlib day to day with xonsh we recommend to take a look into [xontrib-jupyter](https://github.com/xonsh/xontrib-jupyter) that could be used both in web-based Jupyter Notebook and in terminal with Euporia.

## Credits

This package was created with [xontrib cookiecutter template](https://github.com/xonsh/xontrib-cookiecutter).
