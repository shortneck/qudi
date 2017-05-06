#!/bin/bash

function test_notebook () {
    let "total += 1"
    jupyter-nbconvert --execute $1;
    grep '<div.*output_stderr' `basename $1 .ipynb`".html"
    retcode=$?

    if ! kill -0 $QUDIPID; then
        echo "Test run has failed: $QUDIPID not here" >&2
        print_log
        exit 1
    fi;

    if [ $retcode -ne 0 ]; then
        return 0;
    else
        let "failed += 1"
        echo "Failed / Total: $failed / $total"
        return 1;
    fi;
}

function print_log () {
    echo "======== Qudi Logfile ========"
    cat qudi.log

    if [ -e crash.log ]; then
        echo "======== Qudi Crashfile ========"
        cat crash.log
    fi
}

if [[ $(python --version 2>&1) == *"2.7"* ]]; then
    PYCMD=python3
else
    PYCMD=python
fi

$PYCMD start.py &
QUDIPID=$!

sleep 10

if ! kill -0 $QUDIPID; then
    echo "Start has failed: $QUDIPID not here" >&2
    print_log
    exit 1
fi

jupyter-nbconvert --execute notebooks/debug.ipynb

total=0
failed=0

test_notebook notebooks/matplotlib.ipynb
test_notebook notebooks/fit_testing_exponential.ipynb
test_notebook notebooks/fit_testing_gaussian.ipynb
test_notebook notebooks/fit_testing_lorentzian.ipynb
test_notebook notebooks/fit_testing_N14.ipynb
test_notebook notebooks/fit_testing_N15.ipynb
test_notebook notebooks/fit_testing_poissonian.ipynb
test_notebook notebooks/fit_testing_sine.ipynb


jupyter-nbconvert --execute notebooks/shutdown.ipynb

sleep 20

if kill $QUDIPID; then
    echo "Shutdown has failed: $QUDIPID was killed" >&2
    print_log
    exit 1
fi

grep "^....-..-.. ..:..:.. error" qudi.log
if [ $? -eq 0 ]; then
    let "failed += 1"
fi

exit $failed

