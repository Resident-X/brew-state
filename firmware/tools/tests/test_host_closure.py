"""The host-tier closure check runs the host tasks in a tree of declared paths only.

Run on synthetic repositories and a stand-in task runner that reads the files it
is told to and records the tree it ran in, so what the check builds, what it
fails on and what it refuses to pass are observed without running a build.
"""

from __future__ import annotations

import ast
import os
import stat
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import round_gate  # noqa: E402

GIT_ENVIRONMENT = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Synthetic",
    "GIT_AUTHOR_EMAIL": "synthetic@example.invalid",
    "GIT_COMMITTER_NAME": "Synthetic",
    "GIT_COMMITTER_EMAIL": "synthetic@example.invalid",
}

TASKS = ["t:one", "t:two"]

#: The stand-in task runner: records the task and where it ran, lists the files in the
#: tree it was started in, fails the task it is told to, and reads each file named in
#: the list it is handed -- failing, as a test reading a missing file does, when one is absent.
TASK_RUNNER = (
    "#!/bin/sh\n"
    'echo "$1" >> "$CLOSURE_LOG/asked"\n'
    'pwd -P >> "$CLOSURE_LOG/cwd"\n'
    'find . -path ./.git -prune -o -type f -print | sort > "$CLOSURE_LOG/files"\n'
    '[ -d .git ] && echo yes > "$CLOSURE_LOG/hasgit"\n'
    'git log --format="%an|%s" > "$CLOSURE_LOG/gitlog" 2>&1\n'
    'git ls-files > "$CLOSURE_LOG/committed" 2>&1\n'
    'if [ "$1" = "$CLOSURE_FAIL" ]; then exit 3; fi\n'
    'if [ -f "$CLOSURE_READS" ]; then\n'
    '  while read -r name; do\n'
    '    [ -f "$name" ] || { echo "cannot read $name" >&2; exit 4; }\n'
    '  done < "$CLOSURE_READS"\n'
    'fi\n'
    "exit 0\n"
)


class Setting:
    """A synthetic repository, a log directory and the stand-in runner, removed after the test."""

    def __init__(self, files: dict[str, str]):
        self.directory = tempfile.TemporaryDirectory()
        base = os.path.realpath(self.directory.name)
        self.repo = os.path.join(base, "repo")
        self.log = os.path.join(base, "log")
        os.makedirs(self.repo)
        os.makedirs(self.log)
        self.runner = os.path.join(base, "task")
        with open(self.runner, "w", encoding="utf-8") as handle:
            handle.write(TASK_RUNNER)
        os.chmod(self.runner, os.stat(self.runner).st_mode | stat.S_IEXEC)
        self.git("init", "-q")
        for path, content in files.items():
            self.write(path, content)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "synthetic")

    def git(self, *arguments: str) -> None:
        subprocess.run(
            ["git", "-C", self.repo, *arguments], capture_output=True, check=True, env=GIT_ENVIRONMENT
        )

    def write(self, path: str, content: str = "content\n") -> None:
        full = os.path.join(self.repo, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(content)

    def reads(self, *names: str) -> None:
        """The files the stand-in runner must find in the tree it runs in."""
        with open(os.path.join(self.log, "reads"), "w", encoding="utf-8") as handle:
            handle.write("".join(f"./{name}\n" for name in names))

    def logged(self, name: str) -> list[str]:
        path = os.path.join(self.log, name)
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as handle:
            return handle.read().split()

    def run(
        self, paths: tuple[str, ...] | None, fail: str = "", tasks: list[str] = TASKS,
        repo: str | None = None, include_untracked: bool = False,
    ):
        arguments = [sys.executable, os.path.join(TOOLS, "host_closure.py"), "--task", self.runner]
        if include_untracked:
            arguments.append("--include-untracked")
        for name in tasks:
            arguments += ["--host", name]
        for path in paths or ():
            arguments += ["--path", path]
        arguments += ["--repo", repo or self.repo]
        environment = {
            **GIT_ENVIRONMENT,
            "CLOSURE_LOG": self.log,
            "CLOSURE_READS": os.path.join(self.log, "reads"),
            "CLOSURE_FAIL": fail,
        }
        return subprocess.run(
            arguments, cwd=self.log, capture_output=True, text=True, check=False, env=environment
        )


FILES = {
    "declared/a.txt": "a\n",
    "declared/deep/b.txt": "b\n",
    "outside/c.txt": "c\n",
    "top.txt": "top\n",
    "top.txt.orig": "orig\n",
}


class TheHostTierRunsInATreeOfTheDeclaredPathsOnly(unittest.TestCase):
    def setUp(self):
        self.setting = Setting(FILES)
        self.addCleanup(self.setting.directory.cleanup)

    def test_a_command_reading_only_declared_files_passes_and_every_task_runs_in_order(self):
        # SOL-VERIFY-ROUND-GATE-HOST-TIER-BY-PATH.C4: The complete verification runs the host tier in a tree holding only the paths the round declares it reads
        self.setting.reads("declared/a.txt", "declared/deep/b.txt", "top.txt")
        result = self.setting.run(("declared/", "top.txt"))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(TASKS, self.setting.logged("asked"))
        self.assertIn("HOST CLOSURE PASSED", result.stdout)
        self.assertIn("3 tracked file(s)", result.stdout)

    def test_a_command_reading_a_file_outside_the_declared_paths_fails_and_the_file_is_absent(self):
        # SOL-VERIFY-ROUND-GATE-HOST-TIER-BY-PATH.C4: The complete verification runs the host tier in a tree holding only the paths the round declares it reads
        self.setting.reads("declared/a.txt", "outside/c.txt")
        result = self.setting.run(("declared/",))
        self.assertNotEqual(0, result.returncode)
        self.assertIn("HOST CLOSURE FAILED: t:one failed (exit status 4)", result.stdout)
        self.assertIn("cannot read ./outside/c.txt", result.stderr)
        self.assertIn("HOST_READS", result.stdout)
        # The tree held the declared files and nothing else.
        self.assertEqual(["./declared/a.txt", "./declared/deep/b.txt"], self.setting.logged("files"))
        self.assertNotIn("HOST CLOSURE PASSED", result.stdout)

    def test_the_same_command_passes_once_the_file_it_reads_is_declared(self):
        # SOL-VERIFY-ROUND-GATE-HOST-TIER-BY-PATH.C4: The complete verification runs the host tier in a tree holding only the paths the round declares it reads
        # What failed above failed for the declaration, not for anything else about the setting.
        self.setting.reads("declared/a.txt", "outside/c.txt")
        result = self.setting.run(("declared/", "outside/"))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_a_declared_set_selecting_no_tracked_file_fails_and_runs_nothing(self):
        # SOL-VERIFY-ROUND-GATE-HOST-TIER-BY-PATH.C4: The complete verification runs the host tier in a tree holding only the paths the round declares it reads
        for paths in (("nothing/",), ("nothing.txt",), ("declared",), ("top.tx",)):
            with self.subTest(paths=paths):
                result = self.setting.run(paths)
                self.assertNotEqual(0, result.returncode, result.stdout)
                self.assertIn("select no file git tracks", result.stdout)
                self.assertEqual([], self.setting.logged("asked"))
                self.assertNotIn("PASSED", result.stdout)

    def test_a_declared_entry_selecting_no_file_fails_naming_it_while_others_match(self):
        # SOL-VERIFY-ROUND-GATE-HOST-TIER-BY-PATH.C4: The complete verification runs the host tier in a tree holding only the paths the round declares it reads
        for stale in ("renamed/", "gone.txt", "declared/missing.txt"):
            with self.subTest(stale=stale):
                result = self.setting.run(("declared/", stale, "top.txt"))
                self.assertEqual(1, result.returncode, result.stdout)
                self.assertIn("HOST CLOSURE FAILED: 1 declared path(s) select no file", result.stdout)
                self.assertIn(f"    {stale}\n", result.stdout)
                self.assertNotIn("    declared/\n", result.stdout)
                self.assertNotIn("    top.txt\n", result.stdout)
                self.assertEqual([], self.setting.logged("asked"))
                self.assertNotIn("PASSED", result.stdout)

    def test_every_stale_entry_is_named(self):
        # SOL-VERIFY-ROUND-GATE-HOST-TIER-BY-PATH.C4: The complete verification runs the host tier in a tree holding only the paths the round declares it reads
        result = self.setting.run(("declared/", "gone/", "also-gone.txt"))
        self.assertEqual(1, result.returncode)
        self.assertIn("2 declared path(s) select no file", result.stdout)
        self.assertIn("    gone/\n", result.stdout)
        self.assertIn("    also-gone.txt\n", result.stdout)

    def test_an_entry_matched_only_by_an_untracked_file_is_not_stale_when_those_are_included(self):
        # SOL-VERIFY-ROUND-GATE-HOST-TIER-BY-PATH.C4: The complete verification runs the host tier in a tree holding only the paths the round declares it reads
        self.setting.write("fresh/new.txt")
        refused = self.setting.run(("declared/", "fresh/"))
        self.assertEqual(1, refused.returncode)
        self.assertIn("    fresh/\n", refused.stdout)
        result = self.setting.run(("declared/", "fresh/"), include_untracked=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_paths_with_pattern_characters_spaces_or_odd_names_are_taken_literally(self):
        # SOL-VERIFY-ROUND-GATE-HOST-TIER-BY-PATH.C4: The complete verification runs the host tier in a tree holding only the paths the round declares it reads
        odd = ["star*.txt", "set[1].txt", "what?.txt", "with space.txt", "dir [x]/in side.txt", ":colon.txt", "a1.txt"]
        setting = Setting({**FILES, **{name: "x\n" for name in odd}})
        self.addCleanup(setting.directory.cleanup)
        for declared, expected in (
            ("star*.txt", ["./star*.txt"]),
            ("set[1].txt", ["./set[1].txt"]),
            ("what?.txt", ["./what?.txt"]),
            ("with space.txt", ["./with space.txt"]),
            ("dir [x]/", ["./dir [x]/in side.txt"]),
            (":colon.txt", ["./:colon.txt"]),
        ):
            with self.subTest(declared=declared):
                setting.reads(expected[0][2:])
                result = setting.run((declared,))
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                (listed,) = [line for line in open(os.path.join(setting.log, "files"), encoding="utf-8").read().splitlines()]
                self.assertEqual(expected[0], listed)
                self.assertIn("copied 1 tracked file(s)", result.stdout)
        # A pattern character is not a wildcard: "*" selects nothing here, and "set[1].txt" does not take "set1.txt".
        setting.reads()
        self.assertEqual(1, setting.run(("*.txt",)).returncode)
        setting.write("set1.txt")
        setting.git("add", "-A")
        setting.git("commit", "-q", "-m", "more")
        result = setting.run(("set[1].txt",))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("copied 1 tracked file(s)", result.stdout)

    def test_a_file_that_is_not_tracked_is_not_in_the_tree(self):
        # SOL-VERIFY-ROUND-GATE-HOST-TIER-BY-PATH.C4: The complete verification runs the host tier in a tree holding only the paths the round declares it reads
        self.setting.write("declared/untracked.txt")
        self.setting.reads("declared/untracked.txt")
        result = self.setting.run(("declared/",))
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn("./declared/untracked.txt", self.setting.logged("files"))

    def test_the_tree_is_a_git_repository_of_its_own_holding_the_files_in_one_commit(self):
        # SOL-VERIFY-ROUND-GATE-HOST-TIER-BY-PATH.C4: The complete verification runs the host tier in a tree holding only the paths the round declares it reads
        before = subprocess.run(
            ["git", "-C", self.setting.repo, "log", "--format=%H"], capture_output=True, text=True,
            env=GIT_ENVIRONMENT, check=True,
        ).stdout
        result = self.setting.run(("declared/", "top.txt"))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(["yes"], self.setting.logged("hasgit"))
        # One commit, by the fixed identity, and git itself lists the files committed.
        self.assertEqual(["host-closure|host", "closure"], self.setting.logged("gitlog"))
        self.assertEqual(["declared/a.txt", "declared/deep/b.txt", "top.txt"], self.setting.logged("committed"))
        # The real repository is left as it was: no commit, no configuration written.
        after = subprocess.run(
            ["git", "-C", self.setting.repo, "log", "--format=%H"], capture_output=True, text=True,
            env=GIT_ENVIRONMENT, check=True,
        ).stdout
        self.assertEqual(before, after)
        self.assertFalse(os.path.exists(os.path.join(self.setting.repo, ".git", "host-closure")))
        config = subprocess.run(
            ["git", "-C", self.setting.repo, "config", "--local", "--list"], capture_output=True, text=True,
            env=GIT_ENVIRONMENT, check=True,
        ).stdout
        self.assertNotIn("host-closure", config)

    def test_untracked_files_are_copied_only_when_asked_for_and_ignored_ones_never(self):
        # SOL-VERIFY-ROUND-GATE-HOST-TIER-BY-PATH.C4: The complete verification runs the host tier in a tree holding only the paths the round declares it reads
        self.setting.write(".gitignore", "declared/ignored.txt\n")
        self.setting.git("add", ".gitignore")
        self.setting.git("commit", "-q", "-m", "ignore")
        self.setting.write("declared/new.txt")
        self.setting.write("declared/ignored.txt")
        self.setting.write("outside/new.txt")
        self.setting.reads("declared/new.txt")
        refused = self.setting.run(("declared/",))
        self.assertNotEqual(0, refused.returncode)
        result = self.setting.run(("declared/",), include_untracked=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(
            ["./declared/a.txt", "./declared/deep/b.txt", "./declared/new.txt"],
            self.setting.logged("files"),
        )
        self.assertIn("copied 3 tracked or untracked file(s)", result.stdout)
        self.assertIn("3 tracked or untracked file(s) under", result.stdout.split("HOST CLOSURE PASSED")[1])
        self.assertNotIn("tracked file(s) under", result.stdout.replace("tracked or untracked file(s)", ""))

    def test_the_number_of_files_copied_is_printed(self):
        # SOL-VERIFY-ROUND-GATE-HOST-TIER-BY-PATH.C4: The complete verification runs the host tier in a tree holding only the paths the round declares it reads
        result = self.setting.run(("declared/",))
        self.assertIn("copied 2 tracked file(s)", result.stdout)

    def test_a_path_naming_a_file_does_not_take_a_file_that_only_shares_its_prefix(self):
        # SOL-VERIFY-ROUND-GATE-HOST-TIER-BY-PATH.C4: The complete verification runs the host tier in a tree holding only the paths the round declares it reads
        result = self.setting.run(("top.txt",))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(["./top.txt"], self.setting.logged("files"))

    def test_a_failing_command_fails_the_run_and_the_tasks_after_it_do_not_run(self):
        # SOL-VERIFY-ROUND-GATE-HOST-TIER-BY-PATH.C4: The complete verification runs the host tier in a tree holding only the paths the round declares it reads
        result = self.setting.run(("declared/",), fail="t:one")
        self.assertEqual(1, result.returncode)
        self.assertEqual(["t:one"], self.setting.logged("asked"))
        self.assertIn("HOST CLOSURE FAILED: t:one failed (exit status 3)", result.stdout)
        self.assertNotIn("PASSED", result.stdout)

    def test_a_later_task_failing_fails_the_run_after_the_earlier_ones_passed(self):
        # SOL-VERIFY-ROUND-GATE-HOST-TIER-BY-PATH.C4: The complete verification runs the host tier in a tree holding only the paths the round declares it reads
        result = self.setting.run(("declared/",), fail="t:two")
        self.assertEqual(1, result.returncode)
        self.assertEqual(TASKS, self.setting.logged("asked"))
        self.assertIn("t:two failed (exit status 3)", result.stdout)

    def test_the_tasks_run_in_a_tree_of_their_own_that_is_removed_afterwards(self):
        # SOL-VERIFY-ROUND-GATE-HOST-TIER-BY-PATH.C4: The complete verification runs the host tier in a tree holding only the paths the round declares it reads
        result = self.setting.run(("declared/",))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        (first, second) = self.setting.logged("cwd")
        self.assertEqual(first, second)
        self.assertNotEqual(self.setting.repo, first)
        self.assertFalse(first.startswith(self.setting.repo))
        self.assertFalse(os.path.exists(first))

    def test_a_task_runner_that_cannot_start_fails_the_run(self):
        # SOL-VERIFY-ROUND-GATE-HOST-TIER-BY-PATH.C4: The complete verification runs the host tier in a tree holding only the paths the round declares it reads
        os.remove(self.setting.runner)
        result = self.setting.run(("declared/",))
        self.assertEqual(1, result.returncode)
        self.assertIn("could not be started", result.stdout)
        self.assertIn("HOST CLOSURE FAILED", result.stdout)

    def test_a_tracked_file_missing_from_the_working_tree_fails_naming_it(self):
        # SOL-VERIFY-ROUND-GATE-HOST-TIER-BY-PATH.C4: The complete verification runs the host tier in a tree holding only the paths the round declares it reads
        os.remove(os.path.join(self.setting.repo, "declared", "a.txt"))
        result = self.setting.run(("declared/",))
        self.assertEqual(1, result.returncode)
        self.assertIn("    declared/a.txt", result.stdout)
        self.assertEqual([], self.setting.logged("asked"))

    def test_a_directory_that_is_not_a_repository_fails(self):
        # SOL-VERIFY-ROUND-GATE-HOST-TIER-BY-PATH.C4: The complete verification runs the host tier in a tree holding only the paths the round declares it reads
        with tempfile.TemporaryDirectory() as bare:
            result = self.setting.run(("declared/",), repo=bare)
        self.assertEqual(1, result.returncode)
        self.assertEqual([], self.setting.logged("asked"))
        self.assertIn("HOST CLOSURE FAILED", result.stdout)

    def test_a_symbolic_link_is_carried_as_a_link(self):
        # SOL-VERIFY-ROUND-GATE-HOST-TIER-BY-PATH.C4: The complete verification runs the host tier in a tree holding only the paths the round declares it reads
        os.symlink("a.txt", os.path.join(self.setting.repo, "declared", "link.txt"))
        self.setting.git("add", "-A")
        self.setting.git("commit", "-q", "-m", "link")
        self.setting.reads("declared/link.txt")
        result = self.setting.run(("declared/",))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


class TheDefaultDeclaredPathsAreTheRoundGatesHostReads(unittest.TestCase):
    def test_without_paths_given_the_tree_holds_exactly_what_the_round_gate_declares(self):
        # SOL-VERIFY-ROUND-GATE-HOST-TIER-BY-PATH.C4: The complete verification runs the host tier in a tree holding only the paths the round declares it reads
        files = {
            "firmware/src/a.c": "a\n",
            "Taskfile.yml": "version: '3'\n",
            ".github/workflows/w.yml": "name: w\n",
            "docs/d.md": "d\n",
            "specs/s.yaml": "s\n",
            "hardware/h.txt": "h\n",
            "hardware/m/board/b.kicad_pcb": "pcb\n",
            "hardware/README.md": "notes\n",
            "hardware/tools/board_check.py": "check\n",
            "hardware/tools/board_other.py": "other\n",
            "hardware/tools/board_views.py": "views\n",
            "hardware/tools/tests/test_board_check_kicad.py": "test\n",
            "CLAUDE.md": "instructions\n",
            ".gitattributes": "* text=auto\n",
            "Taskfile.yml.orig": "o\n",
            "CLAUDE.md.orig": "o\n",
        }
        setting = Setting(files)
        self.addCleanup(setting.directory.cleanup)
        result = setting.run(None)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(
            sorted([
                "./.github/workflows/w.yml", "./Taskfile.yml", "./firmware/src/a.c", "./CLAUDE.md",
                "./.gitattributes", "./hardware/README.md", "./hardware/tools/board_check.py",
                "./hardware/tools/board_views.py", "./hardware/tools/tests/test_board_check_kicad.py",
            ]),
            sorted(setting.logged("files")),
        )
        self.assertEqual(
            sorted(f"./{path}" for path in files if round_gate.reads(path, round_gate.HOST_READS)),
            sorted(setting.logged("files")),
        )

    def test_a_repository_holding_none_of_the_round_gates_paths_fails(self):
        # SOL-VERIFY-ROUND-GATE-HOST-TIER-BY-PATH.C4: The complete verification runs the host tier in a tree holding only the paths the round declares it reads
        setting = Setting({"docs/d.md": "d\n"})
        self.addCleanup(setting.directory.cleanup)
        result = setting.run(None)
        self.assertEqual(1, result.returncode)
        self.assertIn("select no file git tracks", result.stdout)


class TheClosureCheckNeedsOnlyTheStandardLibrary(unittest.TestCase):
    """The nightly runs the check and the host tier runs these tests, so a third-party
    import in either fails them on a machine that lacks it."""

    def test_the_check_and_its_tests_import_only_the_standard_library(self):
        # SOL-VERIFY-ROUND-GATE-HOST-TIER-BY-PATH.C4: The complete verification runs the host tier in a tree holding only the paths the round declares it reads
        for path in (os.path.join(TOOLS, "host_closure.py"), os.path.abspath(__file__)):
            with open(path, encoding="utf-8") as handle:
                tree = ast.parse(handle.read())
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    imported.add(node.module.split(".")[0])
            foreign = sorted(
                name for name in imported
                if name not in sys.stdlib_module_names
                and name not in ("__future__", "round_gate", "task_gate")
            )
            with self.subTest(path=os.path.basename(path)):
                self.assertIn("subprocess", imported)
                self.assertEqual([], foreign)


if __name__ == "__main__":
    unittest.main()
