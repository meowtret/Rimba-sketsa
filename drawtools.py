# -*- coding: utf-8 -*-
# Rimba Sketsa (turunan qdrawEVT / QDraw): alat gambar pada kanvas peta
# Author: Jérémy Kalsron, François Thévand
# Robustification: Maintien de la logique d’origine, compatibilité QGIS 3.34 / PyQt6

from __future__ import print_function
from builtins import range
from math import sqrt, pi, cos, sin
from qgis.gui import (
    QgsMapTool,
    QgsRubberBand,
    QgsMapToolEmitPoint,
    QgsProjectionSelectionDialog
)
from qgis.core import (
    QgsWkbTypes,
    QgsPointXY,
    QgsMessageLog,
    Qgis,
)
from qgis.PyQt.QtCore import (
    Qt,
    QCoreApplication,
    pyqtSignal,
    QPoint,
    QRegularExpression,
)
from qgis.PyQt.QtGui import (
    QDoubleValidator,
    QRegularExpressionValidator,
    QIntValidator,
    QKeySequence,
)
from qgis.PyQt.QtWidgets import (
    QDialog,
    QLineEdit,
    QMessageBox,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QGroupBox,
    QVBoxLayout,
    QComboBox,
    QPushButton,
    QInputDialog,
)

from .qt_compat import (
    BUTTONBOX_CANCEL,
    BUTTONBOX_OK,
    DIALOG_ACCEPTED,
    ORIENTATION_HORIZONTAL,
    make_regex,
    scoped_enum,
)


def msg_inf(msg='', parent=None):
    """Affiche un message d'information sécurisé."""
    try:
        QMessageBox.information(parent, 'Information', msg)
    except Exception as e:
        QgsMessageLog.logMessage(f"[msg_inf] Erreur: {e}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))


# --------------------------------------------------------------------
# ---------------------- OUTIL RECTANGLE -----------------------------
# --------------------------------------------------------------------
class DrawRect(QgsMapToolEmitPoint):
    selectionDone = pyqtSignal()
    move = pyqtSignal()

    def __init__(self, iface, couleur):
        canvas = iface.mapCanvas() if iface else None
        super().__init__(canvas)
        self.iface = iface
        self.canvas = canvas
        self.rb = QgsRubberBand(self.canvas, scoped_enum(QgsWkbTypes, "GeometryType", "PolygonGeometry")) if canvas else None
        if self.rb:
            self.rb.setColor(couleur)
        self.reset()

    def reset(self):
        self.startPoint = self.endPoint = None
        self.isEmittingPoint = False
        if self.rb:
            self.rb.reset(scoped_enum(QgsWkbTypes, "GeometryType", "PolygonGeometry"))

    def canvasPressEvent(self, e):
        if not e or e.button() != Qt.MouseButton.LeftButton:
            return
        try:
            self.startPoint = self.toMapCoordinates(e.pos())
            self.endPoint = self.startPoint
            self.isEmittingPoint = True
        except Exception as err:
            QgsMessageLog.logMessage(f"[DrawRect] PressEvent: {err}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))

    def canvasMoveEvent(self, e):
        if not self.isEmittingPoint:
            return
        try:
            self.move.emit()
            self.endPoint = self.toMapCoordinates(e.pos())
            self.showRect(self.startPoint, self.endPoint)
        except Exception as err:
            QgsMessageLog.logMessage(f"[DrawRect] MoveEvent: {err}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))

    def canvasReleaseEvent(self, e):
        if not e or e.button() != Qt.MouseButton.LeftButton:
            return
        try:
            self.isEmittingPoint = False
            if self.rb.numberOfVertices() > 3:
                self.selectionDone.emit()
            else:
                width, height, ok = RectangleDialog().getSize()
                if width > 0 and height > 0 and ok:
                    self.rb.addPoint(QgsPointXY(
                        self.startPoint.x() + width,
                        self.startPoint.y() - height))
                    self.showRect(self.startPoint,
                                  QgsPointXY(self.startPoint.x() + width, self.startPoint.y() - height))
                    self.selectionDone.emit()
        except Exception as err:
            QgsMessageLog.logMessage(f"[DrawRect] ReleaseEvent: {err}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))

    def showRect(self, startPoint, endPoint):
        if not startPoint or not endPoint:
            return
        try:
            self.rb.reset(scoped_enum(QgsWkbTypes, "GeometryType", "PolygonGeometry"))
            if startPoint.x() == endPoint.x() or startPoint.y() == endPoint.y():
                return
            points = [
                QgsPointXY(startPoint.x(), startPoint.y()),
                QgsPointXY(startPoint.x(), endPoint.y()),
                QgsPointXY(endPoint.x(), endPoint.y()),
                QgsPointXY(endPoint.x(), startPoint.y())
            ]
            for pt in points[:-1]:
                self.rb.addPoint(pt, False)
            self.rb.addPoint(points[-1], True)
            self.rb.show()
        except Exception as err:
            QgsMessageLog.logMessage(f"[DrawRect] showRect: {err}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))

    def deactivate(self):
        if self.rb:
            self.rb.reset(scoped_enum(QgsWkbTypes, "GeometryType", "PolygonGeometry"))
        super().deactivate()


class RectangleDialog(QDialog):

    def tr(self, message):
        return QCoreApplication.translate('RectangleDialog', message)

    """Fenêtre de saisie largeur/hauteur."""
    def __init__(self):
        super().__init__()

        self.setWindowTitle(self.tr('Rectangle size'))
        self.width = QLineEdit()
        self.height = QLineEdit()
        self.width.setValidator(QDoubleValidator())
        self.height.setValidator(QDoubleValidator())
        buttons = QDialogButtonBox(BUTTONBOX_OK | BUTTONBOX_CANCEL, ORIENTATION_HORIZONTAL, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        grid = QGridLayout()
        grid.addWidget(QLabel(self.tr('Give a size in m:')), 0, 0, 1, 2)
        grid.addWidget(QLabel(self.tr('Width:')), 1, 0)
        grid.addWidget(self.width, 1, 1)
        grid.addWidget(QLabel(self.tr('Height:')), 2, 0)
        grid.addWidget(self.height, 2, 1)
        grid.addWidget(buttons, 3, 0, 1, 2)
        self.setLayout(grid)

    def getSize(self):
        try:
            dialog = RectangleDialog()
            result = dialog.exec()
            w = float(dialog.width.text()) if dialog.width.text().strip() else 0
            h = float(dialog.height.text()) if dialog.height.text().strip() else 0
            return w, h, result == DIALOG_ACCEPTED
        except Exception as e:
            QgsMessageLog.logMessage(f"[RectangleDialog] Erreur: {e}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))
            return 0, 0, False


# --------------------------------------------------------------------
# ---------------------- OUTIL POLYGONE ------------------------------
# --------------------------------------------------------------------
class DrawPolygon(QgsMapTool):
    selectionDone = pyqtSignal()
    move = pyqtSignal()

    def __init__(self, iface, couleur):
        canvas = iface.mapCanvas() if iface else None
        super().__init__(canvas)
        self.canvas = canvas
        self.iface = iface
        self.status = 0
        self.rb = QgsRubberBand(self.canvas, scoped_enum(QgsWkbTypes, "GeometryType", "PolygonGeometry")) if canvas else None
        if self.rb:
            self.rb.setColor(couleur)

    def keyPressEvent(self, e):
        try:
            if e.matches(scoped_enum(QKeySequence, "StandardKey", "Undo")) and self.rb and self.rb.numberOfVertices() > 1:
                self.rb.removeLastPoint()
        except Exception as err:
            QgsMessageLog.logMessage(f"[DrawPolygon] keyPressEvent: {err}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))

    def canvasPressEvent(self, e):
        try:
            if not self.rb:
                return
            if e.button() == Qt.MouseButton.LeftButton:
                if self.status == 0:
                    self.rb.reset(scoped_enum(QgsWkbTypes, "GeometryType", "PolygonGeometry"))
                    self.status = 1
                self.rb.addPoint(self.toMapCoordinates(e.pos()))
            else:
                if self.rb.numberOfVertices() > 2:
                    self.status = 0
                    self.selectionDone.emit()
                else:
                    self.reset()
        except Exception as err:
            QgsMessageLog.logMessage(f"[DrawPolygon] PressEvent: {err}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))

    def canvasMoveEvent(self, e):
        try:
            if not self.rb:
                return
            if self.rb.numberOfVertices() > 0 and self.status == 1:
                self.rb.removeLastPoint(0)
                self.rb.addPoint(self.toMapCoordinates(e.pos()))
            self.move.emit()
        except Exception as err:
            QgsMessageLog.logMessage(f"[DrawPolygon] MoveEvent: {err}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))

    def reset(self):
        self.status = 0
        if self.rb:
            self.rb.reset(scoped_enum(QgsWkbTypes, "GeometryType", "PolygonGeometry"))

    def deactivate(self):
        if self.rb:
            self.rb.reset(scoped_enum(QgsWkbTypes, "GeometryType", "PolygonGeometry"))
        super().deactivate()


# --------------------------------------------------------------------
# ---------------------- OUTIL CERCLE --------------------------------
# --------------------------------------------------------------------
def rbcircle(rb, center, edgePoint, N):
    """Dessine un cercle via RubberBand"""
    try:
        r = sqrt(center.sqrDist(edgePoint))
        rb.reset(scoped_enum(QgsWkbTypes, "GeometryType", "PolygonGeometry"))
        for itheta in range(N + 1):
            theta = itheta * (2.0 * pi / N)
            rb.addPoint(QgsPointXY(center.x() + r * cos(theta), center.y() + r * sin(theta)))
    except Exception as err:
        QgsMessageLog.logMessage(f"[rbcircle] Erreur: {err}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))


class DrawCircle(QgsMapTool):
    selectionDone = pyqtSignal()
    move = pyqtSignal()

    def tr(self, message):
        return QCoreApplication.translate('DrawCircle', message)

    def __init__(self, iface, color, segments):
        canvas = iface.mapCanvas() if iface else None
        super().__init__(canvas)
        self.canvas = canvas
        self.iface = iface
        self.status = 0
        self.segments = segments
        self.rb = QgsRubberBand(self.canvas, scoped_enum(QgsWkbTypes, "GeometryType", "PolygonGeometry")) if canvas else None
        if self.rb:
            self.rb.setColor(color)

    def canvasPressEvent(self, e):
        if not e or e.button() != Qt.MouseButton.LeftButton:
            return
        try:
            self.status = 1
            self.center = self.toMapCoordinates(e.pos())
            rbcircle(self.rb, self.center, self.center, self.segments)
        except Exception as err:
            QgsMessageLog.logMessage(f"[DrawCircle] PressEvent: {err}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))

    def canvasMoveEvent(self, e):
        if self.status != 1:
            return
        try:
            cp = self.toMapCoordinates(e.pos())
            rbcircle(self.rb, self.center, cp, self.segments)
            self.rb.show()
            self.move.emit()
        except Exception as err:
            QgsMessageLog.logMessage(f"[DrawCircle] MoveEvent: {err}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))

    def canvasReleaseEvent(self, e):
        try:
            if not e or e.button() != Qt.MouseButton.LeftButton:
                return
            self.status = 0
            if self.rb.numberOfVertices() > 3:
                self.selectionDone.emit()
            else:
                radius, ok = QInputDialog.getDouble(self.iface.mainWindow(), self.tr('Radius'), self.tr('Give a radius in m:'), min=0)
                if ok and radius > 0:
                    cp = self.toMapCoordinates(e.pos())
                    cp.setX(cp.x() + radius)
                    rbcircle(self.rb, self.toMapCoordinates(e.pos()), cp, self.segments)
                    self.rb.show()
                    self.selectionDone.emit()
        except Exception as err:
            QgsMessageLog.logMessage(f"[DrawCircle] ReleaseEvent: {err}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))

    def reset(self):
        self.status = 0
        if self.rb:
            self.rb.reset(scoped_enum(QgsWkbTypes, "GeometryType", "PolygonGeometry"))

    def deactivate(self):
        if self.rb:
            self.rb.reset(scoped_enum(QgsWkbTypes, "GeometryType", "PolygonGeometry"))
        super().deactivate()


# --------------------------------------------------------------------
# ---------------------- OUTIL LIGNE ---------------------------------
# --------------------------------------------------------------------
class DrawLine(QgsMapTool):
    selectionDone = pyqtSignal()
    move = pyqtSignal()

    def __init__(self, iface, couleur):
        canvas = iface.mapCanvas() if iface else None
        super().__init__(canvas)
        self.canvas = canvas
        self.iface = iface
        self.status = 0
        self.rb = QgsRubberBand(self.canvas, scoped_enum(QgsWkbTypes, "GeometryType", "LineGeometry")) if canvas else None
        if self.rb:
            self.rb.setColor(couleur)

    def keyPressEvent(self, e):
        try:
            if e.matches(scoped_enum(QKeySequence, "StandardKey", "Undo")) and self.rb.numberOfVertices() > 1:
                self.rb.removeLastPoint()
        except Exception as err:
            QgsMessageLog.logMessage(f"[DrawLine] keyPressEvent: {err}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))

    def canvasPressEvent(self, e):
        try:
            if e.button() == Qt.MouseButton.LeftButton:
                if self.status == 0:
                    self.rb.reset(scoped_enum(QgsWkbTypes, "GeometryType", "LineGeometry"))
                    self.status = 1
                self.rb.addPoint(self.toMapCoordinates(e.pos()))
            else:
                if self.rb.numberOfVertices() > 2:
                    self.status = 0
                    self.selectionDone.emit()
                else:
                    self.reset()
        except Exception as err:
            QgsMessageLog.logMessage(f"[DrawLine] PressEvent: {err}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))

    def canvasMoveEvent(self, e):
        try:
            if self.rb.numberOfVertices() > 0 and self.status == 1:
                self.rb.removeLastPoint(0)
                self.rb.addPoint(self.toMapCoordinates(e.pos()))
            self.move.emit()
        except Exception as err:
            QgsMessageLog.logMessage(f"[DrawLine] MoveEvent: {err}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))

    def reset(self):
        self.status = 0
        if self.rb:
            self.rb.reset(scoped_enum(QgsWkbTypes, "GeometryType", "LineGeometry"))

    def deactivate(self):
        if self.rb:
            self.rb.reset(scoped_enum(QgsWkbTypes, "GeometryType", "LineGeometry"))
        super().deactivate()


# --------------------------------------------------------------------
# ---------------------- OUTIL POINT ---------------------------------
# --------------------------------------------------------------------
class DrawPoint(QgsMapTool):
    selectionDone = pyqtSignal()

    def __init__(self, iface, couleur):
        canvas = iface.mapCanvas() if iface else None
        super().__init__(canvas)
        self.canvas = canvas
        self.iface = iface
        self.rb = QgsRubberBand(self.canvas, scoped_enum(QgsWkbTypes, "GeometryType", "PointGeometry")) if canvas else None
        if self.rb:
            self.rb.setColor(couleur)
            self.rb.setWidth(3)

    def canvasReleaseEvent(self, e):
        if not e or e.button() != Qt.MouseButton.LeftButton:
            return
        try:
            self.rb.addPoint(self.toMapCoordinates(e.pos()))
            self.selectionDone.emit()
        except Exception as err:
            QgsMessageLog.logMessage(f"[DrawPoint] ReleaseEvent: {err}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))

    def reset(self):
        if self.rb:
            self.rb.reset(scoped_enum(QgsWkbTypes, "GeometryType", "PointGeometry"))

    def deactivate(self):
        if self.rb:
            self.rb.reset(scoped_enum(QgsWkbTypes, "GeometryType", "PointGeometry"))
        super().deactivate()


# --------------------------------------------------------------------
# ---------------------- OUTIL SELECTION POINT -----------------------
# --------------------------------------------------------------------
class SelectPoint(QgsMapTool):
    select = pyqtSignal()
    selectionDone = pyqtSignal()

    def __init__(self, iface, couleur):
        canvas = iface.mapCanvas() if iface else None
        super().__init__(canvas)
        self.canvas = canvas
        self.iface = iface
        self.rb = QgsRubberBand(self.canvas, scoped_enum(QgsWkbTypes, "GeometryType", "PolygonGeometry"))
        self.rb.setColor(couleur)
        self.rbSelect = QgsRubberBand(self.canvas, scoped_enum(QgsWkbTypes, "GeometryType", "PolygonGeometry"))
        self.rbSelect.setColor(couleur)
        self.last_click_map_point = None
        self.last_canvas_pos = None

    def canvasReleaseEvent(self, e):
        try:
            if e.button() == Qt.MouseButton.LeftButton:
                self.last_canvas_pos = e.pos()
                # mémorise le point cliqué en coordonnées carte
                self.last_click_map_point = self.toMapCoordinates(e.pos())

                self.rbSelect.reset(scoped_enum(QgsWkbTypes, "GeometryType", "PolygonGeometry"))
                pts = [
                    QPoint(e.pos().x() - 5, e.pos().y() - 5),
                    QPoint(e.pos().x() + 5, e.pos().y() - 5),
                    QPoint(e.pos().x() + 5, e.pos().y() + 5),
                    QPoint(e.pos().x() - 5, e.pos().y() + 5)
                ]
                for p in pts:
                    self.rbSelect.addPoint(self.toMapCoordinates(p))
                self.select.emit()
            else:
                self.selectionDone.emit()
        except Exception as err:
            QgsMessageLog.logMessage(f"[SelectPoint] ReleaseEvent: {err}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))

    def reset(self):
        self.rb.reset(scoped_enum(QgsWkbTypes, "GeometryType", "PolygonGeometry"))
        self.rbSelect.reset(scoped_enum(QgsWkbTypes, "GeometryType", "PolygonGeometry"))

    def deactivate(self):
        self.reset()
        super().deactivate()


# --------------------------------------------------------------------
# ---------------------- DIALOGUES COORDONNÉES -----------------------
# --------------------------------------------------------------------
class DMSDialog(QDialog):

    def tr(self, message):
        return QCoreApplication.translate('DMSDialog', message)

    """Dialogue pour coordonnées en degrés/minutes/secondes."""
    def __init__(self):
        super().__init__()
        try:
            self.setWindowTitle(self.tr('DMS Point Tool'))
            self.lat_D, self.lat_M, self.lat_S, self.lat_DM = [QLineEdit() for _ in range(4)]
            self.lon_D, self.lon_M, self.lon_S, self.lon_DM = [QLineEdit() for _ in range(4)]

            motif = r"^-?[0-9]+([\.,][0-9]+)?$"
            regex = make_regex(motif)
            validators = {
                'float': QRegularExpressionValidator(regex),
                'int': QIntValidator()
            }
            for f in [self.lat_S, self.lat_DM, self.lon_S, self.lon_DM]:
                f.setValidator(validators['float'])
            for f in [self.lat_D, self.lon_D]:
                f.setValidator(validators['int'])

            self.lat_NS = QComboBox()
            self.lat_NS.addItems(["N", "S"])
            self.lon_EW = QComboBox()
            self.lon_EW.addItems(["E", "W"])

            buttons = QDialogButtonBox(BUTTONBOX_OK | BUTTONBOX_CANCEL, ORIENTATION_HORIZONTAL, self)
            buttons.accepted.connect(self.accept)
            buttons.rejected.connect(self.reject)

            # Layouts
            lat_grp = QGroupBox(self.tr("Latitude"))
            lon_grp = QGroupBox(self.tr("Longitude"))
            lat_grid = QGridLayout()
            lon_grid = QGridLayout()

            lat_grid.addWidget(QLabel(self.tr("Degrees")), 0, 0)
            lat_grid.addWidget(QLabel(self.tr("Minutes")), 0, 1)
            lat_grid.addWidget(QLabel(self.tr("Seconds")), 0, 2)
            lat_grid.addWidget(QLabel(self.tr("Direction")), 0, 3)
            lat_grid.addWidget(self.lat_D, 1, 0)
            lat_grid.addWidget(self.lat_M, 1, 1)
            lat_grid.addWidget(self.lat_S, 1, 2)
            lat_grid.addWidget(self.lat_NS, 1, 3)
            lat_grp.setLayout(lat_grid)

            lon_grid.addWidget(QLabel(self.tr("Degrees")), 0, 0)
            lon_grid.addWidget(QLabel(self.tr("Minutes")), 0, 1)
            lon_grid.addWidget(QLabel(self.tr("Seconds")), 0, 2)
            lon_grid.addWidget(QLabel(self.tr("Direction")), 0, 3)
            lon_grid.addWidget(self.lon_D, 1, 0)
            lon_grid.addWidget(self.lon_M, 1, 1)
            lon_grid.addWidget(self.lon_S, 1, 2)
            lon_grid.addWidget(self.lon_EW, 1, 3)
            lon_grp.setLayout(lon_grid)

            vbox = QVBoxLayout()
            vbox.addWidget(lat_grp)
            vbox.addWidget(lon_grp)
            vbox.addWidget(buttons)
            self.setLayout(vbox)
        except Exception as err:
            QgsMessageLog.logMessage(f"[DMSDialog] Erreur init: {err}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Critical"))

    def getPoint(self):
        try:
            dialog = DMSDialog()
            result = dialog.exec()
            latitude = longitude = 0.0
            if all(f.text().strip() for f in [dialog.lat_D, dialog.lat_M, dialog.lat_S, dialog.lon_D, dialog.lon_M, dialog.lon_S]):
                latitude = int(dialog.lat_D.text()) + float(dialog.lat_M.text().replace(',', '.')) / 60 + float(dialog.lat_S.text().replace(',', '.')) / 3600
                if dialog.lat_NS.currentIndex() == 1:
                    latitude *= -1
                longitude = int(dialog.lon_D.text()) + float(dialog.lon_M.text().replace(',', '.')) / 60 + float(dialog.lon_S.text().replace(',', '.')) / 3600
                if dialog.lon_EW.currentIndex() == 1:
                    longitude *= -1
            return QgsPointXY(longitude, latitude), result == DIALOG_ACCEPTED
        except Exception as err:
            QgsMessageLog.logMessage(f"[DMSDialog] getPoint: {err}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))
            return QgsPointXY(0, 0), False


class XYDialog(QDialog):
    """Dialogue pour saisie XY"""
    crs = None

    def tr(self, message):
        return QCoreApplication.translate('XYDialog', message)

    def __init__(self):
        super().__init__()
        try:
            self.setWindowTitle(self.tr('XY Point drawing tool'))
            self.X, self.Y = QLineEdit(), QLineEdit()
            motif = r"^-?[0-9]+([\.,][0-9]+)?$"
            regex = make_regex(motif)
            self.X.setValidator(QRegularExpressionValidator(regex))
            self.Y.setValidator(QRegularExpressionValidator(regex))
            self.crsButton = QPushButton(self.tr("Projection"))
            self.crsButton.clicked.connect(self.changeCRS)
            self.crsLabel = QLabel("")

            buttons = QDialogButtonBox(BUTTONBOX_OK | BUTTONBOX_CANCEL, ORIENTATION_HORIZONTAL, self)
            buttons.accepted.connect(self.accept)
            buttons.rejected.connect(self.reject)

            grid = QGridLayout()
            grid.addWidget(QLabel("X"), 0, 0)
            grid.addWidget(QLabel("Y"), 0, 1)
            grid.addWidget(self.X, 1, 0)
            grid.addWidget(self.Y, 1, 1)
            grid.addWidget(self.crsButton, 2, 0)
            grid.addWidget(self.crsLabel, 2, 1)
            grid.addWidget(buttons, 3, 0, 1, 2)
            self.setLayout(grid)
        except Exception as err:
            QgsMessageLog.logMessage(f"[XYDialog] Erreur init: {err}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))

    def changeCRS(self):
        try:
            dlg = QgsProjectionSelectionDialog()
            dlg.exec()
            self.crs = dlg.crs()
            self.crsLabel.setText(self.crs.authid())
        except Exception as err:
            QgsMessageLog.logMessage(f"[XYDialog] changeCRS: {err}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))

    def getPoint(self, crs):
        try:
            dialog = XYDialog()
            dialog.crs = crs
            dialog.crsLabel.setText(crs.authid())
            result = dialog.exec()
            if dialog.X.text().strip() and dialog.Y.text().strip():
                X = float(dialog.X.text().replace(',', '.'))
                Y = float(dialog.Y.text().replace(',', '.'))
                return [QgsPointXY(X, Y), dialog.crs], result == DIALOG_ACCEPTED
            else:
                return [QgsPointXY(0, 0), crs], False
        except Exception as err:
            QgsMessageLog.logMessage(f"[XYDialog] getPoint: {err}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))
            return [QgsPointXY(0, 0), crs], False
