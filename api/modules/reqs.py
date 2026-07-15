import re
import json
from decimal import Decimal
from postgrex import PostgresModelAsync
#from postgrex import PostgresModel


def jsonsafe(dd):
    def deff(obj):
        s = str(obj)
        if isinstance(obj, Decimal):
            if re.search('\.', s):
                return float(obj)
            else:
                return int(obj)
        else:
            return s
            
    return json.dumps(dd, ensure_ascii=False, default=deff)

async def select(db, sql, params=[]):
    rr = await PostgresModelAsync.bselect_safe(db, sql, params)
    return {'rows': json.loads(jsonsafe(rr))}
