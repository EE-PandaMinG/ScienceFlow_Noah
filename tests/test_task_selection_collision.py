"""Task discovery keeps registered names usable after successful-run export."""

from types import SimpleNamespace

from scienceflow.research.onboarding.library import catalog


def test_builtin_name_and_completion_stay_short_with_same_name_local_task(monkeypatch, tmp_path):
    local = tmp_path / 'task_library' / 'circle-packing-version'
    builtin = tmp_path / 'builtins' / 'circle-packing'
    monkeypatch.setattr(catalog, 'local_packages', lambda _: [
        SimpleNamespace(source_dir=local, task_id='circle-packing'),
    ])
    monkeypatch.setattr(catalog, 'iter_task_packages', lambda: [
        SimpleNamespace(source_dir=builtin, task_id='circle-packing'),
    ])
    text, choices = catalog.task_selection_text(tmp_path)
    assert len(choices) == 1
    assert text.count('circle-packing') == 1
    assert catalog.resolve_task_selection('circle-packing', choices) == 'circle-packing'
    assert catalog.resolve_task_selection('1', choices) == 'circle-packing'
    assert catalog.resolve_task_selection('circle-packing workers=2', choices) == (
        'circle-packing workers=2'
    )
    assert catalog.task_choices(tmp_path) == (
        ('circle-packing', 'circle-packing · Built-in'),
    )
    assert catalog.resolve_task_selection(str(local), choices) == str(local)


def test_catalog_deduplicates_local_entries_by_task_id(monkeypatch, tmp_path):
    monkeypatch.setattr(catalog, 'iter_task_packages', lambda: [])
    monkeypatch.setattr(catalog, 'local_packages', lambda _: [
        SimpleNamespace(source_dir=tmp_path / 'one', task_id='packing'),
        SimpleNamespace(source_dir=tmp_path / 'two', task_id='packing'),
    ])
    choices = catalog.discover_tasks(tmp_path)
    assert len(choices) == 1
    assert catalog.resolve_task_selection('packing', choices) == str(tmp_path / 'one')
    assert catalog.task_choices(tmp_path) == (('packing', 'packing · Local'),)


def test_builtin_resolution_is_not_shadowed_by_local_export(monkeypatch, tmp_path):
    from scienceflow.research.onboarding.support import task_defaults

    builtin = SimpleNamespace(task_id='circle-packing')
    local = SimpleNamespace(task_id='circle-packing')
    monkeypatch.setattr(task_defaults, 'find_task_package',
                        lambda value: builtin if value == 'circle-packing' else None)
    monkeypatch.setattr(catalog, 'resolve_local', lambda *_: local)
    assert task_defaults.resolve_task_package(
        '', 'circle-packing workers=2', workspace=tmp_path,
    ) is builtin
    assert task_defaults.resolve_task_package(
        '', '/tasks/local-copy', workspace=tmp_path,
    ) is local
