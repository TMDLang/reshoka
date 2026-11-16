#!/bin/sh
set -e

if [ ! -d "venv" ]; then
  python3 -m venv venv
  . venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
else
  . venv/bin/activate
fi

exec mkdocs serve --dirty "$@"
