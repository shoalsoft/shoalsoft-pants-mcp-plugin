# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Pants plugin that provides a Model Context Protocol (MCP) server for Pants repositories. The plugin allows LLM agents to interact with Pants build system through MCP protocol, currently serving over stdio.

## Architecture

The plugin follows Pants' standard plugin architecture:

- **`register.py`**: Entry point that registers the plugin's goals and rules with Pants
- **`goals.py`**: Contains `McpGoal` - an auxiliary goal that runs the MCP server
- **`__init__.py`**: Standard Python package initialization

The MCP server is implemented using the `mcp` Python library and serves over stdio (standard input/output) rather than HTTP, making it suitable for direct integration with MCP clients.

## Development Commands

This project uses Pants as its build system. Key commands:

**Testing:**
```bash
pants test ::
```

**Linting and Formatting:**
```bash
pants lint ::          # Run all linters (flake8, black, isort, docformatter)
pants fmt ::           # Auto-format code with black and isort
pants check ::         # Run mypy type checking
```

**Building:**
```bash
pants package ::       # Build the plugin
```

## Configuration

- Python version: 3.11 (specified in `pants.toml`)
- Dependencies managed through Pants resolves in `3rdparty/python/`
- Main resolve: `pants-2.27` (includes MCP dependencies)
- Test resolve: `pytest`
- Type checking resolve: `mypy`

## Code Style

- Line length: 100 characters
- Black code formatting
- isort import sorting with black profile
- flake8 linting with custom config in `build-support/flake8/.flake8`
- Full mypy type checking with strict settings

## Key Implementation Details

The MCP server in `goals.py`:
- Extends `AuxiliaryGoal` to integrate with Pants goal system
- Uses async/await pattern with `stdio_server` from mcp library
- Currently implements a minimal server with empty tools list
- Server name: "shoalsoft-pants-modelcontext-plugin"


## Development Workflow

- When testing changes, first check formatting, linting, and type checking via the Pants `fmt`, `lint`, and `check` goals respectively. Then run tests using the Pants `test` goal. Do not attempt to run tests directly using `pytest` since Pants supplies the execution environment; instead use the Pants `test` goal. Also do not attempt to run mypy directly; instead use the Pants `check` goal.