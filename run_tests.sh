#!/bin/bash
uv run python --version
uv run flake8 punjab

cd tests;export PYTHONPATH=${PWD};uv run trial xep124 testparser xep206
