import csv
import json
import zipfile
from pathlib import Path
import pytest
from cad_archiver.core import make_plan, create_archive, verify_archive
from cad_archiver.cli import main


def sample(tmp_path):
    p = tmp_path / 'Hospital A'
    (p / 'Components').mkdir(parents=True)
    for path, value in [('assembly.sldasm', 'assy'), ('Components/part.sldprt', 'part'),
                        ('report.pdf', 'report'), ('draft.bak', 'valuable recovery'),
                        ('calc.log', 'simulation log'), ('~$draft.docx', 'lock file')]:
        (p / path).write_text(value)
    return p


def test_preview_does_not_create_output(tmp_path):
    p = sample(tmp_path)
    assert main([str(p)]) == 0
    assert not (tmp_path / 'CAD_Archives').exists()


def test_archive_preserves_all_files_and_structure(tmp_path):
    p = sample(tmp_path)
    original = {x.relative_to(p).as_posix(): x.read_bytes() for x in p.rglob('*') if x.is_file()}
    z, m = create_archive(p, tmp_path / 'out', make_plan(p), retention_start='2026-10-01')
    with zipfile.ZipFile(z) as f:
        for rel, data in original.items():
            assert f.read('Original_Project/' + rel) == data
        assert 'manifest.json' in f.namelist()
    assert verify_archive(z, m)['retention_start_date'] == '2026-10-01'
    assert original == {x.relative_to(p).as_posix(): x.read_bytes() for x in p.rglob('*') if x.is_file()}


def test_index_and_verify_cli(tmp_path):
    p = sample(tmp_path)
    out = tmp_path / 'out'
    assert main([str(p), '--archive', '--output', str(out), '--project-id', 'HOSP-01']) == 0
    with (out / 'archive_registry.csv').open(newline='') as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]['project_id'] == 'HOSP-01'
    assert main(['--verify', str(next(out.glob('*.zip')))]) == 0


def test_corrupted_archive_fails_verification(tmp_path):
    p = sample(tmp_path)
    z, m = create_archive(p, tmp_path / 'out', make_plan(p))
    with z.open('r+b') as f:
        f.seek(0)
        f.write(b'xxxxxxxxxxxxxxxxxxxx')
    with pytest.raises((ValueError, zipfile.BadZipFile, OSError)):
        verify_archive(z, m)


def test_changed_after_plan_rejected(tmp_path):
    p = sample(tmp_path)
    plan = make_plan(p)
    (p / 'new.pdf').write_text('new')
    with pytest.raises(RuntimeError):
        create_archive(p, tmp_path / 'out', plan)


def test_source_destination_overlap_rejected(tmp_path):
    p = sample(tmp_path)
    with pytest.raises(ValueError):
        create_archive(p, p / 'ARCHIVES', make_plan(p))
    with pytest.raises(ValueError):
        create_archive(p, tmp_path, make_plan(p))


def test_symlink_rejected(tmp_path):
    p = sample(tmp_path)
    outside = tmp_path / 'outside'
    outside.write_text('secret')
    try:
        (p / 'link').symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip('Symlinks unavailable')
    with pytest.raises(ValueError):
        make_plan(p)
