import pytest

from scripts.prune_render_tests import prune_tests


def test_prune_tests_removes_only_the_test_tree(tmp_path):
    for name in ("Procfile", "requirements.txt", "wsgi.py"):
        (tmp_path / name).touch()

    test_file = tmp_path / "tests" / "unit" / "test_sample.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("assert True\n", encoding="utf-8")
    app_file = tmp_path / "src" / "app.py"
    app_file.parent.mkdir()
    app_file.write_text("application = True\n", encoding="utf-8")

    assert prune_tests(tmp_path) == 1
    assert not (tmp_path / "tests").exists()
    assert app_file.exists()


def test_prune_tests_refuses_a_directory_without_project_markers(tmp_path):
    (tmp_path / "tests").mkdir()

    with pytest.raises(RuntimeError, match="project root"):
        prune_tests(tmp_path)
