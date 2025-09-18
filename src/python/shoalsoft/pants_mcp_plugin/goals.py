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

import asyncio
import io
import logging
import os
import sys
from pathlib import Path

from pants.base.exiter import ExitCode
from pants.engine.env_vars import CompleteEnvironmentVars
from pants.engine.goal import CurrentExecutingGoals
from pants.engine.internals.session import SessionValues
from pants.engine.rules import collect_rules
from pants.goal.auxiliary_goal import AuxiliaryGoal, AuxiliaryGoalContext
from pants.option.option_types import BoolOption
from pants.option.options_bootstrapper import OptionsBootstrapper
from shoalsoft.pants_mcp_plugin.mcp_server import get_query_rules, setup_and_run_mcp_server

logger = logging.getLogger(__name__)


class McpGoal(AuxiliaryGoal):
    """Run a MCP server for the current Pants project."""

    name = "shoalsoft-mcp"
    help = 'Run a Model Context Protocol server ("MCP") for the current repository.'

    run_stdio_server = BoolOption(
        default=False,
        advanced=True,
        help="Internal option used to invoke the MCP server. DO NOT USE DIRECTLY!",
    )

    def _run_server(self, context: AuxiliaryGoalContext) -> ExitCode:
        scheduler_session = context.graph_session.scheduler_session.scheduler.new_session(
            build_id="mcp",
            dynamic_ui=False,
            session_values=SessionValues(
                {
                    OptionsBootstrapper: OptionsBootstrapper.create(args=[], env={}),
                    CompleteEnvironmentVars: CompleteEnvironmentVars([]),
                    CurrentExecutingGoals: CurrentExecutingGoals(),
                }
            ),
        )

        saved_stdout = sys.stdout
        saved_stdin = sys.stdin
        try:
            sys.stdout = io.TextIOWrapper(os.fdopen(sys.stdout.fileno(), "wb", buffering=0))
            sys.stdin = io.TextIOWrapper(os.fdopen(sys.stdin.fileno(), "rb", buffering=0))
            asyncio.run(
                setup_and_run_mcp_server(
                    graph_session=context.graph_session,
                    session=scheduler_session,
                    build_root=Path.cwd(),
                    union_membership=context.union_membership,
                    build_config=context.build_config,
                    options=context.options,
                )
            )
        finally:
            sys.stdout = saved_stdout
            sys.stdin = saved_stdin
        return ExitCode(0)

    def run(
        self,
        context: AuxiliaryGoalContext,
    ) -> ExitCode:
        if self.run_stdio_server:
            return self._run_server(context)

        sys.stderr.write("TODO: Easy setup coming soon to this MCP near you!\n")
        return ExitCode(0)


def rules():
    return (
        *collect_rules(),
        *get_query_rules(),
    )
