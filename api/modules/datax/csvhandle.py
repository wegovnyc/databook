import csv
import json
import io
import re

from .util import utils


class CSVHandle:
    def __init__(self, file_path, delimiter=',', quote='"', newline='\n', titles=True):
        self.__file_path = file_path
        self.__delimiter = delimiter
        self.__quote = quote
        self.__newline = newline
        self.__titles = titles

    def __lines_gen(self, content: str):
        rr = content.strip(self.__newline).split(self.__newline)
        for r in rr:
            yield r
        
    '''
    def __lines_gen__(self, content: str):
        skip_len = 0

        quote_len = len(self.__quote)
        newline_len = len(self.__newline)

        while True:
            newline_index = content.find(self.__newline, skip_len)

            if newline_index < 0:
                break

            quote_index = content.find(self.__quote, skip_len)

            if quote_index < 0 or newline_index < quote_index:
                yield content[:newline_index]
                content = content[newline_index + newline_len:]
                skip_len = 0
                continue

            skip_len = quote_index + quote_len

            # skipping quoted value
            while True:
                # if check: closing quote exists
                skip_len = content.find(self.__quote, skip_len) + quote_len

                if content.find(self.__quote, skip_len) != skip_len:
                    # exits on closing quote
                    break

                # skips double quote
                skip_len += quote_len
    '''
    
    def decode(self, data: str):
        data = re.sub('\x00', '', data)
        result = csv.reader(self.__lines_gen(data), delimiter=self.__delimiter, quotechar=self.__quote)
        if self.__titles:
            return utils.dicts_from_matrix(result)

        return list(result)

    '''
    def decode(self, data: str):
        result = csv.reader(self.__lines_gen(data))

        if self.__titles:
            return utils.dicts_from_matrix(result)

        return list(result)
    '''
    
    def read(self):
        # using generator for memory saving
        with open(self.__file_path, 'r', encoding='utf8') as file:
            return self.decode(file.read())

    def encode(self, data):
        with io.StringIO() as buffer:
            if self.__titles:
                titles = utils.get_titles(data)
                writer = csv.DictWriter(buffer, fieldnames=titles,
                                        delimiter=self.__delimiter, quotechar=self.__quote,
                                        lineterminator=self.__newline)
                writer.writeheader()
            else:
                writer = csv.writer(buffer,
                                    delimiter=self.__delimiter, quotechar=self.__quote, lineterminator=self.__newline)

            for row in data:
                writer.writerow(row)

            return buffer.getvalue()

    def write(self, data):
        with open(self.__file_path, 'w+', encoding='utf8', newline='') as file:
            file.write(self.encode(data))
