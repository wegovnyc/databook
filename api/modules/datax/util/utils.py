import itertools


def dicts_from_matrix(data):
    it = iter(data)
    try:
        first = tuple(next(it))
    except StopIteration:
        return []

    return [dict(itertools.zip_longest(first, row, fillvalue='')) for row in it]


def expand_unique(dst: list, src: list):
    for i in src:
        if i not in dst:
            dst.append(i)


def get_titles(data: list):
    result = []

    for row in data:
        for key in row.keys():
            if key not in result:
                result.append(key)

    return result
