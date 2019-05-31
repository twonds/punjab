#!/bin/bash
python --version
flake8 punjab

cd tests;export PYTHONPATH=${PWD};trial xep124 testparser xep206

