# -*- coding: utf-8 -*-
# Rimba Sketsa: alat gambar dan seleksi cepat untuk QGIS
# Pengembang: Alfian (meowtret). Turunan dari qdrawEVT (François Thévand)
# dan QDraw (Jérémy Kalsron).
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

from builtins import str
from pathlib import Path

from qgis.PyQt.QtCore import QCoreApplication, pyqtSignal
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
    QgsMessageLog,
    Qgis,
)

from .qt_compat import scoped_enum


# --- Chemin des resources ---
PLUGIN_DIR = Path(__file__).resolve().parent


def plugin_file(*parts) -> str:
    return str(PLUGIN_DIR.joinpath(*parts))


class SketsaSettings(QWidget):
    """Window used to change settings (transparency/color/text font)"""
    settingsChanged = pyqtSignal()

    def __init__(self, iface):
        super().__init__()

        self.iface = iface
        from .logger import redirect_print_to_log
        redirect_print_to_log()
        self.project = QgsProject.instance()

        self.setWindowTitle(self.tr('Rimba Sketsa - Settings'))
        self.setFixedSize(400, 160)
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

        # Mise en page
        vbox = QVBoxLayout()
        vbox.addWidget(self.lbl_opacity)
        vbox.addWidget(self.sld_opacity)
        vbox.addWidget(self.btn_chColor)
        vbox.addWidget(self.btn_chFont)
        vbox.addWidget(self.btn_chColorFont)
        self.setLayout(vbox)


    # --- Traduction ---
    def tr(self, message):
        return QCoreApplication.translate('SketsaSettings', message)

    # --- Slider de transparence ---
    def handler_opacitySliderValue(self, val):
        try:
            self.color.setAlpha(val)
            self.lbl_opacity.setText(f"{self.tr('Opacity')}: {int(val / 2.55)}%")
            self.save_settings()
            self.settingsChanged.emit()
        except Exception as e:
            QgsMessageLog.logMessage(f"Erreur dans handler_opacitySliderValue : {e}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))

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
            QgsMessageLog.logMessage(f"Erreur dans handler_chColor : {e}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))

    # --- Changement de police ---
    def handler_chFont(self):
        try:
            font, ok = self.dlg_font.getFont(self.font)
            if ok:
                self.font = font
                self.save_settings()
                self.settingsChanged.emit()
        except Exception as e:
            QgsMessageLog.logMessage(f"Erreur dans handler_chFont : {e}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))

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
            QgsMessageLog.logMessage(f"Erreur dans handler_chColorFont : {e}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))

    # --- Sauvegarde et restauration des paramètres ---
    def save_settings(self):
        try:
            settings = QgsSettings()
            settings.beginGroup("/RimbaSketsa")
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
            QgsMessageLog.logMessage(f"Erreur dans save_settings : {e}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))

    def restore_settings(self):
        try:
            settings = QgsSettings()
            settings.beginGroup("/RimbaSketsa")
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
            QgsMessageLog.logMessage(f"Erreur dans restore_settings : {e}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))

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
            QgsMessageLog.logMessage("Attribut color introuvable dans SketsaSettings", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))
            return QColor(0, 0, 0, 255)

    def getFont(self):
        """Renvoie la police utilisée pour le texte."""
        try:
            return self.font
        except AttributeError:
            QgsMessageLog.logMessage("Attribut font introuvable dans SketsaSettings", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))
            return QFont('Arial', 12)

    def getColorFont(self):
        """Renvoie la couleur du texte."""
        try:
            return self.colorFont
        except AttributeError:
            QgsMessageLog.logMessage("Attribut colorFont introuvable dans SketsaSettings", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))
            return QColor(0, 0, 0, 255)

    def getOpacity(self):
        """Renvoie l'opacité actuelle (0-255)."""
        try:
            return self.color.alpha()
        except AttributeError:
            QgsMessageLog.logMessage("Attribut color introuvable pour getOpacity", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))
            return 255
