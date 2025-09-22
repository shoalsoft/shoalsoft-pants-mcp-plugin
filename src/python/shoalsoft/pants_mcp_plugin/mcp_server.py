# Copyright (C) 2025 Shoal Software LLC. All rights reserved.
#
# This is commercial software and cannot be used without prior permission.
# See the included LICENSE file for further specific terms and conditions.
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
import json
import typing
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from mcp import types as mcp_types
from mcp.server.lowlevel import Server
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.server.stdio import stdio_server
from pydantic.networks import AnyUrl

from pants.base.specs import Specs
from pants.base.specs_parser import SpecsParser
from pants.build_graph.build_configuration import BuildConfiguration
from pants.engine.addresses import Addresses
from pants.engine.console import Console
from pants.engine.environment import EnvironmentName
from pants.engine.fs import Workspace
from pants.engine.goal import Goal
from pants.engine.internals.parser import BuildFileSymbolsInfo
from pants.engine.internals.scheduler import SchedulerSession
from pants.engine.internals.selectors import Params
from pants.engine.rules import QueryRule, Rule
from pants.engine.target import (
    AllTargets,
    RegisteredTargetTypes,
    WrappedTarget,
    WrappedTargetRequest,
)
from pants.engine.unions import UnionMembership
from pants.help.help_info_extracter import GoalHelpInfo, HelpInfoExtracter
from pants.init.engine_initializer import GraphSession
from pants.option.options import Options
from pants.option.options_bootstrapper import OptionsBootstrapper

try:
    from pants.core.environments.rules import (  # type: ignore[import-not-found, unused-ignore]
        determine_bootstrap_environment,
    )
except ImportError:
    from pants.core.util_rules.environments import (  # type: ignore[import-not-found, no-redef, unused-ignore]
        determine_bootstrap_environment,
    )


_PANTS_TARGET_ADDR_SCHEME = "pants-target"


def _determine_available_goals(
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


def _setup_tools(goal_name_to_goal_info: dict[str, GoalHelpInfo]) -> list[mcp_types.Tool]:
    tools: list[mcp_types.Tool] = []
    for goal_name, goal_info in goal_name_to_goal_info.items():
        input_schema = {
            "type": "object",
            "required": ["pants_target_address"],
            "properties": {
                "pants_target_address": {
                    "type": "string",
                    "description": f"The address of the Pants target to invoke with the `{goal_name}` goal ",
                }
            },
        }
        output_schema = {
            "type": "object",
            "properties": {
                "exit_code": {
                    "type": "integer",
                    "description": f"The exit code returned by the Pants `{goal_name}` goal",
                },
                "stdout": {
                    "type": "string",
                    "description": f"Standard output captured from running the Pants `{goal_name}` goal",
                },
                "stderr": {
                    "type": "string",
                    "description": f"Standard error output captured from running the Pants `{goal_name}` goal",
                },
            },
            "required": ["exit_code", "stdout", "stderr"],
        }
        tool = mcp_types.Tool(
            name=f"pants-goal-{goal_name}",
            title=f"Run the Pants `{goal_name}` goal.",
            description=goal_info.description,
            inputSchema=input_schema,
            outputSchema=output_schema,
        )
        tools.append(tool)

    return tools


def _setup_goal_map_from_rules(rules: Iterable[Rule]) -> Mapping[str, type[Goal]]:
    goal_map: dict[str, type[Goal]] = {}
    for rule in rules:
        output_type = getattr(rule, "output_type", None)
        if not output_type or not issubclass(output_type, Goal):
            continue

        goal = output_type.name
        deprecated_goal = output_type.subsystem_cls.deprecated_options_scope
        for goal_name in [goal, deprecated_goal] if deprecated_goal else [goal]:
            if goal_name in goal_map:
                raise Exception(
                    f"could not map goal `{goal_name}` to rule `{rule}`: already claimed by product "
                    f"`{goal_map[goal_name]}`"
                )
            goal_map[goal_name] = output_type
    return goal_map


def get_query_rules() -> Iterable[QueryRule]:
    return [
        QueryRule(AllTargets, ()),
        QueryRule(Addresses, (Specs, OptionsBootstrapper, EnvironmentName)),
        QueryRule(WrappedTarget, (WrappedTargetRequest,)),
    ]


async def setup_and_run_mcp_server(
    *,
    graph_session: GraphSession,
    session: SchedulerSession,
    build_root: Path,
    union_membership: UnionMembership,
    build_config: BuildConfiguration,
    options: Options,
) -> None:
    server: Server = Server("shoalsoft-pants-mcp-plugin")

    goal_name_to_goal_info = _determine_available_goals(
        graph_session=graph_session,
        scheduler_session=session,
        union_membership=union_membership,
        build_config=build_config,
        options=options,
    )

    tools = _setup_tools(goal_name_to_goal_info)
    tools_by_name = {tool.name: tool for tool in tools}
    goal_map = _setup_goal_map_from_rules(build_config.rules)

    async def run_goal(goal_name: str, pants_target_address: str) -> dict[str, Any]:
        env_name = determine_bootstrap_environment(session)

        goal_product = goal_map.get(goal_name)
        if goal_product is None:
            raise ValueError(f"Unknown goal: {goal_name}")

        specs = SpecsParser(root_dir=str(build_root)).parse_specs(
            [pants_target_address], description_of_origin="MCP run_test_goal tool"
        )

        stdout, stderr = io.StringIO(), io.StringIO()
        console = Console(stdout=stdout, stderr=stderr, use_colors=False, session=session)

        # TODO: Consider whether we need to ensure cwd is build root (like RuleRunner does).
        exit_code = session.run_goal_rule(
            goal_product,
            Params(
                specs,
                console,
                Workspace(session),
                env_name,
            ),
        )

        return {
            "exit_code": exit_code,
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
        }

    async def get_pants_target_resources() -> list[mcp_types.Resource]:
        result = session.product_request(AllTargets, [Params()])
        targets: AllTargets = result[0]

        def abs_spec(spec: str) -> str:
            """Make sure the spec is absolute so its URL form is parsed
            correctly."""
            if not spec.startswith("//"):
                return "//" + spec
            return spec

        return [
            mcp_types.Resource(
                name=tgt.address.target_name,
                uri=AnyUrl(f"{_PANTS_TARGET_ADDR_SCHEME}://{abs_spec(str(tgt.address))}"),
                mimeType="text/json",
                description="A JSON document representing the metadata of this Pants target",
            )
            for tgt in targets
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in tools_by_name:
            raise ValueError(f"Unknown tool: {name}")

        goal_name = name.split("-")[2]

        if "pants_target_address" not in arguments:
            raise ValueError(f"Parameter `pants_target_address` is required for tool `{name}`.")
        pants_target_address = arguments.get("pants_target_address")
        if pants_target_address is None or not isinstance(pants_target_address, str):
            raise ValueError(
                f"Expected parameter `pants_target_address` for tool `{name}` to be a `str`."
            )
        return await run_goal(goal_name, pants_target_address)

    @server.list_tools()
    async def list_tools() -> list[mcp_types.Tool]:
        return tools

    @server.list_resources()
    async def list_resources() -> list[mcp_types.Resource]:
        target_resources = await get_pants_target_resources()
        return target_resources

    def resolve_specs_to_addresses(raw_specs: Iterable[str]) -> Addresses:
        specs = SpecsParser(root_dir=str(build_root)).parse_specs(
            specs=raw_specs, description_of_origin=""
        )
        options_bootstrapper = session.py_session.session_values[OptionsBootstrapper]
        env_name = determine_bootstrap_environment(session)
        results = session.product_request(
            Addresses, [Params(specs, options_bootstrapper, env_name)]
        )
        return typing.cast(Addresses, results[0])

    async def read_pants_target_resource(url: AnyUrl) -> Iterable[ReadResourceContents]:
        spec = url.path
        assert spec is not None, "MCP URL must not be empty."
        addresses = resolve_specs_to_addresses([spec])
        if not addresses:
            raise ValueError(f"No Pants target found for `{spec}`")
        if len(addresses) != 1:
            raise ValueError(f"Multiple Pants targets matched spec `{spec}`.")

        results = session.product_request(
            WrappedTarget,
            [WrappedTargetRequest(addresses[0], description_of_origin="MCP server")],
        )
        target = results[0].target
        return [
            ReadResourceContents(
                content=json.dumps(
                    {
                        "alias": target.alias,
                        "address": str(target.address),
                    }
                ),
                mime_type="text/json",
            )
        ]

    @server.read_resource()
    async def read_resource(url: AnyUrl) -> str | bytes | Iterable[ReadResourceContents]:
        if url.scheme == _PANTS_TARGET_ADDR_SCHEME:
            return await read_pants_target_resource(url)

        raise ValueError(f"Unknown resource: {url}")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
