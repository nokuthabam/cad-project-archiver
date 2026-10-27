# CAD Project Archiver v1.1

A small, **non-destructive**, Python-based archiving utility for completed engineering projects. Built for a real Windows File Explorer workflow, and published with synthetic test data only.

> **Not a certified records-management or regulatory-compliance system.** The reported ten-year retention requirement and its trigger must be confirmed against the actual contracts and applicable rules. Do not delete source records based on an archived ZIP alone.

## Features

- **Dry-run by default**: prints a complete inventory without changing any file.
- **Lossless ZIP**: keeps original folder hierarchy under `Original_Project/`, including `.bak`, `.tmp`, `.log`, and office lock files. No silent filtering or sorting that might break CAD references.
- **Non-destructive**: leaves source folders untouched. Never deletes originals or prior archives.
- **SHA-256**: records per-file checksums in both embedded `manifest.json` and external JSON manifest; independently rechecks content after ZIP creation.
- **Retention metadata**: optional project ID, retention start date and documented basis. If unknown, records that they are **unconfirmed**, not a made-up expiry date.
- **CSV index**: appends archive entries including ZIP checksum and filename. The index is a convenience, not a database or immutable audit log.
- **Verification command**: checks archive contents against manifest at a later date.
- **Windows File Explorer**: optional right-click context menu examples.

## Install on Windows (Python 3.10+)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest -q
```

## Usage

```powershell
# Preview a disposable test project (no writes)
cad-archive "C:\Projects\Hospital_A"

# Make a verified ZIP in an archives folder (not inside the project)
cad-archive "C:\Projects\Hospital_A" --archive --output "C:\Users\YOU\OneDrive\Engineering Archives" --project-id HOSP-2026-001

# If and only if the correct date and legal basis are known:
cad-archive "C:\Projects\Hospital_A" --archive --project-id HOSP-2026-001 --retention-start 2026-10-01 --retention-basis "Contract reference verified by owner"

# Verify ZIP in the future, including sidecar JSON when present:
cad-archive --verify "C:\Users\YOU\OneDrive\Engineering Archives\Hospital_A_20261027_120000.zip"
```

**Note:** The `--retention-start` field is optional because the ten-year clock may start at a contractual milestone other than archiving. A ten-year expectation does **not** instruct the tool to calculate an automatic deletion date. No automatic deletion exists.

### Example ZIP

```text
Hospital_A_20261027_120000.zip
├── Original_Project/
│   ├── assembly.sldasm
│   ├── Components/part.sldprt
│   ├── draft.bak
│   ├── calculations.log
│   └── final_report.pdf
└── manifest.json
```

A sidecar `<archive name>.json` and `archive_registry.csv` live next to the ZIP, not inside the source folder. The archive itself carries the embedded manifest, so a sidecar isn't essential to verification.

## Windows Explorer integration

The `windows/` directory includes registry examples for previewing or creating an archive by right-clicking a folder. **Edit the absolute `python.exe` paths to your installation** before importing; they are examples only. The sample archive action uses the default sibling `CAD_Archives` folder, not your OneDrive location. Use the CLI `--output` flag for a chosen OneDrive folder, or change the registry command *after testing*. Back up registry keys before changes.

## Important storage and records limitations

- **OneDrive is sync, not an independent backup.** A ZIP created under a local OneDrive folder may not have uploaded yet. The program cannot confirm cloud upload, retention configuration or remote recoverability.
- Keep **independent, protected copies**, check permissions, periodically run `--verify`, and perform actual restore tests. Agree the backup and retention procedure with the records owner.
- Verify whether personal OneDrive is permitted for government/client records; protect confidential information and confirm applicable contractual or regulatory requirements.
- No automatic purge, cleaning, expiry enforcement, encryption, immutability, e-signature, cloud upload verification, access auditing, or legally compliant retention policy engine is provided.
- Archived data is not an atomic snapshot. Run only after the project is closed and files have stopped changing. Some simultaneous edits can escape change detection.
- Symlinks cause the tool to refuse to archive the folder (to avoid silently omitting data). Empty directories are not represented in ZIP.
- Keep the original source folders until an approved archiving, backup and restore procedure authorises their removal.
- The CSV registry append is **not transactionally atomic**; cloud-sync collisions or concurrent writers can corrupt the index. The sidecar and embedded manifests remain available to rebuild it.
- Avoid filenames containing sensitive project identifiers if cloud/account permissions do not allow their disclosure.

## Portfolio notes

Demonstrates Python filesystem programming, CLI design, ZIP verification, metadata management, defensive programming, hashing, test coverage and real-world workflow integration. There are no client records in this public repository.

## Development

```powershell
python -m pytest -q
```

MIT licence. No production dependencies beyond the Python standard library.
