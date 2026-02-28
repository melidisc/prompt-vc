# Installation

## Requirements

- Python 3.10 or higher
- Git (for `diff` and version control features)

## Install with uv (Recommended)

[uv](https://docs.astral.sh/uv/) is the fastest Python package manager:

```bash
uv add prompt-vc
```

## Install with pip

```bash
pip install prompt-vc
```

## Install from Source

For development or to get the latest features:

```bash
git clone https://github.com/melidisc/prompt-vc.git
cd prompt-vc
pip install -e ".[dev]"
```

## Verify Installation

```bash
prompt-vc --version
```

You should see output like:

```
prompt-vc, version 0.1.0
```

## Optional Dependencies

### For Graph Rendering

To render dependency graphs as PNG/SVG/PDF (not just DOT format), install Graphviz:

```bash
# macOS
brew install graphviz

# Ubuntu/Debian
sudo apt install graphviz

# Windows (with Chocolatey)
choco install graphviz
```

### For Documentation Development

To build and preview the documentation locally:

```bash
pip install prompt-vc[docs]
mkdocs serve
```

## Next Steps

- [Quick Start Guide](quickstart.md) - Create your first prompt with metadata
- [CLI Reference](../cli.md) - Full command documentation
