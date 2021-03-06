# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""dispatch chunks based on properties to distribute work

Copyright (C) 2013 Dan Meliza <dmeliza@gmail.com>
Created Thu Jul 11 17:13:34 2013
"""
import logging
_log = logging.getLogger("mspikes.dispatcher")


def parallel(keyfun, *tags):
    """Decorate a Node to operate in parallel over chunks with different
    return values of keyfun(chunk)

    The decorator dynamically creates a subclass of its argument. The
    instantiation of the derived class dispatches to workers, which are
    instances of the base class. The worker classes have their own state, but do
    share a list of targets, so that calls to add_target on the derived class
    affect all workers.

    Important: decorated classes must not use super() to look up methods in base
    classes, because this will resolve to the class itself. Instead, directly
    access the method of the base class.

    keyfun - keyfun(chunk) should return key used to split data. can also be the
             name of an attribute

    tags - if not None, only chunks matching this list will be processed by
           workers; other chunks will be passed to downstream targets without
           processing

    """
    from mspikes.util import defaultdict
    from mspikes.filters import any_tag
    import operator
    import weakref

    if isinstance(keyfun, basestring):
        keyfun = operator.attrgetter(keyfun)
    tagfun = any_tag(*tags)

    def decorate(cls):
        from mspikes.types import Node

        # replacement methods
        def __init__(self, name, *args, **kwargs):
            # bind the intialization arguments to the derived class and use them
            # to instantiate workers. note that we're using the class as a
            # function to call the constructor.
            Node.__init__(self, name)
            self._log.debug("running in parallel")

            self._targets = []  # this will be shared with all workers
            # weakref prevents the closure from creating a reference to the
            # wrapper object; otherwise the destructor will never be called
            this = weakref.ref(self)
            def init(key):
                obj = cls("%s:%s" % (name, key), *args, **kwargs)
                obj._targets = this()._targets
                return obj

            self.__workers__ = defaultdict(init)

        def __del__(self):
            try:
                self.__workers__.clear()
            except:
                pass
            Node.__del__(self)

        def send(self, chunk):
            if tagfun(chunk):
                key = keyfun(chunk)
                self.__workers__[key].send(chunk)
            else:
                Node.send(self, chunk)

        def close(self):
            # send close to all workers
            for w in self.__workers__.values():
                w.close()

        def throw(self, exception):
            for w in self.__workers__.values():
                w.throw(exception)

        name = cls.__name__ + "_p"
        return type(name, (cls,), dict(__init__=__init__,
                                       __del__=__del__,
                                       __doc__=cls.__doc__,
                                       __keyfun__=keyfun,
                                       send=send,
                                       close=close,
                                       throw=throw))
    return decorate

# Variables:
# End:
