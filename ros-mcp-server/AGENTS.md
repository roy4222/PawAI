# PROJECT KNOWLEDGE BASE

## OVERVIEW
Standalone Python MCP server for ROS/ROS2 control. Packaged via pyproject.toml with a console script entry point.

## STRUCTURE
```
ros-mcp-server/
├── server.py              # MCP server implementation
├── server.json            # Default registry config
├── pyproject.toml         # Packaging + ruff config
├── utils/                 # Helper modules
├── config/                # Config defaults
├── robot_specifications/  # Robot profiles (.yaml)
├── docs/                  # Installation docs
└── examples/              # Demo scenarios
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| CLI entry | ros-mcp-server/server.py | `main()` used by console script
| Packaging | ros-mcp-server/pyproject.toml | deps + ruff settings
| Robot profiles | ros-mcp-server/robot_specifications/ | YAML specs
| Examples | ros-mcp-server/examples/ | Per-robot demos

## CONVENTIONS
- Ruff is the formatter/linter (line length 100).
- Console script name is `ros-mcp` (pyproject.toml).

## ANTI-PATTERNS
- Do not bypass server.py entry when changing CLI options; keep argument parsing centralized.
- Do not add robot specs without updating server.json if required.
