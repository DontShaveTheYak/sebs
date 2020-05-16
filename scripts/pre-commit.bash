#!/usr/bin/env bash

cd "${0%/*}/.."

cd ..

if [ -z $VIRTUAL_ENV ]; then
    source ./venv/bin/activate
fi

echo "Running pre-commit hook"
echo
echo "Linting changed python files"
echo
./scripts/run-lint.bash
# $? stores exit value of the last command
if [ $? -ne 0 ]; then
 echo
 echo "Please lint before commiting."
 exit 1
fi

./scripts/run-tests.bash

# $? stores exit value of the last command
if [ $? -ne 0 ]; then
 echo "Tests must pass before commiting!"
 exit 1
fi
