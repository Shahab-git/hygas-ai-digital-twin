"""In-memory stand-in for the Supabase client used by the tests (audit fix J).

Nothing here touches the network or any credential. FakeSupabase records every
call (operation, table) in `.calls` so a test can assert "zero network calls"
or "exactly one insert per cycle". It implements only what this repo's own code
uses: table().select/insert/upsert/update/delete with .eq/.is_/.order/.limit
and .execute(); a table listed in `missing_tables` raises the same PGRST205
error text the real project returns for a table that does not exist.
"""
import contextlib
import copy
from types import SimpleNamespace

MISSING_TABLE_MESSAGE = (
    "{'message': \"Could not find the table 'public.%s' in the schema cache\", "
    "'code': 'PGRST205', 'hint': None, 'details': None}"
)


class _Query:
    def __init__(self, client, name):
        self._c, self._name = client, name
        self._op, self._payload, self._conflict = None, None, None
        self._filters, self._order, self._limit, self._count = [], None, None, None

    # --- chain builders
    def select(self, cols="*", count=None):
        self._op, self._count = "select", count
        return self

    def insert(self, payload):
        self._op, self._payload = "insert", payload
        return self

    def upsert(self, payload, on_conflict=None):
        self._op, self._payload, self._conflict = "upsert", payload, on_conflict
        return self

    def update(self, payload):
        self._op, self._payload = "update", payload
        return self

    def delete(self):
        self._op = "delete"
        return self

    def eq(self, col, val):
        self._filters.append(("eq", col, val))
        return self

    def is_(self, col, val):
        self._filters.append(("is", col, val))
        return self

    def order(self, col, desc=False):
        self._order = (col, desc)
        return self

    def limit(self, n):
        self._limit = n
        return self

    # --- execution
    def _match(self, row):
        for kind, col, val in self._filters:
            if kind == "eq" and row.get(col) != val:
                return False
            if kind == "is" and val == "null" and row.get(col) is not None:
                return False
        return True

    def execute(self):
        c = self._c
        c.calls.append((self._op, self._name))
        if self._name in c.missing_tables:
            raise Exception(MISSING_TABLE_MESSAGE % self._name)
        rows = c.tables.setdefault(self._name, [])
        if self._op == "select":
            out = [copy.deepcopy(r) for r in rows if self._match(r)]
            if self._order:
                out.sort(key=lambda r: r.get(self._order[0]) or "", reverse=self._order[1])
            if self._limit is not None:
                out = out[: self._limit]
            return SimpleNamespace(data=out, count=len(out))
        payloads = self._payload if isinstance(self._payload, list) else [self._payload]
        if self._op == "insert":
            for p in payloads:
                row = copy.deepcopy(p)
                row.setdefault("id", len(rows) + 1)
                rows.append(row)
            return SimpleNamespace(data=copy.deepcopy(rows[-len(payloads):]), count=len(payloads))
        if self._op == "upsert":
            keys = [k.strip() for k in (self._conflict or "id").split(",")]
            for p in payloads:
                new = copy.deepcopy(p)
                hit = next((r for r in rows if all(r.get(k) == new.get(k) for k in keys)), None)
                if hit is None:
                    new.setdefault("id", len(rows) + 1)
                    rows.append(new)
                else:
                    hit.update(new)
            return SimpleNamespace(data=copy.deepcopy(payloads), count=len(payloads))
        if self._op == "update":
            n = 0
            for r in rows:
                if self._match(r):
                    r.update(copy.deepcopy(self._payload))
                    n += 1
            return SimpleNamespace(data=[], count=n)
        if self._op == "delete":
            keep = [r for r in rows if not self._match(r)]
            n = len(rows) - len(keep)
            c.tables[self._name] = keep
            return SimpleNamespace(data=[], count=n)
        raise AssertionError(f"FakeSupabase: unsupported operation {self._op!r}")


class FakeSupabase:
    def __init__(self, tables=None, missing_tables=()):
        self.tables = copy.deepcopy(tables) if tables else {}
        self.missing_tables = set(missing_tables)
        self.calls = []

    def table(self, name):
        return _Query(self, name)

    def count(self, op=None, table=None):
        return sum(1 for o, t in self.calls if (op is None or o == op) and (table is None or t == table))


@contextlib.contextmanager
def patched_supabase(client):
    """Routes every Supabase access in this repo to `client`: vendor_log's
    client (used by operator_setpoints, measurement_promotion, the AI-011
    logger, the driver script and app.py) AND confirmation_loop's own client."""
    from python import confirmation_loop, vendor_log
    saved = (vendor_log._get_client, confirmation_loop._get_client,
             getattr(vendor_log, "_client", None), getattr(confirmation_loop, "_client", None))
    vendor_log._get_client = lambda: client
    confirmation_loop._get_client = lambda: client
    try:
        yield client
    finally:
        vendor_log._get_client, confirmation_loop._get_client = saved[0], saved[1]
        vendor_log._client, confirmation_loop._client = saved[2], saved[3]
