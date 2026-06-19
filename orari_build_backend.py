"""Minimal PEP 517/660 backend for offline editable installs in constrained envs."""

from __future__ import annotations

import hashlib
import time
import zipfile
from pathlib import Path

DIST = "orari_agent-0.1.0.dist-info"
VERSION = "0.1.0"


def _metadata() -> str:
    return "\n".join(
        [
            "Metadata-Version: 2.1",
            "Name: orari-agent",
            f"Version: {VERSION}",
            "Summary: Agente base per generare orari settimanali di CarpeEvolution Store e Tenuta del Germano",
            "Requires-Python: >=3.10",
            "",
        ]
    )


def _wheel() -> str:
    return "\n".join(
        [
            "Wheel-Version: 1.0",
            "Generator: orari-build-backend",
            "Root-Is-Purelib: true",
            "Tag: py3-none-any",
            "",
        ]
    )


def _entry_points() -> str:
    return "\n".join(
        [
            "[console_scripts]",
            "orari-agent = orari_agent.cli:main",
            "orari-telegram-bot = orari_agent.bot_runner:main",
            "",
        ]
    )


def _write_metadata_dir(path: Path) -> None:
    dist = path / DIST
    dist.mkdir(parents=True, exist_ok=True)
    (dist / "METADATA").write_text(_metadata())
    (dist / "WHEEL").write_text(_wheel())
    (dist / "entry_points.txt").write_text(_entry_points())


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    _write_metadata_dir(Path(metadata_directory))
    return DIST


def prepare_metadata_for_build_editable(metadata_directory, config_settings=None):
    return prepare_metadata_for_build_wheel(metadata_directory, config_settings)


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    return _build(wheel_directory, editable=False)


def build_editable(wheel_directory, config_settings=None, metadata_directory=None):
    return _build(wheel_directory, editable=True)


def _build(wheel_directory, *, editable: bool) -> str:
    wheel_name = f"orari_agent-{VERSION}-py3-none-any.whl"
    wheel_path = Path(wheel_directory) / wheel_name
    records: list[tuple[str, bytes]] = []
    if editable:
        src_path = (Path.cwd() / "src").resolve().as_posix()
        records.append(("orari_agent_editable.pth", f"{src_path}\n".encode()))
    else:
        for source in (Path.cwd() / "src" / "orari_agent").rglob("*.py"):
            arcname = source.relative_to(Path.cwd() / "src").as_posix()
            records.append((arcname, source.read_bytes()))
    records.extend(
        [
            (f"{DIST}/METADATA", _metadata().encode()),
            (f"{DIST}/WHEEL", _wheel().encode()),
            (f"{DIST}/entry_points.txt", _entry_points().encode()),
        ]
    )
    record_lines = []
    with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for arcname, data in records:
            info = zipfile.ZipInfo(arcname, time.gmtime()[:6])
            zf.writestr(info, data)
            digest = hashlib.sha256(data).digest()
            import base64

            b64 = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
            record_lines.append(f"{arcname},sha256={b64},{len(data)}")
        record_name = f"{DIST}/RECORD"
        record_lines.append(f"{record_name},,")
        zf.writestr(record_name, "\n".join(record_lines) + "\n")
    return wheel_name
