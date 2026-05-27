#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --nodes=1
#SBATCH --ntasks=32
#SBATCH --time=24:00:00

set -euo pipefail
cd "{workdir}"
{command}
