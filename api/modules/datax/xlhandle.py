import os

from .util import xls, xlsx


class XlHandle:
    def __init__(self, file_path: str, titles=True):
        self._file_path = file_path
        self.__titles = titles

        file_type = os.path.splitext(file_path)[-1].lower()
        if file_type == '.xls':
            self.__handle = xls
        elif file_type == '.xlsx':
            self.__handle = xlsx
        else:
            raise ValueError('Unknown file type: {}'.format(file_type))

    def read(self, sheet_name: str):
        return self.__handle.read(self._file_path, sheet_name, self.__titles)

    def write(self, sheet_name: str, data: [], titles=None):
        self.__handle.clear(self._file_path, sheet_name)
        self.append(sheet_name, data, titles)

    def append(self, sheet_name: str, data: [], titles=None):
        self.__handle.append(self._file_path, sheet_name, data, self.__titles, titles)
