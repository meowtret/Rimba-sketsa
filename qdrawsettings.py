# -*- coding: utf-8 -*-
# qdrawEVT: plugin that makes drawing easier
# Author: Jérémy Kalsron
#         jeremy.kalsron@gmail.com
#
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

import unicodedata
from builtins import str
from pathlib import Path

from qgis.PyQt.QtCore import QCoreApplication, pyqtSignal, QVariant
from qgis.PyQt.QtCore import Qt as QtCoreQt
from qgis.PyQt.QtGui import QColor, QFont, QGuiApplication
from qgis.PyQt.QtWidgets import (
    QWidget,
    QPushButton,
    QSlider,
    QLabel,
    QColorDialog,
    QVBoxLayout,
    QFontDialog,
)

from qgis.core import (
    QgsSettings,
    QgsProject,
    QgsVectorLayer,
    QgsVectorFileWriter,
    QgsWkbTypes,
    QgsField,
    QgsFields,
    QgsLayerTreeGroup,
    QgsMessageLog,
    Qgis,
)

from .qt_compat import (
    MSGBOX_CRITICAL,
    MSGBOX_WARNING,
    scoped_enum,
)


# --- Chemin des resources ---
PLUGIN_DIR = Path(__file__).resolve().parent


def plugin_file(*parts) -> str:
    return str(PLUGIN_DIR.joinpath(*parts))


class QdrawSettings(QWidget):
    """Window used to change settings (transparency/color/event layers/layers path)"""
    settingsChanged = pyqtSignal()

    def __init__(self, form_wgt_libelle, iface):
        super().__init__()

        self.form_wgt_libelle = form_wgt_libelle
        self.iface = iface
        from .logger import redirect_print_to_log
        redirect_print_to_log()
        self.project = QgsProject.instance()

        self.setWindowTitle(self.tr('QdrawEVT - Settings'))
        self.setFixedSize(400, 180)
        self.center()
        self.keepselect = False

        # Chargement des préférences utilisateur
        self.restore_settings()

        # Slider d’opacité
        self.sld_opacity = QSlider(QtCoreQt.Orientation.Horizontal, self)
        self.sld_opacity.setRange(0, 255)
        self.sld_opacity.setValue(self.color.alpha())
        self.sld_opacity.valueChanged.connect(self.handler_opacitySliderValue)
        self.lbl_opacity = QLabel(f"{self.tr('Opacity')}: {int(self.color.alpha() / 2.55)}%", self)

        # Boutons de paramétrage
        self.dlg_color = QColorDialog(self)
        self.btn_chColor = QPushButton(self.tr('Change the drawing color'), self)
        self.btn_chColor.clicked.connect(self.handler_chColor)

        self.dlg_font = QFontDialog(self)
        self.btn_chFont = QPushButton(self.tr('Change text font'), self)
        self.btn_chFont.clicked.connect(self.handler_chFont)

        self.dlg_colorFont = QColorDialog(self)
        self.btn_chColorFont = QPushButton(self.tr('Change text color'), self)
        self.btn_chColorFont.clicked.connect(self.handler_chColorFont)

        self.btn_createLayers = QPushButton(self.tr('Create the group and the event layers'), self)
        self.btn_createLayers.clicked.connect(self.handler_createLayers)

        # Mise en page
        vbox = QVBoxLayout()
        vbox.addWidget(self.lbl_opacity)
        vbox.addWidget(self.sld_opacity)
        vbox.addWidget(self.btn_chColor)
        vbox.addWidget(self.btn_chFont)
        vbox.addWidget(self.btn_chColorFont)
        vbox.addWidget(self.btn_createLayers)
        self.setLayout(vbox)

        # Liste brute (non traduite pour les tests internes)
        self.EVT_groups_list = [
            "Enjeux",
            "Aléas/risques",
            "RDI",
            "Administratif",
            "Fonds de plan"
        ]

    # --- Traduction ---
    def tr(self, message):
        return QCoreApplication.translate('QdrawSettings', message)

    def _translation_strings_for_lupdate(self):
        # Fonction jamais appelée : sert uniquement à faire apparaître les chaînes dans le .ts
        self.tr("Enjeux")
        self.tr("Aléas/risques")
        self.tr("RDI")
        self.tr("Administratif")
        self.tr("Fonds de plan")

    # --- Slider de transparence ---
    def handler_opacitySliderValue(self, val):
        try:
            self.color.setAlpha(val)
            self.lbl_opacity.setText(f"{self.tr('Opacity')}: {int(val / 2.55)}%")
            self.save_settings()
            self.settingsChanged.emit()
        except Exception as e:
            QgsMessageLog.logMessage(f"Erreur dans handler_opacitySliderValue : {e}", "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning"))

    # --- Changement de couleur principale ---
    def handler_chColor(self):
        try:
            color = self.dlg_color.getColor(self.color)
            if color.isValid():
                color.setAlpha(self.color.alpha())
                self.color = color
                self.save_settings()
                self.settingsChanged.emit()
        except Exception as e:
            QgsMessageLog.logMessage(f"Erreur dans handler_chColor : {e}", "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning"))

    # --- Changement de police ---
    def handler_chFont(self):
        try:
            font, ok = self.dlg_font.getFont(self.font)
            if ok:
                self.font = font
                self.save_settings()
                self.settingsChanged.emit()
        except Exception as e:
            QgsMessageLog.logMessage(f"Erreur dans handler_chFont : {e}", "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning"))

    # --- Changement de couleur du texte ---
    def handler_chColorFont(self):
        try:
            color = self.dlg_colorFont.getColor(self.colorFont)
            if color.isValid():
                color.setAlpha(self.color.alpha())
                self.colorFont = color
                self.save_settings()
                self.settingsChanged.emit()
        except Exception as e:
            QgsMessageLog.logMessage(f"Erreur dans handler_chColorFont : {e}", "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning"))

    # --- Sauvegarde et restauration des paramètres ---
    def save_settings(self):
        try:
            settings = QgsSettings()
            settings.beginGroup("/Qdraw")
            settings.setValue("font", self.font.family())
            settings.setValue("fontSize", self.font.pointSize())
            settings.setValue("colorFontRed", self.colorFont.red())
            settings.setValue("colorFontGreen", self.colorFont.green())
            settings.setValue("colorFontBlue", self.colorFont.blue())
            settings.setValue("colorFontAlpha", self.colorFont.alpha())
            settings.setValue("colorRed", self.color.red())
            settings.setValue("colorGreen", self.color.green())
            settings.setValue("colorBlue", self.color.blue())
            settings.setValue("colorAlpha", self.color.alpha())
            settings.endGroup()
        except Exception as e:
            QgsMessageLog.logMessage(f"Erreur dans save_settings : {e}", "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning"))

    def restore_settings(self):
        try:
            settings = QgsSettings()
            settings.beginGroup("/Qdraw")
            self.font = QFont(settings.value("font", 'arial'),
                              int(settings.value("fontSize", 16)))
            self.colorFont = QColor(
                int(settings.value("colorFontRed", 0)),
                int(settings.value("colorFontGreen", 0)),
                int(settings.value("colorFontBlue", 0)),
                int(settings.value("colorFontAlpha", 255))
            )
            self.color = QColor(
                int(settings.value("colorRed", 60)),
                int(settings.value("colorGreen", 151)),
                int(settings.value("colorBlue", 255)),
                int(settings.value("colorAlpha", 255))
            )
            settings.endGroup()
        except Exception as e:
            QgsMessageLog.logMessage(f"Erreur dans restore_settings : {e}", "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning"))

    # --- Création des couches événement ---
    # --- Création des couches événement ---
    def handler_createLayers(self):
        try:
            project = QgsProject.instance()
            root = project.layerTreeRoot()

            if not project.fileName():
                MSGBOX_WARNING(
                    self.iface.mainWindow(),
                    self.tr("Creation of event shapefile"),
                    self.tr("Possible only in a saved project."),
                )
                return

            # ------------------------------------------------------------
            # Helpers
            # ------------------------------------------------------------
            def normalize(txt: str) -> str:
                return ''.join(
                    x for x in unicodedata.normalize('NFKD', txt or "")
                    if unicodedata.category(x)[0] == 'L'
                ).upper()

            def find_group_by_name(name: str):
                n = normalize(name)
                for g in root.children():
                    if isinstance(g, QgsLayerTreeGroup) and normalize(g.name()) == n:
                        return g
                return None

            def find_or_create_group(name: str):
                g = find_group_by_name(name)
                if g is None:
                    g = root.insertGroup(0, name)
                return g

            def layer_loaded_for_path(shp_path: Path) -> QgsVectorLayer | None:
                """
                Retourne une couche déjà chargée dans le projet qui pointe vers ce .shp (si existe),
                sinon None. Compare sur le chemin normalisé.
                """
                target = shp_path.resolve().as_posix().lower()
                for lyr in project.mapLayers().values():
                    if isinstance(lyr, QgsVectorLayer):
                        src = (lyr.source() or "").replace("\\", "/").lower()
                        # Pour OGR, la source peut contenir des paramètres après le .shp
                        if target in src:
                            return lyr
                return None

            def add_layer_to_group(vlayer: QgsVectorLayer, group: QgsLayerTreeGroup):
                """Ajoute la couche au groupe Evenements (sans doublon dans l'arbre)."""
                # si déjà dans l'arbre, ne pas dupliquer
                existing_node = root.findLayer(vlayer.id())
                if existing_node is None:
                    project.addMapLayer(vlayer, addToLegend=True)
                    existing_node = root.findLayer(vlayer.id())

                if existing_node is None:
                    return

                # si déjà sous le bon groupe, OK
                parent = existing_node.parent()
                if parent == group:
                    return

                clone = existing_node.clone()
                group.insertChildNode(0, clone)
                parent.removeChildNode(existing_node)

            # ------------------------------------------------------------
            # 1) Créer les groupes EVT_list S’ILS N’EXISTENT PAS
            # ------------------------------------------------------------
            for raw in reversed(self.EVT_groups_list):
                if find_group_by_name(self.tr(raw)) is None and find_group_by_name(raw) is None:
                    root.insertGroup(0, self.tr(raw))

            # ------------------------------------------------------------
            # 2) Dossier cible : dossier du projet + /Evenements
            # ------------------------------------------------------------
            project_path = Path(project.fileName())
            evt_folder = project_path.parent / "Evenements"

            # Cas 1 : aucun dossier Evenements -> on le crée
            evt_folder.mkdir(parents=True, exist_ok=True)

            QgsMessageLog.logMessage(
                f"Dossier Evenements utilisé : {evt_folder}",
                "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Info")
            )

            # ------------------------------------------------------------
            # 3) Définition des 3 couches requises
            #    - on ne remplace jamais un shp existant
            #    - on recrée seulement si manquant
            # ------------------------------------------------------------
            required = {
                "polygone_evenement": {
                    "filename": "POLYGONE_EVENEMENT.shp",
                    "wkb": scoped_enum(QgsWkbTypes, "Type", "MultiPolygon"),
                    "qml": plugin_file("resources", "POLYGONE_EVENEMENT.qml"),
                    "fields": [
                        ("libelle", QVariant.String),
                        ("date", QVariant.String),
                        ("h_creation", QVariant.String),
                        ("source", QVariant.String),
                        ("h_constat", QVariant.String),
                        ("remarques", QVariant.String),
                        ("surface", QVariant.Double),
                        ("utilisatr", QVariant.String),
                    ],
                },
                "ligne_evenement": {
                    "filename": "LIGNE_EVENEMENT.shp",
                    "wkb": scoped_enum(QgsWkbTypes, "Type", "MultiLineString"),
                    "qml": plugin_file("resources", "LIGNE_EVENEMENT.qml"),
                    "fields": [
                        ("libelle", QVariant.String),
                        ("date", QVariant.String),
                        ("h_creation", QVariant.String),
                        ("source", QVariant.String),
                        ("h_constat", QVariant.String),
                        ("remarques", QVariant.String),
                        ("longueur", QVariant.Double),
                        ("utilisatr", QVariant.String),
                    ],
                },
                "point_evenement": {
                    "filename": "POINT_EVENEMENT.shp",
                    "wkb": scoped_enum(QgsWkbTypes, "Type", "MultiPoint"),
                    "qml": plugin_file("resources", "POINT_EVENEMENT.qml"),
                    "fields": [
                        ("libelle", QVariant.String),
                        ("date", QVariant.String),
                        ("h_creation", QVariant.String),
                        ("source", QVariant.String),
                        ("h_constat", QVariant.String),
                        ("remarques", QVariant.String),
                        ("x_gps", QVariant.Double),
                        ("y_gps", QVariant.Double),
                        ("utilisatr", QVariant.String),
                    ],
                },
            }

            crs = project.crs()
            transform_context = project.transformContext()
            save_options = QgsVectorFileWriter.SaveVectorOptions()
            save_options.driverName = "ESRI Shapefile"
            save_options.fileEncoding = "UTF-8"

            # Groupe "Evenements" dans le projet (légende)
            groupevt = find_or_create_group("Evenements")

            # ------------------------------------------------------------
            # 4) (A) Créer physiquement les shapefiles manquants
            # ------------------------------------------------------------
            to_create = []
            for logical_name, spec in required.items():
                shp_path = evt_folder / spec["filename"]
                if shp_path.is_file():
                    QgsMessageLog.logMessage(
                        f"✅ {spec['filename']} déjà présente (non remplacée).",
                        "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Info")
                    )
                else:
                    QgsMessageLog.logMessage(
                        f"➕ {spec['filename']} manquante -> création.",
                        "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Info")
                    )
                    qfields = QgsFields()
                    for (fname, ftype) in spec["fields"]:
                        qfields.append(QgsField(fname, ftype))
                    to_create.append((logical_name, shp_path, qfields, spec["wkb"], spec["qml"]))

            for logical_name, shp_path, qfields, wkb, qml in to_create:
                writer = QgsVectorFileWriter.create(
                    str(shp_path), qfields, wkb,
                    crs, transform_context, save_options
                )
                if writer.hasError() != scoped_enum(QgsVectorFileWriter, "WriterError", "NoError"):
                    MSGBOX_CRITICAL(
                        self.iface.mainWindow(),
                        self.tr("Error when creating shapefile"),
                        writer.errorMessage(),
                    )
                    del writer
                    continue
                del writer

            # ------------------------------------------------------------
            # 4) (B) Charger dans le projet les 3 couches présentes sur disque
            #         - si déjà chargée : ne rien faire
            #         - sinon : charger + style + read-only + placer sous groupe
            # ------------------------------------------------------------
            for logical_name, spec in required.items():
                shp_path = evt_folder / spec["filename"]

                if not shp_path.is_file():
                    # Si on arrive ici, c'est que la création a échoué (ou droits, etc.)
                    QgsMessageLog.logMessage(
                        f"❌ {spec['filename']} introuvable après tentative de création : {shp_path}",
                        "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning")
                    )
                    continue

                existing = layer_loaded_for_path(shp_path)
                if existing is not None:
                    # Déjà chargée : ne pas remplacer / ne pas recharger
                    QgsMessageLog.logMessage(
                        f"ℹ Couche déjà chargée pour {spec['filename']} (non remplacée).",
                        "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Info")
                    )
                    # on s'assure juste qu'elle est bien sous le groupe Evenements
                    add_layer_to_group(existing, groupevt)
                    continue

                vlayer = QgsVectorLayer(str(shp_path), logical_name, "ogr")
                if not vlayer.isValid():
                    QgsMessageLog.logMessage(
                        f"Erreur : couche {shp_path} invalide.",
                        "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Critical")
                    )
                    continue

                # style si dispo
                try:
                    vlayer.loadNamedStyle(spec["qml"])
                except Exception as e:
                    QgsMessageLog.logMessage(
                        f"Style non appliqué pour {logical_name} ({spec['qml']}) : {e}",
                        "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning")
                    )

                add_layer_to_group(vlayer, groupevt)
                vlayer.setReadOnly(True)
                vlayer.triggerRepaint()

            # Optionnel : fermer la fenêtre settings
            self.close()

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Erreur dans handler_createLayers : {e}",
                "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Critical")
            )
            MSGBOX_CRITICAL(
                self.iface.mainWindow(),
                "QdrawEVT", f"Erreur : {e}"
            )

    def center(self):
        screen = QGuiApplication.primaryScreen().geometry()
        size = self.geometry()
        self.move(
            int((screen.width() - size.width()) / 2),
            int((screen.height() - size.height()) / 2)
        )

    # --- Méthodes d'accès pour compatibilité avec le code principal ---
    def getColor(self):
        """Renvoie la couleur de dessin actuelle."""
        try:
            return self.color
        except AttributeError:
            QgsMessageLog.logMessage("Attribut color introuvable dans QdrawSettings", "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning"))
            return QColor(0, 0, 0, 255)

    def getFont(self):
        """Renvoie la police utilisée pour le texte."""
        try:
            return self.font
        except AttributeError:
            QgsMessageLog.logMessage("Attribut font introuvable dans QdrawSettings", "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning"))
            return QFont('Arial', 12)

    def getColorFont(self):
        """Renvoie la couleur du texte."""
        try:
            return self.colorFont
        except AttributeError:
            QgsMessageLog.logMessage("Attribut colorFont introuvable dans QdrawSettings", "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning"))
            return QColor(0, 0, 0, 255)

    def getOpacity(self):
        """Renvoie l'opacité actuelle (0-255)."""
        try:
            return self.color.alpha()
        except AttributeError:
            QgsMessageLog.logMessage("Attribut color introuvable pour getOpacity", "QdrawEVT", scoped_enum(Qgis, "MessageLevel", "Warning"))
            return 255
