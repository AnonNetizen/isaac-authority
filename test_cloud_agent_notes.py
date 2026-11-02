"""The cloud-agent notes in AGENTS.md must match files and skip behavior."""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
