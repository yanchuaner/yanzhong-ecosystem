PYTHON ?= python3.12
VENV := .venv
VENV_PYTHON := $(VENV)/bin/python
SETUP_STAMP := $(VENV)/.governance-ready

.PHONY: setup validate validate-workspace check check-workspace workspace-status workspace-bootstrap clean

setup: $(SETUP_STAMP)

$(SETUP_STAMP): requirements.txt
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install --disable-pip-version-check --require-hashes -r requirements.txt
	$(VENV_PYTHON) -c "import jsonschema, referencing, yaml"
	touch $(SETUP_STAMP)

validate: setup
	$(VENV_PYTHON) docs/validate.py --mode standalone

validate-workspace: setup
	$(VENV_PYTHON) docs/validate.py --mode workspace

check: validate
	git diff --check
	git diff --cached --check

check-workspace: validate-workspace
	$(VENV_PYTHON) scripts/workspace.py diff-check

workspace-status: setup
	$(VENV_PYTHON) scripts/workspace.py status

workspace-bootstrap: setup
	$(VENV_PYTHON) scripts/workspace.py bootstrap

clean:
	rm -rf $(VENV)
