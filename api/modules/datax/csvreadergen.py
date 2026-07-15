import re
import csv
import itertools

class CSVReaderGen:

    def __init__(self, file_path, delimiter=',', quote='"', newline='\n', titles=True):
        self.__file_path = file_path
        self.__delimiter = delimiter
        self.__quote = quote
        self.__newline = newline
        self.__titles = titles
        self.titles = None

    def read(self):
        with open(self.__file_path, newline=self.__newline, encoding='utf-8') as csvfile:
            dgen = csv.reader(csvfile, delimiter=self.__delimiter, quotechar=self.__quote, strict=True, quoting=csv.QUOTE_ALL, dialect='unix', doublequote=True)
            #dgen = csv.reader(csvfile, delimiter=self.__delimiter, quotechar=self.__quote, quoting=csv.QUOTE_ALL, dialect='unix')
            if self.__titles:
                try:
                    self.titles = tuple(next(dgen))
                except StopIteration:
                    return {}
            for r in dgen:
                if self.titles:
                    yield dict(itertools.zip_longest(self.titles, r, fillvalue=''))
                else:
                    yield r
