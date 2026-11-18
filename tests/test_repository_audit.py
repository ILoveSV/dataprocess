from tools.repository_audit import path_errors


def test_raw_files_and_solver_products_are_local_only():
    for name in ("analysis/a.npz", "research/simulation/models/a.mph", "deliverables/a.pptx", ".env"):
        assert path_errors(name, 10)


def test_reports_and_sources_are_allowed():
    for name in ("analysis/report.md", "scripts/a.py", "research/simulation/results/field.csv", ".env.example"):
        assert not path_errors(name, 10)


def test_file_size_limits():
    assert path_errors("analysis/legacy_pipeline/features.csv", 3 * 1024**2)
    assert not path_errors("analysis/features.csv", 3 * 1024**2)
    assert path_errors("analysis/features.csv", 26 * 1024**2)


def test_incomplete_archive_marker_is_rejected():
    assert path_errors("analysis/test/exact_archive/COMPLETE", 0)
