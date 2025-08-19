# fetch-dd-resources

* Run `./setup_datadog_export.sh site=us5 env='DEV,PROD' base=/tmp/exports` to initialize the project(s)
* Run `python fetch-dd-resources.py SANDBOX "Dashboards,Monitors" base=../exports site=us5` to download dashboard, monitors, etc.