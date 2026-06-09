#!/bin/bash

export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0}
export MACE_TIME=true

mpirun -np 1 /path/to/lmp -k on g 1 -sf kk -pk kokkos newton on neigh half -in in.run_mace_npt
