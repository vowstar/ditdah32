# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import json
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import package_release  # noqa: E402

TAG = "v1.2.3"
COMMIT = "a" * 40
EPOCH = 1_700_000_000


def write_variant(root, name, enable_jtag, trace=False, leaked_path=False):
    variant = root / name
    variant.mkdir(parents=True)
    config = {
        "enableJtag": enable_jtag,
        "enableTrace": trace,
        "jtagIdcode": 1,
        "resetVector": 0,
    }
    (variant / "ditdah32_config.json").write_text(json.dumps(config), encoding="utf-8")
    files = ["DitDah32.sv"]
    if enable_jtag:
        files.extend(["DitDah32DebugModule.sv", "DitDah32JtagDtm.sv"])
    (variant / "filelist.f").write_text("\n".join(files) + "\n", encoding="utf-8")
    for filename in files:
        module = Path(filename).stem
        location = " // @[/source/DitDah32.scala:1]" if leaked_path else ""
        (variant / filename).write_text(
            f"module {module};{location}\nendmodule\n", encoding="utf-8"
        )
    (variant / "DitDah32_DV.sv").write_text(
        "module DitDah32_DV; endmodule\n", encoding="utf-8"
    )
    (variant / "DitDah32.dd").write_text("debug metadata\n", encoding="utf-8")


def release_fixture(tmp_path):
    input_dir = tmp_path / "inputs"
    write_variant(input_dir, "standard", False)
    write_variant(input_dir, "jtag", True)
    license_path = tmp_path / "LICENSE"
    license_path.write_text("MIT License\n", encoding="utf-8")
    return input_dir, license_path


def package(tmp_path, output_name="release"):
    input_dir, license_path = release_fixture(tmp_path)
    return package_release.package_release(
        input_dir,
        tmp_path / output_name,
        license_path,
        TAG,
        COMMIT,
        EPOCH,
    )


def test_package_release_builds_two_named_archives(tmp_path):
    archives, checksum_path = package(tmp_path)

    assert [path.name for path in archives] == [
        "ditdah32-v1.2.3.tar.gz",
        "ditdah32-v1.2.3-jtag.tar.gz",
    ]
    checksum_names = [
        line.split()[1]
        for line in checksum_path.read_text(encoding="utf-8").splitlines()
    ]
    assert checksum_names == [
        "ditdah32-v1.2.3.tar.gz",
        "ditdah32-v1.2.3-jtag.tar.gz",
    ]

    with tarfile.open(archives[0], "r:gz") as archive:
        names = set(archive.getnames())
        root = "ditdah32-v1.2.3"
        assert f"{root}/DitDah32.sv" in names
        assert f"{root}/MANIFEST.json" in names
        assert f"{root}/DitDah32_DV.sv" not in names
        assert f"{root}/DitDah32.dd" not in names
        manifest = json.load(archive.extractfile(f"{root}/MANIFEST.json"))
        assert manifest["variant"] == "standard"
        assert manifest["configuration"]["enableTrace"] is False
        assert manifest["configuration"]["enableJtag"] is False

    with tarfile.open(archives[1], "r:gz") as archive:
        names = set(archive.getnames())
        root = "ditdah32-v1.2.3-jtag"
        assert f"{root}/DitDah32DebugModule.sv" in names
        assert f"{root}/DitDah32JtagDtm.sv" in names
        manifest = json.load(archive.extractfile(f"{root}/MANIFEST.json"))
        assert manifest["variant"] == "jtag"
        assert manifest["configuration"]["enableJtag"] is True


def test_package_release_is_deterministic(tmp_path):
    input_dir, license_path = release_fixture(tmp_path)
    first, _ = package_release.package_release(
        input_dir, tmp_path / "first", license_path, TAG, COMMIT, EPOCH
    )
    second, _ = package_release.package_release(
        input_dir, tmp_path / "second", license_path, TAG, COMMIT, EPOCH
    )

    assert [path.read_bytes() for path in first] == [
        path.read_bytes() for path in second
    ]


def test_package_release_rejects_trace_configuration(tmp_path):
    input_dir, license_path = release_fixture(tmp_path)
    config_path = input_dir / "standard" / "ditdah32_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["enableTrace"] = True
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(package_release.ReleaseError, match="enableTrace"):
        package_release.package_release(
            input_dir, tmp_path / "release", license_path, TAG, COMMIT, EPOCH
        )


def test_package_release_rejects_source_locations(tmp_path):
    input_dir, license_path = release_fixture(tmp_path)
    rtl_path = input_dir / "standard" / "DitDah32.sv"
    rtl_path.write_text(
        "module DitDah32; // @[/source/DitDah32.scala:1]\nendmodule\n",
        encoding="utf-8",
    )

    with pytest.raises(package_release.ReleaseError, match="source path leaked"):
        package_release.package_release(
            input_dir, tmp_path / "release", license_path, TAG, COMMIT, EPOCH
        )


def test_package_release_rejects_verification_collateral(tmp_path):
    input_dir, license_path = release_fixture(tmp_path)
    (input_dir / "standard" / "filelist.f").write_text(
        "DitDah32.sv\nDitDah32_DV.sv\n", encoding="utf-8"
    )

    with pytest.raises(package_release.ReleaseError, match="verification collateral"):
        package_release.package_release(
            input_dir, tmp_path / "release", license_path, TAG, COMMIT, EPOCH
        )


def test_package_release_rejects_jtag_rtl_in_standard_archive(tmp_path):
    input_dir, license_path = release_fixture(tmp_path)
    (input_dir / "standard" / "filelist.f").write_text(
        "DitDah32.sv\nDitDah32JtagDtm.sv\n", encoding="utf-8"
    )
    (input_dir / "standard" / "DitDah32JtagDtm.sv").write_text(
        "module DitDah32JtagDtm; endmodule\n", encoding="utf-8"
    )

    with pytest.raises(
        package_release.ReleaseError, match="standard filelist contains JTAG RTL"
    ):
        package_release.package_release(
            input_dir, tmp_path / "release", license_path, TAG, COMMIT, EPOCH
        )


def test_package_release_rejects_incomplete_jtag_filelist(tmp_path):
    input_dir, license_path = release_fixture(tmp_path)
    (input_dir / "jtag" / "filelist.f").write_text(
        "DitDah32.sv\nDitDah32DebugModule.sv\n", encoding="utf-8"
    )

    with pytest.raises(package_release.ReleaseError, match="DitDah32JtagDtm.sv"):
        package_release.package_release(
            input_dir, tmp_path / "release", license_path, TAG, COMMIT, EPOCH
        )


def test_failed_repackage_preserves_previous_assets(tmp_path):
    input_dir, license_path = release_fixture(tmp_path)
    output_dir = tmp_path / "release"
    archives, checksum_path = package_release.package_release(
        input_dir, output_dir, license_path, TAG, COMMIT, EPOCH
    )
    previous = {path.name: path.read_bytes() for path in [*archives, checksum_path]}

    config_path = input_dir / "jtag" / "ditdah32_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["enableTrace"] = True
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(package_release.ReleaseError, match="enableTrace"):
        package_release.package_release(
            input_dir, output_dir, license_path, TAG, COMMIT, EPOCH
        )
    assert {path.name: path.read_bytes() for path in output_dir.iterdir()} == previous
