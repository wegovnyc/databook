import os

import xlrd
import xlutils.copy
import xlwt

from . import utils


def _load(file_path: str):
    with open(file_path, "rb") as file:
        return xlrd.open_workbook(file_contents=file.read())


def read(file_path: str, sheet_name: str, title_row: bool):
    wb_in = _load(file_path)

    sheet_in = wb_in.sheet_by_name(sheet_name)

    result = ((str(cell.value) for cell in row) for row in sheet_in.get_rows())

    if title_row:
        return utils.dicts_from_matrix(result)
    else:
        return list(list(row) for row in result)


def clear(file_path: str, sheet_name: str):
    try:
        wb_in = _load(file_path)
        wb_out = xlutils.copy.copy(wb_in)

        sheet_in = wb_in.sheet_by_name(sheet_name)
        sheet_out = wb_out.get_sheet(sheet_name)

        for row in range(0, sheet_in.nrows):
            for col in range(0, sheet_in.ncols):
                sheet_out.write(row, col, None)

        wb_out.save(file_path)
    except (FileNotFoundError, xlrd.XLRDError):
        pass


def append(file_path: str, sheet_name: str, data: [], title_row: bool, titles):
    if not data and not title_row:
        return

    wb_in = None

    if os.path.isfile(file_path):
        wb_in = _load(file_path)
        wb_out = xlutils.copy.copy(wb_in)
    else:
        parent = os.path.dirname(file_path)
        if not os.path.isdir(parent):
            os.makedirs(parent)
        wb_out = xlwt.Workbook()

    try:
        sheet_out = wb_out.get_sheet(sheet_name)
    except Exception:
        wb_out.add_sheet(sheet_name)
        sheet_out = wb_out.get_sheet(sheet_name)
        wb_out.save(file_path)
        wb_in = _load(file_path)

    sheet_in = wb_in.sheet_by_name(sheet_name)

    offset = sheet_in.nrows

    if title_row:
        if offset > 0:
            sheet_titles = sheet_in.row_values(0)
        else:
            sheet_titles = []
            offset = 1

        if titles is None:
            titles = utils.get_titles(data)
        utils.expand_unique(sheet_titles, titles)

        if titles:
            for col_i in range(0, len(sheet_titles)):
                sheet_out.write(0, col_i, sheet_titles[col_i])

        for title in titles:
            col_i = sheet_titles.index(title)
            row_i = 0
            for row in data:
                sheet_out.write(offset + row_i, col_i, row[title] if title in row else '')
                row_i += 1

    else:
        for row_i in range(0, len(data)):
            row = data[row_i]
            for col_i in range(0, len(row)):
                sheet_out.write(offset + row_i, col_i, row[col_i])

    wb_out.save(file_path)
