#!/bin/bash -l
#SBATCH --job-name={job_name}
#SBATCH --output=out.%j
#SBATCH --error=err.%j
#SBATCH --nodes={nodes}
#SBATCH --ntasks={ntasks}
#SBATCH --cpus-per-task=1

set -euo pipefail

export OMP_NUM_THREADS=${OMP_NUM_THREADS:-1}
ulimit -s unlimited

echo "--------------------------------"
echo "Job started at $(date)"
echo "Running on node(s): ${SLURM_NODELIST:-unknown}"
echo "Using total tasks: ${SLURM_NTASKS:-unknown}"
echo "Working directory: $(pwd)"
echo "--------------------------------"

mpirun {command}

echo "Simulation finished at $(date)"
