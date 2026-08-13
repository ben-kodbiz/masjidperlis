# CONTRIBUTING.md

Thank you for considering contributing to Masjid Events Perlis.

## Ground rules

- Keep the project **lightweight**: vanilla HTML/CSS/JS, JSON, and Python.
- Do **not** introduce frameworks (React, Vue, Tailwind, etc.) without a compelling reason and discussion.
- Never commit secrets, tokens, passwords, or keys.
- The public site must stay static, read-only, and deployable to GitHub Pages.
- Google (Sheets, Maps, auth) must remain an optional adapter, never a core dependency.

## Working model

The project is built **stage-by-stage**; see `TODO_AGENT.md` for the roadmap and definitions of done.

1. Read `ARCHITECTURE.md` and `TODO_AGENT.md`.
2. Check the current stage in `TODO_AGENT.md`.
3. Implement only the current stage.
4. Run validation/tests.
5. Update documentation.
6. Mark the stage complete in `TODO_AGENT.md`.

## Getting started

```bash
# generate masjid/event detail pages, then serve the public site locally
python3 tools/build_site.py
python3 -m http.server 8000 --directory public

# validate the data
python3 tools/validate_data.py
```

## Running the checks

Everything CI runs can be run locally:

```bash
python3 tools/validate_data.py          # canonical data
python3 tests/test_validate.py          # Python test suites (validate,
python3 tests/test_build_site.py        #   build, admin, import, federate,
python3 tests/test_admin.py             #   a11y, perf, security)
python3 tests/test_import_sheet.py
python3 tests/test_federate.py
python3 tests/test_a11y.py
python3 tests/test_perf.py
python3 tests/test_security.py
node tests/test_*.js                    # JS module tests
python3 tools/perf_report.py            # performance budget gate
python3 tools/security_audit.py         # security audit
```

## Pull requests

- Keep changes focused and small.
- Add meaningful commit messages.
- Ensure data validation passes and the existing public site still works.
- Update relevant documentation.

## Reporting issues

- Clearly describe the problem, steps to reproduce, and expected behavior.
- For security issues, follow `SECURITY.md` instead of opening a public issue.

## Code of conduct

Be respectful and constructive. Harassment or discrimination is not tolerated.