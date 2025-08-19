# rebuild conda environment
conda deactivate
conda env remove -n nitools -y
conda env create -f environment.yml
conda activate nitools