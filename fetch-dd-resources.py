#!/usr/bin/env python3
import sys
import os
import json
import pathlib
import re
import time
import datetime
import enum
import base64
from typing import Any, Dict, Iterable, List, Tuple

from dotenv import load_dotenv
from datadog_api_client import ApiClient, Configuration

# v1
from datadog_api_client.v1.api.monitors_api import MonitorsApi
from datadog_api_client.v1.api.dashboards_api import DashboardsApi
from datadog_api_client.v1.api.notebooks_api import NotebooksApi
from datadog_api_client.v1.api.service_level_objectives_api import ServiceLevelObjectivesApi
from datadog_api_client.v1.api.tags_api import TagsApi

# v2
from datadog_api_client.v2.api.roles_api import RolesApi
from datadog_api_client.v2.api.users_api import UsersApi
from datadog_api_client.v2.api.teams_api import TeamsApi
from datadog_api_client.v2.api.restriction_policies_api import RestrictionPoliciesApi
from datadog_api_client.v2.api.on_call_api import OnCallApi
from datadog_api_client.v2.api.software_catalog_api import SoftwareCatalogApi

TIMESTAMP = time.strftime("%Y%m%d-%H%M%S")

# ---------- utils ----------

def _json_default(o):
    if isinstance(o, (datetime.datetime, datetime.date)):
        return o.isoformat()
    if isinstance(o, enum.Enum):
        return o.value
    if isinstance(o, (set, frozenset)):
        return list(o)
    if isinstance(o, (bytes, bytearray)):
        return base64.b64encode(o).decode("ascii")
    # datadog models are ModelNormal; try to_dict if present
    if hasattr(o, "to_dict"):
        try:
            return o.to_dict()
        except Exception:
            pass
    return str(o)

def _slugify(text: str, fallback: str = "item") -> str:
    if not text:
        return fallback
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or fallback

def _ensure_dir(p: pathlib.Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def _write_json(base_dir: pathlib.Path, subdir: str, fname: str, obj: Any) -> pathlib.Path:
    outdir = base_dir / subdir
    _ensure_dir(outdir)
    path = outdir / fname
    path.write_text(json.dumps(obj, default=_json_default, indent=2, sort_keys=False))
    print(f"Wrote: {path}")
    return path

def _fname_with_id_name(prefix_id: Any, name: str, default_prefix: str) -> str:
    sid = str(prefix_id) if prefix_id is not None else "unknown"
    return f"{sid}_{_slugify(name, default_prefix)}.json"

# ---------- fetchers ----------

def fetch_monitors(api_client: ApiClient, base_dir: pathlib.Path) -> None:
    api = MonitorsApi(api_client)
    page = 0
    page_size = 100
    total = 0
    while True:
        batch = api.list_monitors(page=page, page_size=page_size)
        items = [m.to_dict() if hasattr(m, "to_dict") else m for m in batch]  # type: ignore
        for m in items:
            mid = m.get("id")
            name = m.get("name") or f"monitor-{mid}"
            _write_json(base_dir, "monitors", _fname_with_id_name(mid, name, "monitor"), m)
            total += 1
        if len(items) < page_size:
            break
        page += 1
    print(f"Monitors exported: {total}")

def fetch_dashboards(api_client: ApiClient, base_dir: pathlib.Path) -> None:
    api = DashboardsApi(api_client)
    # list returns summaries; fetch each full dashboard by id
    summaries = api.list_dashboards()
    dashboards = getattr(summaries, "dashboards", []) or []
    total = 0
    for d in dashboards:
        did = d.get("id") if isinstance(d, dict) else getattr(d, "id", None)
        title = d.get("title") if isinstance(d, dict) else getattr(d, "title", "") or ""
        if not did:
            continue
        full = api.get_dashboard(did)
        payload = full.to_dict() if hasattr(full, "to_dict") else full
        _write_json(base_dir, "dashboards", _fname_with_id_name(did, title, "dashboard"), payload)
        total += 1
    print(f"Dashboards exported: {total}")

def fetch_notebooks(api_client: ApiClient, base_dir: pathlib.Path) -> None:
    api = NotebooksApi(api_client)
    total = 0
    # Some client versions offer pagination; handle both styles
    try:
        resp = api.list_notebooks()
        data = getattr(resp, "data", None)
        items = data if isinstance(data, list) else (resp if isinstance(resp, list) else [])
    except TypeError:
        # Fallback if signature needs args; last resort, try without args again
        resp = api.list_notebooks()
        data = getattr(resp, "data", None)
        items = data if isinstance(data, list) else (resp if isinstance(resp, list) else [])
    for item in items:
        nb_id = item.get("id") if isinstance(item, dict) else getattr(item, "id", None)
        attributes = item.get("attributes", {}) if isinstance(item, dict) else getattr(item, "attributes", {}) or {}
        title = attributes.get("title") if isinstance(attributes, dict) else getattr(attributes, "title", "") or ""
        if not nb_id:
            continue
        full = api.get_notebook(nb_id)
        payload = full.to_dict() if hasattr(full, "to_dict") else full
        _write_json(base_dir, "notebooks", _fname_with_id_name(nb_id, title, "notebook"), payload)
        total += 1
    print(f"Notebooks exported: {total}")

def fetch_roles(api_client: ApiClient, base_dir: pathlib.Path) -> None:
    api = RolesApi(api_client)
    page_size = 100
    page_number = 0
    total = 0
    while True:
        resp = api.list_roles(page_size=page_size, page_number=page_number)
        data = getattr(resp, "data", []) or []
        for r in data:
            rid = r.get("id") if isinstance(r, dict) else getattr(r, "id", None)
            attributes = r.get("attributes", {}) if isinstance(r, dict) else getattr(r, "attributes", {}) or {}
            name = attributes.get("name") if isinstance(attributes, dict) else getattr(attributes, "name", "") or ""
            _write_json(base_dir, "roles", _fname_with_id_name(rid, name, "role"), r)
            total += 1
        if len(data) < page_size:
            break
        page_number += 1
    print(f"Roles exported: {total}")

def fetch_users(api_client: ApiClient, base_dir: pathlib.Path) -> None:
    api = UsersApi(api_client)
    page_size = 100
    page_number = 0
    total = 0
    while True:
        resp = api.list_users(page_size=page_size, page_number=page_number)
        data = getattr(resp, "data", []) or []
        for u in data:
            uid = u.get("id") if isinstance(u, dict) else getattr(u, "id", None)
            attributes = u.get("attributes", {}) if isinstance(u, dict) else getattr(u, "attributes", {}) or {}
            name = attributes.get("name") if isinstance(attributes, dict) else getattr(attributes, "name", "") or ""
            email = attributes.get("email") if isinstance(attributes, dict) else getattr(attributes, "email", "") or ""
            label = name or email or "user"
            _write_json(base_dir, "users", _fname_with_id_name(uid, label, "user"), u)
            total += 1
        if len(data) < page_size:
            break
        page_number += 1
    print(f"Users exported: {total}")

def fetch_teams(api_client: ApiClient, base_dir: pathlib.Path) -> List[Tuple[str, str]]:
    """Returns list of (team_id, team_name)."""
    api = TeamsApi(api_client)
    page_size = 100
    page_number = 0
    total = 0
    out: List[Tuple[str, str]] = []
    while True:
        resp = api.list_teams(page_size=page_size, page_number=page_number)
        data = getattr(resp, "data", []) or []
        for t in data:
            tid = t.get("id") if isinstance(t, dict) else getattr(t, "id", None)
            attributes = t.get("attributes", {}) if isinstance(t, dict) else getattr(t, "attributes", {}) or {}
            name = attributes.get("name") if isinstance(attributes, dict) else getattr(attributes, "name", "") or ""
            _write_json(base_dir, "teams", _fname_with_id_name(tid, name, "team"), t)
            total += 1
            if tid:
                out.append((tid, name or "team"))
        if len(data) < page_size:
            break
        page_number += 1
    print(f"Teams exported: {total}")
    return out

def fetch_on_call(api_client: ApiClient, base_dir: pathlib.Path, teams_cache: List[Tuple[str, str]] = None) -> None:
    """
    Export On-Call routing rules and current on-call responders per team.
    (Schedules/Policies listing may vary by account; we fetch what we can reliably enumerate.)
    """
    api = OnCallApi(api_client)
    teams = teams_cache or fetch_teams(api_client, base_dir)
    total_rr = 0
    total_users = 0
    for team_id, team_name in teams:
        try:
            rr = api.get_on_call_team_routing_rules(team_id)
            payload = rr.to_dict() if hasattr(rr, "to_dict") else rr
            _write_json(base_dir, "on_call", f"team-routing-rules_{team_id}_{_slugify(team_name,'team')}.json", payload)
            total_rr += 1
        except Exception as e:
            print(f"On-Call routing rules failed for team {team_id}: {e}")
        try:
            users = api.get_team_on_call_users(team_id)
            payload = users.to_dict() if hasattr(users, "to_dict") else users
            _write_json(base_dir, "on_call", f"team-oncall-users_{team_id}_{_slugify(team_name,'team')}.json", payload)
            total_users += 1
        except Exception as e:
            print(f"On-Call users failed for team {team_id}: {e}")
    print(f"On-Call exports — routing rules: {total_rr}, on-call users: {total_users}")

def fetch_tags(api_client: ApiClient, base_dir: pathlib.Path) -> None:
    # Host tags snapshot (organization-wide)
    api = TagsApi(api_client)
    resp = api.list_host_tags()  # returns mapping of host->tags
    payload = resp.to_dict() if hasattr(resp, "to_dict") else resp
    _write_json(base_dir, "tags", f"all_host_tags_{TIMESTAMP}.json", payload)
    print("Tags exported: org host tags snapshot written")

def fetch_slos(api_client: ApiClient, base_dir: pathlib.Path) -> None:
    api = ServiceLevelObjectivesApi(api_client)
    total = 0
    # Prefer search endpoint as it's commonly available
    items = []
    try:
        resp = api.search_slo(query="")
        data = getattr(resp, "data", None)
        items = data if isinstance(data, list) else []
    except AttributeError:
        # Fallback to list_slos (older clients)
        try:
            resp = api.list_slos()
            items = getattr(resp, "data", []) or []
        except Exception:
            items = []

    for slo in items:
        sid = slo.get("id") if isinstance(slo, dict) else getattr(slo, "id", None)
        name = None
        # attributes/name may exist depending on shape
        if isinstance(slo, dict):
            name = slo.get("name") or (slo.get("attributes") or {}).get("name")
        else:
            attributes = getattr(slo, "attributes", {}) or {}
            name = getattr(slo, "name", None) or getattr(attributes, "name", None)
        label = name or "slo"
        _write_json(base_dir, "slos", _fname_with_id_name(sid, label, "slo"), slo)
        total += 1
    print(f"SLOs exported: {total}")

def fetch_restriction_policies(api_client: ApiClient, base_dir: pathlib.Path) -> None:
    """
    Pull restriction policies for enumerated resource types we can list:
    dashboards, monitors, notebooks, slos. (Monitors & Dashboards must exist to retrieve.)
    """
    rapi = RestrictionPoliciesApi(api_client)
    # Build a list of (resource_type, id, label)
    resources: List[Tuple[str, str, str]] = []

    # Dashboards
    try:
        dapi = DashboardsApi(api_client)
        summaries = dapi.list_dashboards()
        for d in getattr(summaries, "dashboards", []) or []:
            did = d.get("id") if isinstance(d, dict) else getattr(d, "id", None)
            title = d.get("title") if isinstance(d, dict) else getattr(d, "title", "") or ""
            if did:
                resources.append(("dashboard", did, title or "dashboard"))
    except Exception as e:
        print(f"RestrictionPolicies: skipping dashboards ({e})")

    # Monitors
    try:
        mapi = MonitorsApi(api_client)
        mons = mapi.list_monitors(page=0, page_size=1000)
        for m in mons:
            md = m.to_dict() if hasattr(m, "to_dict") else m  # type: ignore
            mid = md.get("id")
            name = md.get("name") or "monitor"
            if mid:
                resources.append(("monitor", str(mid), name))
    except Exception as e:
        print(f"RestrictionPolicies: skipping monitors ({e})")

    # Notebooks
    try:
        nbapi = NotebooksApi(api_client)
        resp = nbapi.list_notebooks()
        data = getattr(resp, "data", None)
        items = data if isinstance(data, list) else (resp if isinstance(resp, list) else [])
        for item in items:
            nb_id = item.get("id") if isinstance(item, dict) else getattr(item, "id", None)
            attributes = item.get("attributes", {}) if isinstance(item, dict) else getattr(item, "attributes", {}) or {}
            title = attributes.get("title") if isinstance(attributes, dict) else getattr(attributes, "title", "") or ""
            if nb_id:
                resources.append(("notebook", str(nb_id), title or "notebook"))
    except Exception as e:
        print(f"RestrictionPolicies: skipping notebooks ({e})")

    # SLOs
    try:
        sloapi = ServiceLevelObjectivesApi(api_client)
        try:
            resp = sloapi.search_slo(query="")
            data = getattr(resp, "data", None) or []
        except AttributeError:
            resp = sloapi.list_slos()
            data = getattr(resp, "data", []) or []
        for slo in data:
            sid = slo.get("id") if isinstance(slo, dict) else getattr(slo, "id", None)
            name = None
            if isinstance(slo, dict):
                name = slo.get("name") or (slo.get("attributes") or {}).get("name")
            else:
                attributes = getattr(slo, "attributes", {}) or {}
                name = getattr(slo, "name", None) or getattr(attributes, "name", None)
            if sid:
                resources.append(("slo", str(sid), name or "slo"))
    except Exception as e:
        print(f"RestrictionPolicies: skipping slos ({e})")

    # Try On-Call schedule/escalation policies if available via teams (routing rules)
    # RestrictionPolicies supports on-call types, but IDs are not easily enumerable;
    # we’ll at least fetch policies for any team routing rules we can identify.
    try:
        teams = fetch_teams(api_client, base_dir=base_dir)
        ocapi = OnCallApi(api_client)
        for team_id, team_name in teams:
            try:
                rr = ocapi.get_on_call_team_routing_rules(team_id)
                # 'team routing rules' restriction id format
                rid = f"on-call-team-routing-rules:{team_id}"
                label = f"{team_name} routing rules"
                # If a policy exists, write it
                pol = rapi.get_restriction_policy(rid)
                payload = pol.to_dict() if hasattr(pol, "to_dict") else pol
                _write_json(base_dir, "restriction_policies", _fname_with_id_name(rid, label, "oncall-rr"), payload)
            except Exception:
                pass
    except Exception:
        pass

    # Now fetch policies for the collected resource ids
    total = 0
    for rtype, rid, label in resources:
        res_id = f"{rtype}:{rid}"
        try:
            pol = rapi.get_restriction_policy(res_id)
            payload = pol.to_dict() if hasattr(pol, "to_dict") else pol
            _write_json(base_dir, "restriction_policies", _fname_with_id_name(res_id, label, rtype), payload)
            total += 1
        except Exception as e:
            # Not all resources have policies set; skip quietly
            continue
    print(f"Restriction Policies exported: {total} (only those that exist)")

def fetch_software_catalog(api_client: ApiClient, base_dir: pathlib.Path) -> None:
    api = SoftwareCatalogApi(api_client)
    total = 0
    # Paginated iterator provided by client
    try:
        for entity in api.list_catalog_entity_with_pagination():
            # entity has id/ref/name in attributes; try to shape a label
            eid = getattr(entity, "id", None) or (entity.get("id") if isinstance(entity, dict) else None)
            attributes = getattr(entity, "attributes", {}) or (entity.get("attributes") if isinstance(entity, dict) else {})
            name = getattr(attributes, "name", None) if not isinstance(attributes, dict) else attributes.get("name")
            _write_json(base_dir, "software_catalog", _fname_with_id_name(eid, name or "entity", "entity"), entity)
            total += 1
    except TypeError:
        # Older client without iterator: single page
        resp = api.list_catalog_entity()
        data = getattr(resp, "data", []) or []
        for entity in data:
            eid = entity.get("id")
            attributes = entity.get("attributes", {}) or {}
            name = attributes.get("name")
            _write_json(base_dir, "software_catalog", _fname_with_id_name(eid, name or "entity", "entity"), entity)
            total += 1
    print(f"Software Catalog entities exported: {total}")

# ---------- dispatcher ----------

RESOURCE_ALIASES = {
    "dashboards": "dashboards", "dashboard": "dashboards",
    "monitors": "monitors", "monitor": "monitors",
    "notebooks": "notebooks", "notebook": "notebooks",
    "on call": "on_call", "oncall": "on_call",
    "restriction policies": "restriction_policies", "restriction_policies": "restriction_policies",
    "roles": "roles", "role": "roles",
    "tags": "tags",
    "teams": "teams", "team": "teams",
    "users": "users", "user": "users",
    "slos": "slos", "slo": "slos", "service level objectives": "slos",
    "software catalog": "software_catalog", "software_catalog": "software_catalog", "service catalog": "software_catalog",
}

FETCHERS = {
    "dashboards": fetch_dashboards,
    "monitors": fetch_monitors,
    "notebooks": fetch_notebooks,
    "on_call": fetch_on_call,
    "restriction_policies": fetch_restriction_policies,
    "roles": fetch_roles,
    "tags": fetch_tags,
    "teams": fetch_teams,  # note: returns list for on-call; still writes files
    "users": fetch_users,
    "slos": fetch_slos,
    "software_catalog": fetch_software_catalog,
}

def parse_resources_arg(arg: str) -> List[str]:
    wanted = []
    for raw in (arg or "").split(","):
        key = RESOURCE_ALIASES.get(raw.strip().lower())
        if key:
            wanted.append(key)
    return list(dict.fromkeys(wanted))  # dedupe, keep order

def load_env_for(org_label: str, base: str, site_label: str) -> None:
    """
    Load env vars from: <base>/<site_label>_org_<lower_env>/.env
    Example: base='exports', site_label='us5', org_label='SANDBOX'
             -> exports/us5_org_sandbox/.env
    """
    lower_env = org_label.strip().lower()
    env_dir = pathlib.Path(base) / f"{site_label}_org_{lower_env}"
    env_file = env_dir / ".env"

    if not env_file.exists():
        raise SystemExit(
            f"Env file not found: {env_file}\n"
            f"Expected at: {env_dir}\n"
            "Create it (or run your setup script) and try again."
        )

    load_dotenv(dotenv_path=str(env_file), override=True)


def _parse_kv_args(argv):
    """Parse extra CLI args like base=/path site=us5 into a dict."""
    out = {}
    for a in argv:
        if "=" in a:
            k, v = a.split("=", 1)
            out[k.strip().lower()] = v.strip()
    return out

def _site_label_from_dd_site(dd_site: str) -> str:
    """
    Map DD_SITE domain to a short region label used by folder names.
    Falls back to 'custom' if unrecognized.
    """
    dd_site = (dd_site or "").strip().lower()
    # known regions
    if dd_site == "datadoghq.com":
        return "us1"
    if dd_site == "us3.datadoghq.com":
        return "us3"
    if dd_site == "us5.datadoghq.com":
        return "us5"
    if dd_site == "datadoghq.eu":
        return "eu1"
    if dd_site == "ap1.datadoghq.com":
        return "ap1"
    # generic: try to use leftmost label if it looks like 'xxN.datadoghq.com'
    m = re.match(r"^([a-z0-9\-]+)\.datadoghq\.(com|eu)$", dd_site)
    if m and m.group(1) not in ("www",):
        return m.group(1)
    return "custom"


def main():
    if len(sys.argv) < 2:
        print('Usage: python get-resources.py <DEV|PROD|...> "Dashboards,Monitors,..." [base=/path] [site=us5]')
        sys.exit(2)

    org_label = sys.argv[1]
    resources_arg = sys.argv[2] if len(sys.argv) >= 3 else "Monitors"
    extra = _parse_kv_args(sys.argv[3:])

    # Determine base directory and site label BEFORE loading .env
    base_dir_str = extra.get("base", "datadog-api")
    site_label = (extra.get("site") or "us1").lower()

    # Load .env from <base>/<site>_org_<lower_env>/.env
    load_env_for(org_label, base=base_dir_str, site_label=site_label)

    # DD_SITE comes from the env file; if missing, derive from site_label
    dd_site = os.getenv("DD_SITE") or _site_label_from_dd_site(site_label)

    if not os.getenv("DD_API_KEY") or not os.getenv("DD_APP_KEY"):
        raise SystemExit("Please set DD_API_KEY and DD_APP_KEY in your env file.")

    configuration = Configuration()
    configuration.server_variables["site"] = dd_site

    # Output root: <base>/<site>_org_<lower_env>  (matches setup script)
    base_dir = pathlib.Path(base_dir_str)
    root_dir = base_dir / f"{site_label}_org_{org_label.lower()}"
    _ensure_dir(root_dir)

    wanted = parse_resources_arg(resources_arg)
    if not wanted:
        print("No valid resources requested; nothing to do.")
        sys.exit(0)

    print(f"Base: {base_dir} | Site: {dd_site} (label={site_label}) | Org: {org_label} | Resources: {wanted}")

    with ApiClient(configuration) as api_client:
        # Fetch teams first if On Call is requested (to avoid re-listing)
        teams_cache = None
        if "teams" in wanted or "on_call" in wanted:
            teams_cache = fetch_teams(api_client, base_dir=root_dir)
        for key in wanted:
            if key == "teams":
                # already fetched above
                continue
            if key == "on_call":
                fetch_on_call(api_client, base_dir=root_dir, teams_cache=teams_cache or [])
                continue
            func = FETCHERS.get(key)
            if func is None:
                print(f"Unknown resource '{key}', skipping.")
                continue
            func(api_client, base_dir=root_dir)

    print("Done.")

if __name__ == "__main__":
    main()
