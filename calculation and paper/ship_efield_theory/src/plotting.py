"""Shared plotting helpers."""

from pathlib import Path
import matplotlib.pyplot as plt


def save_current_figure(path):
    """Save and close current matplotlib figure."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output, dpi=180)
    plt.close()
