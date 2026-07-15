from yaml import add_representer

from .yaml import YamlHandle


class Stored(dict):
    def __init__(self, filename: str):
        super().__init__()
        self.__handle = YamlHandle(filename)
        try:
            self.load()
        except FileNotFoundError:
            pass

    def load(self):
        res = self.__handle.read()
        self.clear()
        self.update(res)

    def save(self):
        self.__handle.write(self)

    '''
    def __del__(self):
        if self:
            self.save()
    '''

def _map_presenter(self, data):
    return self.represent_mapping('tag:yaml.org,2002:map', data.items())


add_representer(Stored, _map_presenter)
