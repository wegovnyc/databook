import os
import json
import postgresql
import datetime
import random
from config import Config

# Credential resolution lives in one place — see modules/dbcreds.py.
try:
    import dbcreds
except ImportError:  # when imported as part of the modules package
    from modules import dbcreds



class PostgresModel:
    db = None
    
    def __init__(self):
        # Built from the environment rather than env.yaml's `addr:` DSN.
        #
        # `addr` was a third copy of the credential (`pq://user:pass@host/db`)
        # alongside `user` and `pwd`, and the rotation script only ever rewrote
        # `pwd` — so `addr` silently kept a stale password. Nothing broke only
        # because the password= keyword below overrides whatever the URI carries.
        # The password is deliberately NOT interpolated into the DSN, so it cannot
        # leak into a connection string that ends up in a log or traceback.
        user = os.environ.get('POSTGRES_USER') or Config.db.get('user')
        pwd = dbcreds.password(Config.db.get('pwd') or '')
        host = os.environ.get('POSTGRES_HOST') or Config.db.get('host')
        name = os.environ.get('POSTGRES_DB') or Config.db.get('dbname')
        port = os.environ.get('POSTGRES_PORT', '5432')
        self.db = postgresql.open(f"pq://{user}@{host}:{port}/{name}", password=pwd)

    def select(self, sql, idx: int, simplify=False):
        rr = self.db.query(sql)
        if not rr:
            return None if simplify else {}
        try:
            row = rr[idx]
            return row[0] if simplify else dict(zip(row.keys(), [v.strip() if type(v) == str else v for v in row.values()]))
        except Exception:
            return None if simplify else {}
        
    def bselect(self, sql):
        rr = self.db.query(sql)
        if not rr:
            return {}
        for row in rr: 
            yield dict(zip(row.keys(), [v.strip() if type(v) == str else v for v in row.values()]))
        
    def bselect_safe(self, sql, dd=[]):
        req = self.db.prepare(sql)
        rr = req(*dd)
        if not rr:
            return {}
        for row in rr:
            yield dict(zip(row.keys(), [v.strip() if type(v) == str else v for v in row.values()]))
        
    def q(self, sql):
        return self.db.execute(sql)

    def schema(self, tbl):
        return [r for r in self.bselect("SELECT column_name, data_type, character_maximum_length FROM information_schema.columns WHERE table_name = '{}'".format(tbl))]

    def tables(self):
        return [r['table_name'] for r in self.bselect("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'")]