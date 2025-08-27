conda activate nitools

# Set PYTHONPATH to include the 'src' directory for module discovery
$env:PYTHONPATH = (Join-Path $PSScriptRoot "src")

python ./src/launcher.py