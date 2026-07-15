"""
To set access credentials (2019 Dec 3):
- go to Google console, create or select project
- Dashboard > enable APIs and Services > find and enable Google Drive API + Google Sheets API
- Back arrow > Credentials > Create credentials > Service account key
- Manage service accounts > triple dots button in Actions column > Create key > Json > Create
- rename and save json file, pass it to constructor as cl_secret
- find and copy client_email parameter inside json file
- share your Google Sheets doc with copied email
"""

import os
import sys
import pygsheets

from .util import utils


class GSheetClient:
    def __init__(self, cl_secret: str):
        self.__gc = pygsheets.authorize(service_file=cl_secret)

    def get_table(self, table_name: str):
        return self.__gc.open(table_name)


class GSheetHandle:
    def __init__(self, table_name: str, titles=True, client=None):
        if not client:
            dir = os.path.dirname(os.path.abspath(__file__))
            client = GSheetClient(dir + '/gsheetscredentials/credentials.json')
        self.__table = client.get_table(table_name)
        self.__titles = titles

    def read(self, sheet_name: str):
        sheet = self.__table.worksheet_by_title(sheet_name)

        result = sheet.get_all_values(include_tailing_empty=False, include_tailing_empty_rows=False)

        if self.__titles:
            return utils.dicts_from_matrix(result)

        return result

    def write(self, sheet_name, data, titles=None):
        self.__table.worksheet_by_title(sheet_name).clear()
        self.append(sheet_name, data, titles)

    def append(self, sheet_name: str, data, titles=None):
        if not data and not self.__titles:
            return

        sheet = self.__table.worksheet_by_title(sheet_name)
        new_data = data
        values = sheet.get_all_values(include_tailing_empty=False, include_tailing_empty_rows=False)
        height = len(values) + 1

        if self.__titles:
            sheet_titles = values[0]
            if titles is None:
                titles = utils.get_titles(data)
            utils.expand_unique(sheet_titles, titles)

            if titles:
                sheet.update_row(1, sheet_titles)

            new_data = [
                [
                    row[title] if (title in titles and title in row) else ''
                    for title in sheet_titles
                ]
                for row in data
            ]
        else:
            # values contain 1 empty list if table is empty
            if not (height > 2 or values[0]):
                height -= 1

        if new_data:
            sheet.update_values(crange=(height, 1), values=new_data, extend=True)
