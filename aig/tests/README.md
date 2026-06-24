# AIG Test Suite

This directory contains the baseline automated test suite for AIG using `pytest`.

## Scope

- Unit tests for image decoration helpers in `aig/src/imgproc/img_frame.py`.
- Unit tests for utility helpers in `aig/src/database/utils.py`.
- Unit tests for metadata/environment parsing and image file helpers in `aig/src/database/version.py`.
- API endpoint tests for `aig/src/server/apis/*` using Flask test client and mocked ASE backends.
- Endpoint security tests covering method restrictions, malformed payload rejection, and injection-like path/query handling.

The tests are designed to run without requiring OpenVINO models or a running ChromaDB instance.

## Install test dependencies

From repository root:

```bash
python3 -m pip install -r aig/requirements-test.txt
```

If Flask dependencies are missing, API tests are skipped automatically.

## Run tests

From repository root:

```bash
pytest -q
```

To run only AIG tests explicitly:

```bash
pytest -q aig/tests
```

To run with concise failure output:

```bash
pytest -q --tb=no aig/tests/
```

## Run coverage

From repository root:

```bash
pytest --cov=aig/src --cov-report=term-missing aig/tests/
```

Quiet mode with no traceback details:

```bash
pytest --cov=aig/src --cov-report=term-missing aig/tests/ -q --tb=no
```

Generate HTML coverage report:

```bash
pytest --cov=aig/src --cov-report=html --cov-report=term-missing aig/tests/
```

The HTML report is written to:

```bash
htmlcov/index.html
```
