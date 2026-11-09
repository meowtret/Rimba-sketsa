# -*- coding: utf-8 -*-
"""
Logger Rimba Sketsa (mode senyap).

Semua pemanggilan log.*, qgis_log() dan redirect_print_to_log() aman
dipanggil tetapi tidak menghasilkan keluaran apa pun.
"""



class NullLogger:
    def debug(self, *a, **kw):
        pass

    def info(self, *a, **kw):
        pass

    def warning(self, *a, **kw):
        pass

    def error(self, *a, **kw):
        pass

    def critical(self, *a, **kw):
        pass

    def exception(self, *a, **kw):
        pass


log = NullLogger()


def qgis_log(message, level=None):
    """Tidak melakukan apa pun."""
    pass


def redirect_print_to_log():
    """Sengaja tidak melakukan apa pun.

    Versi asli memulihkan sys.stdout/sys.stderr ke sys.__stdout__, yang di
    Windows bisa bernilai None dan memutus keluaran Python Console QGIS.
    """
    return None
