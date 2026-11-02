"""The cloud-agent notes in AGENTS.md must match files and skip behavior."""

from __future__ import annotations

import ast
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AGENTS = ROOT / "AGENTS.md"
HEADING = "## Cursor Cloud specific instructions"
REPO_FILE = re.compile(r"^(?:[\w.-]+/)*[\w.-]+\.(?:py|txt|sh|json|md|ps1|lua)$")


def cloud_section() -> str:
    text = AGENTS.read_text(encoding="utf-8")
    start = text.index(HEADING)
    rest = text[start + len(HEADING) :]
    next_heading = re.search(r"\n## ", rest)
    if next_heading:
        rest = rest[: next_heading.start()]
    return rest


def collapsed(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def top_level_bullets(section: str) -> list[str]:
    bullets: list[str] = []
    current: list[str] | None = None
    for line in section.splitlines():
        if re.match(r"^- ", line):
            if current is not None:
                bullets.append("\n".join(current))
            current = [line]
            continue
        if current is None:
            continue
        if line.startswith("  ") or line.strip() == "":
            current.append(line)
            continue
        bullets.append("\n".join(current))
        current = None
    if current is not None:
        bullets.append("\n".join(current))
    return bullets


def named_repo_files(section: str) -> list[str]:
    found: list[str] = []
    for token in re.findall(r"`([^`]+)`", section):
        for part in token.split():
            if part.startswith("/") or part.startswith("-"):
                continue
            if REPO_FILE.fullmatch(part):
                found.append(part)
    return found


class CloudNoteTests(unittest.TestCase):
    def test_named_repo_files_exist(self):
        section = cloud_section()
        named = named_repo_files(section)
        self.assertIn("requirements-dev.txt", named)
        self.assertIn("authority/tools/cloud_linux_setup.sh", named)
        self.assertIn("test_stability_patch.py", named)
        missing = [path for path in named if not (ROOT / path).is_file()]
        self.assertEqual(missing, [])

    def test_lupa_pin_is_in_a_named_requirements_file(self):
        section = cloud_section()
        self.assertIn("`lupa==2.6`", section)
        self.assertIn("`requirements-dev.txt`", section)
        pin = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
        self.assertRegex(pin, r"(?m)^lupa==2\.6$")

    def test_compiler_switch_is_backed_by_a_repo_script(self):
        section = cloud_section()
        self.assertNotIn("The environment install does this", section)
        self.assertIn("`authority/tools/cloud_linux_setup.sh`", section)
        script = (ROOT / "authority/tools/cloud_linux_setup.sh").read_text(encoding="utf-8")
        self.assertIn("update-alternatives --set cc /usr/bin/gcc", script)
        self.assertIn("update-alternatives --set c++ /usr/bin/g++", script)
        self.assertIn("requirements-dev.txt", script)
        self.assertIn("pip install", script)

    def test_doc_matches_lua_compile_skip(self):
        section = collapsed(cloud_section())
        self.assertNotIn("the compile check passes", section)
        self.assertIn(
            "The Python `py_compile` check (`CompileTests.test_python_sources_compile`) passes.",
            section,
        )
        self.assertIn(
            "The Lua compile of the patched workshop main.lua "
            "(`StructureTests.test_patched_text_compiles_in_lua53`) also skips",
            section,
        )
        self.assertIn("@REQUIRES_SOURCE", section)
        self.assertIn("`PATCHED` is None", section)

        tree = ast.parse((ROOT / "test_stability_patch.py").read_text(encoding="utf-8"))
        classes = {
            node.name: node for node in tree.body if isinstance(node, ast.ClassDef)
        }
        structure = classes["StructureTests"]
        compile_tests = classes["CompileTests"]
        self.assertTrue(
            any(ast.unparse(item) == "REQUIRES_SOURCE" for item in structure.decorator_list)
        )
        self.assertIn(
            "test_patched_text_compiles_in_lua53",
            [node.name for node in structure.body if isinstance(node, ast.FunctionDef)],
        )
        self.assertFalse(
            any("REQUIRES_SOURCE" in ast.unparse(item) for item in compile_tests.decorator_list)
        )
        self.assertIn(
            "test_python_sources_compile",
            [node.name for node in compile_tests.body if isinstance(node, ast.FunctionDef)],
        )

        env = os.environ.copy()
        env.pop("ISAAC_LASER_SOURCE", None)
        probe = r"""
import json, os, unittest
os.environ.pop("ISAAC_LASER_SOURCE", None)
import patch_watch_out_laser as installer
installer.discover_mod = lambda: (_ for _ in ()).throw(ValueError("workshop main.lua is not in this check"))
import test_stability_patch as tests
loader = unittest.TestLoader()
names = [
    "StructureTests.test_patched_text_compiles_in_lua53",
    "CompileTests.test_python_sources_compile",
]
suite = loader.loadTestsFromNames(names, tests)
result = unittest.TextTestRunner(stream=open(os.devnull, "w"), verbosity=0).run(suite)
print(json.dumps({
    "original_is_none": tests.ORIGINAL is None,
    "patched_is_none": tests.PATCHED is None,
    "ran": result.testsRun,
    "passed": result.testsRun - len(result.skipped) - len(result.failures) - len(result.errors),
    "skipped": [test.id().split(".")[-1] + ": " + reason for test, reason in result.skipped],
    "failed": [test.id() for test, _ in result.failures],
    "errors": [test.id() for test, _ in result.errors],
}))
"""
        completed = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertTrue(report["original_is_none"])
        self.assertTrue(report["patched_is_none"])
        self.assertEqual(report["ran"], 2)
        self.assertEqual(report["passed"], 1)
        self.assertEqual(report["failed"], [])
        self.assertEqual(report["errors"], [])
        self.assertEqual(len(report["skipped"]), 1)
        self.assertIn("test_patched_text_compiles_in_lua53", report["skipped"][0])
        self.assertIn("source not available", report["skipped"][0])

    def test_setup_script_installs_venv_before_compiler_switch(self):
        section = cloud_section()
        script = executable_lines(
            (ROOT / "authority/tools/cloud_linux_setup.sh").read_text(encoding="utf-8")
        )
        # The old script was `python3 -m pip install --user -r ...` with no venv.
        # That line is rejected on PEP 668 Pythons and inside a virtualenv.
        self.assertNotRegex(script, r"pip install --user(?! --break-system-packages)\b")
        self.assertIn("python3 -m venv", script)
        self.assertIn(".venv", script)
        self.assertIn("import ensurepip", script)
        self.assertIn("python3-venv", script)
        self.assertLess(script.index("pip install"), script.index("update-alternatives --set cc"))
        self.assertIn(
            "`.venv/bin/python -m pytest -q test_stability_patch.py`",
            section,
        )
        self.assertNotIn("pip install --user", section)

    @unittest.skipUnless(
        os.name == "posix" and Path("/usr/bin/gcc").is_file() and Path("/usr/bin/g++").is_file(),
        "behavioral install check needs /usr/bin/gcc and /usr/bin/g++",
    )
    def test_simulated_externally_managed_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state"
            state.mkdir()
            log = Path(tmp) / "setup.log"
            first = _run_setup(Path(tmp), state, log, {"SIM_EXTERNALLY_MANAGED": "1", "SIM_NO_ENSUREPIP": "1"})
            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            self._assert_venv_install(log.read_text(encoding="utf-8"), require_apt=True)
            log.write_text("", encoding="utf-8")
            second = _run_setup(Path(tmp), state, log, {"SIM_EXTERNALLY_MANAGED": "1", "SIM_NO_ENSUREPIP": "1"})
            self.assertEqual(second.returncode, 0, second.stderr + second.stdout)
            self._assert_venv_install(log.read_text(encoding="utf-8"), require_apt=False)

    @unittest.skipUnless(
        os.name == "posix" and Path("/usr/bin/gcc").is_file() and Path("/usr/bin/g++").is_file(),
        "behavioral install check needs /usr/bin/gcc and /usr/bin/g++",
    )
    def test_pip_failure_leaves_compilers_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state"
            state.mkdir()
            log = Path(tmp) / "setup.log"
            completed = _run_setup(
                Path(tmp),
                state,
                log,
                {"SIM_EXTERNALLY_MANAGED": "1", "SIM_NO_ENSUREPIP": "1", "SIM_FAIL_PIP": "1"},
            )
            text = log.read_text(encoding="utf-8")
            self.assertNotEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertNotIn("update-alternatives", text)
            self.assertNotIn("--user", text)
            self.assertIn("pip install -r", text)

    def _assert_venv_install(self, text: str, require_apt: bool) -> None:
        self.assertNotIn("--user", text)
        self.assertNotIn("system-pip", text)
        self.assertNotIn("externally-managed-environment", text)
        if require_apt:
            self.assertLess(text.index("apt-get install -y python3-venv"), text.index("\nvenv "))
        self.assertLess(text.index("\nvenv "), text.index("pip install -r"))
        self.assertLess(text.index("pip install -r"), text.index("update-alternatives --set cc /usr/bin/gcc"))
        self.assertLess(
            text.index("update-alternatives --set cc /usr/bin/gcc"),
            text.index("update-alternatives --set c++ /usr/bin/g++"),
        )

    def test_pytest_commands_use_venv_python_after_unconditional_setup(self):
        section = cloud_section()
        self.assertNotIn("python3 -m pytest", section)
        bullets = top_level_bullets(section)
        setup_at = [
            index
            for index, bullet in enumerate(bullets)
            if "to create `.venv`" in collapsed(bullet) and "If CMake" not in bullet
        ]
        self.assertEqual(setup_at, [0])
        command_indexes = [
            index
            for index, bullet in enumerate(bullets)
            if ".venv/bin/python -m pytest" in bullet
            or "run_isolation.py" in bullet
            or "test_isolation.py" in bullet
            or "test_offline_authority.py" in bullet
        ]
        self.assertGreaterEqual(len(command_indexes), 3)
        self.assertTrue(all(index > setup_at[0] for index in command_indexes))
        pytest_bullets = [bullet for bullet in bullets if "pytest" in bullet]
        self.assertGreaterEqual(len(pytest_bullets), 1)
        for bullet in pytest_bullets:
            self.assertNotIn("python3 -m pytest", bullet)
            self.assertIn(".venv/bin/python -m pytest", bullet)

    def test_setup_step_precedes_cmake_error_and_is_not_nested(self):
        section = cloud_section()
        bullets = top_level_bullets(section)
        self.assertGreaterEqual(len(bullets), 2)
        setup = bullets[0]
        self.assertIn(
            "Run `authority/tools/cloud_linux_setup.sh` to create `.venv`",
            collapsed(setup),
        )
        self.assertNotIn("If CMake", setup)
        self.assertNotIn("cannot find -lstdc++", setup)
        for line in setup.splitlines():
            if "cloud_linux_setup.sh" in line:
                self.assertTrue(line.startswith("- "), line)

        cmake_at = [
            index for index, bullet in enumerate(bullets) if "cannot find -lstdc++" in bullet
        ]
        self.assertEqual(len(cmake_at), 1)
        self.assertGreater(cmake_at[0], 0)
        cmake = bullets[cmake_at[0]]
        self.assertEqual(
            collapsed(cmake),
            "- If CMake reports `cannot find -lstdc++` or a missing `iostream`, "
            "delete the failed build directory and configure again.",
        )
        self.assertNotIn("cloud_linux_setup.sh", cmake)
        self.assertNotIn("python3 -m venv", cmake)
        self.assertNotIn(".venv", cmake)
        self.assertNotRegex(cmake, r"(?m)^[ \t]+- ")
        self.assertLess(section.index("to create `.venv`"), section.index("cannot find -lstdc++"))
        self.assertNotIn("cloud_linux_setup.sh", section[section.index("cannot find -lstdc++") :])

    @unittest.skipUnless(
        os.name == "posix" and Path("/usr/bin/gcc").is_file() and Path("/usr/bin/g++").is_file(),
        "real venv install needs /usr/bin/gcc and /usr/bin/g++",
    )
    def test_real_setup_runs_venv_module_and_pip(self):
        sudo = subprocess.run(["sudo", "-n", "true"], capture_output=True, text=True, check=False)
        if sudo.returncode != 0:
            self.skipTest("real setup needs passwordless sudo")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            completed = _run_real_setup(root)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            output = completed.stdout + completed.stderr
            self.assertNotIn("--user", output)
            self.assertNotIn("externally-managed-environment", output)
            self.assertTrue(
                "Successfully installed" in output or "Requirement already satisfied: lupa==2.6" in output,
                output,
            )
            assert_real_venv_install(self, root)


def assert_real_venv_install(test: unittest.TestCase, root: Path) -> None:
    venv = root / ".venv"
    cfg_path = venv / "pyvenv.cfg"
    test.assertTrue(cfg_path.is_file(), "python3 -m venv did not write pyvenv.cfg")
    cfg = cfg_path.read_text(encoding="utf-8")
    test.assertRegex(cfg, r"(?m)^command = .* -m venv ")
    python = venv / "bin" / "python"
    test.assertTrue(os.access(python, os.X_OK))
    probe = subprocess.run(
        [str(python), "-c", "import lupa.lua53, pytest; print(lupa.lua53.LUA_VERSION)"],
        capture_output=True,
        text=True,
        check=False,
    )
    test.assertEqual(probe.returncode, 0, probe.stderr)
    test.assertEqual(probe.stdout.strip(), "(5, 3)")
    shown = subprocess.run(
        [str(python), "-m", "pip", "show", "lupa"],
        capture_output=True,
        text=True,
        check=False,
    )
    test.assertEqual(shown.returncode, 0, shown.stderr)
    test.assertIn("Version: 2.6", shown.stdout)
    location = next(line for line in shown.stdout.splitlines() if line.startswith("Location: "))
    test.assertTrue(location.split(": ", 1)[1].startswith(str(venv)), shown.stdout)


def _run_real_setup(root: Path) -> subprocess.CompletedProcess[str]:
    tools = root / "authority" / "tools"
    tools.mkdir(parents=True, exist_ok=True)
    script_src = ROOT / "authority/tools/cloud_linux_setup.sh"
    script = tools / "cloud_linux_setup.sh"
    script.write_bytes(script_src.read_bytes())
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    (root / "requirements-dev.txt").write_text(
        (ROOT / "requirements-dev.txt").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    env.pop("PYTHONPATH", None)
    env["PATH"] = "/usr/bin:/bin"
    return subprocess.run(
        ["bash", str(script)],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

def executable_lines(script: str) -> str:
    return "\n".join(line for line in script.splitlines() if not line.lstrip().startswith("#"))


def _run_setup(
    tmp: Path,
    state: Path,
    log: Path,
    extra: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    root = tmp / "root"
    tools = root / "authority" / "tools"
    tools.mkdir(parents=True, exist_ok=True)
    script_src = ROOT / "authority/tools/cloud_linux_setup.sh"
    script = tools / "cloud_linux_setup.sh"
    script.write_bytes(script_src.read_bytes())
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    (root / "requirements-dev.txt").write_text(
        (ROOT / "requirements-dev.txt").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    bindir = tmp / "bin"
    bindir.mkdir(exist_ok=True)
    python_stub = bindir / "python3"
    python_stub.write_text(_FAKE_PYTHON, encoding="utf-8")
    python_stub.chmod(0o755)
    sudo_stub = bindir / "sudo"
    sudo_stub.write_text(_FAKE_SUDO, encoding="utf-8")
    sudo_stub.chmod(0o755)
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    env["CLOUD_SETUP_LOG"] = str(log)
    env["SIM_STATE"] = str(state)
    env.update(extra)
    return subprocess.run(
        ["bash", str(script)],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


_FAKE_PYTHON = textwrap.dedent(
    """\
    #!/usr/bin/python3
    import os
    import sys

    log_path = os.environ["CLOUD_SETUP_LOG"]
    state = os.environ["SIM_STATE"]

    def record(line):
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(line + "\\n")

    def ensurepip_ready():
        if os.environ.get("SIM_NO_ENSUREPIP") != "1":
            return True
        return os.path.isfile(os.path.join(state, "apt-venv"))

    args = sys.argv[1:]
    if args[:1] == ["-c"]:
        code = args[1]
        if "ensurepip" in code and not ensurepip_ready():
            sys.stderr.write("ModuleNotFoundError: No module named 'ensurepip'\\n")
            sys.exit(1)
        record("py -c " + code)
        sys.exit(0)

    if args[:2] == ["-m", "venv"]:
        if not ensurepip_ready():
            sys.stderr.write("ensurepip is not available\\n")
            sys.exit(1)
        if len(args) != 3:
            sys.stderr.write("unexpected venv args: %s\\n" % (args,))
            sys.exit(2)
        dest = args[2]
        bindir = os.path.join(dest, "bin")
        os.makedirs(bindir, exist_ok=True)
        launcher = os.path.join(bindir, "python")
        with open(launcher, "w", encoding="utf-8") as handle:
            handle.write(
                "#!/usr/bin/python3\\n"
                "import os, sys\\n"
                "log_path = os.environ['CLOUD_SETUP_LOG']\\n"
                "args = sys.argv[1:]\\n"
                "payload = args[2:] if args[:2] == ['-m', 'pip'] else args\\n"
                "with open(log_path, 'a', encoding='utf-8') as handle:\\n"
                "    handle.write('pip ' + ' '.join(payload) + '\\\\n')\\n"
                "if args[:2] != ['-m', 'pip'] or '--user' in args:\\n"
                "    sys.stderr.write(\\"refusing venv pip args: %s\\\\n\\" % (args,))\\n"
                "    sys.exit(1)\\n"
                "if os.environ.get('SIM_FAIL_PIP') == '1':\\n"
                "    sys.stderr.write('simulated pip failure\\\\n')\\n"
                "    sys.exit(1)\\n"
                "raise SystemExit(0)\\n"
            )
        os.chmod(launcher, 0o755)
        record("venv " + dest)
        sys.exit(0)

    if args[:2] == ["-m", "pip"]:
        record("system-pip " + " ".join(args))
        if "--user" in args and "--break-system-packages" not in args:
            sys.stderr.write("error: externally-managed-environment\\n")
            sys.exit(1)
        if "--user" in args and os.environ.get("SIM_IN_VENV") == "1":
            sys.stderr.write("ERROR: Can not perform a '--user' install.\\n")
            sys.exit(1)
        if os.environ.get("SIM_EXTERNALLY_MANAGED") == "1" and "--break-system-packages" not in args:
            sys.stderr.write("error: externally-managed-environment\\n")
            sys.exit(1)
        sys.exit(0)

    sys.stderr.write("unexpected python args: %s\\n" % (args,))
    sys.exit(2)
    """
)

_FAKE_SUDO = textwrap.dedent(
    """\
    #!/bin/bash
    printf 'sudo %s\\n' "$*" >> "$CLOUD_SETUP_LOG"
    case "$*" in
      *python3-venv*) touch "$SIM_STATE/apt-venv" ;;
    esac
    exit 0
    """
)


if __name__ == "__main__":
    unittest.main(verbosity=2)

