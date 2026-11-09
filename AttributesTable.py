# -*- coding: utf-8 -*-

# Code inspiré de Qgeric: Graphical queries by drawing simple shapes, Author: Jérémy Kalsron - jeremy.kalsron@gmail.com
# Contributor : François Thévand
#         francois.thevand@gmail.com
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from .logger import log

from pathlib import Path
import os
import re
import unicodedata
import weakref
from functools import partial

from qgis.PyQt import QtCore, QtGui
from qgis.PyQt.QtCore import (
    QCoreApplication,
    QDate,
    QDateTime,
    QLocale,
    QSettings,
    QTime,
    QTranslator,
    qVersion,
)
from qgis.PyQt.QtGui import QColor, QGuiApplication, QIcon, QCloseEvent
from qgis.PyQt.QtWidgets import QApplication, QComboBox, QDateEdit, QDateTimeEdit, QDialog, QFileDialog, QInputDialog, QLineEdit, QMenu, QMessageBox, QProgressDialog, QStatusBar, QTabWidget, QTableWidget, QTableWidgetItem, QTimeEdit, QToolBar, QVBoxLayout, QWidget, QWidgetAction
from .qt_compat import QAction, scoped_enum
from qgis.core import (
    Qgis,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsLayerTreeGroup,
    QgsMessageLog,
    QgsProject,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.gui import QgsHighlight

from . import odswriter as ods
from .qt_compat import (
    CUSTOMIZE_WINDOW_HINT,
    CUSTOM_CONTEXT_MENU,
    DISPLAY_ROLE,
    ITEM_IS_EDITABLE,
    MATCH_CONTAINS,
    MATCH_FIXED_STRING,
    MSGBOX_INFORMATION,
    MSGBOX_NO,
    MSGBOX_YES,
    NON_MODAL,
    WA_DELETE_ON_CLOSE,
    WINDOW,
    WINDOW_CLOSE_BUTTON_HINT,
    WINDOW_MAXIMIZE_BUTTON_HINT,
    WINDOW_MINIMIZE_BUTTON_HINT,
    WINDOW_STAYS_ON_TOP_HINT,
    WINDOW_SYSTEM_MENU_HINT,
    WINDOW_TITLE_HINT,
)

# --- Chemin des resources ---
PLUGIN_DIR = Path(__file__).resolve().parent


def plugin_file(*parts) -> str:
    return str(PLUGIN_DIR.joinpath(*parts))


# Display and export attributes from all active layers
class AttributesTable(QDialog):
    _instances = weakref.WeakSet()
    _hooks_installed = False

    # Un attribut passé à une classe se récupère ici dans def __init__
    # def __init__(self, iface, name):
    def __init__(self, name, iface, *, is_evt_mode: bool = False):
        super().__init__(iface.mainWindow() if iface else None)
        self._is_evt_mode = bool(is_evt_mode)
        self.iface = iface
        self._force_close = False
        self.setWindowModality(NON_MODAL)

        # registre global des instances ouvertes
        AttributesTable._instances.add(self)

        # fermeture en cascade si la fenêtre est détruite
        try:

            def _on_destroyed(*_):
                # purge soft : WeakSet va se nettoyer, mais on peut aider si besoin
                # rien d’obligatoire ici, mais au moins pas de capture de self
                return
            self.destroyed.connect(_on_destroyed)
        except Exception:
            log.debug("Ignored exception in AttributesTable.py:131", exc_info=True)

        flags = WINDOW | WINDOW_TITLE_HINT | WINDOW_SYSTEM_MENU_HINT | WINDOW_MINIMIZE_BUTTON_HINT | WINDOW_MAXIMIZE_BUTTON_HINT

        # ✅ croix : désactivée si EVT, activée si non-EVT
        try:
            if self._is_evt_mode:
                flags &= ~WINDOW_CLOSE_BUTTON_HINT
            else:
                flags |= WINDOW_CLOSE_BUTTON_HINT
        except Exception:
            log.debug("Ignored exception in AttributesTable.py:142", exc_info=True)

        self.setWindowFlags(flags)

        # # ✅ IMPORTANT : sous Qt, modifier les flags après création peut nécessiter un "re-show"
        # # (sinon la croix ne reflète pas toujours l'état réel)
        # self.show()
        # self.raise_()
        # self.activateWindow()

        self._is_evt_mode = bool(is_evt_mode)

        from .logger import redirect_print_to_log
        redirect_print_to_log()
        # *** ATTENTION *** : dans le fichier de traduction la ligne <name>QdrawEVT</name> porte sur la classe principale (ici QdrawEVT dans le fichier qdrawEVT.py)
        overrideLocale = QSettings().value("locale/overrideFlag", False, type=bool)
        if not overrideLocale:
            locale = QLocale.system().name()
        else:
            locale = QSettings().value("locale/userLocale", "")
            if locale.__class__.__name__ == 'QVariant':
                locale = 'en'
        locale = locale[0:2]
        locale_path = os.path.join(
            os.path.dirname(__file__),
            'i18n',
            'translate_{}.qm'.format(locale))
        self.translator = None
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        self.setWindowTitle(self.tr('Selection made in %1 perimeter').replace('%1', name))
        self.resize(480, 320)
        self.setMinimumSize(320, 240)
        self.center()

        self.name = name
        # Results export button
        self.btn_saveTab = QAction(QIcon(plugin_file("resources", 'icon_save.png')), self.tr('Save this tab\'s results'), self)
        self.btn_saveTab.triggered.connect(lambda: self.saveAttributes(True))
        self.btn_saveAllTabs = QAction(QIcon(plugin_file("resources", 'icon_saveAll.png')), self.tr('Save all results'), self)
        self.btn_saveAllTabs.triggered.connect(lambda: self.saveAttributes(False))

        # Ajouter un bouton avec icone intégrées à qgis
        # self.btn_monBouton = QAction(QIcon(":images/themes/default/mActionSelectAll.svg"), self.tr('Select all items'), self)

        self.btn_export = QAction(QIcon(plugin_file("resources", 'icon_export.png')), self.tr('Export the selection as a memory layer'), self)
        self.btn_export.triggered.connect(self.exportLayer)
        self.btn_exportAll = QAction(QIcon(plugin_file("resources", 'icon_exportAll.png')), self.tr('Export all tabs as a memory layer'), self)
        self.btn_exportAll.triggered.connect(self.exportAllLayer)
        self.btn_zoom = QAction(QIcon(plugin_file("resources", 'icon_Zoom.png')), self.tr('Zoom to selected attributes'), self)
        self.btn_zoom.triggered.connect(self.zoomToFeature)
        self.btn_selectGeom = QAction(QIcon(plugin_file("resources", 'icon_HlG.png')), self.tr("Highlight feature's geometry"), self)
        self.btn_selectGeom.triggered.connect(self.selectGeomChanged)
        self.btn_rename = QAction(QIcon(plugin_file("resources", 'icon_Settings.png')), self.tr('Settings'), self)
        self.btn_rename.triggered.connect(self.renameWindow)

        self.tabWidget = QTabWidget()  # Tab container
        self.tabWidget.setTabsClosable(True)
        self.tabWidget.currentChanged.connect(self.highlight_features)
        self.tabWidget.tabCloseRequested.connect(self.closeTab)

        self.loadingWindow = QProgressDialog()
        self.loadingWindow.setWindowTitle(self.tr('Loading...'))
        self.loadingWindow.setRange(0, 100)
        self.loadingWindow.setAutoClose(False)
        self.loadingWindow.setCancelButton(None)

        self.project = QgsProject.instance()
        self.root = self.project.layerTreeRoot()

        self.canvas = self.iface.mapCanvas()
        self.canvas.extentsChanged.connect(self.highlight_features)
        self.highlight = []
        self.highlight_rows = []

        toolbar = QToolBar()
        toolbar.addAction(self.btn_saveTab)
        toolbar.addAction(self.btn_saveAllTabs)
        toolbar.addSeparator()
        toolbar.addAction(self.btn_export)
        toolbar.addAction(self.btn_exportAll)
        toolbar.addSeparator()
        toolbar.addAction(self.btn_zoom)
        toolbar.addSeparator()
        toolbar.addAction(self.btn_selectGeom)
        toolbar.addAction(self.btn_rename)

        vbox = QVBoxLayout()
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.addWidget(toolbar)
        vbox.addWidget(self.tabWidget)
        self.setLayout(vbox)

        self.mb = self.iface.messageBar()

        self.selectGeom = False  # False for point, True for geometry

    def force_close_now(self) -> None:
        """
        Fermeture forcée SYNCHRONE (avant les boîtes natives QGIS).
        """
        self._force_close = True
        try:
            self._qdraw_closing = True
        except Exception:
            log.debug("Ignored exception in AttributesTable.py:252", exc_info=True)

        try:
            self.setAttribute(WA_DELETE_ON_CLOSE, True)
        except Exception:
            log.debug("Ignored exception in AttributesTable.py:257", exc_info=True)

        # visuel immédiat
        try:
            self.hide()
        except Exception:
            log.debug("Ignored exception in AttributesTable.py:263", exc_info=True)

        # ✅ fermeture immédiate (pas de singleShot)
        try:
            self.close()
        except Exception:
            log.debug("Ignored exception in AttributesTable.py:269", exc_info=True)

        # ✅ vider tout ce qui est en file (closeEvent, deleteLater, DeferredDelete…)
        try:
            app = QApplication.instance()
            if app:
                app.processEvents()
                QtCore.QCoreApplication.sendPostedEvents(None, scoped_enum(QtCore.QEvent, "Type", "DeferredDelete"))
                app.processEvents()
        except Exception:
            log.debug("Ignored exception in AttributesTable.py:279", exc_info=True)

    @classmethod
    def close_all(cls, reason: str = "") -> None:
        for w in list(cls._instances):
            try:
                w.force_close_now()
            except Exception:
                log.debug("Ignored exception in AttributesTable.py:287", exc_info=True)
        try:
            app = QApplication.instance()
            if app:
                app.processEvents()
                QtCore.QCoreApplication.sendPostedEvents(None, scoped_enum(QtCore.QEvent, "Type", "DeferredDelete"))
                app.processEvents()
        except Exception:
            log.debug("Ignored exception in AttributesTable.py:295", exc_info=True)

    def closeEvent(self, event: QCloseEvent) -> None:
        if getattr(self, "_qdraw_closing", False):
            event.accept()
            return
        self._qdraw_closing = True

        if getattr(self, "_force_close", False):
            event.accept()
            super().closeEvent(event)
            return

        if getattr(self, "_is_evt_mode", False):
            event.ignore()
            self._qdraw_closing = False
            return

        event.accept()
        super().closeEvent(event)

    def layerTreeView(self):
        """Retourne la vue arborescente des couches (Layer Tree View) de QGIS."""
        try:
            if hasattr(self, 'iface') and self.iface is not None:
                return self.iface.layerTreeView()
            # Fallback : accès global
            from qgis.utils import iface
            if iface is not None:
                return iface.layerTreeView()
            else:
                QgsMessageLog.logMessage("Impossible d'accéder à iface.layerTreeView()", "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning"))
                return None
        except Exception as e:
            QgsMessageLog.logMessage(f"[AttributesTable.layerTreeView] Erreur : {e}", "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning"))
            return None

    def renameWindow(self):
        title, ok = QInputDialog.getText(self, self.tr('Rename window'), self.tr('Enter a new title:'))
        if ok:
            self.setWindowTitle(title)

    def closeTab(self, index):
        self.tabWidget.widget(index).deleteLater()
        self.tabWidget.removeTab(index)

    def selectGeomChanged(self):
        if self.selectGeom:
            self.selectGeom = False
            self.btn_selectGeom.setText(self.tr("Highlight feature's geometry"))
            self.btn_selectGeom.setIcon(QIcon(plugin_file("resources", 'icon_HlG.png')))
        else:
            self.selectGeom = True
            self.btn_selectGeom.setText(self.tr("Highlight feature's centroid"))
            self.btn_selectGeom.setIcon(QIcon(plugin_file("resources", 'icon_HlC.png')))
        self.highlight_features()

    def exportAllLayer(self):
        """Exporte toutes les couches visibles des onglets vers des couches mémoire, avec robustesse et gestion d’erreurs."""
        try:
            root = QgsProject.instance().layerTreeRoot()
            if root is None:
                QgsMessageLog.logMessage(
                    "[AttributesTable.exportAllLayer] Impossible d’accéder au layerTreeRoot.",
                    "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Critical")
                )
                return

            # 🔹 Vérification et préparation des groupes principaux
            groups_names = ["DESSINS", "EVENEMENTS", "ENJEUX", "ADMINISTRATIF"]
            groups_found = {}

            for group in root.children():
                try:
                    test = ''.join(
                        x for x in unicodedata.normalize('NFKD', group.name())
                        if unicodedata.category(x)[0] == 'L'
                    ).upper()
                    if test in groups_names:
                        groups_found[test] = group
                        if test in ("DESSINS", "EVENEMENTS", "ADMINISTRATIF"):
                            group.setItemVisibilityCheckedRecursive(False)
                except Exception as e:
                    QgsMessageLog.logMessage(
                        f"[AttributesTable.exportAllLayer] Erreur traitement du groupe {group.name()}: {e}",
                        "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning")
                    )

            # 🔹 Vérification du nombre d’onglets
            tab_count = self.tabWidget.count() if hasattr(self, "tabWidget") else 0
            if tab_count == 0:
                QgsMessageLog.logMessage(
                    "[AttributesTable.exportAllLayer] Aucun onglet présent, rien à exporter.",
                    "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Info")
                )
                return

            # 🔹 Création du groupe d’extraction global
            name_extracts = self.tr("Extracts in {name}").format(name=getattr(self, "name", self.tr("Session")))
            group_extr = root.findGroup(name_extracts)
            if not group_extr:
                root.insertChildNode(0, QgsLayerTreeGroup(name_extracts))
                group_extr = root.findGroup(name_extracts)
                QgsMessageLog.logMessage(
                    f"[AttributesTable.exportAllLayer] Groupe '{name_extracts}' créé.",
                    "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Info")
                )
            else:
                QgsMessageLog.logMessage(
                    f"[AttributesTable.exportAllLayer] Groupe '{name_extracts}' existant réutilisé.",
                    "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Info")
                )

            # 🔹 Export de chaque onglet
            for tab_index in range(tab_count):
                try:
                    tab_widget = self.tabWidget.widget(tab_index)
                    tables = tab_widget.findChildren(QTableWidget)
                    if not tables:
                        continue

                    table = tables[0]
                    table.selectAll()
                    items = table.selectedItems()
                    if not items:
                        continue

                    # Détermination du type géométrique
                    geom_type = items[0].feature.geometry().type()
                    if geom_type == scoped_enum(QgsWkbTypes, "GeometryType", "PointGeometry"):
                        gtype = "Point"
                    elif geom_type == scoped_enum(QgsWkbTypes, "GeometryType", "LineGeometry"):
                        gtype = "LineString"
                    else:
                        gtype = "Polygon"

                    # Collecte des entités uniques
                    features = []
                    for item in items:
                        feat = getattr(item, "feature", None)
                        if feat and feat not in features:
                            features.append(feat)

                    if not features:
                        QgsMessageLog.logMessage(
                            f"[AttributesTable.exportAllLayer] Aucun feature valide trouvé dans l’onglet {table.title}.",
                            "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning")
                        )
                        continue

                    name = self.tr("Extract {title}").format(
                        title=getattr(table, "title", self.tr("Tab {index}").format(index=tab_index))
                    )

                    crs = table.crs.authid() if hasattr(table, "crs") else QgsProject.instance().crs().authid()

                    # Création de la couche mémoire
                    layer = QgsVectorLayer(f"{gtype}?crs={crs}", name, "memory")
                    if not layer.isValid():
                        QgsMessageLog.logMessage(
                            f"[AttributesTable.exportAllLayer] Couche '{name}' invalide, sautée.",
                            "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning")
                        )
                        continue

                    layer.startEditing()
                    layer.dataProvider().addAttributes(features[0].fields().toList())
                    layer.updateFields()
                    layer.dataProvider().addFeatures(features)
                    layer.commitChanges()

                    # Ajout de la couche dans le groupe d’extraction
                    QgsProject.instance().addMapLayer(layer, False)
                    group_extr.insertLayer(0, layer)
                    QgsMessageLog.logMessage(
                        f"[AttributesTable.exportAllLayer] Couche '{name}' exportée avec succès.",
                        "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Info")
                    )

                    # Copie du style
                    try:
                        src_layers = QgsProject.instance().mapLayersByName(table.title)
                        if src_layers:
                            src_layer = src_layers[0]
                            self.iface.setActiveLayer(src_layer)
                            self.iface.actionCopyLayerStyle().trigger()
                            self.iface.setActiveLayer(layer)
                            self.iface.actionPasteLayerStyle().trigger()
                            QgsMessageLog.logMessage(
                                f"[AttributesTable.exportAllLayer] Style copié depuis '{src_layer.name()}'.",
                                "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Info")
                            )
                    except Exception as e_style:
                        QgsMessageLog.logMessage(
                            f"[AttributesTable.exportAllLayer] Erreur copie style '{name}' : {e_style}",
                            "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning")
                        )

                    table.clearSelection()

                except Exception as e_tab:
                    QgsMessageLog.logMessage(
                        f"[AttributesTable.exportAllLayer] Erreur lors de l’export d’un onglet : {e_tab}",
                        "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning")
                    )

            # 🔹 Repli et expansion cohérente des groupes
            try:
                for node in root.children():
                    if isinstance(node, QgsLayerTreeGroup):
                        node.setExpanded(False)

                for g_name in ("DESSINS", "EVENEMENTS"):
                    group = groups_found.get(g_name)
                    if group:
                        group.setItemVisibilityCheckedRecursive(True)
                        group.setExpanded(True)
                        QgsMessageLog.logMessage(
                            f"[AttributesTable.exportAllLayer] Groupe '{group.name()}' réactivé.",
                            "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Info")
                        )

                group_extr.setExpanded(True)
                self.select(name_extracts)
                self.iface.mapCanvas().refresh()
                QgsMessageLog.logMessage(
                    f"[AttributesTable.exportAllLayer] Export global terminé pour '{name_extracts}'.",
                    "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Info")
                )

            except Exception as e_end:
                QgsMessageLog.logMessage(
                    f"[AttributesTable.exportAllLayer] Erreur finale de réorganisation : {e_end}",
                    "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning")
                )

        except Exception as e:
            QgsMessageLog.logMessage(
                f"[AttributesTable.exportAllLayer] Erreur inattendue : {e}",
                "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Critical")
            )

    def exportLayer(self):
        """Exporte la sélection active vers une couche mémoire, de manière robuste et sans interruption."""
        try:
            # Vérification basique de l’état du widget
            if not hasattr(self, "tabWidget") or self.tabWidget is None:
                QgsMessageLog.logMessage(
                    "[AttributesTable.exportLayer] tabWidget introuvable.",
                    "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning")
                )
                return

            if self.tabWidget.count() == 0:
                QgsMessageLog.logMessage(
                    "[AttributesTable.exportLayer] Aucun onglet dans la table, export annulé.",
                    "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Info")
                )
                return

            index = self.tabWidget.currentIndex()
            table_widget = self.tabWidget.widget(index)
            if not table_widget:
                QgsMessageLog.logMessage(
                    "[AttributesTable.exportLayer] Onglet actuel introuvable.",
                    "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning")
                )
                return

            tables = table_widget.findChildren(QTableWidget)
            if not tables:
                QgsMessageLog.logMessage(
                    "[AttributesTable.exportLayer] Aucun QTableWidget trouvé dans l’onglet sélectionné.",
                    "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning")
                )
                return

            table = tables[0]
            table.selectAll()
            items = table.selectedItems()
            if not items:
                QgsMessageLog.logMessage(
                    "[AttributesTable.exportLayer] Aucun élément sélectionné, export annulé.",
                    "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Info")
                )
                table.clearSelection()
                return

            # Définition du nom de la couche et du groupe
            name = self.tr("Extract {}").format(getattr(table, "title", "Unnamed"))
            name_extracts = self.tr("Extracts in {}").format(getattr(self, "name", "Session"))

            root = QgsProject.instance().layerTreeRoot()
            if root is None:
                QgsMessageLog.logMessage(
                    "[AttributesTable.exportLayer] Impossible d’accéder au root du projet.",
                    "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Critical")
                )
                return

            # Création ou récupération du groupe d’extraction
            group_extr = root.findGroup(name_extracts)
            if group_extr is None:
                try:
                    new_group = QgsLayerTreeGroup(name_extracts)
                    root.insertChildNode(0, new_group)
                    group_extr = root.findGroup(name_extracts)
                    QgsMessageLog.logMessage(
                        f"[AttributesTable.exportLayer] Nouveau groupe '{name_extracts}' créé.",
                        "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Info")
                    )
                except Exception as e_group:
                    QgsMessageLog.logMessage(
                        f"[AttributesTable.exportLayer] Erreur lors de la création du groupe : {e_group}",
                        "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Critical")
                    )
                    return
            else:
                QgsMessageLog.logMessage(
                    f"[AttributesTable.exportLayer] Groupe '{name_extracts}' existant réutilisé.",
                    "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Info")
                )

            # Détermination du type géométrique
            try:
                geom_type = items[0].feature.geometry().type()
                if geom_type == scoped_enum(QgsWkbTypes, "GeometryType", "PointGeometry"):
                    gtype = "Point"
                elif geom_type == scoped_enum(QgsWkbTypes, "GeometryType", "LineGeometry"):
                    gtype = "LineString"
                else:
                    gtype = "Polygon"
            except Exception as e_geom:
                QgsMessageLog.logMessage(
                    f"[AttributesTable.exportLayer] Erreur détermination du type géométrique : {e_geom}",
                    "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning")
                )
                gtype = "Polygon"

            # Récupération des entités uniques
            features = []
            try:
                for item in items:
                    feat = getattr(item, "feature", None)
                    if feat and feat not in features:
                        features.append(feat)
            except Exception as e_feat:
                QgsMessageLog.logMessage(
                    f"[AttributesTable.exportLayer] Erreur lors de la collecte des entités : {e_feat}",
                    "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning")
                )

            if not features:
                QgsMessageLog.logMessage(
                    "[AttributesTable.exportLayer] Aucune entité valide trouvée pour l’export.",
                    "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning")
                )
                return

            # Création de la couche mémoire
            try:
                crs = table.crs.authid() if hasattr(table, "crs") else QgsProject.instance().crs().authid()
                layer = QgsVectorLayer(f"{gtype}?crs={crs}", name, "memory")
                if not layer.isValid():
                    QgsMessageLog.logMessage(
                        f"[AttributesTable.exportLayer] Échec de création de la couche mémoire '{name}'.",
                        "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Critical")
                    )
                    return
            except Exception as e_layer:
                QgsMessageLog.logMessage(
                    f"[AttributesTable.exportLayer] Erreur création couche mémoire : {e_layer}",
                    "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Critical")
                )
                return

            # Ajout des attributs et entités
            try:
                layer.startEditing()
                layer.dataProvider().addAttributes(features[0].fields().toList())
                layer.updateFields()
                layer.dataProvider().addFeatures(features)
                layer.commitChanges()
            except Exception as e_add:
                QgsMessageLog.logMessage(
                    f"[AttributesTable.exportLayer] Erreur ajout des entités : {e_add}",
                    "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning")
                )

            # Insertion de la couche dans le groupe
            try:
                QgsProject.instance().addMapLayer(layer, False)
                group_extr.insertLayer(0, layer)
                group_extr.setExpanded(True)
                QgsMessageLog.logMessage(
                    f"[AttributesTable.exportLayer] Couche '{name}' ajoutée dans le groupe '{name_extracts}'.",
                    "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Info")
                )
            except Exception as e_insert:
                QgsMessageLog.logMessage(
                    f"[AttributesTable.exportLayer] Erreur insertion couche dans le groupe : {e_insert}",
                    "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Critical")
                )
                return

            # Copie du style de la couche source
            try:
                src_layers = QgsProject.instance().mapLayersByName(table.title)
                if src_layers:
                    src_layer = src_layers[0]
                    self.iface.setActiveLayer(src_layer)
                    self.iface.actionCopyLayerStyle().trigger()
                    self.iface.setActiveLayer(layer)
                    self.iface.actionPasteLayerStyle().trigger()
                    QgsMessageLog.logMessage(
                        f"[AttributesTable.exportLayer] Style copié depuis '{src_layer.name()}'.",
                        "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Info")
                    )
            except Exception as e_style:
                QgsMessageLog.logMessage(
                    f"[AttributesTable.exportLayer] Erreur lors de la copie du style : {e_style}",
                    "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning")
                )

            # Sélection visuelle du groupe et rafraîchissement
            try:
                self.select(name_extracts)
                layer_node = root.findLayer(layer.id())
                if layer_node:
                    layer_node.setExpanded(False)
                    layer_node.setExpanded(True)
                self.iface.layerTreeView().refreshLayerSymbology(layer.id())
                self.iface.mapCanvas().refresh()
                table.clearSelection()
                QgsMessageLog.logMessage(
                    f"[AttributesTable.exportLayer] Export terminé pour '{name}'.",
                    "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Info")
                )
            except Exception as e_refresh:
                QgsMessageLog.logMessage(
                    f"[AttributesTable.exportLayer] Erreur pendant le rafraîchissement QGIS : {e_refresh}",
                    "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning")
                )
        except Exception as e:
            QgsMessageLog.logMessage(
                f"[AttributesTable.exportLayer] Erreur inattendue : {e}",
                "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Critical")
            )

    def highlight_features(self):
        """Met en surbrillance les entités sélectionnées du tableau actif, de façon robuste."""
        # Nettoyage sûr des highlights précédents
        try:
            for h in getattr(self, "highlight", []):
                try:
                    # Certaines versions exigent un hide() avant la suppression de la scène
                    if hasattr(h, "hide"):
                        h.hide()
                except Exception:
                    log.debug("Ignored exception in AttributesTable.py:754", exc_info=True)
                try:
                    # Selon l’état du canvas, l’item peut déjà avoir été retiré
                    if hasattr(self, "canvas") and self.canvas and self.canvas.scene():
                        self.canvas.scene().removeItem(h)
                except Exception:
                    log.debug("Ignored exception in AttributesTable.py:760", exc_info=True)
        except Exception as e:
            log.warning(f"[highlight_features] Erreur pendant le nettoyage des highlights : {e}")

        # Réinitialisation des collections
        try:
            self.highlight = []
            self.highlight_rows = []
        except Exception:
            # Au cas où les attributs n’existent pas encore
            self.highlight = []
            self.highlight_rows = []

        # Garde-fous sur l’UI
        if not hasattr(self, "tabWidget") or self.tabWidget.count() == 0:
            return
        index = self.tabWidget.currentIndex()
        if index < 0:
            return

        tab = self.tabWidget.widget(index)
        if tab is None:
            return

        # Récupération robuste de la table (premier QTableWidget trouvé dans l’onglet)
        try:
            tables = tab.findChildren(QTableWidget)
            if not tables:
                return
            table = tables[0]
        except Exception as e:
            log.warning(f"[highlight_features] Impossible de récupérer le QTableWidget : {e}")
            return

        # Sélection courante
        try:
            items = table.selectedItems() or []
        except Exception:
            items = []

        if not items:
            # Rien de sélectionné : message de statut réinitialisé si possible
            try:
                if hasattr(tab, "sb"):
                    tab.sb.showMessage(self.tr("No items were selected"))
            except Exception:
                log.debug("Ignored exception in AttributesTable.py:806", exc_info=True)
            return

        # Accumulateurs
        nb = 0
        area = 0.0
        length = 0.0

        # Contexte de reprojection
        project = QgsProject.instance()
        try:
            project_crs = project.crs()
        except Exception:
            project_crs = None

        # Couche de référence pour les highlights (comme dans votre code)
        layer_for_hl = getattr(tab, "layer", None)

        # Évite de compter plusieurs fois la même ligne si plusieurs cellules sont sélectionnées
        seen_rows = set()

        for item in items:
            try:
                row = item.row()
                if row in seen_rows:
                    continue

                # Vérifs robustes sur l’item/feature
                feat = getattr(item, "feature", None)
                if feat is None:
                    continue
                try:
                    geom = feat.geometry()
                except Exception:
                    log.debug("Ignored exception in AttributesTable.py:840", exc_info=True)
                    continue
                if geom is None or geom.isEmpty():
                    continue

                # Choix de la géométrie à surligner (centroïde ou géométrie complète)
                geom_to_show = geom if getattr(self, "selectGeom", False) else geom.centroid()

                # Création du highlight
                try:
                    hl = QgsHighlight(self.canvas, geom_to_show, layer_for_hl)
                    # Couleur rouge comme dans votre code
                    hl.setColor(QColor(255, 0, 0))
                    # Certaines versions apprécient un show() explicite
                    if hasattr(hl, "show"):
                        hl.show()
                    self.highlight.append(hl)
                    self.highlight_rows.append(row)
                except Exception as e_hl:
                    log.warning(f"[highlight_features] Création du highlight échouée (row {row}) : {e_hl}")
                    continue

                # Calcul métrique (aire/longueur) avec reprojection vers CRS projet si possible
                try:
                    g_metric = QgsGeometry(geom)  # copie
                    if layer_for_hl and project_crs:
                        try:
                            xform = QgsCoordinateTransform(layer_for_hl.crs(), project_crs, project)
                            g_metric.transform(xform)
                        except Exception as e_tr:
                            # On continue sans reprojection si ça échoue
                            log.warning(f"[highlight_features] Reprojection échouée (row {row}) : {e_tr}")
                    nb += 1
                    # GeometryType: 2=Polygon, 1=Line, 0=Point
                    gtype = getattr(layer_for_hl, "geometryType", lambda: None)()
                    if gtype == scoped_enum(QgsWkbTypes, "GeometryType", "PolygonGeometry"):
                        area += g_metric.area()
                    elif gtype == scoped_enum(QgsWkbTypes, "GeometryType", "LineGeometry"):
                        length += g_metric.length()
                except Exception as e_metrics:
                    log.warning(f"[highlight_features] Calcul métrique échoué (row {row}) : {e_metrics}")

                seen_rows.add(row)

            except Exception as e_row:
                log.warning(f"[highlight_features] Erreur sur un item sélectionné : {e_row}")

        # Mise à jour de la barre de statut de l’onglet
        try:
            if hasattr(tab, "sb"):
                gtype = getattr(layer_for_hl, "geometryType", lambda: None)()
                if gtype == scoped_enum(QgsWkbTypes, "GeometryType", "PolygonGeometry"):
                    tab.sb.showMessage(self.tr("Selected items: {nb} Area: {area} m²").format(nb=nb, area=area))
                elif gtype == scoped_enum(QgsWkbTypes, "GeometryType", "LineGeometry"):
                    tab.sb.showMessage(self.tr('Selected itemss: {nb} - Length: {lenght}m').format(nb=nb, length=length))
                else:
                    tab.sb.showMessage(self.tr('Selected items: {nb}').format(nb=nb))
        except Exception as e_sb:
            log.warning(self.tr("[highlight_features] Status bar update failed: {e_sb}").format(e_sb=e_sb))

    def tr(self, message):
        return QCoreApplication.translate('AttributesTable', message)

    def zoomToFeature(self):
        """Zoom de manière robuste sur les entités sélectionnées du tableau actif."""
        try:
            # Vérifications de base
            if not hasattr(self, "tabWidget") or self.tabWidget.count() == 0:
                log.info("[zoomToFeature] Aucun onglet dans la table.")
                return

            index = self.tabWidget.currentIndex()
            if index < 0:
                log.info("[zoomToFeature] Aucun onglet actif sélectionné.")
                return

            # Récupération du tableau actif
            tab_widget = self.tabWidget.widget(index)
            if tab_widget is None:
                log.warning("[zoomToFeature] Onglet actif introuvable.")
                return

            tables = tab_widget.findChildren(QTableWidget)
            if not tables:
                log.warning("[zoomToFeature] Aucun QTableWidget trouvé dans l’onglet sélectionné.")
                return

            table = tables[0]

            # Récupération des items sélectionnés
            try:
                items = table.selectedItems() or []
            except Exception as e_items:
                log.warning(f"[zoomToFeature] Impossible d’obtenir la sélection : {e_items}")
                items = []

            if not items:
                log.info("[zoomToFeature] Aucun élément sélectionné pour le zoom.")
                return

            # Collecte des ID de features valides
            feat_ids = []
            valid_features = []
            for item in items:
                feat = getattr(item, "feature", None)
                if feat is not None and hasattr(feat, "id") and hasattr(feat, "geometry"):
                    geom = feat.geometry()
                    if geom and not geom.isEmpty():
                        feat_ids.append(feat.id())
                        valid_features.append(feat)
                    else:
                        log.warning("[zoomToFeature] Géométrie vide ignorée.")
                else:
                    log.warning("[zoomToFeature] Élément sans feature valide ignoré.")

            if not feat_ids:
                log.info("[zoomToFeature] Aucune géométrie valide trouvée pour le zoom.")
                return

            # Récupération de la couche d’origine
            current_layer = getattr(tab_widget, "layer", None)
            if current_layer is None:
                log.warning("[zoomToFeature] Couche associée introuvable dans l’onglet.")
                return

            # Zoom sur la sélection
            if len(valid_features) == 1:
                try:
                    geom = valid_features[0].geometry()
                    if geom and not geom.isEmpty():
                        bbox = geom.buffer(5, 0).boundingBox()  # marge pour les points
                        self.canvas.setExtent(bbox)
                        log.info(f"[zoomToFeature] Zoom sur une seule entité (ID={valid_features[0].id()}).")
                    else:
                        log.warning("[zoomToFeature] Géométrie unique vide, zoom annulé.")
                        return
                except Exception as e_bbox:
                    log.warning(f"[zoomToFeature] Erreur lors du calcul du bounding box : {e_bbox}")
                    return
            else:
                try:
                    self.canvas.zoomToFeatureIds(current_layer, feat_ids)
                    log.info(
                        f"[zoomToFeature] Zoom sur {len(feat_ids)} entités dans la couche '{current_layer.name()}'.")
                except Exception as e_zoom:
                    log.warning(f"[zoomToFeature] Erreur de zoom sur plusieurs entités : {e_zoom}")
                    return

            # Rafraîchissement du canevas
            try:
                self.canvas.refresh()
            except Exception as e_refresh:
                log.warning(f"[zoomToFeature] Erreur lors du rafraîchissement du canevas : {e_refresh}")

        except Exception as e:
            log.critical(f"[zoomToFeature] Erreur inattendue : {e}")

    # Modification F. Thévand ajout paramètre visible :
    # (layer, fields_name, fields_type, cells, idx_visible)

    def addLayer(self, layer, headers, types, features, visible):
        self.layer = layer
        # print(f'layer entrée addLayer : {str(self.layer)})
        tab = QWidget()
        tab.layer = self.layer
        p1_vertical = QVBoxLayout(tab)
        p1_vertical.setContentsMargins(0, 0, 0, 0)

        table = QTableWidget()
        table.itemSelectionChanged.connect(self.highlight_features)
        table.title = self.layer.name()
        table.crs = self.layer.crs()
        table.setColumnCount(len(headers))
        if len(features) > 0:
            table.setRowCount(len(features))
            nbrow = len(features)
            self.loadingWindow.show()
            self.loadingWindow.setLabelText(table.title)
            self.loadingWindow.activateWindow()
            self.loadingWindow.showNormal()

            # Table population
            m = 0
            for feature in features:
                n = 0

                # Ancienne syntaxe :
                #                for cell in feature.attributes():
                #                    item = QTableWidgetItem()
                #                    item.setData(Qt.DisplayRole, cell)
                #                    item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                #                    item.feature = feature
                #                    table.setItem(m, n, item)
                #                    n += 1

                # Modification F. Thévand :
                for idx in visible:
                    try:
                        item = QTableWidgetItem()
                        item.setData(DISPLAY_ROLE, feature[idx])
                        # Fin modification
                        item.setFlags(item.flags() ^ ITEM_IS_EDITABLE)
                        item.feature = feature
                        table.setItem(m, n, item)
                        n += 1
                    except KeyError:
                        log.debug("Ignored exception in AttributesTable.py:1045", exc_info=True)
                m += 1
                self.loadingWindow.setValue(int((float(m) / nbrow) * 100))
                QApplication.processEvents()

        else:
            table.setRowCount(0)

        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionsMovable(True)

        table.types = types
        table.filter_op = []
        table.filters = []
        for i in range(0, len(headers)):
            table.filters.append('')
            table.filter_op.append(0)

        header = table.horizontalHeader()
        header.setContextMenuPolicy(CUSTOM_CONTEXT_MENU)
        header.customContextMenuRequested.connect(partial(self.filterMenu, table))

        table.setSortingEnabled(True)

        p1_vertical.addWidget(table)

        # Status bar to display informations (ie: area)
        tab.sb = QStatusBar()
        p1_vertical.addWidget(tab.sb)

        title = table.title
        # We reduce the title's length to 20 characters
        if len(title) > 20:
            title = title[:20] + '...'

        # We add the number of elements to the tab's title.
        title += ' (' + str(len(features)) + ')'

        self.tabWidget.addTab(tab, title)  # Add the tab to the conatiner
        self.tabWidget.setTabToolTip(self.tabWidget.indexOf(tab), table.title)  # Display the full layer name

    def filterMenu(self, table, pos):
        index = table.columnAt(pos.x())
        menu = QMenu()
        filter_operation = QComboBox()
        if table.types[index] in [10]:
            filter_operation.addItems(['Contains', 'Equals'])
        else:
            filter_operation.addItems(['=', '>', '<'])
        filter_operation.setCurrentIndex(table.filter_op[index])
        action_filter_operation = QWidgetAction(self)
        action_filter_operation.setDefaultWidget(filter_operation)
        if table.types[index] in [14]:
            if not isinstance(table.filters[index], QDate):
                filter_value = QDateEdit()
            else:
                filter_value = QDateEdit(table.filters[index])
        elif table.types[index] in [15]:
            if not isinstance(table.filters[index], QTime):
                filter_value = QTimeEdit()
            else:
                filter_value = QTimeEdit(table.filters[index])
        elif table.types[index] in [16]:
            if not isinstance(table.filters[index], QDateTime):
                filter_value = QDateTimeEdit()
            else:
                filter_value = QDateTimeEdit(table.filters[index])
        else:
            filter_value = QLineEdit(table.filters[index])
        action_filter_value = QWidgetAction(self)
        action_filter_value.setDefaultWidget(filter_value)
        menu.addAction(action_filter_operation)
        menu.addAction(action_filter_value)
        action_filter_apply = QAction(self.tr('Apply'), self)
        action_filter_apply.triggered.connect(partial(self.applyFilter, table, index, filter_value, filter_operation))
        action_filter_cancel = QAction(self.tr('Cancel'), self)
        action_filter_cancel.triggered.connect(partial(self.applyFilter, table, index, None, filter_operation))
        menu.addAction(action_filter_apply)
        menu.addAction(action_filter_cancel)
        menu.exec(QtGui.QCursor.pos())

    def applyFilter(self, table, index, filter_value, filter_operation):
        if filter_value is None:
            table.filters[index] = None
        else:
            if isinstance(filter_value, QDateEdit):
                table.filters[index] = filter_value.date()
            elif isinstance(filter_value, QTimeEdit):
                table.filters[index] = filter_value.time()
            elif isinstance(filter_value, QDateTimeEdit):
                table.filters[index] = filter_value.dateTime()
            else:
                table.filters[index] = filter_value.text()
        table.filter_op[index] = filter_operation.currentIndex()
        nb_elts = 0
        for i in range(0, table.rowCount()):
            table.setRowHidden(i, False)
            nb_elts += 1
        hidden_rows = []
        for nb_col in range(0, table.columnCount()):
            filtered = False
            header = table.horizontalHeaderItem(nb_col).text()
            valid = False
            if table.filters[nb_col] is not None:
                if type(table.filters[nb_col]) in [QDate, QTime, QDateTime]:
                    valid = True
                else:
                    if table.filters[nb_col].strip():
                        valid = True
            if valid:
                filtered = True
                items = None
                if table.types[nb_col] in [10]:  # If it's a string
                    filter_type = None
                    if table.filter_op[nb_col] == 0:  # Contain
                        filter_type = MATCH_CONTAINS
                    if table.filter_op[nb_col] == 1:  # Equal
                        filter_type = MATCH_FIXED_STRING
                    items = table.findItems(table.filters[nb_col], filter_type)
                elif table.types[nb_col] in [14, 15, 16]:  # If it's a date/time
                    items = []
                    for nb_row in range(0, table.rowCount()):
                        item = table.item(nb_row, nb_col)
                        if table.filter_op[nb_col] == 0:  # =
                            if item.data(scoped_enum(QTableWidgetItem, "ItemType", "Type")) == table.filters[nb_col]:
                                items.append(item)
                        if table.filter_op[nb_col] == 1:  # >
                            if item.data(scoped_enum(QTableWidgetItem, "ItemType", "Type")) > table.filters[nb_col]:
                                items.append(item)
                        if table.filter_op[nb_col] == 2:  # <
                            if item.data(scoped_enum(QTableWidgetItem, "ItemType", "Type")) < table.filters[nb_col]:
                                items.append(item)
                else:  # If it's a number
                    items = []
                    for nb_row in range(0, table.rowCount()):
                        item = table.item(nb_row, nb_col)
                        if item.text().strip():
                            if table.filter_op[nb_col] == 0:  # =
                                if float(item.text()) == float(table.filters[nb_col]):
                                    items.append(item)
                            if table.filter_op[nb_col] == 1:  # >
                                if float(item.text()) > float(table.filters[nb_col]):
                                    items.append(item)
                            if table.filter_op[nb_col] == 2:  # <
                                if float(item.text()) < float(table.filters[nb_col]):
                                    items.append(item)
                rows = []
                for item in items:
                    if item.column() == nb_col:
                        rows.append(item.row())
                for i in range(0, table.rowCount()):
                    if i not in rows:
                        if i not in hidden_rows:
                            nb_elts -= 1
                        table.setRowHidden(i, True)
                        hidden_rows.append(i)
            if filtered:
                if header[len(header) - 1] != '*':
                    table.setHorizontalHeaderItem(nb_col, QTableWidgetItem(header + '*'))
            else:
                if header[len(header) - 1] == '*':
                    header = header[:-1]
                    table.setHorizontalHeaderItem(nb_col, QTableWidgetItem(header))

        title = self.tabWidget.tabText(self.tabWidget.currentIndex())
        for i in reversed(range(len(title))):
            if title[i] == ' ':
                break
            title = title[:-1]
        title += '(' + str(nb_elts) + ')'
        self.tabWidget.setTabText(self.tabWidget.currentIndex(), title)

    MAX_SHEET_NAME = 20

    def make_sheet_name(self, raw_title) -> str:
        """Nom de feuille propre, sans chars interdits, tronqué à 20 + « … » si besoin."""
        # défaut traduit si vide/None
        name = (str(raw_title).strip() if raw_title else self.tr("Sheet"))

        # remplace les caractères interdits (Excel/ODS) : \ / : * ? [ ]
        name = re.sub(r'[\\/:*?\[\]]', '_', name)

        # espace propre
        name = re.sub(r'\s+', ' ', name).strip()

        # tronque proprement
        if len(name) > self.MAX_SHEET_NAME:
            name = name[:self.MAX_SHEET_NAME].rstrip() + "…"

        # fallback si tout a été vidé
        if not name:
            name = self.tr("Sheet")

        return name

    def saveAttributes(self, active):
        """Sauvegarde les attributs des tables au format .ods avec écriture atomique (tmp -> replace)."""
        from pathlib import Path
        import os
        import re
        import stat

        def sanitize_filename(s: str, max_len: int = 120) -> str:
            s = re.sub(r'[\\/:*?"<>|]+', '_', s).strip().strip('.')
            s = re.sub(r'\s+', ' ', s)
            return s[:max_len] if len(s) > max_len else s

        # -- Dossier de sortie
        project = QgsProject.instance()
        project_path = Path(project.homePath() or Path.cwd())
        output_dir = project_path / "Extractions"
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            QMessageBox.critical(self, self.tr("Error"), self.tr("Cannot create export folder."))
            return False

        # -- Nom de l’objet de sélection (self.name défini dans __init__)
        selection_object = getattr(self, "name", "") or ""
        if not selection_object:
            title = (self.windowTitle() or "").strip()
            prefix = self.tr("Selection made in")
            if title.lower().startswith(prefix.lower()):
                selection_object = title[len(prefix):].strip(" :")
            if not selection_object:
                selection_object = "Selection"
        selection_object = sanitize_filename(selection_object)

        # -- Nom proposé
        if active:
            current_tab = self.tabWidget.currentWidget()
            if not current_tab:
                QMessageBox.information(self, self.tr("Information"), self.tr("No active tab found."))
                return False
            tables = current_tab.findChildren(QTableWidget)
            if not tables:
                QMessageBox.information(self, self.tr("Information"), self.tr("No data to save."))
                return False
            tab_title = getattr(tables[0], "title", "Attributs") or "Attributs"
            default_name = f"{sanitize_filename(tab_title)} dans {selection_object}"
        else:
            default_name = f"Selection dans {selection_object}"

        # -- Enregistrer sous… (Qt gère la question “remplacer ?”)
        default_file = (output_dir / sanitize_filename(default_name)).with_suffix(".ods")
        file_path_str, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save in..."),
            str(default_file),
            self.tr("OpenDocument Spreadsheet (*.ods)")
        )
        if not file_path_str:
            return False

        file_path = Path(file_path_str)
        if file_path.suffix.lower() != ".ods":
            file_path = file_path.with_suffix(".ods")

        # -- Quelles tables exporter
        if active:
            current_tab = self.tabWidget.currentWidget()
            tabs = current_tab.findChildren(QTableWidget) if current_tab else []
        else:
            tabs = self.tabWidget.findChildren(QTableWidget)

        if not tabs:
            QMessageBox.information(self, self.tr("Information"), self.tr("No data to save."))
            return False

        # -- Écrire dans un fichier temporaire (même dossier), puis remplacer
        tmp_path = file_path.with_suffix(file_path.suffix + ".tmp")
        try:
            # 1) Nettoyage éventuel d'un ancien .tmp
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    log.debug("Ignored exception in AttributesTable.py:1322", exc_info=True)

            # 2) Écriture ODS vers le .tmp
            with ods.writer(str(tmp_path)) as odsfile:
                for table in reversed(tabs):
                    raw_title = getattr(table, "title", self.tr("Sheet") or self.tr("Sheet"))
                    sheet_name = self.make_sheet_name(raw_title)
                    sheet_name = sanitize_filename(sheet_name)

                    sheet = odsfile.new_sheet(sheet_name)
                    sheet.writerow([raw_title])

                    nb_row = table.rowCount()
                    nb_col = table.columnCount()

                    headers = []
                    for i in range(nb_col):
                        hdr = table.horizontalHeaderItem(i)
                        headers.append(hdr.text() if hdr else "")
                    sheet.writerow(headers)

                    for i in range(nb_row):
                        if table.isRowHidden(i):
                            continue
                        row_data = []
                        for j in range(nb_col):
                            item = table.item(i, j)
                            val = item.text() if item else ""
                            try:
                                if val and val[:1] != "0":
                                    val = float(val)
                                elif val.startswith(("0,", "0.")):
                                    val = float(val)
                            except Exception:
                                log.debug("Ignored exception in AttributesTable.py:1356", exc_info=True)
                            row_data.append(val)
                        sheet.writerow(row_data)

            # 3) Si la cible existe et est en lecture seule, tenter d’enlever l’attribut
            if file_path.exists():
                try:
                    mode = file_path.stat().st_mode
                    if not (mode & stat.S_IWRITE):
                        file_path.chmod(mode | stat.S_IWRITE)
                except Exception:
                    # on ignore, on tentera quand même le replace()
                    log.debug("Ignored exception in AttributesTable.py:1368", exc_info=True)

            # 4) Remplacement atomique (échoue proprement si le fichier est ouvert ailleurs)
            try:
                tmp_path.replace(file_path)
            except PermissionError:
                # Fichier cible probablement ouvert dans un tableur
                try:
                    if tmp_path.exists():
                        tmp_path.unlink()
                except Exception:
                    log.debug("Ignored exception in AttributesTable.py:1379", exc_info=True)
                QMessageBox.critical(
                    self,
                    self.tr("Error"),
                    self.tr("Unable to replace the existing file.\n"
                            "Please close it if it is open in another application, then try again.\n\n{path}").format(path=str(file_path))
                )
                return False
            except Exception as e_rep:
                try:
                    if tmp_path.exists():
                        tmp_path.unlink()
                except Exception:
                    log.debug("Ignored exception in AttributesTable.py:1392", exc_info=True)
                QMessageBox.critical(
                    self,
                    self.tr("Error"),
                    self.tr("Unable to write file:\n{e_rep}").format(e_rep=e_rep)
                )
                return False

        finally:
            # Sécurité : tenter de supprimer un .tmp qui trainerait
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    log.debug("Ignored exception in AttributesTable.py:1406", exc_info=True)

        # -- Proposer d’ouvrir -----------------------------------------------
        msg = QMessageBox(self.iface.mainWindow())
        msg.setWindowFlags(WINDOW | WINDOW_STAYS_ON_TOP_HINT | CUSTOMIZE_WINDOW_HINT)
        msg.setIcon(MSGBOX_INFORMATION)
        msg.setWindowTitle(self.tr("Open file?"))
        msg.setText(
            self.tr("ODS workbook created successfully:\n\n{path}\n\nOpen file?").format(path=str(file_path))
        )
        msg.setStandardButtons(MSGBOX_YES | MSGBOX_NO)
        msg.setDefaultButton(MSGBOX_YES)

        # Renommer les boutons (optionnel, plus clair)
        msg.button(MSGBOX_YES).setText(self.tr("Open"))
        msg.button(MSGBOX_NO).setText(self.tr("Cancel"))

        # ✅ Important : récupérer le bouton cliqué, pas le code de retour
        msg.exec()
        if msg.clickedButton() == msg.button(MSGBOX_YES):
            try:
                opened = QtGui.QDesktopServices.openUrl(
                    QtCore.QUrl.fromLocalFile(str(file_path))
                )
                if not opened:
                    raise RuntimeError(self.tr("No application accepted the ODS file."))
            except Exception as e_open:
                QMessageBox.warning(
                    self,
                    self.tr("Error"),
                    self.tr("Unable to open the ODS file automatically:\n\n{e_open}").format(e_open=e_open)
                )

        return True

    def center(self):
        # Déprécié de Qt6 : QGuiApplication.primaryScreen().geometry()
        # reste la méthode de référence disponible via qgis.PyQt.
        screen = QGuiApplication.primaryScreen().geometry()
        size = self.size()
        x = int((screen.width() - size.width()) / 2)
        y = int((screen.height() - size.height()) / 2)
        self.move(x, y)

    def clear(self):
        """Efface proprement toutes les tables et onglets du widget."""
        try:
            log.info("[clear] Nettoyage des tables et onglets de la fenêtre AttributesTable...")
            # Fermer chaque onglet proprement
            count = self.tabWidget.count()
            for i in reversed(range(count)):
                try:
                    widget = self.tabWidget.widget(i)
                    if widget is not None:
                        # Supprimer tous les QTableWidget enfants
                        for table in widget.findChildren(QTableWidget):
                            try:
                                table.clear()
                                table.deleteLater()
                            except Exception as e_table:
                                log.warning(f"[clear] Erreur lors de la suppression d’un QTableWidget : {e_table}")
                        widget.deleteLater()
                    self.tabWidget.removeTab(i)
                except Exception as e_tab:
                    log.warning(f"[clear] Erreur lors du retrait d’un onglet : {e_tab}")
            # Double sécurité : suppression des références résiduelles
            self.tabWidget.clear()
            QApplication.processEvents()

            log.info("[clear] Nettoyage terminé avec succès.")
        except Exception as e_main:
            log.critical(f"[clear] Erreur inattendue pendant le nettoyage : {e_main}")

    def select(self, group_extr):
        """Sélectionne un groupe de couches dans l’arborescence QGIS (QGIS 3.22 → 3.42)."""
        try:
            view = self.iface.layerTreeView()
            if view is None:
                return

            root = QgsProject.instance().layerTreeRoot()
            if not root:
                return

            # Recherche du groupe
            group = None
            for child in root.children():
                if child.name().lower() == str(group_extr).lower():
                    group = child
                    break

            if group is None:
                QgsMessageLog.logMessage(
                    f"[AttributesTable.select] Groupe '{group_extr}' introuvable.",
                    "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Info")
                )
                return

            proxy_model = view.model()

            # --- Proxy → source ---
            if hasattr(proxy_model, "sourceModel"):
                source_model = proxy_model.sourceModel()
            else:
                source_model = proxy_model

            # --------------------------------------------------
            # API COMPAT : indexFromLayerTreeNode / indexFromNode
            # --------------------------------------------------
            index_source = None

            if hasattr(source_model, "indexFromLayerTreeNode"):
                index_source = source_model.indexFromLayerTreeNode(group)
            elif hasattr(source_model, "indexFromNode"):
                index_source = source_model.indexFromNode(group)
            else:
                QgsMessageLog.logMessage(
                    "[AttributesTable.select] Impossible de créer un index pour le groupe.",
                    "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning")
                )
                return

            if not index_source or not index_source.isValid():
                return

            # Remap vers proxy si nécessaire
            if proxy_model is not source_model and hasattr(proxy_model, "mapFromSource"):
                index = proxy_model.mapFromSource(index_source)
            else:
                index = index_source

            if index.isValid():
                view.setCurrentIndex(index)

            QgsMessageLog.logMessage(
                f"[AttributesTable.select] Groupe '{group.name()}' sélectionné.",
                "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Info")
            )

        except Exception as e:
            QgsMessageLog.logMessage(
                f"[AttributesTable.select] Erreur inattendue : {e}",
                "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Critical")
            )
