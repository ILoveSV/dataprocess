from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("theory_first", [False, True])
def test_theory_and_processing_imports_are_order_independent(theory_first):
    imports = [
        "import src.features.fft_core as processing",
        "import scripts.background_field_reference_20260927 as theory",
    ]
    if theory_first:
        imports.reverse()
    code = "\n".join(imports + [
        "assert theory.skin_depth.__module__ == '_dataprocess_ship_theory.propagation'",
        "assert processing.__name__ == 'src.features.fft_core'",
    ])
    subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1], check=True)
