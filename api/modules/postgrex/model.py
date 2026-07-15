import os
import json
import postgresql
import datetime
import random
from config import Config


class PostgresModel:
    db = None
    
    def __init__(self):
        self.db = postgresql.open(Config.db['addr'], password=Config.db['pwd'])

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