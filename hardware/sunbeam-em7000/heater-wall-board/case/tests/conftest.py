"""Test options of the printed case: the heavy tests are left out of a default run and included with `--heavy`."""

import os
import sys

import pytest

CASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CASE_DIR)
import case  # noqa: E402,I001  (build123d before vtk)
import negatives  # noqa: E402


def pytest_addoption(parser):
    parser.addoption("--heavy", action="store_true", default=False,
                     help="also run the tests marked heavy (the rebuild of every extreme of the seating range, about ten minutes)")


def pytest_configure(config):
    config.addinivalue_line("markers", "heavy: a test that takes many minutes; deselected unless --heavy is given")
    config.addinivalue_line("markers", "controls(*names): the negative controls of negatives.py this test reads; they are started together before the first test")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--heavy"):
        return
    kept, dropped = [], []
    for item in items:
        (dropped if item.get_closest_marker("heavy") else kept).append(item)
    if dropped:
        config.hook.pytest_deselected(items=dropped)
        items[:] = kept


# The session fixtures every test file shares, so that one run builds the model once.
@pytest.fixture(scope="session")
def model():
    return case.build()


@pytest.fixture(scope="session")
def results(controls):
    return controls.get("nominal")


@pytest.fixture(scope="session")
def basis():
    return case.basis()


@pytest.fixture(scope="session", autouse=True)
def controls(request):
    """The nominal check and the negative controls the selected tests read, started together on the pool before the first test runs.

    The main process builds the nominal model first, which the tests read, and the pool starts when that is done, so that no more
    than four processes compute at once: the nominal check itself runs on the pool as one of the jobs, for `results`."""
    wanted = [name for item in request.session.items for mark in item.iter_markers("controls") for name in mark.args]
    if any("results" in item.fixturenames for item in request.session.items):
        wanted.append("nominal")
    if any({"model", "results"} & set(item.fixturenames) for item in request.session.items):
        request.getfixturevalue("model")
    pool = negatives.Controls(wanted)
    yield pool
    pool.close()


@pytest.fixture(scope="session")
def renders(tmp_path_factory):
    """The folder of renders every test that reads an image uses: all three colour forms drawn once per session, on first use, into a
    temporary folder (the plain views in it, the installed views and the two sheets in its `directions` folder)."""
    import render
    folder = str(tmp_path_factory.mktemp("renders"))
    assert render.main(["--out", folder]) == 0
    assert render.main(["--directions", "--out", os.path.join(folder, "directions")]) == 0
    return folder
