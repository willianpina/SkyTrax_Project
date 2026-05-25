# Contributing to SkyTrax Airline Intelligence Platform

Thank you for your interest in contributing. This document outlines the process for contributing to this project.

## Reporting Bugs

Open a [bug report issue](../../issues/new?template=bug_report.md) with the following details:

- A clear and descriptive title.
- Steps to reproduce the issue.
- Expected vs. actual behavior.
- Environment details (OS, Python version, Docker version, browser).
- Relevant logs or screenshots.

## Suggesting Features

Open a [feature request issue](../../issues/new?template=feature_request.md) describing:

- The problem the feature would solve.
- Your proposed solution.
- Any alternatives you considered.

## Development Setup

1. Clone the repository:

```bash
git clone https://github.com/willianpina/SkyTrax_Project.git
cd SkyTrax_Project
```

2. Copy the environment file:

```bash
cp .env.example .env
```

3. Start the full stack using Make:

```bash
make build
make up
```

4. Run database migrations:

```bash
make migrate
```

See the `Makefile` for all available commands (`make help`).

## Code Style

- **Python**: This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting. Run checks locally before submitting a PR:

```bash
ruff check .
ruff format .
```

- **JavaScript/TypeScript**: Follow the ESLint configuration in the `frontend/` directory.
- Keep functions focused and well-named. Avoid unnecessary abstractions.

## Pull Request Process

1. Fork the repository and create a branch from `main`.
2. Name your branch descriptively: `fix/scraper-timeout`, `feat/airline-comparison`, etc.
3. Make your changes in small, focused commits following [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` new feature
   - `fix:` bug fix
   - `docs:` documentation only
   - `refactor:` code restructuring without behavior change
   - `test:` adding or updating tests
   - `chore:` maintenance tasks
4. Ensure all existing tests pass and add tests for new functionality.
5. Run linting and formatting before pushing.
6. Open a pull request against `main` using the provided PR template.
7. Address review feedback promptly.

## Commit Messages

Follow the Conventional Commits specification:

```
feat(scraper): add retry logic for rate-limited requests
fix(api): correct pagination offset in reviews endpoint
docs: update deployment instructions in README
```

## Code of Conduct

All contributors are expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
