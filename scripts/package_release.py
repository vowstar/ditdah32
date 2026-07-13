#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

"""Build deterministic RTL release archives from audited Nix outputs."""

import argparse
import gzip
import hashlib
import json
import re
import shlex
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TAG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40,64}$")
TRACE_RE = re.compile(r"\b(?:rvfi|trace)_[A-Za-z0-9_]*\b")
PRIVATE_PATH_RES = (
    re.compile(r"@\["),
    re.compile(r"/(?:home|Users|build|nix/store|github/workspace)/"),
    re.compile(r"[A-Za-z]:\\(?:Users|build)\\"),
)


class ReleaseError(RuntimeError):
    pass


@dataclass(frozen=True)
class Variant:
    directory: str
    suffix: str
    enable_jtag: bool
    required_rtl: tuple[str, ...]


VARIANTS = (
    Variant("standard", "", False, ("DitDah32.sv",)),
    Variant(
        "jtag",
        "-jtag",
        True,
        ("DitDah32.sv", "DitDah32DebugModule.sv", "DitDah32JtagDtm.sv"),
    ),
)


def is_u32(value):
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value <= 0xFFFFFFFF
    )


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReleaseError(f"missing file: {path.name}") from exc
    except json.JSONDecodeError as exc:
        raise ReleaseError(f"invalid JSON in {path.name}: {exc}") from exc


def read_filelist(variant_dir):
    path = variant_dir / "filelist.f"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise ReleaseError(f"missing file: {path.name}") from exc

    entries = []
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        fields = shlex.split(line)
        if len(fields) != 1:
            raise ReleaseError(f"filelist.f:{line_number} must contain one path")
        entry = Path(fields[0])
        if entry.is_absolute() or ".." in entry.parts or entry.suffix != ".sv":
            raise ReleaseError(f"unsafe RTL path in filelist.f: {entry}")
        if entry.name.endswith("_DV.sv") or entry.name.startswith(("layers-", "ref_")):
            raise ReleaseError(f"verification collateral is not releasable: {entry}")
        if entry in entries:
            raise ReleaseError(f"duplicate RTL path in filelist.f: {entry}")
        entries.append(entry)

    if not entries:
        raise ReleaseError("filelist.f contains no RTL files")
    return entries


def audit_text(path, text):
    if TRACE_RE.search(text):
        raise ReleaseError(f"trace collateral is not releasable: {path.name}")
    for pattern in PRIVATE_PATH_RES:
        if pattern.search(text):
            raise ReleaseError(f"source path leaked into release input: {path.name}")


def audit_variant(input_dir, variant):
    variant_dir = (input_dir / variant.directory).resolve()
    if not variant_dir.is_dir():
        raise ReleaseError(f"missing release variant: {variant.directory}")

    config_path = variant_dir / "ditdah32_config.json"
    config = read_json(config_path)
    required_config = {"enableTrace": False, "enableJtag": variant.enable_jtag}
    for key, expected in required_config.items():
        if config.get(key) != expected:
            raise ReleaseError(
                f"{variant.directory} config {key} is {config.get(key)!r}, expected {expected!r}"
            )
    reset_vector = config.get("resetVector")
    if not is_u32(reset_vector):
        raise ReleaseError(f"{variant.directory} config resetVector is invalid")
    jtag_idcode = config.get("jtagIdcode")
    if not is_u32(jtag_idcode):
        raise ReleaseError(f"{variant.directory} config jtagIdcode is invalid")

    rtl_entries = read_filelist(variant_dir)
    rtl_names = {entry.as_posix() for entry in rtl_entries}
    missing_rtl = sorted(set(variant.required_rtl) - rtl_names)
    if missing_rtl:
        raise ReleaseError(
            f"{variant.directory} filelist is missing: {', '.join(missing_rtl)}"
        )
    unexpected_debug = sorted(
        {"DitDah32DebugModule.sv", "DitDah32JtagDtm.sv"} & rtl_names
    )
    if not variant.enable_jtag and unexpected_debug:
        raise ReleaseError(
            f"standard filelist contains JTAG RTL: {', '.join(unexpected_debug)}"
        )

    for entry in rtl_entries:
        path = (variant_dir / entry).resolve()
        try:
            path.relative_to(variant_dir)
        except ValueError as exc:
            raise ReleaseError(f"RTL path escapes variant directory: {entry}") from exc
        if not path.is_file():
            raise ReleaseError(f"missing RTL file: {entry}")
        audit_text(path, path.read_text(encoding="utf-8"))

    audit_text(config_path, config_path.read_text(encoding="utf-8"))
    return variant_dir, config, rtl_entries


def manifest_files(root, paths):
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": sha256(path),
            "size": path.stat().st_size,
        }
        for path in sorted(paths, key=lambda item: item.relative_to(root).as_posix())
    ]


def write_archive(root, archive_path, epoch):
    with archive_path.open("wb") as raw_file:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            compresslevel=9,
            fileobj=raw_file,
            mtime=epoch,
        ) as gzip_file:
            with tarfile.open(
                fileobj=gzip_file, mode="w", format=tarfile.USTAR_FORMAT
            ) as archive:
                paths = [
                    root,
                    *sorted(
                        root.rglob("*"),
                        key=lambda path: path.relative_to(root).as_posix(),
                    ),
                ]
                for path in paths:
                    arcname = Path(root.name) / path.relative_to(root)
                    info = archive.gettarinfo(str(path), arcname.as_posix())
                    info.uid = 0
                    info.gid = 0
                    info.uname = "root"
                    info.gname = "root"
                    info.mtime = epoch
                    info.mode = 0o755 if path.is_dir() else 0o644
                    if path.is_file():
                        with path.open("rb") as source:
                            archive.addfile(info, source)
                    else:
                        archive.addfile(info)


def stage_variant(input_dir, output_dir, license_path, tag, commit, epoch, variant):
    variant_dir, config, rtl_entries = audit_variant(input_dir, variant)
    asset_stem = f"ditdah32-{tag}{variant.suffix}"
    archive_path = output_dir / f"{asset_stem}.tar.gz"

    with tempfile.TemporaryDirectory(prefix="ditdah32-release-") as temporary:
        root = Path(temporary) / asset_stem
        root.mkdir()
        copied = []
        for entry in rtl_entries:
            destination = root / entry
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((variant_dir / entry).read_bytes())
            copied.append(destination)

        filelist_path = root / "filelist.f"
        filelist_path.write_text(
            "".join(f"{entry.as_posix()}\n" for entry in rtl_entries),
            encoding="utf-8",
        )
        copied.append(filelist_path)

        config_path = root / "ditdah32_config.json"
        config_path.write_text(
            json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        copied.append(config_path)

        license_destination = root / "LICENSE"
        license_destination.write_bytes(license_path.read_bytes())
        copied.append(license_destination)

        manifest = {
            "commit": commit,
            "configuration": config,
            "files": manifest_files(root, copied),
            "license": "MIT",
            "release": tag,
            "rtl_filelist": [entry.as_posix() for entry in rtl_entries],
            "schema_version": 1,
            "variant": variant.directory,
        }
        manifest_path = root / "MANIFEST.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        write_archive(root, archive_path, epoch)
    return archive_path


def verify_archive(archive_path):
    with tempfile.TemporaryDirectory(prefix="ditdah32-release-check-") as temporary:
        temporary_path = Path(temporary)
        with tarfile.open(archive_path, mode="r:gz") as archive:
            archive.extractall(temporary_path, filter="data")
        root = temporary_path / archive_path.name.removesuffix(".tar.gz")
        commands = (
            [
                "iverilog",
                "-g2012",
                "-s",
                "DitDah32",
                "-o",
                str(temporary_path / "rtl.vvp"),
                "-f",
                "filelist.f",
            ],
            [
                "verilator",
                "--lint-only",
                "--timing",
                "-Wno-fatal",
                "--top-module",
                "DitDah32",
                "--Mdir",
                str(temporary_path / "obj_dir"),
                "-f",
                "filelist.f",
            ],
        )
        for command in commands:
            try:
                completed = subprocess.run(
                    command,
                    cwd=root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    check=False,
                )
            except FileNotFoundError as exc:
                raise ReleaseError(
                    f"required verification tool is missing: {command[0]}"
                ) from exc
            if completed.returncode != 0:
                output = completed.stdout[-4000:].strip()
                raise ReleaseError(
                    f"{command[0]} rejected {archive_path.name}:\n{output}"
                )


def package_release(
    input_dir, output_dir, license_path, tag, commit, epoch, verify=False
):
    if not TAG_RE.fullmatch(tag):
        raise ReleaseError(f"invalid release tag: {tag}")
    if not COMMIT_RE.fullmatch(commit):
        raise ReleaseError(f"invalid commit digest: {commit}")
    if epoch < 0 or epoch > 0xFFFFFFFF:
        raise ReleaseError(f"invalid source date epoch: {epoch}")
    if not license_path.is_file():
        raise ReleaseError(f"missing license: {license_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="ditdah32-release-output-", dir=output_dir.parent
    ) as temporary:
        temporary_output = Path(temporary)
        temporary_archives = [
            stage_variant(
                input_dir,
                temporary_output,
                license_path,
                tag,
                commit,
                epoch,
                variant,
            )
            for variant in VARIANTS
        ]

        if verify:
            for archive_path in temporary_archives:
                verify_archive(archive_path)

        temporary_checksum = temporary_output / "SHA256SUMS"
        temporary_checksum.write_text(
            "".join(f"{sha256(path)}  {path.name}\n" for path in temporary_archives),
            encoding="utf-8",
        )

        archives = []
        for temporary_archive in temporary_archives:
            destination = output_dir / temporary_archive.name
            temporary_archive.replace(destination)
            archives.append(destination)
        checksum_path = output_dir / temporary_checksum.name
        temporary_checksum.replace(checksum_path)
    return archives, checksum_path


def git_output(*args):
    completed = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ReleaseError(completed.stderr.strip() or "git command failed")
    return completed.stdout.strip()


def main():
    parser = argparse.ArgumentParser(
        description="Package standard and JTAG RTL release archives"
    )
    parser.add_argument("--tag", required=True)
    parser.add_argument("--commit")
    parser.add_argument("--source-date-epoch", type=int)
    parser.add_argument(
        "--input-dir", type=Path, default=REPO_ROOT / "result" / "release-inputs"
    )
    parser.add_argument(
        "--out-dir", type=Path, default=REPO_ROOT / "result" / "release"
    )
    parser.add_argument("--license", type=Path, default=REPO_ROOT / "LICENSE")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    try:
        commit = args.commit or git_output("rev-parse", "HEAD")
        epoch = args.source_date_epoch
        if epoch is None:
            epoch = int(git_output("show", "-s", "--format=%ct", commit))
        archives, checksum_path = package_release(
            args.input_dir.resolve(),
            args.out_dir.resolve(),
            args.license.resolve(),
            args.tag,
            commit,
            epoch,
            verify=args.verify,
        )
    except (ReleaseError, ValueError) as exc:
        print(f"release package error: {exc}", file=sys.stderr)
        return 1

    for path in [*archives, checksum_path]:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
