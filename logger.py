# # -*- coding: utf-8 -*-
from .qt_compat import scoped_enum
# """
# Logger QdrawEVT — version légère et non bloquante
# -------------------------------------------------
# ✅ Aucun fichier sur disque
# ✅ Aucun blocage au démarrage de QGIS
# ✅ Redirection print() manuelle (optionnelle)
# ✅ Capture des erreurs Python durant la session
# """
#
# import sys
# # import traceback
# from qgis.core import QgsMessageLog, Qgis
#
#
# # === Initialisation simple du logger ===
# log = logging.getLogger("QdrawEVT")
# log.setLevel(logging.DEBUG)
#
# # Utiliser le flux réel sans interception
# _original_stdout = sys.stdout
# _original_stderr = sys.stderr
#
# # Handler console (stdout QGIS)
# console_handler = logging.StreamHandler(_original_stdout)
# console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
#
# if not log.hasHandlers():
#     log.addHandler(console_handler)
#
#
# # === Redirection print() optionnelle et sûre ===
# class PrintLogger:
#     """Redirige print() vers le logger QdrawEVT sans blocage ni récursion."""
#
#     def __init__(self, real_stream):
#         self.real_stream = real_stream
#
#     def write(self, message: str):
#         msg = (message or "").strip()
#         if not msg:
#             return
#         # Éviter les récursions
#         try:
#             log.info(msg)
#         except Exception:
#             # En cas d'erreur, on repasse par le flux original (jamais le logger)
#             try:
#                 self.real_stream.write(msg + "\n")
#             except Exception:
#                 pass
#
#     def flush(self):
#         try:
#             self.real_stream.flush()
#         except Exception:
#             pass
#
#
# def redirect_print_to_log():
#     """Active manuellement la redirection print() → logger QdrawEVT.
#     ⚠️ À appeler après que QGIS ait fini de charger (dans initGui, pas à l'import).
#     """
#     try:
#         sys.stdout = PrintLogger(_original_stdout)
#         sys.stderr = PrintLogger(_original_stderr)
#         log.info("Redirection print() → logger QdrawEVT activée (session uniquement).")
#     except Exception as e:
#         _original_stderr.write(f"[QdrawEVT] Redirection print échouée : {e}\n")
#         sys.stdout = _original_stdout
#         sys.stderr = _original_stderr
#
#
# # === Journalisation dans QGIS ===
# def qgis_log(message: str, level: Qgis = Qgis.Info):
#     """Affiche le message dans QGIS et le logger."""
#     msg = str(message)
#     QgsMessageLog.logMessage(msg, "QdrawEVT", level)
#     if level == Qgis.Critical:
#         log.error(msg)
#     elif level == Qgis.Warning:
#         log.warning(msg)
#     else:
#         log.info(msg)
#
#
# # === Capture globale des exceptions ===
# def handle_uncaught_exception(exctype, value, tb):
#     """Capture les erreurs Python non interceptées pendant la session."""
#     err_text = "".join(traceback.format_exception(exctype, value, tb))
#     log.critical(f"Exception non interceptée : {err_text}")
#     try:
#         QgsMessageLog.logMessage(
#             f"Erreur non interceptée : {err_text}", "QdrawEVT", Qgis.Critical
#         )
#     except Exception:
#         pass
#
#
# # On installe l'excepthook immédiatement (sûr)
# sys.excepthook = handle_uncaught_exception
#
# # Message dans le log QGIS
# log.info("Logger QdrawEVT initialisé (aucun fichier, session uniquement, sûr au démarrage).")

# -*- coding: utf-8 -*-
"""
Logger QdrawEVT — mode désactivé
--------------------------------
Cette version ne fait absolument rien.
Tous les appels à log, qgis_log, redirect_print_to_log
sont neutres et ne produisent aucune sortie.
"""

import sys
from qgis.core import Qgis

# === Création d'un faux logger neutre ===


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


def qgis_log(message: str, level: Qgis = scoped_enum(Qgis, "MessageLevel", "Info")):
    """Ne fait rien."""
    pass


def redirect_print_to_log():
    """Ne redirige rien."""
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
    return
