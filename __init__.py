# -*- coding: utf-8 -*-
# QDraw: plugin that makes drawing easier
# Author: Jérémy Kalsron
#         jeremy.kalsron@gmail.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

from qgis.core import QgsMessageLog, Qgis
from .qt_compat import scoped_enum

# ==================================================================
# MODE DÉVELOPPEUR : DEBUG = True / MODE PRODUCTION : DEBUG = False
# ==================================================================
DEBUG = True

_PLUGIN_DIR = Path(__file__).resolve().parent


# ============================================================
#           REDIRECTION stdout / stderr vers le log
# ============================================================
class LogRedirector:
    def __init__(self, level="INFO"):
        self.level = level

    def write(self, message):
        message = message.strip()
        if not message:
            return

        level = scoped_enum(Qgis, "MessageLevel", "Info") if self.level == "INFO" else scoped_enum(Qgis, "MessageLevel", "Critical")
        QgsMessageLog.logMessage(message, "QdrawEVT", level)

    def flush(self):
        pass


# Redirection conservée pour le mode développeur actuel.
sys.stdout = LogRedirector("INFO")
sys.stderr = LogRedirector("ERROR")


# ============================================================
#        IDENTIFICATION DE L'ORIGINE D'UNE EXCEPTION
# ============================================================
def _safe_resolve(path):
    try:
        return Path(path).resolve()
    except Exception:
        return Path(path)


def _is_inside(path, directory):
    path = _safe_resolve(path)
    directory = _safe_resolve(directory)
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


def _origin_from_path(filepath):
    """Retourne (categorie, nom, titre) à partir du fichier fautif."""
    path = _safe_resolve(filepath)
    parts = [part.lower() for part in path.parts]

    # 1. Le plugin qdrawEVT lui-même
    if _is_inside(path, _PLUGIN_DIR):
        return (
            "Extension qdrawEVT",
            "qdrawEVT",
            "Erreur qdrawEVT (mode développeur)",
        )

    # 2. Script Processing du profil utilisateur
    for marker in (("processing", "scripts"), ("processing", "models")):
        for index in range(len(parts) - 1):
            if parts[index:index + 2] == list(marker):
                kind = "script Processing" if marker[1] == "scripts" else "modèle Processing"
                return (
                    kind.capitalize(),
                    path.name,
                    f"Erreur {kind} : {path.name} (mode développeur)",
                )

    # 3. Autre plugin QGIS : .../python/plugins/<nom_plugin>/...
    for index in range(len(parts) - 2):
        if parts[index:index + 2] == ["python", "plugins"]:
            plugin_name = path.parts[index + 2]
            return (
                "Autre extension QGIS",
                plugin_name,
                f"Erreur extension QGIS : {plugin_name} (mode développeur)",
            )

    # 4. Code QGIS / PyQGIS
    qgis_markers = ("qgis", "osgeo4w", "apps")
    if any(marker in parts for marker in qgis_markers):
        return (
            "QGIS / PyQGIS",
            path.name,
            f"Erreur QGIS / PyQGIS : {path.name} (mode développeur)",
        )

    # 5. Python ou bibliothèque tierce
    return (
        "Python ou bibliothèque externe",
        path.name,
        f"Erreur Python externe : {path.name} (mode développeur)",
    )


def _build_exception_report(exctype, value, tb):
    frames = traceback.extract_tb(tb)
    last = frames[-1] if frames else None

    if last is not None:
        filepath = last.filename
        filename = os.path.basename(filepath)
        line = last.lineno
        function = last.name
        module = os.path.splitext(filename)[0]
    else:
        filepath = "Inconnu"
        filename = "Inconnu"
        line = "Inconnue"
        function = "Inconnue"
        module = "Inconnu"

    category, origin_name, title = _origin_from_path(filepath)
    tb_str = "".join(traceback.format_exception(exctype, value, tb))

    header = (
        f"Origine       : {category}\n"
        f"Composant     : {origin_name}\n\n"
        f"Type d'erreur : {exctype.__name__}\n"
        f"Message       : {value}\n\n"
        f"Module        : {module}\n"
        f"Fichier       : {filepath}\n"
        f"Ligne         : {line}\n"
        f"Fonction      : {function}\n\n"
        "Traceback complet ci-dessous :\n"
    )

    return title, category, header, tb_str


# ============================================================
#              EXCEPTION HOOK GLOBAL (DEBUG/PROD)
# ============================================================
def handle_uncaught_exception(exctype, value, tb):
    """
    Intercepte les exceptions Python non gérées de la session QGIS.

    - identifie l'origine réelle de l'erreur ;
    - ne présente une erreur comme qdrawEVT que si la dernière frame fautive
      appartient effectivement au dossier du plugin ;
    - affiche en mode développeur une fenêtre détaillée et scrollable ;
    - journalise toujours le traceback complet dans le panneau Messages.
    """
    title, category, header, tb_str = _build_exception_report(exctype, value, tb)
    full_report = header + tb_str

    # Un canal distinct évite d'attribuer à qdrawEVT les erreurs externes.
    log_tag = "QdrawEVT" if category == "Extension qdrawEVT" else "Intercepteur Python"
    QgsMessageLog.logMessage(full_report, log_tag, scoped_enum(Qgis, "MessageLevel", "Critical"))

    if DEBUG:
        from qgis.utils import iface
        from qgis.PyQt.QtWidgets import (
            QDialog,
            QHBoxLayout,
            QPushButton,
            QTextEdit,
            QVBoxLayout,
        )

        dialog = QDialog(iface.mainWindow())
        dialog.setWindowTitle(title)
        dialog.resize(950, 650)

        layout = QVBoxLayout(dialog)
        text = QTextEdit(dialog)
        text.setReadOnly(True)
        text.setPlainText(full_report)
        layout.addWidget(text)

        btn_layout = QHBoxLayout()
        close_btn = QPushButton("Fermer", dialog)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        close_btn.clicked.connect(dialog.accept)

        dialog.exec()

        # Ne pas relancer l'exception depuis sys.excepthook : cela peut créer
        # des doublons ou une récursion. L'exception est déjà loguée et affichée.
        return

    from qgis.PyQt.QtWidgets import QMessageBox

    QMessageBox.warning(
        None,
        title.replace(" (mode développeur)", ""),
        f"Une erreur est survenue.\n\nOrigine : {category}\n\n{value}\n\n"
        "Le détail complet est disponible dans le panneau Messages de QGIS.",
    )


# Active le hook global.
sys.excepthook = handle_uncaught_exception


# ============================================================
#            IMPORT DE LA CLASSE PRINCIPALE DU PLUGIN
# ============================================================
def classFactory(iface):
    from .qdrawEVT import QdrawEVT
    return QdrawEVT(iface)
