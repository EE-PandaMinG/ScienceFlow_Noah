from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _requirement_names(requirements: list[str]) -> set[str]:
    names: set[str] = set()
    for requirement in requirements:
        match = re.match(r"[A-Za-z0-9_.-]+", requirement)
        assert match, requirement
        names.add(match.group(0).lower().replace("_", "-"))
    return names


def _project_metadata() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_default_install_includes_cpu_data_without_optional_accelerators() -> None:
    metadata = _project_metadata()
    core = _requirement_names(metadata["project"]["dependencies"])
    forbidden = {
        "catboost",
        "lightgbm",
        "mlebench",
        "datasets",
        "pytest",
        "scikit-learn",
        "tabpfn",
        "torch",
        "torchaudio",
        "torchvision",
        "transformers",
        "ultralytics",
        "xgboost",
    }
    assert not core & forbidden
    assert {
        "httpx", "inquirycraft", "numpy", "openai", "pandas", "reportlab", "scipy"
    } <= core
    assert metadata["tool"]["uv"]["default-groups"] == []
    assert _requirement_names(metadata["dependency-groups"]["dev"]) == {
        "pytest",
        "pytest-asyncio",
        "pytest-cov",
    }


def test_full_profile_covers_task_profiles() -> None:
    extras = _project_metadata()["project"]["optional-dependencies"]
    assert {"ml", "gpu", "mlebench", "detection-2d", "full"} <= set(extras)
    full = _requirement_names(extras["full"])
    task_profiles = set().union(
        *(
            _requirement_names(extras[name])
            for name in ("ml", "gpu", "mlebench", "detection-2d")
        )
    )
    assert task_profiles <= full
    assert "torch" not in _requirement_names(extras["ml"])
    assert "tabpfn" not in _requirement_names(extras["ml"])
    assert "datasets" in _requirement_names(extras["scientific-design"])
    for name in ("ml", "gpu", "full"):
        assert not {"numpy", "pandas", "scipy"} & _requirement_names(extras[name])


def test_public_install_surface_is_light_and_full() -> None:
    public_docs = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "pip install scienceflow" in public_docs
    assert 'pip install "scienceflow[full]==0.2.0b7"' in public_docs
    for internal_extra in ("ml", "gpu", "mlebench"):
        assert f'scienceflow[{internal_extra}]' not in public_docs


def test_builtin_skills_are_declared_as_installed_data() -> None:
    setuptools = _project_metadata()["tool"]["setuptools"]
    assert setuptools["data-files"] == {
        "share/scienceflow/skills/data_processing": ["skills/data_processing/*.md"]
    }
    skill_names = {
        path.name for path in (ROOT / "skills" / "data_processing").glob("*.md")
    }
    assert skill_names == {
        "bson_image_loading.md",
        "data_prep.md",
        "image_task_guide.md",
        "recommender_time_split.md",
        "self_eval.md",
        "tabular_preprocess_speedup.md",
    }
