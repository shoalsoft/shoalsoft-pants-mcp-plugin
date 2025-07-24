# Copyright (C) 2025 Shoal Software LLC. All rights reserved.
#
# This is commercial software and cannot be used without prior permission.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import asyncio
import os
import subprocess
import tempfile
import textwrap
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from packaging.version import Version

from pants.testutil.python_interpreter_selection import python_interpreter_path
from pants.util.dirutil import safe_file_dump
from shoalsoft.pants_modelcontext_plugin.pants_integration_testutil import (
    PantsJoinHandle,
    PantsResult,
    PreparedPantsInvocation,
    prepare_pants_invocation,
    run_pants_with_workdir,
    run_pants_with_workdir_without_waiting,
)


def _safe_write_files(base_path: str | os.PathLike, files: Mapping[str, str | bytes]) -> None:
    for name, content in files.items():
        safe_file_dump(os.path.join(base_path, name), content, makedirs=True)


class IsolatedPantsTestContext:
    def __init__(
        self,
        *,
        buildroot: Path,
        workdir_base: Path,
        pants_exe_args: Iterable[str],
        extra_env: Mapping[str, str],
    ):
        self.buildroot = buildroot
        self.workdir_base = workdir_base
        self.pants_exe_args = list(pants_exe_args)
        self.extra_env = extra_env

    @contextmanager
    def prepared_pants_invocation(
        self, args: Iterable[str]
    ) -> Generator[PreparedPantsInvocation, None, None]:
        with tempfile.TemporaryDirectory(dir=self.workdir_base) as workdir:
            yield prepare_pants_invocation(
                command=list(args),
                pants_exe_args=self.pants_exe_args,
                cwd=self.buildroot,
                workdir=workdir,
                extra_env=self.extra_env,
            )

    def run_pants(self, args: Iterable[str]) -> PantsResult:
        with tempfile.TemporaryDirectory(dir=self.workdir_base) as workdir:
            return run_pants_with_workdir(
                command=list(args),
                pants_exe_args=self.pants_exe_args,
                cwd=self.buildroot,
                workdir=workdir,
                extra_env=self.extra_env,
            )

    @contextmanager
    def run_pants_without_waiting(
        self, args: Iterable[str]
    ) -> Generator[PantsJoinHandle, None, None]:
        with tempfile.TemporaryDirectory(dir=self.workdir_base) as workdir:
            yield run_pants_with_workdir_without_waiting(
                command=list(args),
                pants_exe_args=self.pants_exe_args,
                cwd=self.buildroot,
                workdir=workdir,
                extra_env=self.extra_env,
            )


@contextmanager
def isolated_pants(pants_version_str: str):
    pants_version = Version(pants_version_str)
    pants_major_minor = f"{pants_version.major}.{pants_version.minor}"

    # Find the Python interpreter compatible with this version of Pants.
    py_version_for_pants_major_minor = (
        "3.11" if Version(pants_major_minor) >= Version("2.25") else "3.9"
    )
    python_path = python_interpreter_path(py_version_for_pants_major_minor)
    assert (
        python_path
    ), f"Did not find a compatible Python interpreter for test: Pants v{pants_major_minor}"

    # Install a venv expanded from the plugin's pex file. (The BUILD file arranges for the pex files to be materialized
    # in the sandbox as dependencies.)
    plugin_venv_path = (Path.cwd() / f"plugin-venv-{pants_major_minor}").resolve()
    plugin_venv_path.mkdir(parents=True)
    plugin_pex_files = [
        name
        for name in os.listdir(Path.cwd())
        if name.startswith(f"shoalsoft-pants-modelcontext-plugin-pants{pants_major_minor}")
        and name.endswith(".pex")
    ]
    assert (
        len(plugin_pex_files) == 1
    ), f"Expected to find exactly one pex file for Pants {pants_major_minor}."
    subprocess.run(
        [python_path, plugin_pex_files[0], "venv", str(plugin_venv_path)],
        env={"PEX_TOOLS": "1"},
        check=True,
    )
    site_packages_path = (
        plugin_venv_path / "lib" / f"python{py_version_for_pants_major_minor}" / "site-packages"
    )

    # A pex of the Pants version in this resolve is materialised as `pants-MAJOR.MINOR.pex` in the sandbox.
    # This is done to isolate the test environment's virtualenv from the Pants under test.
    pants_pex_path = (Path.cwd() / f"pants-{pants_major_minor}.pex").resolve()
    assert pants_pex_path.exists(), f"Expected to find pants-{pants_major_minor}.pex in sandbox."

    buildroot = (Path.cwd() / f"buildroot-{pants_major_minor}").resolve()
    buildroot.mkdir(parents=True)

    workdir_base = buildroot / ".pants.d" / "workdirs"
    workdir_base.mkdir(parents=True)

    pants_exe_args = [str(pants_pex_path)]
    extra_env = {"PEX_PYTHON": python_path}

    safe_file_dump(
        str(buildroot / "pants.toml"),
        textwrap.dedent(
            f"""\
        [GLOBAL]
        pants_version = "{pants_version}"
        pythonpath = ["{site_packages_path}"]
        backend_packages = [
          "pants.backend.python",
          "pants.backend.shell",
          "shoalsoft.pants_modelcontext_plugin",
        ]
        print_stacktrace = true
        pantsd = false

        [python]
        interpreter_constraints = "==3.11.*"
        pip_version = "latest"

        [pex-cli]
        version = "v2.45.2"
        known_versions = [
        "v2.45.2|macos_arm64|570a3d5ca306a39aa3a180bd4cf3e2661b7c74b0579422b34659246daf122384|4833957",
        "v2.45.2|macos_x86_64|570a3d5ca306a39aa3a180bd4cf3e2661b7c74b0579422b34659246daf122384|4833957",
        "v2.45.2|linux_arm64|570a3d5ca306a39aa3a180bd4cf3e2661b7c74b0579422b34659246daf122384|4833957",
        "v2.45.2|linux_x86_64|570a3d5ca306a39aa3a180bd4cf3e2661b7c74b0579422b34659246daf122384|4833957",
        ]
        """
        ),
    )

    isolated_pants_test_context = IsolatedPantsTestContext(
        buildroot=buildroot,
        workdir_base=workdir_base,
        pants_exe_args=pants_exe_args,
        extra_env=extra_env,
    )

    yield isolated_pants_test_context


@pytest.mark.parametrize("pants_version_str", ["2.27.0"])
def test_mcp_server_tools(pants_version_str: str) -> None:
    with isolated_pants(pants_version_str) as context:
        sources = {
            "BUILD": """test_shell_command(name="test_tgt", command="echo xyzzy ; exit 1")\n""",
        }
        _safe_write_files(context.buildroot, sources)

        result1 = context.run_pants(["help", "goals"])
        result1.assert_success()
        assert "shoalsoft-mcp" in result1.stdout, "The `shoalsoft-mcp` goal was not configured."

        with context.prepared_pants_invocation(
            ["shoalsoft-mcp", "--run-stdio-server"]
        ) as invocation:

            async def _run_client_test() -> None:
                server_params = StdioServerParameters(
                    command=invocation.pants_command[0],
                    args=invocation.pants_command[1:],
                    env={str(key): str(value) for key, value in invocation.env.items()},
                    cwd=invocation.cwd,
                )
                async with stdio_client(server_params) as (reader, writer):
                    async with ClientSession(reader, writer) as session:
                        await session.initialize()

                        try:
                            list_tools_result = await session.list_tools()
                            tools_by_name = {tool.name: tool for tool in list_tools_result.tools}

                            print(f"TOOLS: {','.join(tools_by_name.keys())}")
                            # Ensure a known subset of tools were exposed.
                            for goal_name in (
                                "test",
                                "package",
                                "peek",
                                "list",
                            ):
                                tool_name = f"pants-goal-{goal_name}"
                                assert (
                                    tool_name in tools_by_name
                                ), f"Expected tool `{tool_name}` to be defined."

                            test_tool = tools_by_name.get("pants-goal-test")
                            assert (
                                test_tool is not None
                            ), "The `pants-goal-test` tool was not in the MCP tools list."

                            test_tool_result = await session.call_tool(
                                name=test_tool.name,
                                arguments={"pants_target_address": "//:test_tgt"},
                            )

                            test_goal_result: dict[str, Any] = getattr(
                                test_tool_result, "structuredContent", {}
                            )

                            exit_code = test_goal_result.get("exit_code")
                            assert (
                                exit_code is not None
                            ), "Expected `exit_code` field in structured output"
                            assert isinstance(exit_code, int), "Expected `exit_code` to be integer."
                            assert exit_code == 1

                            stdout = test_goal_result.get("stdout")
                            assert (
                                stdout is not None
                            ), "Expected `stdout` field in structured output"
                            assert isinstance(stdout, str), "Expected `stdout` to be string."
                            assert stdout == ""

                            stderr = test_goal_result.get("stderr")
                            assert (
                                stderr is not None
                            ), "Expected `stderr` field in structured output"
                            assert isinstance(stderr, str), "Expected `stderr` to be string."
                            assert "//:test_tgt failed" in stderr
                        except Exception as e:
                            # This seems to be necessary with the asyncio since the exception is not
                            # propagating back to pytest for some reason.
                            print(f"EXCEPTION: {e}")
                            raise

            asyncio.run(_run_client_test())
