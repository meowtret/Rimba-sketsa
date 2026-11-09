# -*- coding: utf-8 -*-
from .qt_compat import BUTTONBOX_CANCEL, BUTTONBOX_OK, DIALOG_ACCEPTED, scoped_enum
# QDraw: plugin that makes drawing easier
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

from qgis.PyQt.QtCore import QCoreApplication, Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QComboBox,
    QLineEdit,
    QVBoxLayout,
    QCheckBox,
    QDialogButtonBox,
    QLabel,
    QTextEdit,
)

from qgis.core import QgsProject, QgsWkbTypes, QgsMapLayer

import unicodedata
from typing import Optional


class QDrawLayerDialog(QDialog):

    def __init__(
        self,
        iface,
        gtype=None,
        layer_evt_name=None,
        draw_shape=None,
        evt=False,
        toolname=None,
        title_override: Optional[str] = None,
        label_override: Optional[str] = None,
        placeholder_override: Optional[str] = None,
        **kwargs,
    ):

        super().__init__()
        self.iface = iface
        self.draw_shape = draw_shape or gtype
        self.toolname = toolname or ""

        from .logger import redirect_print_to_log
        redirect_print_to_log()

        # --------------------------------------------------
        # 1) Détermination du type de géométrie (COMME ORIGINAL)
        # --------------------------------------------------
        if gtype == 'text':
            self.gtype = 'text'
        elif gtype in ('point', 'XYpoint'):
            self.gtype = 'Point'
        elif gtype == 'line':
            self.gtype = 'LineString'
        else:
            self.gtype = 'Polygon'
        # --------------------------------------------------
        # 2) Widgets (CRÉER AVANT USAGE)
        # --------------------------------------------------
        self.lbl_prompt = QLabel(self.tr("Give a name to the item:"))

        self.name = QLineEdit()
        self.name.setPlaceholderText(self.tr("Name…"))

        self.text_multiline = QTextEdit()
        self.text_multiline.setPlaceholderText(self.tr("Text…"))
        self.text_multiline.setVisible(False)

        # --------------------------------------------------
        # 3) UI adaptative (APRÈS création widgets)
        # --------------------------------------------------
        self.setWindowTitle(self.tr("Drawing"))  # défaut

        if gtype == "text":
            self.setWindowTitle(self.tr("Add text"))
            self.lbl_prompt.setText(self.tr("Type the text to display:"))
            self.name.setVisible(False)
            self.text_multiline.setVisible(True)

        elif gtype in ("point", "XYpoint"):
            self.setWindowTitle(self.tr("Add point"))
            self.lbl_prompt.setText(self.tr("Give a name to the point:"))
            self.name.setPlaceholderText(self.tr("Point…"))

        elif gtype == "line":
            self.setWindowTitle(self.tr("Add line"))
            self.lbl_prompt.setText(self.tr("Give a name to the line:"))
            self.name.setPlaceholderText(self.tr("Line…"))

        else:
            self.setWindowTitle(self.tr("Add polygon"))
            self.lbl_prompt.setText(self.tr("Give a name to the polygon:"))
            self.name.setPlaceholderText(self.tr("Polygon…"))

        # Adaptation toolname (optionnel)
        if self.toolname == "drawBuffer":
            self.setWindowTitle(self.tr("Buffer selection"))
            self.lbl_prompt.setText(self.tr("Name this selection (buffer):"))
            self.name.setPlaceholderText(self.tr("Buffer…"))
        # --------------------------------------------------
        # 3bis) Override dynamique (tampon/polygone) - APRES titres par défaut
        # --------------------------------------------------
        if title_override:
            self.setWindowTitle(title_override)
        if label_override:
            self.lbl_prompt.setText(label_override)
        if placeholder_override:
            if gtype == "text":
                self.text_multiline.setPlaceholderText(placeholder_override)
            else:
                self.name.setPlaceholderText(placeholder_override)
        # --------------------------------------------------
        # 4) Liste couches
        # --------------------------------------------------
        self.layerBox = QComboBox()
        self.layers = []

        target_evt_only = bool(evt and layer_evt_name and self.gtype != 'text')
        target_evt_norm = self._normalize_layer_name(layer_evt_name) if layer_evt_name else ""

        for layer in QgsProject.instance().mapLayers().values():
            if layer.type() != scoped_enum(QgsMapLayer, "LayerType", "VectorLayer"):
                continue

            add_layer = False

            if target_evt_only:
                # En mode EVT, une forme évènement ne doit jamais proposer une
                # couche de dessin standard. La seule cible autorisée est celle
                # imposée par qdrawEVT.py : POINT/LIGNE/POLYGONE_EVENEMENT.
                add_layer = self._normalize_layer_name(layer.name()) == target_evt_norm
            else:
                # Hors mode EVT : comportement QDraw classique, proposition des
                # couches compatibles avec la géométrie.
                geom_type = QgsWkbTypes.geometryType(layer.wkbType())
                if self.gtype in ("Point", "text"):
                    add_layer = geom_type == scoped_enum(QgsWkbTypes, "GeometryType", "PointGeometry")
                elif self.gtype == "LineString":
                    add_layer = geom_type == scoped_enum(QgsWkbTypes, "GeometryType", "LineGeometry")
                else:
                    add_layer = geom_type == scoped_enum(QgsWkbTypes, "GeometryType", "PolygonGeometry")

            if add_layer and layer not in self.layers:
                self.layers.append(layer)
                self.layerBox.addItem(layer.name())

        # --------------------------------------------------
        # 5) Checkbox ajouter à une couche existante (LOGIQUE ORIGINALE)
        # --------------------------------------------------
        self.addLayer = QCheckBox(self.tr('Add to an existing layer'))
        self.addLayer.toggled.connect(self.addLayerChecked)

        if not evt:
            self.addLayer.setEnabled(True)
            self.addLayer.setChecked(False)
        else:
            if self.gtype != 'text':
                self.addLayer.setEnabled(False)
                self.addLayer.setChecked(True)
            else:
                self.addLayer.setEnabled(False)
                self.addLayer.setChecked(False)

        # --------------------------------------------------
        # 6) Boutons OK / Annuler
        # --------------------------------------------------
        buttons = QDialogButtonBox(
            BUTTONBOX_OK | BUTTONBOX_CANCEL,
            Qt.Orientation.Horizontal,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        # --------------------------------------------------
        # 7) Layout (NE PAS oublier text_multiline)
        # --------------------------------------------------
        vbox = QVBoxLayout()
        vbox.addWidget(self.lbl_prompt)
        vbox.addWidget(self.name)
        vbox.addWidget(self.text_multiline)   # ✅ ajouté
        vbox.addWidget(self.addLayer)
        vbox.addWidget(self.layerBox)

        if not self.layers:
            self.addLayer.setEnabled(False)
            self.layerBox.setEnabled(False)

        vbox.addWidget(buttons)
        self.setLayout(vbox)

        # Focus
        if gtype == "text":
            self.text_multiline.setFocus()
        else:
            self.name.setFocus()

    @staticmethod
    def _normalize_layer_name(name):
        return ''.join(
            x for x in unicodedata.normalize('NFKD', str(name or ''))
            if unicodedata.category(x)[0] == 'L'
        ).upper()

    def tr(self, message):
        return QCoreApplication.translate('QDrawLayerDialog', message)

    def addLayerChecked(self):
        self.layerBox.setEnabled(self.addLayer.isChecked())

    @staticmethod
    def getName(
            iface,
            gtype,
            layerevt,
            evt,
            toolname=None,
            draw_shape=None,
            title_override: Optional[str] = None,
            label_override: Optional[str] = None,
            placeholder_override: Optional[str] = None,
    ):
        dialog = QDrawLayerDialog(
            iface,
            gtype=gtype,
            layer_evt_name=layerevt,  # ⚠️ ton __init__ attend layer_evt_name
            evt=evt,
            draw_shape=draw_shape,
            toolname=toolname,
            title_override=title_override,
            label_override=label_override,
            placeholder_override=placeholder_override,
        )
        result = dialog.exec()

        if gtype == "text":
            txt = dialog.text_multiline.toPlainText()
        else:
            txt = dialog.name.text()

        return (
            txt,
            dialog.addLayer.isChecked(),
            dialog.layerBox.currentIndex(),
            dialog.layers,
            result == DIALOG_ACCEPTED,
        )
