# PROJECT KNOWLEDGE BASE

## OVERVIEW
ROS2 Python package for simple patrol and Nav2 validation. Focused on quick navigation tests without VLM.

## STRUCTURE
```
src/search_logic/
├── search_logic/     # Package code
├── config/           # patrol_params.yaml
├── launch/           # patrol.launch.py
├── test/             # pytest checks
├── setup.py          # console_scripts
└── README.md
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Patrol node | src/search_logic/search_logic/simple_patrol_node.py | State machine + Nav2 client
| Nav2 client | src/search_logic/search_logic/nav2_client.py | Action client wrapper
| Params | src/search_logic/config/patrol_params.yaml | Patrol points + loop
| Launch | src/search_logic/launch/patrol.launch.py | Start node with params

## CONVENTIONS
- Entry point is `simple_patrol_node` in `src/search_logic/setup.py`.
- Tests live in `src/search_logic/test/` and use pytest.

## ANTI-PATTERNS
- Do not change patrol topic names without updating README and tests.
