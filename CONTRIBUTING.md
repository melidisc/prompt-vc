# Contributing to prompt-vc

Thank you for your interest in contributing!

## Development Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/prompt-vc.git
cd prompt-vc

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check .
mypy src/
```

## Project Structure

```
prompt-vc/
├── src/prompt_vc/     # Main package
│   ├── __init__.py
│   ├── cli.py         # CLI commands
│   ├── models.py      # Pydantic schemas
│   └── hashing.py     # Content hashing utilities
├── docs/              # Documentation
├── examples/          # Example prompts and manifests
├── tests/             # Test suite
└── pyproject.toml     # Package configuration
```

## Making Changes

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## Code Style

- Use [ruff](https://github.com/astral-sh/ruff) for linting
- Use type hints throughout
- Follow existing patterns in the codebase

## Adding CLI Commands

1. Add the command to `src/prompt_vc/cli.py`
2. Document it in `docs/cli.md`
3. Add tests in `tests/test_cli.py`

## Schema Changes

If modifying the meta or manifest schemas:

1. Update `src/prompt_vc/models.py`
2. Update the corresponding doc in `docs/`
3. Update examples if needed
4. Consider backward compatibility

## Questions?

Open an issue for discussion.
