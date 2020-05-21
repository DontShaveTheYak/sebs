## Setup

To start contributing you will want to create a virtual environment for python3 in the root of the repo with
the name `venv`. Once your virtual environment is activated, install the requirements.

```
pip install -r requirements.txt
```

## Running Tests

### Unit

To run unit tests you have severals options. We recommened you install our pre-commit hook which will run
unit tests every time you commit a change.

```BASH
bash scripts/install-hooks.bash 
```

You can also run the tests by manually by using this script.

```BASH
./scripts/run-tests.bash
```

Or by running the test command.

```BASH
python -m unittest discover -s tests/unit/
```

### Functional
Functional tests will create and destroy resources on AWS. You do not have to run these localy if you
don't want to.

```
python -m unittest discover -s tests/functional/ -f -c
```


### Linting

We use autopep8 to format our files. If you have installed our pre-commit hook then autopep8 will
run everytime you commit changes.

You can also run our linting script.

```
./scripts/run-list.bash
```

Note: If files are found with issues then autopep8 will change those files for you. You will then have
to stage those files again with git.
