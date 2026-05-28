# Contributing to GalleryControl

Thank you for your interest in contributing to GalleryControl!

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/gallerycontrol.git`
3. Create a branch: `git checkout -b feature/your-feature`
4. Make your changes
5. Run tests: `cd gallerycontrol && poetry run pytest`
6. Commit: `git commit -m "Add your feature"`
7. Push: `git push origin feature/your-feature`
8. Open a Pull Request

## Development Setup

```bash
# Install dependencies
cd gallerycontrol
poetry install

# Run the development server
poetry run uvicorn gallerycontrol.main:app --reload

# Run tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=gallerycontrol
```

## Code Style

- We use [Black](https://github.com/psf/black) for Python formatting
- We use [Ruff](https://github.com/astral-sh/ruff) for linting
- Line length: 100 characters
- Type hints are encouraged

```bash
# Format code
poetry run black .

# Lint code
poetry run ruff check .
```

## Pull Request Guidelines

- Keep PRs focused on a single change
- Update documentation if needed
- Add tests for new features
- Ensure all tests pass
- Follow the existing code style

## Reporting Issues

When reporting issues, please include:

- GalleryControl version
- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs or error messages

## Adding Device Support

To add support for a new device type:

1. Create a new manager in `gallerycontrol/devices/`
2. Implement the `DeviceManager` base class
3. Register the device type in the orchestrator
4. Add tests in `tests/unit/`
5. Update documentation

## Questions?

Open an issue with the "question" label or reach out to the maintainers.
