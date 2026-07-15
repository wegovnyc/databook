'''https://stackoverflow.com/questions/21356659/singleton-with-subclasses-in-python

Rough implementation - all singletone instances are stored in dictionary but it is easy inheritable

'''


class Singleton:
    __instances = {}

    def __new__(cls, *args, **kwargs):
        if cls.__instances.get(cls, None) is None:
            # cls.__instances[cls] = super(Singleton, cls).__new__(cls, *args, **kwargs)
            cls.__instances[cls] = super(Singleton, cls).__new__(cls)
        return Singleton.__instances[cls]
