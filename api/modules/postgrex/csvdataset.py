import os
import re
import json
import math
import datetime
import random
import shutil
import requests
from datax import CSVReaderGen
from config import Config
from postgrex import PostgresModel


class CsvDataset:
    db = None
    datadir = None
    fn = None
    
    def __init__(self):
        self.db = PostgresModel()
        env = getattr(Config, 'env', 'linux')  # Default to linux if not defined
        self.datadir = (Config.rootdir + Config.db['datadir']) if env == 'win' else '/var/tmp/'

    def download(self, url: str):
        try:
            if not (os.path.isdir(self.datadir)):
                os.mkdir(self.datadir)
            self.set_fn(__class__.url2fn(url))
            #r = requests.get(url)
            with requests.get(url, stream=True) as r:
                with open(self.fn, 'wb') as f:
                    shutil.copyfileobj(r.raw, f)
            '''
            if r.status_code != 200:
                return False
            with open(self.fn, 'w', encoding='utf-8') as f:
                f.write(r.text)
            '''
            os.chmod(self.fn, 0o777)
            return True
        except Exception as e:
            raise e
            return False
            
    def delete_file(self):
        if self.fn:
            try:
                os.remove(self.fn)
                return True
            except Exception:
                return False
        return False
        
    def model(self, fn='', dd=None):
        if not dd:
            fn = '{}/{}'.format(self.datadir, fn) if fn else self.fn
            if not (os.path.isfile(fn)):
                return None
            csv = CSVReaderGen(fn)
            dd = csv.read()
        rr = {}
        for d in dd:
            for k, v in d.items():
                if not k:
                    print('MALFORMED', d)
                if type(v) in [int, bool, float]:
                    t = 'numeric'
                elif type(v) in [type(None)]:
                    t = 'string'
                elif type(v) in [str]:
                    if v == '':
                        t = 'string';
                    else:
                        t = 'numeric' if re.search('^[-+]?\s*\d+\.?\d*$', v.strip()) else 'string'
                else:
                    t = 'string'
                    
                if k in rr:
                    if rr[k]['type'] == 'string':
                        t = 'string'
                    
                if k not in rr:
                    rr[k] = {'type': None, 'min': 999, 'max': 0}
                    
                if t == 'string':
                    rr[k] = {'type': 'string', 'min': min(rr[k]['min'], len(v)), 'max': max(rr[k]['max'], math.floor(len(v) * 1.6))}
                elif t == 'numeric':
                    rr[k] = {'type': 'numeric', 'min': min(rr[k]['min'], len(str(v))), 'max': max(rr[k]['max'], math.floor(len(str(v)) * 1.6))}
            
        for f, r in rr.items():
            if r['type'] in ['string', None] and r['max'] > 20:
                rr[f]['postgres'] = 'text'
            elif r['type'] == 'string':
                rr[f]['postgres'] = 'char({})'.format(max(2, r['max']))
            else:
                rr[f]['postgres'] = rr[f]['type']
        
        return rr

    def match_model(self, tbl, model):
        sch = self.db.schema(tbl)
        #print(sch)
        if not sch:
            return False
        for f in sch:
            if f['column_name'] == '_uid':
                continue
            #print(f['column_name'])
            if f['column_name'] not in model:
                return False
            elif model[f['column_name']]['type'] == 'string' and f['data_type'] in ['numeric']:
                return False
            elif model[f['column_name']]['type'] == 'string' and f['data_type'] in ['character'] and model[f['column_name']]['max'] > f['character_maximum_length']:
                return False
        return True

    def create_tbl(self, tbl, model, idxs):
        ff = ['"{}" {} DEFAULT {} NOT NULL'.format(f, pp['postgres'], 0 if pp['type'] == 'numeric' else "''") for f, pp in model.items()]
        req = 'CREATE TABLE {} ({}, "_uid" serial)'.format(tbl, ', '.join(ff))
        #print(req)
        self.db.q(req)
        if idxs:
            for idx in idxs.split(','):
                self.db.q('CREATE INDEX "{}-{}" ON {} ("{}")'.format(tbl, idx, tbl, idx))
        
    def import_csv(self, tbl, fn, idxs):
        self.set_fn(fn)

        model = self.model(fn)
        if not model:
            return None
        ff = ', '.join(['"{}"'.format(f) for f in model])
        if tbl in self.db.tables():
            if self.match_model(tbl, model):
                self.db.q('TRUNCATE {} RESTART IDENTITY'.format(tbl))
            else:
                self.db.q('DROP TABLE {}'.format(tbl))
        if not tbl in self.db.tables():
            self.create_tbl(tbl, model, idxs)
        req = "COPY {} ({}) FROM '{}' (FORMAT csv, HEADER, NULL 'null', DELIMITER ',')".format(tbl, ff, ('/var/tmp/' + fn) if Config.env == 'win' else self.fn)
        self.db.q(req)
        return req
    
    def set_fn(self, fn):
        self.fn = '{}/{}'.format(self.datadir, fn)
        
    def delete(self, tbl):
        self.set_fn(tbl)
        try:
            self.db.q("DROP TABLE {}".format(tbl))
        except Exception:
            pass
        return self.delete_file()
        
        
    def url2fn(url):
        return re.findall('([^/]+?)(?:\.csv)?$', url)[0].lower()
        
