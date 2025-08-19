# fetch-dd-resources

* Run `git clone https://github.com/levihernandez/fetch-dd-resources.git`
* Run `./setup_datadog_export.sh site=us5 env='DEV,PROD' base=/tmp/exports` to initialize the project(s)
* Update the APP and API keys in `exports/<project name>/.env` 
* Run `python fetch-dd-resources.py SANDBOX "Dashboards,Monitors" base=../exports site=us5` to download dashboard, monitors, etc.