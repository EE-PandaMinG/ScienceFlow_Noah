"""Task discovery keeps registered names usable after successful-run export."""

from types import SimpleNamespace

import pytest

from scienceflow.research.onboarding.library import catalog


def test_local_name_wins_but_builtin_number_keeps_its_source(monkeypatch, tmp_path):
    local = tmp_path / 'task_library' / 'circle-packing-version'
    builtin = tmp_path / 'builtins' / 'circle-packing'
    monkeypatch.setattr(catalog, 'local_packages', lambda _: [
        SimpleNamespace(source_dir=local, task_id='circle-packing'),
    ])
    monkeypatch.setattr(catalog, 'iter_task_packages', lambda: [
        SimpleNamespace(source_dir=builtin, task_id='circle-packing'),
    ])
    _, choices = catalog.task_selection_text(tmp_path)
    assert catalog.resolve_task_selection('circle-packing', choices) == str(local)
    assert catalog.resolve_task_selection('circle-packing workers=2', choices) == (
        f'{local} workers=2'
    )
    assert catalog.resolve_task_selection('2', choices) == str(builtin)
    assert catalog.resolve_task_selection('2 workers=2', choices) == f'{builtin} workers=2'
    assert catalog.resolve_task_selection(str(builtin), choices) == str(builtin)


def test_multiple_local_versions_show_usable_numbers_and_paths():
    choices = (
        catalog.TaskChoice('/tasks/packing-one', 'packing', 'Local'),
        catalog.TaskChoice('/tasks/packing-two', 'packing', 'Local'),
        catalog.TaskChoice('/builtin/packing', 'packing', 'Built-in'),
    )
    with pytest.raises(ValueError) as error:
        catalog.resolve_task_selection('packing', choices)
    assert '1. packing · Local · /tasks/packing-one' in str(error.value)
    assert '2. packing · Local · /tasks/packing-two' in str(error.value)
    assert catalog.resolve_task_selection('2', choices) == '/tasks/packing-two'
    assert catalog.resolve_task_selection('/tasks/packing-one', choices) == '/tasks/packing-one'
