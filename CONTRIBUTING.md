# Contributing to CyberScout AI

Thank you for your interest in contributing to CyberScout AI! We welcome contributions from developers, security researchers, technical writers, and testers.

---

## 📜 Code of Conduct

All contributors must adhere to our [Code of Conduct](CODE_OF_CONDUCT.md). Please read it before participating.

---

## 🌿 Git Branching Model

- `main`: Production release branch. Must remain stable and tested.
- `feature/<feature-name>`: Development branch for new features or subsystems (e.g. `feature/plugin-framework`).
- `fix/<bug-description>`: Branch for bug fixes (e.g. `fix/rss-parser-timeout`).

---

## 📝 Commit Message Conventions

We follow Conventional Commits format:

```text
<type>(<scope>): <short summary>

[optional body description]
```

Types:
- `feat`: New feature or capability
- `fix`: Bug fix
- `docs`: Documentation updates
- `test`: Adding or updating test cases
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `chore`: Repository maintenance or configuration changes

Example:
```bash
git commit -m "feat(collectors): add custom parser for RSS feeds"
```

---

## 🧪 Testing Guidelines

- Every code change must include corresponding unit tests in `tests/unit/`.
- Ensure all automated tests pass prior to submitting a Pull Request:
```bash
python -m unittest discover -s tests/unit
```
- Ensure zero memory leaks and proper resource cleanup.

---

## 📥 Pull Request (PR) Checklist

1. Fork repository and create your feature branch from `main`.
2. Ensure code follows PEP 8 guidelines and SOLID design principles.
3. Write/update unit tests for all modified logic.
4. Run `python -m unittest discover -s tests/unit` (100% pass rate required).
5. Open a Pull Request using our [PR Template](.github/pull_request_template.md).
