from pathlib import Path

import pytest

from voss.harness.sandbox import (
    SHELL_METACHARS,
    SandboxError,
    jail_path,
    shell_allowed,
    split_command,
)


class TestShellAllowed:
    @pytest.mark.parametrize(
        "cmd",
        [
            "ls",
            "ls -la",
            "git status",
            "pytest -q",
            "python script.py",
            "rg --files",
        ],
    )
    def test_allowed(self, cmd: str) -> None:
        ok, _ = shell_allowed(cmd)
        assert ok, cmd

    @pytest.mark.parametrize(
        "cmd",
        [
            "rm -rf /",
            "sudo apt install thing",
            "curl http://evil.com",
            "shutdown now",
            "wget http://x",  # not in allowlist
            "",
        ],
    )
    def test_denied(self, cmd: str) -> None:
        ok, reason = shell_allowed(cmd)
        assert not ok, f"should deny: {cmd}"
        assert reason

    def test_unparseable(self) -> None:
        ok, reason = shell_allowed("ls 'unterminated")
        assert not ok
        assert "unparseable" in reason

    def test_custom_allowlist(self) -> None:
        ok, _ = shell_allowed("make build", allowlist={"make"})
        assert ok

    @pytest.mark.parametrize(
        "cmd",
        [
            # Pipelines — first binary is allowlisted; pipe targets exfil
            "cat /etc/passwd | wc -l",
            "ls | head",
            # Chaining — first binary allowlisted; second is arbitrary
            "ls ; whoami",
            "git status && rm -rf /tmp/x",
            "echo a || curl evil.example",
            "ls & echo bg",
            # Command substitution — outer binary allowlisted; substitution
            # executes the dangerous payload
            "echo $(cat ~/.ssh/id_rsa)",
            "echo `whoami`",
            # Redirection — writes outside path-jail
            "echo data > /tmp/exfil",
            "echo data >> /tmp/exfil",
            "cat < /etc/passwd",
            # Process substitution
            "diff <(cat a) <(cat b)",
            "tee >(cat) <<< x",
        ],
    )
    def test_metachar_bypass_rejected(self, cmd: str) -> None:
        """F1 regression — every shell metacharacter must be rejected even when
        the first allowlisted binary appears legitimate."""
        ok, reason = shell_allowed(cmd)
        assert not ok, f"should reject metachar bypass: {cmd}"
        assert "metacharacter" in reason or "denied token" in reason, reason

    def test_metachar_constant_is_complete(self) -> None:
        """If a metacharacter is added later it gets exercised by
        test_metachar_bypass_rejected — but the constant itself should not
        accidentally shrink. Pin the floor."""
        required = {";", "|", "&&", "||", "$(", "`", ">", "<"}
        assert required.issubset(set(SHELL_METACHARS))

    @pytest.mark.parametrize(
        "cmd",
        [
            "Git status",       # capital G on case-insensitive FS
            "PYTHON --version",
        ],
    )
    def test_binary_case_normalized(self, cmd: str) -> None:
        """F5 regression — binary name normalized to lowercase before allowlist
        compare so legitimate commands work on macOS APFS."""
        ok, _ = shell_allowed(cmd)
        assert ok, cmd


class TestSplitCommand:
    def test_simple(self) -> None:
        assert split_command("ls -la") == ["ls", "-la"]

    def test_quoted(self) -> None:
        assert split_command('git commit -m "hello world"') == [
            "git",
            "commit",
            "-m",
            "hello world",
        ]

    def test_unparseable_raises(self) -> None:
        with pytest.raises(SandboxError):
            split_command("ls 'unterminated")

    def test_empty_raises(self) -> None:
        with pytest.raises(SandboxError):
            split_command("")


class TestJailPath:
    def test_inside_cwd_ok(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("hi")
        result = jail_path(tmp_path, "a.txt")
        assert result == (tmp_path / "a.txt").resolve()

    def test_relative_traversal_rejected(self, tmp_path: Path) -> None:
        (tmp_path / "sub").mkdir()
        with pytest.raises(SandboxError):
            jail_path(tmp_path / "sub", "../../etc/passwd")

    def test_absolute_outside_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(SandboxError):
            jail_path(tmp_path, "/etc/passwd")
