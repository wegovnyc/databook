import re
from datax import YamlHandle

class Config:

    def load(data={}, file=''):
        if data and file:
            raise AttributeError('Both data and file attributes set')
        if file:
            try:
                yaml = YamlHandle(file)
                data = yaml.read()
            except FileNotFoundError:
                pass
        __class__.__config(data)

    def __config(data: dict):
        for key, val in data.items():
            if not re.match('__', key):
                setattr(__class__, key, val)
