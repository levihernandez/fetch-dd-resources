# `setup_datadog_export` setup & execution
```bash
# Generate the directory structure
chmod +x setup_datadog_export.sh
./setup_datadog_export.sh               # creates DEV and PROD
./setup_datadog_export.sh site=us5 env='DEV STAGING'   # custom envs

# If selecting a different directory, provide the path under `base=`
./setup_datadog_export.sh site=us5 env='DEV,PROD' base=/tmp/exports
# OR
./setup_datadog_export.sh site=us5 env='sandbox' base=../exports
```

```bash
# Setup the python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run the fetch resources as follows by env only and a single resource, example
python fetch-dd-resources.py SANDBOX "Monitors" base=../ site=us5
# OR download multiple resources, example:
python fetch-dd-resources.py SANDBOX "Dashboards,Monitors" base=../exports site=us5
```