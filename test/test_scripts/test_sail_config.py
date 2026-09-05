# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import run_sail_iss_smoke as sail  # noqa: E402


def default_config():
    """A Sail default configuration reduced to the keys the driver rewrites."""
    io_attributes = {"mem_type": "IOMemory", "executable": False, "writable": True}
    ram_attributes = {
        "mem_type": "MainMemory",
        "executable": True,
        "writable": True,
        "misaligned_exceptions": {
            "load_store": {"None": None},
            "vector": {"None": None},
            "amo": "AccessFault",
        },
    }
    return {
        "base": {
            "xlen": 32,
            "E": False,
            "writable_misa": True,
            "mstatus": {"fs_legal_states": "ExtContext_FourState", "vs_legal_states": "ExtContext_FourState"},
        },
        "memory": {
            "dtb_address": {"len": 64, "value": "0x1000"},
            "misaligned": {"exceptions": {"load_store": {"None": None}}, "byte_by_byte": False},
            "regions": [
                {"base": {"len": 64, "value": "0x1000"}, "size": {"len": 64, "value": "0x1000"},
                 "attributes": io_attributes, "include_in_device_tree": False},
                {"base": {"len": 64, "value": "0x80000000"}, "size": {"len": 64, "value": "0x80000000"},
                 "attributes": ram_attributes, "include_in_device_tree": True},
            ],
        },
        "platform": {
            "clint": {"supported": True, "base": 0x0200_0000, "size": 0xC_0000},
            "simple_interrupt_generator": {"supported": True, "base": 0x0C00_0000},
            "wfi_is_nop": False,
        },
        "extensions": {
            "Zicsr": {"supported": False},
            "Zca": {"supported": False},
            "M": {"supported": True},
            "S": {"supported": True},
            "U": {"supported": True},
            "V": {"supported": True, "support_level": "Full"},
        },
    }


def build(monkeypatch, ram_base, clint_base, memory_size=0x0010_0000):
    monkeypatch.setattr(sail, "sail_default_config", lambda _cmd: default_config())
    return sail.make_sail_config("sail_riscv_sim", memory_size, ram_base, clint_base)


def test_strip_jsonc_drops_comment_lines():
    text = '// leading\n{\n  // inner\n  "a": 1\n}\n'
    assert json.loads(sail.strip_jsonc(text)) == {"a": 1}


def test_strip_jsonc_keeps_slashes_inside_values():
    text = '{\n  "path": "a//b"\n}\n'
    assert json.loads(sail.strip_jsonc(text))["path"] == "a//b"


def test_regions_ascend_when_ram_sits_above_the_clint(monkeypatch):
    config = build(monkeypatch, ram_base=0x8000_0000, clint_base=0x0200_0000)
    bases = [int(region["base"]["value"], 16) for region in config["memory"]["regions"]]
    assert bases == sorted(bases)


def test_regions_ascend_when_ram_sits_below_the_clint(monkeypatch):
    config = build(monkeypatch, ram_base=0x0, clint_base=0xA000_0000)
    bases = [int(region["base"]["value"], 16) for region in config["memory"]["regions"]]
    assert bases == sorted(bases)


def test_ram_region_takes_the_requested_map(monkeypatch):
    config = build(monkeypatch, ram_base=0x0, clint_base=0xA000_0000, memory_size=0x8010_0000)
    ram = next(r for r in config["memory"]["regions"] if r["attributes"]["mem_type"] == "MainMemory")
    assert (ram["base"]["value"], ram["size"]["value"]) == ("0x0", "0x80100000")


def test_device_tree_address_stays_inside_an_io_region(monkeypatch):
    config = build(monkeypatch, ram_base=0x0, clint_base=0xA000_0000)
    dtb = int(config["memory"]["dtb_address"]["value"], 16)
    io = next(r for r in config["memory"]["regions"] if r["attributes"]["mem_type"] == "IOMemory")
    start = int(io["base"]["value"], 16)
    assert start <= dtb < start + int(io["size"]["value"], 16)
    assert dtb >= config["platform"]["clint"]["base"] + config["platform"]["clint"]["size"]


def test_register_file_is_restricted_to_rv32e(monkeypatch):
    config = build(monkeypatch, ram_base=0x0, clint_base=0xA000_0000)
    assert config["base"]["E"] is True
    assert config["base"]["writable_misa"] is False


def test_only_zicsr_and_zca_are_supported(monkeypatch):
    config = build(monkeypatch, ram_base=0x0, clint_base=0xA000_0000)
    supported = {name for name, ext in config["extensions"].items() if ext["supported"]}
    assert supported == {"Zicsr", "Zca"}
    assert config["extensions"]["V"]["support_level"] == "Disabled"


def test_misaligned_access_traps_globally_and_per_region(monkeypatch):
    config = build(monkeypatch, ram_base=0x0, clint_base=0xA000_0000)
    assert config["memory"]["misaligned"]["exceptions"]["load_store"] == {"Some": "AlignmentException"}
    ram = next(r for r in config["memory"]["regions"] if r["attributes"]["mem_type"] == "MainMemory")
    assert ram["attributes"]["misaligned_exceptions"]["load_store"] == {"Some": "AlignmentException"}
    assert "lrsc" not in ram["attributes"]["misaligned_exceptions"]


def test_platform_matches_the_core(monkeypatch):
    config = build(monkeypatch, ram_base=0x0, clint_base=0xA000_0000)
    assert config["platform"]["clint"]["base"] == 0xA000_0000
    assert config["platform"]["wfi_is_nop"] is True
    assert config["platform"]["simple_interrupt_generator"]["supported"] is False
    assert config["base"]["mstatus"]["fs_legal_states"] == "ExtContext_Off"
    assert config["base"]["mstatus"]["vs_legal_states"] == "ExtContext_Off"


def test_the_two_regions_do_not_share_an_attributes_object(monkeypatch):
    config = build(monkeypatch, ram_base=0x0, clint_base=0xA000_0000)
    ram, mmio = config["memory"]["regions"]
    assert ram["attributes"] is not mmio["attributes"]
    assert ram["attributes"]["mem_type"] == "MainMemory"
    assert mmio["attributes"]["mem_type"] == "IOMemory"
