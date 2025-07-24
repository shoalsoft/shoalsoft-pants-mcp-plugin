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


from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from mcp import types as mcp_types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from pants.base.specs_parser import SpecsParser
from pants.build_graph.build_configuration import BuildConfiguration
from pants.core.goals.test import Test
from pants.core.util_rules.environments import determine_bootstrap_environment
from pants.engine.console import Console
from pants.engine.fs import Workspace
from pants.engine.internals.parser import BuildFileSymbolsInfo
from pants.engine.internals.scheduler import SchedulerSession
from pants.engine.internals.selectors import Params
from pants.engine.target import RegisteredTargetTypes
from pants.engine.unions import UnionMembership
from pants.help.help_info_extracter import GoalHelpInfo, HelpInfoExtracter
from pants.init.engine_initializer import GraphSession
from pants.option.options import Options


def extract_goals(
    *,
    graph_session: GraphSession,
    scheduler_session: SchedulerSession,
    union_membership: UnionMembership,
    build_config: BuildConfiguration,
    options: Options,
) -> dict[str, GoalHelpInfo]:
    env_name = determine_bootstrap_environment(scheduler_session)
    build_symbols = scheduler_session.product_request(BuildFileSymbolsInfo, [Params(env_name)])[0]
    all_help_info = HelpInfoExtracter.get_all_help_info(
        options,
        union_membership,
        graph_session.goal_consumed_subsystem_scopes,
        RegisteredTargetTypes.create(build_config.target_types),
        build_symbols,
        build_config,
    )

    goal_name_to_goal_info: dict[str, GoalHelpInfo] = {}
    for goal_info in all_help_info.name_to_goal_info.values():
        if goal_info.is_implemented:
            goal_name_to_goal_info[goal_info.name] = goal_info

    return goal_name_to_goal_info


async def setup_and_run_mcp_server(
    *,
    graph_session: GraphSession,
    session: SchedulerSession,
    build_root: Path,
    union_membership: UnionMembership,
    build_config: BuildConfiguration,
    options: Options,
) -> None:
    server: Server = Server("shoalsoft-pants-modelcontext-plugin")

    async def run_test_goal(pants_target_address: str) -> dict[str, Any]:
        specs = SpecsParser(root_dir=str(build_root)).parse_specs(
            [pants_target_address], description_of_origin="MCP run_test_goal tool"
        )

        stdout, stderr = io.StringIO(), io.StringIO()
        console = Console(stdout=stdout, stderr=stderr, use_colors=False, session=session)

        # TODO: Consider whether we need to ensure cwd is build root (like RuleRunner does).
        exit_code = session.run_goal_rule(
            Test,
            Params(
                specs,
                console,
                Workspace(session),
            ),
        )

        return {
            "exit_code": exit_code,
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
        }

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        match name:
            case "pants-run-test-goal":
                if "pants_target_address" not in arguments:
                    raise ValueError(
                        f"Parameter `pants_target_address` is required for tool `{name}`."
                    )
                pants_target_address = arguments.get("pants_target_address")
                if pants_target_address is None or not isinstance(pants_target_address, str):
                    raise ValueError(
                        f"Expected parameter `pants_target_address` for tool `{name}` to be a `str`."
                    )
                return await run_test_goal(pants_target_address)
            case _:
                raise ValueError(f"Unknown tool: {name}")

    @server.list_tools()
    async def list_tools() -> list[mcp_types.Tool]:
        return [
            mcp_types.Tool(
                name="pants-run-test-goal",
                title="Run a Pants test target.",
                description="Runs a Pants test target using the `test` goal.",
                inputSchema={
                    "type": "object",
                    "required": ["pants_target_address"],
                    "properties": {
                        "pants_target_address": {
                            "type": "string",
                            "description": "The address of the Pants target to invoke with the test goal ",
                        }
                    },
                },
                outputSchema={
                    "type": "object",
                    "properties": {
                        "exit_code": {
                            "type": "integer",
                            "description": "The exit code returned by the Pants test goal",
                        },
                        "stdout": {
                            "type": "string",
                            "description": "Standard output captured from running the test goal",
                        },
                        "stderr": {
                            "type": "string",
                            "description": "Standard error output captured from running the test goal",
                        },
                    },
                    "required": ["exit_code", "stdout", "stderr"],
                },
            )
        ]

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
