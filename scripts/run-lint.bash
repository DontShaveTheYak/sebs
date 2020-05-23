#!/usr/bin/env bash

# if any command inside script returns error, exit and return that error 
set -e

# magic line to ensure that we're always inside the root of our application,
# no matter from which directory we'll run script
# thanks to it we can just enter `./scripts/run-tests.bash`
cd "${0%/*}/.."

if(git diff --cached --name-only --diff-filter=AM HEAD | grep 'py')
then
    if !(git diff --cached --name-only --diff-filter=AM HEAD | grep 'py' | xargs -P 10 -n1 autopep8 --in-place --exit-code)
    then
        echo
        echo "Error: You attempted to commit one or more python files with format errors."
        echo
        echo "Please fix them and retry the commit."
        echo
        exit 1
    fi
    exit 0
fi

echo "No modified python files to lint"
