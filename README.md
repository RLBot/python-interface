# RLBot Python Interface

A high performance Python interface for communicating with RLBot v5.

## Making a bot with this interface

See this video tutorial on YouTube for a quick start guide: <https://www.youtube.com/watch?v=GLqvodQ942A>

Also see the [main RLBot wiki](https://wiki.rlbot.org/) (make sure to avoid info on v4) and also see [this project's wiki](https://github.com/RLBot/python-interface/wiki)

## Dev setup

The following is how to set up a development environment for this project, not how to create a bot using this interface.

- Ensure Python 3.11+ is installed.
- Install [uv](https://docs.astral.sh/uv/).
- Create the environment and install the package with development dependencies:
  - `uv sync --dev`
- Activate the virtual environment when needed:
  - Windows: `.venv\Scripts\activate`
  - Linux: `source .venv/bin/activate`
- Run commands without activating the environment with `uv run`.
- If you are making changes involving the FlatBuffer schema and
  [flatbuffers_python](https://github.com/RLBot/flatbuffers-python),
  also install your local copy of that package in editable mode:
  - `uv pip uninstall rlbot_flatbuffers`
  - `uv pip install --editable <path/to/rlbot_flatbuffers>`

This project is formatted using [Ruff](https://docs.astral.sh/ruff/formatter/).

- Check code: `uv run ruff check .`
- Sort imports: `uv run ruff check --select I --fix`
- Format code: `uv run ruff format`

## Updating dependencies

Use uv to change dependencies and update the lock file.

- Add a runtime dependency: `uv add <package>`.
- Add a development dependency: `uv add --dev <package>`.
- Remove a dependency: `uv remove <package>`.
- Update one dependency: `uv lock --upgrade-package <package>`.
- Update all dependencies: `uv lock --upgrade`.
- Install the locked dependencies: `uv sync --dev`.

## Testing

- Run all pytest tests with `uv run pytest`.
- Test launching a match with `uv run python tests/runner.py`.

## Building

- You can build the package with `python -m build`
  - Note: You might have to `pip install -U build` first
  - `rlbot-5.0.0-py3-none-any.whl` and `rlbot-5.0.0.tar.gz`
  will be created in the `dist` folder
