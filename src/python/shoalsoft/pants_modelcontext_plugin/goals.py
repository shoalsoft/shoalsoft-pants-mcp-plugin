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

import logging
import sys

from pants.base.exiter import ExitCode
from pants.engine.rules import collect_rules
from pants.goal.auxiliary_goal import AuxiliaryGoal, AuxiliaryGoalContext

logger = logging.getLogger(__name__)


class McpGoal(AuxiliaryGoal):
    """Run a MCP server for the current Pants project."""

    name = "shoalsoft-mcp"
    help = 'Run a Model Context Protocol server ("MCP") for the current repository.'

    def run(
        self,
        context: AuxiliaryGoalContext,
    ) -> ExitCode:
        sys.stdout.write("MCP goal says hello.\n")
        return ExitCode(0)


def rules():
    return collect_rules()
