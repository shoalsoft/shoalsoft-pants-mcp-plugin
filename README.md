# Pantsbuild Model Context Protocol Plugin

## Overview

This project is an **experimental** plugin to the [Pantsbuild](https://pantsbuild.org/) build orchestration tool to expose a Model Contect Protocol ("MCP") server for LLM coding agents to interact with.

## Installation

From PyPI:

1. In the relevant Pants project, edit `pants.toml` to set the `[GLOBAL].plugins` option to include `shoalsoft-pants-mcp-plugin==VERSION` (replacing `VERSION` with the applicable version) and the `[GLOBAL].backend_packages` option to include `shoalsoft.pants_mcp_plugin`.

2. Confogure your LLM coding agent to invoke `pants shoalsoft-mcp --run-stdio-server` in the repository as follows:

  - [Claude Code setup](https://docs.claude.com/en/docs/claude-code/mcp#option-1%3A-add-a-local-stdio-server)
  - [ChatGPT Codex setup](https://github.com/openai/codex/blob/main/docs/advanced.md#model-context-protocol-mcp)

## Usage

If the MCP server is started correctly by your LLM coding agent, then the agent should take advantage of the exposed MCP tools, which include a tool for each Pants goals.

## Development

### Workflow

- Run formating and type checks (mypy): `pants fmt lint check ::`

- Run tests: `pants test ::`

### Building

TBD

## License

This is currently commercial software and requires prior permission to use. See the [LICENSE](./LICENSE) file in this repository for specific details.
