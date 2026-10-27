"""Lossless, non-destructive engineering project archiving.

Archives preserve original paths and include ALL regular files. Symlinks are
rejected (not silently omitted), and no source files are modified or deleted.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path

BLOCK = 1024 * 1024


@dataclass(frozen=True)
class PlannedFile:
    source: str
    destination: str
    size_bytes: int
    modified_ns: int


def _inside(candidate: Path, root: Path) -> bool:
    return candidate == root or root in candidate.parents


def hash_stream(f) -> str:
    h = hashlib.sha256()
    for chunk in iter(lambda: f.read(BLOCK), b''):
        h.update(chunk)
    return h.hexdigest()


def hash_file(path: Path) -> str:
    with path.open('rb') as f:
        return hash_stream(f)


def make_plan(project: Path) -> list[PlannedFile]:
    project = project.resolve(strict=True)
    if not project.is_dir():
        raise ValueError('Project must be a directory')
    plan = []
    for folder, dirs, files in os.walk(project, followlinks=False):
        dirs.sort()
        for d in dirs:
            if (Path(folder) / d).is_symlink():
                raise ValueError(f'Symlinked directory not supported: {d}')
        for filename in sorted(files):
            p = Path(folder) / filename
            if p.is_symlink():
                raise ValueError(f'Symlinked file not supported: {p}')
            if not p.is_file():
                raise ValueError(f'Not a regular file: {p}')
            rel = p.relative_to(project).as_posix()
            stat = p.stat()
            plan.append(PlannedFile(rel, f'Original_Project/{rel}', stat.st_size, stat.st_mtime_ns))
    return plan


def _zip_hash(zf: zipfile.ZipFile, member: str) -> str:
    with zf.open(member) as f:
        return hash_stream(f)


def verify_archive(archive: Path, manifest_file: Path | None = None) -> dict:
    """Validate ZIP bytes against embedded inventory and optional sidecar."""
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate ZIP members')
        if 'manifest.json' not in names:
            raise ValueError('Missing embedded manifest')
        manifest = json.loads(zf.read('manifest.json'))
        members = manifest['files']
        expected = {r['archive_path'] for r in members} | {'manifest.json'}
        if set(names) != expected:
            raise ValueError('ZIP member list differs from manifest')
        for row in members:
            if _zip_hash(zf, row['archive_path']) != row['sha256']:
                raise ValueError(f"Checksum mismatch: {row['archive_path']}")
    if manifest_file is not None:
        if json.loads(manifest_file.read_text(encoding='utf-8')) != manifest:
            raise ValueError('Sidecar manifest differs from embedded manifest')
    return manifest


def create_archive(project: Path, output_dir: Path, plan: list[PlannedFile],
                   project_id: str | None = None, retention_start: str | None = None,
                   retention_basis: str = 'unconfirmed') -> tuple[Path, Path]:
    project = project.resolve(strict=True)
    output_dir = output_dir.resolve()
    if _inside(output_dir, project) or _inside(project, output_dir):
        raise ValueError('Output cannot contain source or be within source (avoid recursive archiving)')
    # Validate explicit date without assuming that creation date starts retention.
    if retention_start:
        date.fromisoformat(retention_start)
    # Re-enumerate to detect additions/deletions after preview.
    if make_plan(project) != plan:
        raise RuntimeError('Project changed since preview. Run preview again.')
    output_dir.mkdir(parents=True, exist_ok=True)
    created = datetime.now(timezone.utc).isoformat()
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    project_label = project.name.replace('/', '_').replace('\\', '_')
    basename = f'{project_label}_{stamp}'
    index = 0
    while True:
        name = basename + (f'_{index}' if index else '')
        archive = output_dir / f'{name}.zip'
        sidecar = output_dir / f'{name}.json'
        if not archive.exists() and not sidecar.exists():
            break
        index += 1
    fd, staging_name = tempfile.mkstemp(prefix='.staging_', suffix='.zip', dir=output_dir)
    os.close(fd)
    staging = Path(staging_name)
    inventory = []
    try:
        with zipfile.ZipFile(staging, 'w', zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as zf:
            for item in plan:
                source = project / item.source
                if source.is_symlink() or not source.is_file() or not _inside(source.resolve(), project):
                    raise RuntimeError(f'Unsafe source: {item.source}')
                before = source.stat()
                if (before.st_size, before.st_mtime_ns) != (item.size_bytes, item.modified_ns):
                    raise RuntimeError(f'Source changed since preview: {item.source}')
                checksum = hash_file(source)
                zf.write(source, item.destination)
                after = source.stat()
                if (after.st_size, after.st_mtime_ns) != (before.st_size, before.st_mtime_ns):
                    raise RuntimeError(f'Source changed during archive: {item.source}')
                inventory.append({'source_path': item.source, 'archive_path': item.destination,
                                  'size_bytes': item.size_bytes, 'sha256': checksum})
            manifest = {
                'schema_version': 2, 'project_id': project_id or project.name,
                'project_name': project.name, 'created_utc': created,
                'retention_years_expected': 10,
                'retention_start_date': retention_start,
                'retention_basis': retention_basis,
                'retention_policy_verified': False,
                'source_files_modified': False,
                'files': inventory,
            }
            zf.writestr('manifest.json', json.dumps(manifest, indent=2, ensure_ascii=False))
        verify_archive(staging)
        # Write sidecar before publishing; using exclusive creation prevents overwrite.
        with sidecar.open('x', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        try:
            # Do not silently overwrite even if another process created the same filename.
            with staging.open('rb') as src, archive.open('xb') as dst:
                import shutil
                shutil.copyfileobj(src, dst, BLOCK)
            verify_archive(archive, sidecar)
        except Exception:
            archive.unlink(missing_ok=True)
            sidecar.unlink(missing_ok=True)
            raise
        return archive, sidecar
    finally:
        staging.unlink(missing_ok=True)


def add_registry_entry(registry: Path, archive: Path, sidecar: Path) -> None:
    """Append index; a convenience catalogue, not a compliance retention system."""
    registry.parent.mkdir(parents=True, exist_ok=True)
    doc = json.loads(sidecar.read_text(encoding='utf-8'))
    new = not registry.exists() or registry.stat().st_size == 0
    with registry.open('a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if new:
            writer.writerow(['project_id', 'project_name', 'created_utc', 'retention_start_date',
                             'retention_basis', 'archive_filename', 'sha256_zip', 'sidecar_filename'])
        writer.writerow([doc['project_id'], doc['project_name'], doc['created_utc'],
                         doc['retention_start_date'] or '', doc['retention_basis'],
                         archive.name, hash_file(archive), sidecar.name])
