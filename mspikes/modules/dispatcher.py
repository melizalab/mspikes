# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""dispatch chunks based on properties to distribute work

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Thu Jul 11 17:13:34 2013
"""

class parallel(object):

    def __init__(self, dispatch_attr):
        from collections import defaultdict

        self.workers = defaultdict(module_initializer)
        self.keyfun = attrgetter(dispatch_attr)

    def send(self, chunk):
        key = self.keyfun(chunk)
        self.workers[key].send(chunk)




def parallel(keyfun):
    """Decorate a Node to operate in parallel over chunks with different
    return values of keyfun(chunk)

    The decorator dynamically creates a subclass of its argument. The
    instantiation of the derived class dispatches to workers, which are
    instances of the base class. The worker classes have their own state, but do
    share a list of targets, so that calls to add_target on the derived class
    affect all workers.

    """
    from collections import defaultdict
    from functools import partial

    def decorate(cls):

        # replacement methods
        def __init__(self, *args, **kwargs):
            # bind the intialization arguments to the derived class and use them
            # to instantiate workers. note that we're using the class as a
            # function to call the constructor.

            self._targets = []  # this will be shared with all workers
            def init():
                obj = cls(*args, **kwargs)
                obj._targets = self._targets
                return obj

            self.__workers__ = defaultdict(init)

        def send(self, chunk):
            key = keyfun(chunk)
            self.__workers__[key].send(chunk)

        def close(self):
            # send close to all workers
            for w in self.__workers__.values():
                w.close()

        def throw(self, exception):
            for w in self.__workers__.values():
                w.throw(exception)

        name = cls.__name__ + "_p"
        return type(name, (cls,), dict(__init__=__init__,
                                       __keyfun__=keyfun,
                                       send=send,
                                       close=close,
                                       throw=throw))
    return decorate

# Variables:
# End:
