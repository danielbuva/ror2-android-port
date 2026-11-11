# Agent Directives

Guidance for automated agents operating on this repository.

1. **Architecture Target**: All native, Unity, and Android packaging targets use **x64 (`x86_64`)**.
2. **CI Workflow**: Keep `.github/workflows/build-apk.yml` as the single GitHub Actions workflow so that GitHub Actions builds only the x64 APK.
3. **Format Standard**: All C# code conforms to `.clang-format` (Microsoft C# style, 140 column limit). All Python code conforms to `ruff.toml`.
