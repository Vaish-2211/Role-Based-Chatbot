# Activate venv
source .venv/bin/activate  

# Run all unit tests (verbose — shows each test name)
.venv/bin/python -m pytest tests/unit/ -v

# Run just the auth tests
.venv/bin/python -m pytest tests/unit/test_auth.py -v

# Run just the RBAC tests
.venv/bin/python -m pytest tests/unit/test_rbac.py -v

# Run a single specific test by name
.venv/bin/python -m pytest tests/unit/test_auth.py::test_create_and_decode_token -v