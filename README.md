# ARM64 Android environment bootstrap

Toolchain validation only. This repository contains no Risk of Rain 2 assets or assemblies.

Start with [the environment report](environment/ENVIRONMENT_REPORT.md).

```sh
./scripts/doctor.sh
./scripts/doctor.sh --json
```

Isolated, disposable Unity project: `smoke/`, Unity **2021.3.33f1**, IL2CPP ARM64.

```sh
./scripts/build-smoke.sh
python3 scripts/smoke-device.py
```

The device script installs only `dev.localbootstrap.arm64smoke`, records logs and a screenshot, and removes that package afterwards. It refuses to overwrite a pre-existing package. It never changes storage settings or other applications.

Tool wrappers: `scripts/assetripper`, `scripts/ilspycmd`. MCP server: `scripts/mcp-server.sh` (loopback port 8080); keep the smoke project open and connect through Window > MCP for Unity. Probe with `.local/tools/unity-mcp/Server/.venv/bin/python scripts/mcp-check.py`.

Local downloads, proprietary files, build outputs, editor caches, and credentials must remain outside Git. See `.gitignore`.
