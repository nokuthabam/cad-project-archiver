"""Command line interface; dry run is default."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from .core import add_registry_entry, create_archive, make_plan, verify_archive


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description='Lossless engineering project preservation tool')
    p.add_argument('project', type=Path, nargs='?', help='Existing completed project folder')
    p.add_argument('--archive', action='store_true', help='Explicitly create and verify a ZIP')
    p.add_argument('--verify', type=Path, help='Recheck an existing ZIP against its embedded manifest')
    p.add_argument('--output', type=Path, help='Archive destination (outside project)')
    p.add_argument('--project-id', help='Project reference for archive registry')
    p.add_argument('--retention-start', help='Confirmed ISO date YYYY-MM-DD (optional)')
    p.add_argument('--retention-basis', default='unconfirmed', help='Contract/regulation reference; verify externally')
    p.add_argument('--pause', action='store_true', help='Pause console for Explorer')
    args = p.parse_args(argv)
    try:
        if args.verify:
            doc = verify_archive(args.verify, args.verify.with_suffix('.json') if args.verify.with_suffix('.json').exists() else None)
            print(f"VERIFIED: {args.verify} ({len(doc['files'])} original files)")
            return 0
        if not args.project:
            p.error('Provide a project folder or --verify ARCHIVE.zip')
        plan = make_plan(args.project)
        print(f'Project: {args.project.resolve()}\nFiles preserved: {len(plan)}')
        for item in plan:
            print(f'  KEEP {item.source} -> {item.destination}')
        if not args.archive:
            print('\nDRY RUN. No changes made. Use --archive to create a verified ZIP.')
            return 0
        output = args.output or args.project.resolve().parent / 'CAD_Archives'
        z, manifest = create_archive(args.project, output, plan, args.project_id,
                                     args.retention_start, args.retention_basis)
        # Registry is best-effort; a failed registry write never invalidates an archive.
        try:
            add_registry_entry(output / 'archive_registry.csv', z, manifest)
        except OSError as exc:
            print(f'WARNING: Archive created, but index could not be updated: {exc}', file=sys.stderr)
        print(f'VERIFIED ZIP: {z}\nMANIFEST: {manifest}')
        print('Source untouched. Cloud sync and independent backup are NOT verified.')
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, __import__('zipfile').BadZipFile) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1
    finally:
        if args.pause:
            try:
                input('Press Enter to close...')
            except EOFError:
                pass


if __name__ == '__main__':
    raise SystemExit(main())
