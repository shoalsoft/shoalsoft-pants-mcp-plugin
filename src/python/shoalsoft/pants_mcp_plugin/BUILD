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

PLUGIN_VERSION = "0.1.0.dev1"

PANTS_MAJOR_MINOR_VERSIONS = ["2.29", "2.28", "2.27"]

python_sources(
    sources=["*.py", "!*_test.py", "!*_integration_test.py"],
    **parametrize(
        "pants-2.29",
        resolve="pants-2.29",
    ),
    **parametrize(
        "pants-2.28",
        resolve="pants-2.28",
    ),
    **parametrize(
        "pants-2.27",
        resolve="pants-2.27",
    ),
)


python_tests(
    name="integration_tests",
    sources=["*_integration_test.py"],
    runtime_package_dependencies=[
        *(f":pex-{pants_version}" for pants_version in PANTS_MAJOR_MINOR_VERSIONS),
        *(
            f":pants-for-tests@parametrize=pants-{pants_version}"
            for pants_version in PANTS_MAJOR_MINOR_VERSIONS
        ),
    ],
    # Integration tests take forever given how they are run. :(
    timeout=600,
)

pex_binary(
    name="pants-for-tests",
    entry_point="pants",
    execution_mode="venv",
    layout="zipapp",
    **parametrize(
        "pants-2.29",
        resolve="pants-2.29",
        dependencies=["3rdparty/python:pants-2.29#pantsbuild.pants"],
        output_path="pants-2.29.pex",
    ),
    **parametrize(
        "pants-2.28",
        resolve="pants-2.28",
        dependencies=["3rdparty/python:pants-2.28#pantsbuild.pants"],
        output_path="pants-2.28.pex",
    ),
    **parametrize(
        "pants-2.27",
        resolve="pants-2.27",
        dependencies=["3rdparty/python:pants-2.27#pantsbuild.pants"],
        output_path="pants-2.27.pex",
    ),
)


def declare_pex_artifact(pants_major_minor_version):
    pex_binary(
        name=f"pex-{pants_major_minor_version}",
        output_path=f"shoalsoft-pants-mcp-plugin-pants{pants_major_minor_version}-v{PLUGIN_VERSION}.pex",
        interpreter_constraints=(f"==3.11.*",),
        dependencies=[
            f"./register.py@parametrize=pants-{pants_major_minor_version}",
            # Exclude Pants and its transitive dependencies since the Pants will supply those
            # dependencies itself from its own venv.
            f"!!3rdparty/python:pants-{pants_major_minor_version}#pantsbuild.pants",
        ],
        include_tools=True,
        resolve=f"pants-{pants_major_minor_version}",
    )


for pants_version in PANTS_MAJOR_MINOR_VERSIONS:
    declare_pex_artifact(pants_version)


# This is a partial copy of the README.md geared more for the PyPI UX.
LONG_DESCRIPTION = """\
# Pantsbuild Model Context Protocol Plugin

## Installation

From PyPI:

1. In the relevant Pants project, edit `pants.toml` to set the `[GLOBAL].plugins` option to include `shoalsoft-pants-mcp-plugin==VERSION` (replacing `VERSION` with the applicable version) and the `[GLOBAL].backend_packages` option to include `shoalsoft.pants_mcp_plugin`.

2. Confogure your LLM coding agent to invoke `pants shoalsoft-mcp --run-stdio-server` in the repository as follows:

  - [Claude Code setup](https://docs.claude.com/en/docs/claude-code/mcp#option-1%3A-add-a-local-stdio-server)
  - [ChatGPT Codex setup](https://github.com/openai/codex/blob/main/docs/advanced.md#model-context-protocol-mcp)

## Licensing

This project is commercial software subject [to a license](https://github.com/shoalsoft/shoalsoft-pants-mcp-plugin/blob/main/LICENSE).

Permission is granted for personal, non-commercial use and for commercial evaluation, but not regular commercial use (which includes using the project for software development workflows in a commercial setting) without explicit permission.
"""

# Add a single wheel which is not specific to any particular Pants version.
python_distribution(
    name=f"wheel",
    interpreter_constraints=[f"==3.11.*"],
    provides=setup_py(
        name="shoalsoft-pants-mcp-plugin",
        description=f"Pantsbuild Model Context Protocol Plugin from Shoal Software LLC",
        long_description=LONG_DESCRIPTION,
        long_description_content_type="text/markdown",
        python_requires=f"==3.11.*",
        version=PLUGIN_VERSION,
        author="Tom Dyas",
        author_email="tom@shoalsoftware.com",
        url="https://github.com/shoalsoft/shoalsoft-pants-mcp-plugin",
    ),
    dependencies=[
        f"./register.py@parametrize=pants-2.29",
        # Exclude Pants and its transitive dependencies since the Pants will supply those
        # dependencies itself from its own venv.
        f"!!3rdparty/python:pants-2.29#pantsbuild.pants",
    ],
)
