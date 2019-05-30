#!/bin/bash

flake8 punjab

cd tests;export PYTHONPATH=${PWD};trial xep124;trial testparser;trial xep206
