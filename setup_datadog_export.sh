#!/usr/bin/env bash
set -euo pipefail

# Defaults
SITE="us1"
ENVS="DEV,PROD"
BASE="datadog-api"   # parent "container" dir; inside it we create <site>_org_<env>

# Parse key=value args
for arg in "$@"; do
  case "$arg" in
    site=*) SITE="${arg#site=}" ;;
    env=*)  ENVS="${arg#env=}" ;;
    base=*) BASE="${arg#base=}" ;;
    *)
      echo "Ignoring unrecognized arg: $arg" >&2
      ;;
  esac
done

# Region -> DD_SITE mapping
case "$SITE" in
  us1) DD_SITE="datadoghq.com" ;;
  us3) DD_SITE="us3.datadoghq.com" ;;
  us5) DD_SITE="us5.datadoghq.com" ;;
  eu1) DD_SITE="datadoghq.eu" ;;            # bonus: common extra
  *)
    echo "Warning: unknown site '$SITE'. Using as-is for DD_SITE." >&2
    DD_SITE="$SITE"
    ;;
esac

RESOURCES=(
  dashboards
  monitors
  notebooks
  on_call
  restriction_policies
  roles
  tags
  teams
  users
  slos
  software_catalog
)

mkdir -p "$BASE"

# Split envs by comma, trim whitespace
IFS=',' read -r -a ENV_ARR <<< "$ENVS"

for raw in "${ENV_ARR[@]}"; do
  ENV="$(echo "$raw" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  [ -z "$ENV" ] && continue
  lower_env="$(echo "$ENV" | tr '[:upper:]' '[:lower:]')"

  project_dir="${BASE}/${SITE}_org_${lower_env}"     # e.g., datadog-api/us5_org_sandbox
  env_file="${project_dir}/.env"                    # e.g., sandbox-org.env

  echo "----"
  echo "Setting up: site=${SITE} (DD_SITE=${DD_SITE}) env=${ENV}"
  echo "Project dir: ${project_dir}"
  mkdir -p "${project_dir}"

  # Resource subfolders
  for r in "${RESOURCES[@]}"; do
    mkdir -p "${project_dir}/${r}"
  done

  # .env creation/update
  if [ -f "${env_file}" ]; then
    echo "Env file exists, updating DD_SITE: ${env_file}"
    if ! grep -q '^DD_SITE=' "${env_file}"; then
      printf "\nDD_SITE=%s\n" "${DD_SITE}" >> "${env_file}"
    else
      # Replace DD_SITE=... in-place (portable-ish with backup)
      sed -i.bak -E "s|^DD_SITE=.*$|DD_SITE=${DD_SITE}|g" "${env_file}" && rm -f "${env_file}.bak"
    fi
  else
    cat > "${env_file}" <<EOF
# ${ENV} Datadog org credentials for region ${SITE}
# Get your API and APP keys from Datadog: https://docs.datadoghq.com/account_management/api-app-keys/?site=${SITE}
# Use with:  python fetch-dd-resources.py ${ENV} "Dashboards,Monitors" base=../exports site=us1"
DD_SITE=${DD_SITE}
DD_API_KEY=__REPLACE_ME__
DD_APP_KEY=__REPLACE_ME__

# Optional proxy/certs
# HTTP_PROXY=
# HTTPS_PROXY=
# DD_CA_BUNDLE=
EOF
    chmod 600 "${env_file}"
    echo "Created ${env_file} (chmod 600)."
  fi
done

echo "----"
echo "Done."
echo "Base directory: ${BASE}"
echo "Created/verified project(s):"
find "${BASE}" -maxdepth 1 -type d -name "${SITE}_org_*" -print | sort
echo "You can now run: "
echo "  python fetch-dd-resources.py sandbox \"Dashboards,Monitors\" base=${BASE} site=${SITE}"
echo "----"
