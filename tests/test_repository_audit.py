from tools.repository_audit import path_errors


def test_raw_files_and_solver_products_are_local_only():
    for name in ("results/a.npz", "comsol/models/a.mph", "output/a.pptx", ".env"):
        assert path_errors(name, 10)


def test_reports_and_sources_are_allowed():
    for name in ("results/report.md", "scripts/a.py", "comsol/results/field.csv", ".env.example"):
        assert not path_errors(name, 10)


def test_file_size_limits():
    assert path_errors("analysis_out/features.csv", 3 * 1024**2)
    assert not path_errors("results/features.csv", 3 * 1024**2)
    assert path_errors("results/features.csv", 26 * 1024**2)


def test_incomplete_archive_marker_is_rejected():
    assert path_errors("results/test/exact_archive/COMPLETE", 0)
