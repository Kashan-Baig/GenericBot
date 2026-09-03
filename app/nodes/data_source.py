"""Data Source node.

Lets a flow pull records from a controlled, credential-backed source
(PostgreSQL, MySQL, a REST API, or a CSV file) and expose them to later
nodes as plain JSON — a list of dicts under a variable name — instead of
handing raw database access to the LLM. This mirrors the "DataSource / Tool
interface" architecture: every source type below implements the same
contract (config + credential in, ``List[Dict[str, Any]]`` out), so adding a
new source later (MongoDB, Google Sheets, vector stores, ...) means adding
another branch here, not reshaping the node or the executor.

Security notes:
  * DB/API secrets are never read from the node config. They live only in
    the encrypted Credential Manager (app/storage/credentials.py) and are
    looked up by ``credential_id`` at execution time.
  * Table/column identifiers used to build SQL are validated against a
    strict allow-list pattern; only the WHERE-clause *values* are passed as
    bound parameters. Raw SQL is only ever run if the flow author explicitly
    supplies a ``query``, which is an intentional power-user escape hatch,
    not something reachable from end-user chat input.
  * CSV reads are sandboxed to app/storage/data_files to prevent a workflow
    from reading arbitrary files off the server's disk.
"""
import csv
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from app.nodes.base import BaseNodeExecutor, render_template
from app.storage.credentials import get_credential

logger = logging.getLogger("flow_engine.nodes.data_source")

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# CSV reads are restricted to this directory so a flow can never be used to
# read arbitrary files off the server.
CSV_ROOT = Path(__file__).resolve().parent.parent / "storage" / "data_files"


def _require_identifier(value: str, what: str) -> str:
    value = (value or "").strip()
    if not _IDENTIFIER_RE.match(value):
        raise ValueError(
            f"Invalid {what} '{value}'. Only letters, numbers, and underscores are allowed."
        )
    return value


def _resolve_csv_path(file_name: str) -> Path:
    CSV_ROOT.mkdir(parents=True, exist_ok=True)
    candidate = (CSV_ROOT / file_name).resolve()
    if CSV_ROOT.resolve() not in candidate.parents and candidate != CSV_ROOT.resolve():
        raise ValueError("Invalid file path: must stay within the data files directory.")
    if not candidate.exists():
        raise FileNotFoundError(f"CSV file '{file_name}' was not found.")
    return candidate


def _fetch_sql(
    dialect: str,
    credential: Dict[str, Any],
    table: Optional[str],
    query: Optional[str],
    filters: Dict[str, Any],
    limit: Optional[int],
) -> List[Dict[str, Any]]:
    import sqlalchemy
    from sqlalchemy import text

    extra = credential.get("extra") or {}
    host = extra.get("host", "localhost")
    port = extra.get("port") or ("5432" if dialect == "postgresql" else "3306")
    database = extra.get("database", "")
    username = extra.get("username", "")
    password = extra.get("password", "")

    if not database:
        raise ValueError("Credential is missing a 'database' value.")

    driver = "psycopg2" if dialect == "postgresql" else "pymysql"
    url = sqlalchemy.engine.URL.create(
        f"{dialect}+{driver}",
        username=username or None,
        password=password or None,
        host=host,
        port=int(port) if str(port).isdigit() else None,
        database=database,
    )

    # Hosted providers (Neon, Supabase, RDS, PlanetScale, ...) reject plain
    # connections outright, so default to SSL for any non-local host. A
    # credential can still override this explicitly via extra["sslmode"]
    # (postgres) / extra["ssl"] (mysql) if a self-managed server needs
    # something different.
    is_local_host = host in ("localhost", "127.0.0.1", "::1")
    connect_args: Dict[str, Any] = {}
    if dialect == "postgresql":
        connect_args["sslmode"] = extra.get("sslmode") or ("require" if not is_local_host else "prefer")
    elif dialect == "mysql":
        ssl_setting = extra.get("ssl")
        if ssl_setting is not None:
            connect_args["ssl"] = ssl_setting
        elif not is_local_host:
            connect_args["ssl"] = {"ssl": {}}

    engine = sqlalchemy.create_engine(
        url, pool_pre_ping=True, pool_recycle=300, connect_args=connect_args
    )
    try:
        try:
            conn_ctx = engine.connect()
        except sqlalchemy.exc.OperationalError as exc:
            msg = str(exc.orig) if getattr(exc, "orig", None) else str(exc)
            if "does not exist" in msg and "database" in msg.lower():
                raise ValueError(
                    f"Database '{database}' does not exist on this server. Double-check the "
                    "exact database name in your provider's dashboard (it's often different "
                    "from the project/credential nickname)."
                ) from exc
            raise
        with conn_ctx as conn:
            if query and query.strip():
                # Power-user escape hatch: the flow author (not chat input)
                # wrote this SQL. Filters are still passed as bound params
                # if the query references them via :name placeholders.
                result = conn.execute(text(query), filters or {})
            else:
                if not table:
                    raise ValueError("Either a table name or a raw query is required.")
                table = _require_identifier(table, "table name")
                where_sql = ""
                if filters:
                    for col in filters:
                        _require_identifier(col, "filter column")
                    where_sql = " WHERE " + " AND ".join(f"{col} = :{col}" for col in filters)
                limit_sql = f" LIMIT {int(limit)}" if limit else ""
                sql = f"SELECT * FROM {table}{where_sql}{limit_sql}"
                result = conn.execute(text(sql), filters or {})

            rows = result.mappings().all()
            return [dict(row) for row in rows]
    finally:
        engine.dispose()


def _fetch_rest(
    credential: Optional[Dict[str, Any]],
    base_url: Optional[str],
    endpoint: str,
    filters: Dict[str, Any],
    limit: Optional[int],
) -> List[Dict[str, Any]]:
    extra = (credential or {}).get("extra") or {}
    resolved_base = base_url or (credential or {}).get("api_url") or extra.get("base_url") or ""
    if not resolved_base:
        raise ValueError("REST API source needs a base URL (from the node config or the credential).")

    url = endpoint if endpoint.startswith("http") else resolved_base.rstrip("/") + "/" + endpoint.lstrip("/")

    headers: Dict[str, str] = {}
    api_key = (credential or {}).get("api_key")
    if api_key:
        header_name = extra.get("auth_header", "Authorization")
        header_value = f"Bearer {api_key}" if header_name.lower() == "authorization" else api_key
        headers[header_name] = header_value

    params = dict(filters or {})
    if limit:
        params.setdefault("limit", limit)

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        resp = client.get(url, headers=headers, params=params)
        if resp.status_code >= 400:
            raise RuntimeError(f"REST API returned HTTP {resp.status_code} from {url}: {resp.text[:500]}")
        data = resp.json()

    # Normalize common shapes into a flat list of records.
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("results", "data", "records", "items"):
            if isinstance(data.get(key), list):
                return data[key]
        return [data]
    return []


def _fetch_csv(file_name: str, filters: Dict[str, Any], limit: Optional[int]) -> List[Dict[str, Any]]:
    path = _resolve_csv_path(file_name)
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if filters and any(str(row.get(k, "")) != str(v) for k, v in filters.items()):
                continue
            records.append(dict(row))
            if limit and len(records) >= limit:
                break
    return records


class DataSourceNodeExecutor(BaseNodeExecutor):
    """Fetches records from PostgreSQL, MySQL, a REST API, or a CSV file.

    Config fields:
      source_type:      "postgresql" | "mysql" | "rest_api" | "csv"
      credential_id:     id of a saved credential (required for db/rest_api)
      table:             table name (db sources) — validated, never interpolated raw SQL
      query:              optional raw SQL (db sources) — power-user escape hatch
      endpoint:          path or full URL (rest_api)
      file_name:         file under app/storage/data_files (csv)
      filters:           dict of column/param -> value (rendered against state variables)
      limit:             optional max row count
      output_variable:   variable name records are stored under (default "records")
    """

    def execute(self, node_config: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        config = node_config.get("config") or node_config.get("data") or {}
        variables = state.get("variables", {}) or {}

        source_type = str(
            config.get("source_type") or node_config.get("source_type") or ""
        ).lower().strip()
        if source_type not in {"postgresql", "mysql", "rest_api", "csv"}:
            raise ValueError(
                f"Unsupported data source type '{source_type or '(none)'}'. "
                "Expected one of: postgresql, mysql, rest_api, csv."
            )

        credential_id = config.get("credential_id") or node_config.get("credential_id")
        credential = get_credential(str(credential_id)) if credential_id else None
        if source_type in {"postgresql", "mysql"} and not credential:
            raise ValueError("This data source needs a saved database credential.")

        # Render {{variable}} templates in filter values so a filter can
        # reference conversation state, e.g. {"appointment_date": "{{today}}"}.
        raw_filters = config.get("filters") or config.get("filter") or {}
        filters: Dict[str, Any] = {}
        if isinstance(raw_filters, dict):
            for key, value in raw_filters.items():
                filters[key] = render_template(str(value), variables) if isinstance(value, str) else value

        limit = config.get("limit") or node_config.get("limit")
        try:
            limit = int(limit) if limit else None
        except (TypeError, ValueError):
            limit = None

        if source_type in {"postgresql", "mysql"}:
            table = config.get("table") or node_config.get("table")
            query = config.get("query") or node_config.get("query")
            records = _fetch_sql(source_type, credential, table, query, filters, limit)
        elif source_type == "rest_api":
            endpoint = render_template(
                str(config.get("endpoint") or node_config.get("endpoint") or ""), variables
            )
            base_url = config.get("base_url") or node_config.get("base_url")
            records = _fetch_rest(credential, base_url, endpoint, filters, limit)
        else:  # csv
            file_name = config.get("file_name") or node_config.get("file_name")
            if not file_name:
                raise ValueError("CSV data source needs a file_name.")
            records = _fetch_csv(str(file_name), filters, limit)

        output_variable = str(
            config.get("output_variable") or node_config.get("output_variable") or "records"
        ).strip() or "records"

        state.setdefault("variables", {})
        state["variables"][output_variable] = records
        state["variables"][f"{output_variable}_count"] = len(records)

        logger.info(
            "[DATA SOURCE] node='%s' type='%s' -> %d record(s) into '%s'",
            node_config.get("id"), source_type, len(records), output_variable,
        )

        explicit_next = node_config.get("next_node") or config.get("next_node")
        if explicit_next:
            state["current_node"] = explicit_next

        state["status"] = "running"
        return state
