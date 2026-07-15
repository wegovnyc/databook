"""
https://pyyaml.org/wiki/PyYAMLDocumentation
"""
import os
import re

from yaml import FullLoader
from yaml import load, dump


def get_empty():
    class Empty:
        pass

    return Empty()


class YamlHandle:
    def __init__(self, file_path):
        self.__file_path = file_path

    def setup(self, target=None):
        if target is None:
            target = get_empty()

        res = self.read()
        for key, value in res.items():
            if not re.match('__', key):
                setattr(target, key, value)

        return target

    def read(self) -> dict:
        try:
            with open(self.__file_path, 'r', encoding='utf8')as file:
                res = load(file, Loader=FullLoader)
            if res is not None:
                return res
        except FileNotFoundError:
            pass

        return {}

    def write(self, data):
        dir_name = os.path.dirname(self.__file_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(self.__file_path, 'w+', encoding='utf8') as file:
            file.write(dump(data, allow_unicode=True))