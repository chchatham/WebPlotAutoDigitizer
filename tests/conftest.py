from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from tests.generate_plots import generate_baseline_suite, PlotOutput


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(scope="session")
def baseline_plots(tmp_path_factory: pytest.TempPathFactory) -> list[PlotOutput]:
    out_dir = tmp_path_factory.mktemp("baseline_plots")
    return generate_baseline_suite(out_dir)
