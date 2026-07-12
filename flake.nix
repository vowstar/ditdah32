# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT
{
  description = "DitDah32 tiny two-stage RV32EC core using zaozi EDSL";

  inputs = {
    zaozi.url = "github:sequencer/zaozi";
    nixpkgs.follows = "zaozi/nixpkgs";
    flake-utils.follows = "zaozi/flake-utils";
    riscv-dv = {
      url = "github:google/riscv-dv/b7a0b4b0b51346a3c64f159f81ea262d867c14a9";
      flake = false;
    };
    riscv-formal = {
      url = "github:YosysHQ/riscv-formal/2aa7b4934190baeb2ef62b2de414f104b489d3cc";
      flake = false;
    };
  };

  outputs = { self, nixpkgs, flake-utils, zaozi, riscv-dv, riscv-formal }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgsBase = zaozi.legacyPackages.${system};
        scalaIvyCache = pkgsBase.ivy-gather ./nix/zaozi-lock.nix;
        pkgs = pkgsBase.extend (final: prev: {
          zaozi = prev.zaozi // {
            zaozi-assembly = prev.zaozi.zaozi-assembly.overrideAttrs (old: {
              # Zaozi rev 19de5b5 ships an offline Mill lock generated for Mill
              # 1.0.0, but the followed nixpkgs ships Mill 1.1.2, whose launcher
              # coursier-fetches mill-runner-daemon_3-1.1.2 at startup. Use the
              # full source tree (its packaged fileset omits testlib/) and swap
              # in a vendored lock regenerated against 1.1.2.
              src = zaozi.outPath;

              prePatch = ''
                cp ${./nix/zaozi-lock.nix} nix/zaozi/zaozi-lock.nix
              '';

              # --offline is load-bearing: future Mill skew fails loudly instead
              # of silently reaching the network and breaking sealed CI.
              buildPhase = ''
                runHook preBuild
                mill --no-daemon --offline '__.assembly'
                runHook postBuild
              '';

              # Replace the upstream offline ivy cache (built from the 1.0.0
              # lock) with one gathered from the vendored 1.1.2 lock; without
              # this --offline cannot find mill-runner-daemon_3-1.1.2.
              buildInputs =
                builtins.filter
                  (pkg: (pkg.name or "") != "build-ivy-cache-env")
                  (old.buildInputs or [])
                ++ [ scalaIvyCache ];

              # The assembly target does not use espresso, and keeping it in
              # nativeBuildInputs makes fresh CI runners fetch an unrelated
              # fixed-output source before any DitDah32 smoke test can run.
              nativeBuildInputs = builtins.filter
                (pkg: (pkg.pname or pkg.name or "") != "espresso")
                (old.nativeBuildInputs or []);
            });
          };
        });

        ditdah32Config = {
          resetVector = 0;
          enableTrace = false;
          enableJtag = false;
          jtagIdcode = 1;
        };

        # yosys-slang frontend, statically linked against vendored slang/fmt.
        # Provides read_slang so the formal flow can resolve CIRCT layer-bound
        # DV probe XMRs in the generated DitDah32.sv.
        yosys-slang = pkgs.stdenv.mkDerivation {
          pname = "yosys-slang";
          version = "3251530";
          src = pkgs.fetchgit {
            url = "https://github.com/povik/yosys-slang";
            rev = "3251530961e0e8a8054098c9bb8376474958944a";
            fetchSubmodules = true;
            hash = "sha256-e3DPddB5dQeA7EvUxO5wl7GwhI6bSoAulADl2MDIk70=";
          };
          nativeBuildInputs = [ pkgs.cmake pkgs.pkg-config pkgs.python3 ];
          buildInputs = [ pkgs.yosys ];
          dontUseCmakeConfigure = true;
          buildPhase = ''
            runHook preBuild
            cmake -S . -B build \
              -DYOSYS_CONFIG=${pkgs.yosys}/bin/yosys-config \
              -DCMAKE_BUILD_TYPE=Release \
              -DSLANG_INCLUDE_TESTS=OFF \
              -DSLANG_USE_CPPTRACE=OFF \
              -DBUILD_TESTING=OFF
            cmake --build build -j$NIX_BUILD_CORES
            runHook postBuild
          '';
          installPhase = ''
            runHook preInstall
            mkdir -p $out/lib
            cp build/slang.so $out/lib/slang.so
            runHook postInstall
          '';
        };
        slangSo = "${yosys-slang}/lib/slang.so";

        zaozi-jar = "${pkgs.zaozi.zaozi-assembly}/share/java/elaborator.jar";
        javaLibraryPath = "${pkgs.circt-install}/lib:${pkgs.mlir-install}/lib";

        commonScalaArgs = pkgs.lib.escapeShellArgs [
          "--server=false"
          "--extra-jars" zaozi-jar
          "--scala-version" "3.6.2"
          "-O=-experimental"
          "--java-opt" "--enable-native-access=ALL-UNNAMED"
          "--java-opt" "--enable-preview"
          "--java-opt" "-Djava.library.path=${javaLibraryPath}"
        ];

        firtoolArgs = pkgs.lib.escapeShellArgs [
          "--split-verilog"
          "-disable-all-randomization"
          "-g"
          "--emit-hgldd"
          "--lowering-options=noAlwaysComb,disallowLocalVariables,disallowPackedArrays,emittedLineLength=160,verifLabels,explicitBitcast,locationInfoStyle=wrapInAtSquareBracket,maximumNumberOfTermsPerExpression=24,disallowExpressionInliningInPorts,caseInsensitiveKeywords"
        ];

        pythonEnv = pkgs.python3.withPackages (ps:
          let
            pythonJsonschemaObjects = ps.buildPythonPackage rec {
              pname = "python-jsonschema-objects";
              version = "0.5.7";
              format = "wheel";
              src = pkgs.fetchurl {
                url = "https://files.pythonhosted.org/packages/5f/c8/8687dcf8cd09b8c76da19ce96cd6cdfe10fba042d3bfdd9f002462fadcf5/python_jsonschema_objects-${version}-py2.py3-none-any.whl";
                hash = "sha256-W0W353bLnMhiVnIeECQA2i/pICH4qVZqVwwdChXEBl0=";
              };
              propagatedBuildInputs = [
                ps.inflection
                ps.markdown
                ps.jsonschema
              ];
              doCheck = false;
            };
            pyboolector = ps.buildPythonPackage rec {
              pname = "pyboolector";
              version = "3.2.4.19342042739";
              format = "wheel";
              src = pkgs.fetchurl {
                url = "https://files.pythonhosted.org/packages/f1/41/1352b6495268d39d77e6d2c672f05253429e63fc7d8a2266c1cab024a56a/pyboolector-${version}-cp313-cp313-manylinux_2_34_x86_64.whl";
                hash = "sha256-p4X8G4CfXECEar3zkUuwbg5EdpMhzzAyNCOZ17fX6zE=";
              };
              nativeBuildInputs = [ pkgs.autoPatchelfHook ];
              buildInputs = [ pkgs.stdenv.cc.cc.lib ];
              doCheck = false;
            };
            pyucis = ps.buildPythonPackage rec {
              pname = "pyucis";
              version = "0.1.4";
              format = "wheel";
              src = pkgs.fetchurl {
                url = "https://files.pythonhosted.org/packages/4f/e8/5a97731f2eef2a1fcda1927411611684859bd3a62a654c73ed0f67c91ba7/pyucis-${version}-py2.py3-none-any.whl";
                hash = "sha256-d7+j7U6sipjZyDXLaRukypCmI3XIlkIkCdFmZWwlUqA=";
              };
              propagatedBuildInputs = [
                ps.lxml
                pythonJsonschemaObjects
                ps.jsonschema
                ps.pyyaml
                ps.mcp
              ];
              doCheck = false;
            };
            pyvsc = ps.buildPythonPackage rec {
              pname = "pyvsc";
              version = "0.9.4.25837897616";
              format = "wheel";
              src = pkgs.fetchurl {
                url = "https://files.pythonhosted.org/packages/1e/2d/288b98263cb8b86194ce75ad8ab823521f21462c28af1c168c29f76b74e2/pyvsc-${version}-py2.py3-none-any.whl";
                hash = "sha256-koKJ+CP2ct2TBm7OrhbF44gzG6gOos8mqo9y55PvODY=";
              };
              propagatedBuildInputs = [
                pyboolector
                pyucis
                ps.toposort
              ];
              doCheck = false;
            };
          in with ps; [
            bitstring
            cocotb
            pandas
            pytest
            pyvsc
            pyyaml
            tabulate
          ]);

        buildScript = pkgs.writeShellScriptBin "build-ditdah32" ''
          set -euo pipefail

          JAVA_LIBRARY_PATH="${javaLibraryPath}"
          OUTPUT_DIR="''${OUTPUT_DIR:-$PWD/result}"
          ENABLE_TRACE="''${DITDAH32_ENABLE_TRACE:-${if ditdah32Config.enableTrace then "true" else "false"}}"
          ENABLE_JTAG="''${DITDAH32_ENABLE_JTAG:-${if ditdah32Config.enableJtag then "true" else "false"}}"

          while [ "$#" -gt 0 ]; do
            case "$1" in
              --trace)
                ENABLE_TRACE=true
                ;;
              --no-trace)
                ENABLE_TRACE=false
                ;;
              --jtag)
                ENABLE_JTAG=true
                ;;
              --no-jtag)
                ENABLE_JTAG=false
                ;;
              --help)
                cat <<'EOF'
Usage: build-ditdah32 [--trace|--no-trace] [--jtag|--no-jtag]

Generate DitDah32 Verilog into OUTPUT_DIR, defaulting to ./result.
The default production build omits architectural trace ports. Use --trace
or DITDAH32_ENABLE_TRACE=1 for RTL simulation, trace comparison, and RVFI.
The default build omits JTAG ports and debug logic. Use --jtag or
DITDAH32_ENABLE_JTAG=1 to generate the optional debug configuration.
EOF
                exit 0
                ;;
              *)
                echo "unknown build-ditdah32 option: $1" >&2
                exit 2
                ;;
            esac
            shift
          done

          case "$ENABLE_TRACE" in
            1|true|TRUE|yes|YES|on|ON)
              ENABLE_TRACE=true
              ;;
            0|false|FALSE|no|NO|off|OFF)
              ENABLE_TRACE=false
              ;;
            *)
              echo "invalid DITDAH32_ENABLE_TRACE value: $ENABLE_TRACE" >&2
              exit 2
              ;;
          esac

          case "$ENABLE_JTAG" in
            1|true|TRUE|yes|YES|on|ON)
              ENABLE_JTAG=true
              ;;
            0|false|FALSE|no|NO|off|OFF)
              ENABLE_JTAG=false
              ;;
            *)
              echo "invalid DITDAH32_ENABLE_JTAG value: $ENABLE_JTAG" >&2
              exit 2
              ;;
          esac

          mkdir -p "$OUTPUT_DIR"
          OUTPUT_DIR=$(realpath "$OUTPUT_DIR")

          echo "=== Building DitDah32 with zaozi ==="
          echo "OUTPUT_DIR: $OUTPUT_DIR"
          echo "ENABLE_TRACE: $ENABLE_TRACE"
          echo "ENABLE_JTAG: $ENABLE_JTAG"

          rm -f DitDah32*.mlirbc

          scala-cli run \
            ${commonScalaArgs} \
            --main-class com.vowstar.ditdah32.DitDah32Module \
            ditdah32/src \
            -- config "$OUTPUT_DIR/ditdah32_config.json" \
            --resetVector ${toString ditdah32Config.resetVector} \
            --enableTrace "$ENABLE_TRACE" \
            --enableJtag "$ENABLE_JTAG" \
            --jtagIdcode ${toString ditdah32Config.jtagIdcode}

          scala-cli run \
            ${commonScalaArgs} \
            --main-class com.vowstar.ditdah32.DitDah32Module \
            ditdah32/src \
            -- design "$OUTPUT_DIR/ditdah32_config.json"

          MLIRBC_FILE=$(ls DitDah32.mlirbc 2>/dev/null | head -1)

          if [ -z "$MLIRBC_FILE" ]; then
            echo "Error: no DitDah32 .mlirbc file generated"
            exit 1
          fi

          ${pkgs.circt-install}/bin/firld DitDah32*.mlirbc \
            --base-circuit DitDah32 \
            --no-mangle \
            --emit-bytecode \
            -o DitDah32-linked.mlirbc

          ${pkgs.circt-install}/bin/firtool DitDah32-linked.mlirbc \
            ${firtoolArgs} \
            --hgldd-output-dir="$OUTPUT_DIR" \
            -o "$OUTPUT_DIR"

          rm -f DitDah32*.mlirbc

          # The DV trace surface always lowers to separate layer("DV") bind
          # collateral, never into the DitDah32 main module. The production
          # (--no-trace) deliverable is the lone trace-free core; verification
          # (--trace) keeps the bind collateral for cocotb and the formal flow.
          if [ "$ENABLE_TRACE" != "true" ]; then
            rm -f "$OUTPUT_DIR"/DitDah32_DV.sv \
                  "$OUTPUT_DIR"/layers-DitDah32-DV.sv \
                  "$OUTPUT_DIR"/ref_DitDah32.sv \
                  "$OUTPUT_DIR"/DitDah32_DV.dd
            if [ -f "$OUTPUT_DIR"/filelist.f ]; then
              ${pkgs.gnugrep}/bin/grep -v -e DitDah32_DV.sv -e layers-DitDah32-DV.sv \
                "$OUTPUT_DIR"/filelist.f > "$OUTPUT_DIR"/filelist.f.tmp \
                && mv "$OUTPUT_DIR"/filelist.f.tmp "$OUTPUT_DIR"/filelist.f || true
            fi
          fi

          echo "=== Verilog generated in: $OUTPUT_DIR ==="
        '';

        riscvDvPythonCompat = pkgs.runCommand "riscv-dv-python-compat" { } ''
          mkdir -p "$out"
          cat > "$out/imp.py" <<'PY'
from importlib import reload
PY
        '';

        riscvDvScript = pkgs.writeShellScriptBin "riscv-dv" ''
          set -euo pipefail
          if [ "''${1:-}" = "--path" ]; then
            echo "${riscv-dv}"
            exit 0
          fi
          if [ "''${1:-}" = "--version" ]; then
            echo "riscv-dv b7a0b4b0b51346a3c64f159f81ea262d867c14a9"
            exit 0
          fi
          export PYTHONDONTWRITEBYTECODE=1
          export PYTHONPATH="$PWD/test/riscv_dv/pygen_overlay:${riscvDvPythonCompat}:${riscv-dv}/pygen:''${PYTHONPATH:-}"
          exec ${pythonEnv}/bin/python3 ${riscv-dv}/run.py "$@"
        '';

        riscvDvRunPyScript = pkgs.writeShellScriptBin "run.py" ''
          set -euo pipefail
          exec ${riscvDvScript}/bin/riscv-dv "$@"
        '';

        riscvFormalScript = pkgs.writeShellScriptBin "riscv-formal" ''
          set -euo pipefail
          if [ "''${1:-}" = "--path" ]; then
            echo "${riscv-formal}"
            exit 0
          fi
          if [ "''${1:-}" = "--version" ]; then
            echo "riscv-formal 2aa7b4934190baeb2ef62b2de414f104b489d3cc"
            exit 0
          fi
          if [ "''${1:-}" = "--help" ] || [ "$#" -eq 0 ]; then
            cat <<'EOF'
Usage: riscv-formal --path
       riscv-formal --version
       riscv-formal genchecks [args...]

Wrapper for the pinned YosysHQ/riscv-formal source tree in this dev shell.
EOF
            exit 0
          fi
          if [ "$1" = "genchecks" ]; then
            shift
            exec ${pythonEnv}/bin/python3 ${riscv-formal}/checks/genchecks.py "$@"
          fi
          echo "unknown riscv-formal wrapper command: $1" >&2
          exit 2
        '';

        rtlShellEnv = {
          CIRCT_INSTALL_PATH = pkgs.circt-install;
          MLIR_INSTALL_PATH = pkgs.mlir-install;
          JEXTRACT_INSTALL_PATH = pkgs.jextract-21;
          JAVA_TOOL_OPTIONS = "--enable-preview -Djextract.decls.per.header=65535";
          RISCV_PREFIX = "riscv32-none-elf-";
          ZAOZI_JAR = zaozi-jar;
        };

        rtlShellHook = ''
          export PATH="${pythonEnv}/bin:${pkgs.pkgsCross.riscv32-embedded.stdenv.cc}/bin:${pkgs.pkgsCross.riscv32-embedded.buildPackages.binutils}/bin:$PATH"
          echo "========================================"
          echo "DitDah32 Zaozi Development Environment"
          echo "========================================"
          echo "Build Verilog:  build-ditdah32"
          echo "Run tests:      cd test/test_ditdah32 && make"
          echo "========================================"
        '';

        mkRtlShell = buildInputs: extraEnv: pkgs.mkShell {
          inherit buildInputs;
          env = rtlShellEnv // extraEnv;
          shellHook = rtlShellHook;
        };

        smokeBuildInputs = [
          buildScript
          pkgs.scala-cli
          pkgs.circt-install
          pkgs.mlir-install
          pkgs.jextract-21
          pkgs.pkgsCross.riscv32-embedded.stdenv.cc
          pkgs.pkgsCross.riscv32-embedded.buildPackages.binutils
          pythonEnv
        ];

        fullBuildInputs = smokeBuildInputs ++ [
          pkgs.iverilog
          pkgs.openocd
          pkgs.pkgsCross.riscv32-embedded.buildPackages.gdb
          pkgs.verilator
          pkgs.yosys
          yosys-slang
          pkgs.z3
        ];

        ciEvidenceBuildInputs = [
          pkgs.gh
          pythonEnv
        ];

        defaultBuildInputs = [
          buildScript
          riscvDvScript
          riscvDvRunPyScript
          riscvFormalScript
          pkgs.scala-cli
          pkgs.circt-install
          pkgs.mlir-install
          pkgs.jextract-21
          pkgs.mill
          pkgs.iverilog
          pkgs.openocd
          pkgs.pkgsCross.riscv32-embedded.buildPackages.gdb
          pkgs.verilator
          pkgs.yosys
          yosys-slang
          pkgs.z3
          pkgs.spike
          pkgs.sail-riscv
          pkgs.pkgsCross.riscv32-embedded.stdenv.cc
          pkgs.pkgsCross.riscv32-embedded.buildPackages.binutils
          pythonEnv
        ];

        scoreScript = pkgs.writeShellApplication {
          name = "score-ditdah32";
          runtimeInputs = [
            buildScript
            pkgs.scala-cli
            pkgs.circt-install
            pkgs.mlir-install
            pkgs.jextract-21
            pkgs.pkgsCross.riscv32-embedded.stdenv.cc
            pkgs.pkgsCross.riscv32-embedded.buildPackages.binutils
            pkgs.verilator
            pythonEnv
          ];
          text = ''
            build-ditdah32 --no-trace
            python3 scripts/run_bench_sim.py "$@"
          '';
        };
      in
      {
        packages.default = pkgs.runCommand "ditdah32-verilog" {
          nativeBuildInputs = [ pkgs.scala-cli pkgs.circt-install pkgs.mlir-install ];
          JAVA_TOOL_OPTIONS = "--enable-preview";
        } ''
          mkdir -p $out
          cp -R ${./ditdah32/src} source
          chmod -R u+w source
          cd source

          JAVA_LIBRARY_PATH="${javaLibraryPath}"
          export COURSIER_CACHE="$NIX_BUILD_TOP/coursier-cache"
          cp -R ${scalaIvyCache}/cache "$COURSIER_CACHE"
          chmod -R u+w "$COURSIER_CACHE"

          rm -f DitDah32*.mlirbc

          scala-cli run \
            --power \
            --offline \
            ${commonScalaArgs} \
            --main-class com.vowstar.ditdah32.DitDah32Module \
            . \
            -- config "$out/ditdah32_config.json" \
            --resetVector ${toString ditdah32Config.resetVector} \
            --enableTrace ${if ditdah32Config.enableTrace then "true" else "false"} \
            --enableJtag ${if ditdah32Config.enableJtag then "true" else "false"} \
            --jtagIdcode ${toString ditdah32Config.jtagIdcode}

          scala-cli run \
            --power \
            --offline \
            ${commonScalaArgs} \
            --main-class com.vowstar.ditdah32.DitDah32Module \
            . \
            -- design "$out/ditdah32_config.json"

          MLIRBC_FILE=$(ls DitDah32.mlirbc 2>/dev/null | head -1)

          ${pkgs.circt-install}/bin/firld DitDah32*.mlirbc \
            --base-circuit DitDah32 \
            --no-mangle \
            --emit-bytecode \
            -o DitDah32-linked.mlirbc

          ${pkgs.circt-install}/bin/firtool DitDah32-linked.mlirbc \
            ${firtoolArgs} \
            --hgldd-output-dir="$out" \
            -o "$out"

          rm -f "$out"/DitDah32_DV.sv \
                "$out"/layers-DitDah32-DV.sv \
                "$out"/ref_DitDah32.sv \
                "$out"/DitDah32_DV.dd
          ${pkgs.gnugrep}/bin/grep -v -e DitDah32_DV.sv -e layers-DitDah32-DV.sv \
            "$out"/filelist.f > "$out"/filelist.f.tmp
          mv "$out"/filelist.f.tmp "$out"/filelist.f
        '';

        apps.default = {
          type = "app";
          program = "${buildScript}/bin/build-ditdah32";
        };

        apps.build = {
          type = "app";
          program = "${buildScript}/bin/build-ditdah32";
        };

        apps.score = {
          type = "app";
          program = "${scoreScript}/bin/score-ditdah32";
        };

        devShells = {
          smoke = mkRtlShell smokeBuildInputs { };
          full = mkRtlShell fullBuildInputs { SLANG_SO = slangSo; };
          ci-evidence = pkgs.mkShell {
            buildInputs = ciEvidenceBuildInputs;
          };
          default = mkRtlShell defaultBuildInputs { SLANG_SO = slangSo; };
        };
      }
    );
}
