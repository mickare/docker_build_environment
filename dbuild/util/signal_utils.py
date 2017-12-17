import signal

SIGNALS_TO_NAMES_DICT = dict((getattr(signal, n), n) \
                             for n in dir(signal) if n.startswith('SIG') and '_' not in n)


def getSignalName(signum) -> str:
    return SIGNALS_TO_NAMES_DICT.get(signum, "Unnamed signal: %d" % signum)
