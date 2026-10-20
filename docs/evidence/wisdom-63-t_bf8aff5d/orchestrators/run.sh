#!/bin/bash
R=$HOME/.hermes/cache/scratch/w63/rerun
n=$1; home=$2
cd $R/work-$n && env HERMES_HOME=$R/home-$home hermes chat -Q --source tool --max-turns 80 --run-budget 1800 --query-file request.md > $R/orch-$n.out 2>&1; echo "EXIT=$?" >> $R/orch-$n.out
