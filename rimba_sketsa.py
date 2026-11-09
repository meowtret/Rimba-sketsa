# -*- coding: utf-8 -*-

# Rimba Sketsa: alat gambar dan seleksi cepat untuk QGIS
# Pengembang : Alfian (meowtret) - alfianbphlxii@gmail.com
#
# Turunan dari qdrawEVT 2.74 karya François Thévand
# (francois.thevand@gmail.com), yang berbasis QDraw karya Jérémy Kalsron.
#
# Licence GNU GPL v3+
# Program ini didistribusikan TANPA JAMINAN APA PUN.
# Lihat <http://www.gnu.org/licenses/>.

from __future__ import print_function, absolute_import, annotations
from builtins import str, object
from typing import Optional, cast, Tuple

# --- Initialisation du logger global ---
from .logger import log, redirect_print_to_log

# --- Capture des exceptions globales ---

# def handle_uncaught_exception(exctype, value, tb):
#     """Capture toute erreur Python non interceptée et l’envoie au logger."""
#     import traceback
#     err = ''.join(traceback.format_exception(exctype, value, tb))
#     log.critical(f"Exception non interceptée : {err}")

# --- Imports QGIS / PyQt ---
from qgis.PyQt.QtCore import (
    Qt,
    QEvent,
    QUrl,
    QTranslator,
    QCoreApplication,
    QLocale,
    QTimer,
    QDateTime,
    QPoint,
    QObject,
)

from qgis.PyQt.QtWidgets import QApplication, QMessageBox, QMenu, QInputDialog, QLineEdit, QGroupBox, QPushButton, QLabel, QCheckBox, QProgressDialog, QStyledItemDelegate, QDialog, QVBoxLayout, QDialogButtonBox, QButtonGroup, QRadioButton, QTextBrowser, QHBoxLayout, QToolBar, QTableWidget, QWidget
from .qt_compat import QAction, scoped_enum

from qgis.PyQt.QtGui import QIcon, QDesktopServices

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsCoordinateTransformContext,
    QgsFeature,
    QgsFeatureRequest,
    QgsGeometry,
    QgsLayerTreeGroup,
    QgsLayerTreeLayer,
    QgsMapLayer,
    QgsMessageLog,
    QgsPalLayerSettings,
    QgsProject,
    QgsRenderContext,
    QgsSettings,
    QgsSimpleMarkerSymbolLayerBase,
    QgsTextFormat,
    QgsVectorLayer,
    QgsVectorLayerSimpleLabeling,
    QgsWkbTypes,
)
from qgis.gui import QgsMapToolIdentify, QgsRubberBand

# --- Imports internes du plugin ---
from .AttributesTable import AttributesTable
from .drawtools import DrawPoint, DrawRect, DrawLine, DrawCircle, DrawPolygon, SelectPoint, XYDialog, DMSDialog
from .settings import SketsaSettings
from .layer_dialog import SketsaLayerDialog
import os
import unicodedata

from pathlib import Path
import weakref

from .qt_compat import (
    MSGBOX_QUESTION,
    MSGBOX_CRITICAL,
    MSGBOX_WARNING,
    MSGBOX_INFORMATION,
    MSGBOX_YES,
    MSGBOX_NO,
    MSGBOX_OK,
    WINDOW_MODAL,
    APPLICATION_MODAL,
    CUSTOMIZE_WINDOW_HINT,
    WINDOW_TITLE_HINT,
    WINDOW_STAYS_ON_TOP_HINT,
    WINDOW,
    DIALOG_ACCEPTED,
    EVENT_MOUSE_BUTTON_RELEASE,
    EVENT_SHOW,
    WA_DELETE_ON_CLOSE,
    MSGBOX_ACCEPT_ROLE,
    MSGBOX_REJECT_ROLE,
    BUTTONBOX_CANCEL,
    BUTTONBOX_OK,
)

redirect_print_to_log()
log.info("=== Rimba Sketsa plugin initialization ===")

# --- Chemin des resources ---
PLUGIN_DIR = Path(__file__).resolve().parent
PLUGIN_NAME = "Rimba Sketsa"


def plugin_file(*parts) -> str:
    return str(PLUGIN_DIR.joinpath(*parts))


# Prise en compte des variables dans la traduction
def normalize(s):
    return ''.join(x for x in unicodedata.normalize('NFKD', s)
                   if unicodedata.category(x)[0] == 'L').upper()


# Grup layer yang tidak ikut diseleksi (peta dasar / batas administrasi).
# Nama dinormalisasi: tanpa spasi, tanda baca, dan aksen; huruf besar.
lst_group_no_select = [
    normalize('FONDSDEPLAN'),
    normalize('ADMINISTRATIF'),
    normalize('PETADASAR'),
    normalize('BASEMAP'),
    normalize('ADMINISTRASI'),
]

lst_group_drawing = [
    normalize('DESSINS'),
    normalize('DRAWINGS'),
    normalize('SKETSA'),
]


# Fonction de reconstruction du chemin absolu vers la ressource image ou autre fichier
def resolve(name, basepath=None):
    if not basepath:
        basepath = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(basepath, name)


class UrlDelegate(QStyledItemDelegate):
    def editorEvent(self, event, model, option, index):
        """Ouvre un lien dans le navigateur si la cellule contient une URL."""
        if event.type() == EVENT_MOUSE_BUTTON_RELEASE:
            url = str(index.data() or "")
            if url.lower().startswith(("http://", "https://")):
                QDesktopServices.openUrl(QUrl(url))
        return super().editorEvent(event, model, option, index)


# --------------------------------------------------
#  Constantes internes (NE PAS traduire)
# --------------------------------------------------
DRAWINGS_GROUP_KEY = "rimba_sketsa:DRAWINGS"
GROUP_KEY_PROPERTY = "rimba_sketsa/group_key"
DRAWINGS_FIELD_NAME = "drawings"  # nom interne stable du champ (non traduit)

TOOLBAR_OBJECT_NAME = "RimbaSketsaToolbar"
TOOLBAR_TITLE = PLUGIN_NAME


class _QgisDialogsOnTopFilter(QObject):
    """
    Force les boîtes QGIS (QMessageBox, certains QDialog) à se mettre au premier plan.
    """
    def eventFilter(self, obj, event):
        try:
            if event.type() == EVENT_SHOW:
                # 1) QMessageBox (confirm save, etc.)
                if isinstance(obj, QMessageBox):
                    obj.raise_()
                    obj.activateWindow()
                    return False

                # 2) Optionnel : certains dialogs QGIS héritent de QDialog
                # (si tu veux être conservateur, commente ce bloc)
                if isinstance(obj, QDialog):
                    # seulement ceux parentés à la mainWindow (donc très probablement QGIS)
                    parent = obj.parent()
                    if parent is not None:
                        obj.raise_()
                        obj.activateWindow()
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
        return False


class _QgisNativePromptWatcher(QObject):
    """
    Observe l'apparition de dialogs QGIS (save confirmation, open/new, etc.)
    et minimise les AttributesTable immédiatement.
    """
    def __init__(self, plugin):
        super().__init__(plugin.iface.mainWindow() if getattr(plugin, "iface", None) else None)
        self._plugin = plugin

    def eventFilter(self, obj, event):
        try:
            et = event.type()

            # Les prompts natifs QGIS apparaissent typiquement en QDialog / QMessageBox (Show / WindowActivate)
            if et in (EVENT_SHOW, scoped_enum(QEvent, "Type", "WindowActivate")):
                if isinstance(obj, (QMessageBox, QDialog)):
                    # On cible uniquement les dialogs "top-level" (sinon bruit)
                    w = obj if isinstance(obj, QWidget) else None
                    if w is not None and w.isWindow():
                        # Minimise immédiatement toutes les AttributesTable
                        self._plugin.minimizeAttributesTables()
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

        return False  # ne pas bloquer QGIS


class RimbaSketsa(object):
    def __init__(self, iface):
        self._qdraw_close_in_progress = False

        # --- filtres app (init AVANT singleShot) ---
        self._filters_installed = False
        self._prompt_watcher = None
        self._qgis_dialogs_filter = None

        self._buffer_warned_no_intersection = None
        self.action_aide = None
        self.groupe_selectionne = None
        self._groupe_msg_nul = None
        self._groupe_msg_affiche = None
        self.iface = iface

        # ------------------------------------------------------------------
        # AttributesTable tracking (weakref + anti doublon + closing)
        # ------------------------------------------------------------------
        self.results = []
        self._results_index = {}
        self._results_destroyed_connected = set()

        # ✅ installer les filtres APRES init des champs (et via la boucle Qt)
        try:
            QTimer.singleShot(0, self._install_app_event_filters)
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

        log.info("Rimba Sketsa plugin: base initialization OK")

        self.table = None
        self.feature = None
        self.features = None
        self.layer = None
        self.index = None
        self.layers = None
        self.featureid = None
        self.groupes_coches = None
        self.request = None
        self.XYcrs = None
        self.drawShape = None
        self._buffer_mode: Optional[str] = None

        # --- Terjemahan: teks dasar Inggris, file i18n/rimba_sketsa_<lang>.qm ---
        # Satu translator untuk semua konteks (RimbaSketsa, AttributesTable,
        # dialog, settings, drawtools). Bahasa mengikuti bahasa UI QGIS.
        self.locale = self._current_locale()
        locale_path = plugin_file('i18n', 'rimba_sketsa_{}.qm'.format(self.locale))

        self.translator = None
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            if self.translator.load(locale_path):
                QCoreApplication.installTranslator(self.translator)
            else:
                self.translator = None

        # Obtenir l'instance du projet en cours
        self.project = QgsProject.instance()

        self._install_attributes_table_close_hooks()

        # Root du projet en cours
        self.root = self.project.layerTreeRoot()

        # --------------------------------------------------
        # Nettoyage automatique des groupes Dessins / Drawings
        # - déclenché à chaque chargement / ouverture de projet
        # --------------------------------------------------
        try:
            self.project.readProject.connect(self._auto_cleanup_drawings_groups)
            QTimer.singleShot(0, self._auto_cleanup_drawings_groups)
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Rimba Sketsa: readProject hook failed: {e}",
                "Rimba Sketsa",
                scoped_enum(Qgis, "MessageLevel", "Warning")
            )

        # ✅ Nettoyage auto : fusionne Drawings/Dessins legacy en un seul groupe stable
        self._auto_cleanup_drawings_groups()

        self.group_no_select = []
        self.group_drawing = []

        self.sb = self.iface.statusBarIface()
        self.tool = None
        self.toolname = None

        self._hooked_qgis_actions = False

        self.bGeom = None

        self.toolbar = None
        self.actions = []
        self.menu = PLUGIN_NAME

        self.settings = SketsaSettings(self.iface)
        # self.bridge = QgsLayerTreeMapCanvasBridge(QgsProject.instance().layerTreeRoot(), self.iface.mapCanvas())

        # Ajout de la fenêtre de sélection
        self.loadingWindow = QProgressDialog(self.tr('Selecting...'), self.tr('Pass'), 0, 100)
        self.loadingWindow.setAutoClose(False)
        self.loadingWindow.close()

        # --- Anti double-déclenchement (clic rapide / double signal) ---
        self._buffer_draw_lock: bool = False
        self._buffer_draw_last_ms: int = 0
        self._buffer_draw_debounce_ms: int = 250  # ajuste si besoin (200-400ms)

        # self._hook_close_before_qgis_prompts()

    def tr(self, message):
        return QCoreApplication.translate('RimbaSketsa', message)

    @staticmethod
    def _current_locale() -> str:
        """Kode bahasa 2 huruf dari bahasa UI QGIS (mis. 'id', 'en')."""
        try:
            loc = QgsApplication.locale() or ""
        except Exception:
            loc = ""
        if not loc:
            try:
                if QgsSettings().value("locale/overrideFlag", False, type=bool):
                    loc = str(QgsSettings().value("locale/userLocale", "") or "")
                else:
                    loc = QLocale.system().name()
            except Exception:
                loc = "en"
        return (loc or "en")[0:2].lower()

    def _install_app_event_filters(self) -> None:
        app = QApplication.instance()
        if not app:
            return

        # évite double install (y compris reload partiel)
        if getattr(self, "_filters_installed", False):
            return

        # créer les filtres si absents / invalides
        def _is_qobj_alive(obj) -> bool:
            if obj is None:
                return False
            try:
                obj.objectName()  # touche légère
                return True
            except RuntimeError:
                return False
            except Exception:
                return True

        if not _is_qobj_alive(getattr(self, "_prompt_watcher", None)):
            # IMPORTANT: parent = app (QObject)
            self._prompt_watcher = _QgisNativePromptWatcher(app)

        if not _is_qobj_alive(getattr(self, "_qgis_dialogs_filter", None)):
            self._qgis_dialogs_filter = _QgisDialogsOnTopFilter(app)

        # installer
        try:
            app.installEventFilter(self._prompt_watcher)
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

        try:
            app.installEventFilter(self._qgis_dialogs_filter)
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

        self._filters_installed = True

    def minimizeAttributesTables(self) -> None:
        """Minimise toutes les fenêtres AttributesTable ouvertes."""
        try:
            self._cleanup_results()
            for w in list(self._iter_live_results()):
                if w is None:
                    continue
                if bool(getattr(w, "_qdraw_closing", False)):
                    continue
                try:
                    w.showMinimized()
                except Exception:
                    log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

    def eventFilter(self, obj, event):
        if event.type() == EVENT_SHOW:
            if isinstance(obj, QMessageBox):
                try:
                    obj.setWindowFlag(WINDOW_STAYS_ON_TOP_HINT, True)
                    obj.show()  # réappliquer les flags
                    obj.raise_()
                    obj.activateWindow()
                except Exception:
                    log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
        return False

    # ------------------------------------------------------------------
    # Helpers weakref
    # ------------------------------------------------------------------
    def _wrap_weak(self, w):
        # callback quand l'objet Qt est détruit => purge
        return weakref.ref(w, lambda _wr: self._cleanup_results())

    def _on_result_dead(self, _wr):
        """Callback appelé quand Qt détruit le widget (référence weakref morte)."""
        self._cleanup_results()

    def _qt_alive(self, w) -> bool:
        if w is None:
            return False
        try:
            _ = w.objectName()
            return True
        except RuntimeError:
            return False
        except Exception:
            return True  # on considère vivant

    def _cleanup_results(self):
        """Retire weakrefs mortes + widgets déjà détruits côté Qt."""
        cleaned = []
        for wr in list(getattr(self, "results", [])):
            try:
                w = wr()
            except Exception:
                w = None
            if not self._qt_alive(w):
                continue
            cleaned.append(wr)
        self.results = cleaned

        idx = getattr(self, "_results_index", None)
        if isinstance(idx, dict):
            for k, wr in list(idx.items()):
                try:
                    if wr() is None:
                        idx.pop(k, None)
                except Exception:
                    idx.pop(k, None)

    def _iter_live_results(self):
        """Itère sur les AttributesTable encore vivantes (sans RuntimeError)."""
        for wr in list(getattr(self, "results", [])):
            try:
                w = wr()
            except Exception:
                w = None
            if not self._qt_alive(w):
                continue
            yield w

    def _result_key(self, w):
        try:
            on = w.objectName() or ""
        except Exception:
            on = ""
        return (on, id(w))

    # ------------------------------------------------------------------
    # API publique : enregistrer / fermer / nettoyer
    # ------------------------------------------------------------------
    def registerAttributesTable(self, tab):
        if tab is None:
            return

        self._cleanup_results()

        # marqueur "closing" (évite double close)
        try:
            if not hasattr(tab, "_qdraw_closing"):
                tab._qdraw_closing = False
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

        # anti-doublon par (objectName, id)
        if not hasattr(self, "_results_index") or self._results_index is None:
            self._results_index = {}

        key = self._result_key(tab)
        old_wr = self._results_index.get(key)
        if old_wr:
            try:
                old = old_wr()
            except Exception:
                old = None
            if old is not None:
                # si l'ancien n'est pas en train de fermer => ne pas dupliquer
                if not bool(getattr(old, "_qdraw_closing", False)):
                    return

        wr = self._wrap_weak(tab)
        self.results.append(wr)
        self._results_index[key] = wr

        # connecter destroyed une seule fois
        try:
            tid = id(tab)
            if tid not in self._results_destroyed_connected:
                self._results_destroyed_connected.add(tid)
                tab.destroyed.connect(lambda *_: self._cleanup_results())
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

    def closeAllAttributesTablesBeforeQgis(self):
        """
        À appeler depuis les QAction (New/Open/Exit) avec scoped_enum(Qt, "ConnectionType", "DirectConnection").
        """
        self.closeAttributesTable(tab=None, force=True)

    def _force_close_all_attributes_tables(self) -> None:
        # ferme toutes les fenêtres AttributesTable ouvertes (widgets vivants)
        for w in list(self._iter_live_results()):
            try:
                if getattr(w, "_qdraw_closing", False):
                    continue
                w._qdraw_closing = True

                if hasattr(w, "force_close_now"):
                    w.force_close_now()
                else:
                    w.close()
            except Exception:
                log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

        self._cleanup_results()

    def _attr_close_all_direct(self, *args) -> None:
        """
        Slot ultra-court (DirectConnection) : ferme tout avant les prompts QGIS.
        - pas de lambda/closure
        - pas de logs
        - flush DeferredDelete
        """
        # 1) fermeture immédiate
        try:
            self.closeAttributesTable(tab=None, force=True)
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

        # 2) flush minimal (indispensable pour battre les prompts QGIS)
        try:
            app = QApplication.instance()
            if app:
                app.processEvents()
                QCoreApplication.sendPostedEvents(None, scoped_enum(QEvent, "Type", "DeferredDelete"))
                app.processEvents()
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

    # def _install_attributes_table_close_hooks(self) -> None:
    #     """Ferme AttributesTable AVANT les prompts QGIS (new/open/quit/clear)."""
    #     if getattr(self, "_attr_hooks_installed", False):
    #         return
    #     self._attr_hooks_installed = True
    #
    #     if not hasattr(self, "_attr_close_connected_actions"):
    #         self._attr_close_connected_actions = set()  # set[int(id(QAction))]
    #
    #     def _close_all(*_args, **_kwargs):
    #         self.closeAttributesTable(tab=None, force=True)
    #         # ✅ flush immédiat pour passer avant les dialogues QGIS
    #         try:
    #             app = QApplication.instance()
    #             if app:
    #                 app.processEvents()
    #                 QtCore.QCoreApplication.sendPostedEvents(None, scoped_enum(QtCore.QEvent, "Type", "DeferredDelete"))
    #                 app.processEvents()
    #         except Exception:
    #             pass
    #
    #     # 1) Hooks projet
    #     try:
    #         p = QgsProject.instance()
    #         if hasattr(p, "aboutToClear"):
    #             p.aboutToClear.connect(_close_all)
    #         if hasattr(p, "cleared"):
    #             p.cleared.connect(_close_all)
    #     except Exception:
    #         pass
    #
    #     # 2) Hook application (fermeture QGIS)
    #     try:
    #         from qgis.core import QgsApplication
    #         app = QgsApplication.instance()
    #         if app and hasattr(app, "aboutToQuit"):
    #             app.aboutToQuit.connect(_close_all)
    #     except Exception:
    #         pass
    #
    #     # 3) Actions UI (DirectConnection)
    #     def _connect_action(act):
    #         if not act:
    #             return
    #
    #         # (optionnel) propriété persistante côté QObject
    #         try:
    #             if act.property("_rimba_sketsa_attr_close_hooked"):
    #                 return
    #             act.setProperty("_rimba_sketsa_attr_close_hooked", True)
    #         except Exception:
    #             pass
    #
    #         aid = id(act)
    #         if aid in self._attr_close_connected_actions:
    #             return
    #         self._attr_close_connected_actions.add(aid)
    #
    #         try:
    #             act.triggered.connect(_close_all, scoped_enum(Qt, "ConnectionType", "DirectConnection"))
    #         except TypeError:
    #             try:
    #                 act.triggered.connect(_close_all, type=scoped_enum(Qt, "ConnectionType", "DirectConnection"))
    #             except Exception:
    #                 pass
    #         except Exception:
    #             pass
    #
    #     try:
    #         _connect_action(self.iface.actionNewProject())
    #         _connect_action(self.iface.actionOpenProject())
    #         _connect_action(self.iface.actionExit())
    #     except Exception:
    #         pass
    def _install_attributes_table_close_hooks(self) -> None:
        if getattr(self, "_attr_hooks_installed", False):
            return
        self._attr_hooks_installed = True

        # actions UI : DirectConnection + slot bound (pas de lambda)
        try:
            act = self.iface.actionNewProject()
            if act:
                act.triggered.connect(self._attr_close_all_direct, scoped_enum(Qt, "ConnectionType", "DirectConnection"))
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

        try:
            act = self.iface.actionOpenProject()
            if act:
                act.triggered.connect(self._attr_close_all_direct, scoped_enum(Qt, "ConnectionType", "DirectConnection"))
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

        try:
            act = self.iface.actionExit()
            if act:
                act.triggered.connect(self._attr_close_all_direct, scoped_enum(Qt, "ConnectionType", "DirectConnection"))
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

        # hook projet : aucun lambda/closure non plus
        try:
            p = QgsProject.instance()
            if hasattr(p, "aboutToClear"):
                p.aboutToClear.connect(self._attr_close_all_direct)
            if hasattr(p, "cleared"):
                p.cleared.connect(self._attr_close_all_direct)
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

        # hook app : aucun lambda/closure
        try:
            app = QgsApplication.instance()
            if app and hasattr(app, "aboutToQuit"):
                app.aboutToQuit.connect(self._attr_close_all_direct)
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

    def _get_or_create_toolbar(self):
        mw = self.iface.mainWindow()

        # 1) Réutiliser si existe déjà (rechargement du plugin)
        for tb in mw.findChildren(QToolBar):
            if tb.objectName() == TOOLBAR_OBJECT_NAME:
                self.toolbar = tb
                break

        # 2) Sinon créer
        if self.toolbar is None:
            self.toolbar = self.iface.addToolBar(TOOLBAR_TITLE)
            self.toolbar.setObjectName(TOOLBAR_OBJECT_NAME)
            self.toolbar.setToolTip(PLUGIN_NAME)

        return self.toolbar

    def _clear_plugin_actions(self):
        if not getattr(self, "toolbar", None):
            return

        for action in list(getattr(self, "actions", [])):
            # Retirer du menu
            try:
                self.iface.removePluginMenu(self.menu, action)
            except Exception:
                log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

            # Retirer de la toolbar
            try:
                self.toolbar.removeAction(action)
            except Exception:
                log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

            # Détruire l'action
            try:
                action.deleteLater()
            except Exception:
                log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

        self.actions = []

    def _remove_existing_toolbar(self):
        mw = self.iface.mainWindow()
        for tb in mw.findChildren(QToolBar):
            if tb.objectName() == TOOLBAR_OBJECT_NAME:
                mw.removeToolBar(tb)
                tb.deleteLater()

    def _canvas_pos_from_tool(self) -> Optional[QPoint]:
        """
        Récupère la position pixel-canvas du dernier clic depuis le MapTool.
        """
        if not getattr(self, "tool", None):
            return None

        for attr in (
                "last_canvas_pos",  # ✅ ce qu’on va mettre dans SelectPoint
                "lastPoint",  # (souvent utilisé ailleurs)
                "last_pos", "lastPos",
                "pos", "mouse_pos", "mousePos",
        ):
            p = getattr(self.tool, attr, None)
            if isinstance(p, QPoint):
                return p
        return None

    def identify_topmost_vector_feature(self, canvas_pos: QPoint) -> Optional[Tuple[QgsVectorLayer, QgsFeature]]:
        canvas = self.iface.mapCanvas()
        ident = QgsMapToolIdentify(canvas)
        root = QgsProject.instance().layerTreeRoot()

        layers = []
        for lyr in canvas.layers():
            if isinstance(lyr, QgsVectorLayer):
                node = root.findLayer(lyr.id())
                if node is not None and node.isVisible():
                    layers.append(lyr)

        if not layers:
            return None

        results = ident.identify(
            canvas_pos.x(),
            canvas_pos.y(),
            layers,
            scoped_enum(QgsMapToolIdentify, "IdentifyMode", "TopDownStopAtFirst"),
        )

        for r in results:
            lyr = r.mLayer
            feat = r.mFeature
            if isinstance(lyr, QgsVectorLayer) and feat and feat.isValid():
                return lyr, feat

        return None

    def _identify_feature_under_click(self, canvas_pos: QPoint) -> Optional[tuple]:
        """
        Retourne (layer, feature) pour la première entité trouvée sous le clic,
        en scannant les couches vectorielles visibles.
        """
        try:
            from qgis.gui import QgsMapToolIdentify
        except Exception:
            return None

        try:
            ident = QgsMapToolIdentify(self.iface.mapCanvas())
            results = ident.identify(
                canvas_pos.x(),
                canvas_pos.y(),
                [scoped_enum(QgsMapLayer, "LayerType", "VectorLayer")],
                scoped_enum(QgsMapToolIdentify, "IdentifyMode", "TopDownAll")
            )
        except Exception as e:
            self._buffer_log("ERROR", f"[Buffer] identify() a échoué: {e}")
            return None

        # on prend le 1er résultat valide visible
        root = QgsProject.instance().layerTreeRoot()
        for r in results:
            try:
                layer = r.mLayer
                feat = r.mFeature
                if layer is None or feat is None:
                    continue
                node = root.findLayer(layer.id())
                if node is None or not node.isVisible():
                    continue
                return (layer, feat)
            except Exception:
                log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
                continue

        return None

    def _find_group_by_key(self, key: str):
        """Trouve un groupe via customProperty, pas via le nom (qui peut être traduit)."""
        root = self.root
        stack = [root]
        while stack:
            node = stack.pop()
            if isinstance(node, QgsLayerTreeGroup):
                if node.customProperty(GROUP_KEY_PROPERTY, "") == key:
                    return node
            for ch in node.children():
                stack.append(ch)
        return None

    def _get_or_create_drawings_group(self):
        """Retourne le groupe Drawings (clé interne stable) et applique le nom UI traduit."""
        g = self._find_group_by_key(DRAWINGS_GROUP_KEY)
        if g is None:
            g = QgsLayerTreeGroup("DRAWINGS")  # nom provisoire interne
            g.setCustomProperty(GROUP_KEY_PROPERTY, DRAWINGS_GROUP_KEY)
            self.root.insertChildNode(0, g)
        # Nom visible (traduit)
        g.setName(self.tr("Drawings"))
        return g

    def _apply_drawings_field_alias(self, layer):
        """Applique l'alias traduit 'Drawings' sur le champ interne drawings."""
        try:
            idx = layer.fields().indexOf(DRAWINGS_FIELD_NAME)
            if idx != -1:
                layer.setFieldAlias(idx, self.tr("Drawings"))
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

    # --------------------------------------------------
    #  Nettoyage automatique Drawings / Dessins (legacy)
    # --------------------------------------------------

    def _iter_groups_recursive(self, group: QgsLayerTreeGroup):
        """Itère récursivement sur tous les sous-groupes (incluant le group lui-même)."""
        stack = [group]
        while stack:
            g = stack.pop()
            yield g
            for ch in g.children():
                if isinstance(ch, QgsLayerTreeGroup):
                    stack.append(ch)

    def _find_all_legacy_drawings_groups(self):
        """
        Retourne tous les groupes dont le nom normalisé est dans lst_group_drawing
        et qui ne sont PAS tagués avec la clé interne.
        Recherche récursive dans tout l'arbre.
        """
        legacy = []
        for g in self._iter_groups_recursive(self.root):
            try:
                if g is self.root:
                    continue
                # ignore le groupe tagué
                if g.customProperty(GROUP_KEY_PROPERTY, "") == DRAWINGS_GROUP_KEY:
                    continue
            except Exception:
                log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

            try:
                if normalize(g.name()) in lst_group_drawing:
                    legacy.append(g)
            except Exception:
                log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
        return legacy

    def _ensure_main_drawings_group(self) -> QgsLayerTreeGroup:
        """Crée ou récupère le groupe Drawings tagué (stable)."""
        g = self._find_group_by_key(DRAWINGS_GROUP_KEY)
        if g is None:
            g = QgsLayerTreeGroup("DRAWINGS")
            g.setCustomProperty(GROUP_KEY_PROPERTY, DRAWINGS_GROUP_KEY)
            # au choix : en haut de l’arbre
            self.root.insertChildNode(0, g)
        g.setName(self.tr("Drawings"))
        return g

    def _move_children(self, src: QgsLayerTreeGroup, dst: QgsLayerTreeGroup):
        """
        Déplace les enfants de src vers dst en conservant leur ordre visuel.
        IMPORTANT : on déplace les nodes eux-mêmes (pas clone),
        car clone + remove est souvent source de surprises.
        """
        if src is None or dst is None or src == dst:
            return

        # On prend une copie de la liste car on va la modifier
        children = list(src.children())
        if not children:
            return

        # Déplacement : on retire puis on insère dans dst
        # On conserve l'ordre (les ajouter à la fin)
        for node in children:
            try:
                src.removeChildNode(node)
                dst.addChildNode(node)
            except Exception:
                # fallback "clone" si QGIS refuse de déplacer un node existant
                try:
                    cloned = node.clone()
                    dst.addChildNode(cloned)
                    src.removeChildNode(node)
                except Exception:
                    log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

    def _remove_group_if_empty(self, g: QgsLayerTreeGroup):
        """Supprime un groupe s’il est vide."""
        try:
            if g is None or g is self.root:
                return
            if len(g.children()) > 0:
                return
            parent = g.parent()
            if parent:
                parent.removeChildNode(g)
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

    def _auto_cleanup_drawings_groups(self):
        """
        Fusionne tous les groupes legacy Dessins/Drawings (même imbriqués) vers le groupe tagué.
        Puis supprime les legacy vides.
        """
        root = QgsProject.instance().layerTreeRoot()
        # Noms à surveiller
        candidates = {"Dessins", "Drawings"}
        # Cherche si au moins un groupe existe déjà
        existing = [g for g in root.findGroups() if g.name() in candidates]

        # ✅ Si aucun groupe legacy n'existe, on ne fait RIEN (et surtout on ne crée rien)
        if not existing:
            return
        # ... ensuite seulement : logique de fusion/renommage
        try:
            main = self._ensure_main_drawings_group()

            legacy_groups = self._find_all_legacy_drawings_groups()
            if not legacy_groups:
                return

            # Si par malheur le main est aussi dans legacy (cas bizarre), on l’enlève
            legacy_groups = [g for g in legacy_groups if g != main]

            # Fusion
            for g in legacy_groups:
                self._move_children(g, main)

            # Suppression legacy vides
            for g in legacy_groups:
                self._remove_group_if_empty(g)

            # Garantit le nom UI final (traduit)
            main.setName(self.tr("Drawings"))

            # Rafraîchit la vue
            try:
                self.iface.layerTreeView().refreshLayerSymbology("")
            except Exception:
                log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

    def unload(self):
        log.info("Rimba Sketsa plugin unloaded cleanly.")

        # --- (optionnel conseillé) fermer tes fenêtres plugin avant de démonter les hooks
        try:
            self.closeAttributesTable(tab=None, force=True)
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

        # 1) Retirer actions menu/toolbar
        for action in list(getattr(self, "actions", [])):
            try:
                self.iface.removePluginMenu(self.menu, action)
            except Exception:
                log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
            try:
                tb = getattr(self, "toolbar", None)
                if tb:
                    tb.removeAction(action)
            except Exception:
                log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
            try:
                action.deleteLater()
            except Exception:
                log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
        self.actions = []

        # Toolbar milik plugin ini saja => dihapus saat unload
        try:
            self._remove_existing_toolbar()
        except Exception:
            log.debug("Ignored exception while removing toolbar", exc_info=True)
        self.toolbar = None

        # Lepas translator agar tidak menumpuk saat plugin dimuat ulang
        if getattr(self, "translator", None) is not None:
            try:
                QCoreApplication.removeTranslator(self.translator)
            except Exception:
                log.debug("Ignored exception while removing translator", exc_info=True)
            self.translator = None

        # Lepas sambungan sinyal proyek
        try:
            self.project.readProject.disconnect(self._auto_cleanup_drawings_groups)
        except Exception:
            log.debug("Ignored exception while disconnecting readProject", exc_info=True)

        # 2) Retirer event filters + deleteLater + reset flags
        try:
            app = QApplication.instance()
        except Exception:
            app = None

        def _safe_remove_filter(app, f):
            if not app or f is None:
                return
            try:
                app.removeEventFilter(f)
            except (TypeError, RuntimeError):
                log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
            except Exception:
                log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
            try:
                f.deleteLater()
            except (TypeError, RuntimeError):
                log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
            except Exception:
                log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

        if app:
            _safe_remove_filter(app, getattr(self, "_prompt_watcher", None))
            _safe_remove_filter(app, getattr(self, "_qgis_dialogs_filter", None))

            # vider les deletes différés (évite callbacks tardifs après unload)
            try:
                app.processEvents()
                QCoreApplication.sendPostedEvents(None, scoped_enum(QEvent, "Type", "DeferredDelete"))
                app.processEvents()
            except Exception:
                log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

        self._prompt_watcher = None
        self._qgis_dialogs_filter = None
        self._filters_installed = False

        # 3) (optionnel) reset tracking weakref si tu veux être ultra clean au reload
        try:
            self.results = []
            self._results_index = {}
            self._results_destroyed_connected = set()
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

    def add_action(
            self,
            icon_path,
            text,
            callback,
            enabled_flag=True,
            checkable=False,
            add_to_menu=True,
            add_to_toolbar=True,
            status_tip=None,
            whats_this=None,
            menu=None,
            parent=None):
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)
        action.setCheckable(checkable)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if menu is not None:
            action.setMenu(menu)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        # Chargement de l’interface et actions
        log.info("Initialisation de l’interface graphique Rimba Sketsa")

        # ✅ Réutilise la toolbar existante (rechargement)
        self._get_or_create_toolbar()

        # ✅ Nettoie les actions d'un chargement précédent
        self._clear_plugin_actions()

        pointMenu = QMenu()
        pointMenu.addAction(
            QIcon(plugin_file("resources", 'icon_DrawPtXY.png')),
            self.tr('XY Point drawing tool'), self.drawXYPoint)
        pointMenu.addAction(
            QIcon(plugin_file("resources", 'icon_DrawPtDMS.png')),
            self.tr('DMS Point drawing tool'), self.drawDMSPoint)
        icon_path = plugin_file("resources", 'icon_DrawText.png')
        self.add_action(
            icon_path,
            text=self.tr('Text drawing tool'),
            checkable=True,
            callback=self.drawText,
            parent=self.iface.mainWindow()
        )
        icon_path = plugin_file("resources", 'icon_DrawPt.png')
        self.add_action(
            icon_path,
            text=self.tr('Point drawing tool'),
            checkable=True,
            menu=pointMenu,
            callback=self.drawPoint,
            parent=self.iface.mainWindow()
        )
        icon_path = plugin_file("resources", 'icon_DrawL.png')
        self.add_action(
            icon_path,
            text=self.tr('Line drawing tool'),
            checkable=True,
            callback=self.drawLine,
            parent=self.iface.mainWindow()
        )
        icon_path = plugin_file("resources", 'icon_DrawR.png')
        self.add_action(
            icon_path,
            text=self.tr('Rectangle drawing tool'),
            checkable=True,
            callback=self.drawRect,
            parent=self.iface.mainWindow()
        )
        icon_path = plugin_file("resources", 'icon_DrawC.png')
        self.add_action(
            icon_path,
            text=self.tr('Circle drawing tool'),
            checkable=True,
            callback=self.drawCircle,
            parent=self.iface.mainWindow()
        )
        icon_path = plugin_file("resources", 'icon_DrawP.png')
        self.add_action(
            icon_path,
            text=self.tr('Polygon drawing tool'),
            checkable=True,
            callback=self.drawPolygon,
            parent=self.iface.mainWindow()
        )
        bufferMenu = QMenu()
        polygonBufferAction = QAction(
            QIcon(plugin_file("resources", 'icon_DrawTP.png')),
            self.tr('Buffer drawing with polygonal selection of objects in the selected layer'),
            bufferMenu)
        polygonBufferAction.triggered.connect(self.drawPolygonBuffer)
        bufferMenu.addAction(polygonBufferAction)
        icon_path = plugin_file("resources", 'icon_DrawT.png')
        self.add_action(
            icon_path,
            text=self.tr('Buffer drawing on objects in selected layer'),
            checkable=True,
            menu=bufferMenu,
            callback=self.drawBuffer,
            parent=self.iface.mainWindow()
        )
        icon_path = plugin_file("resources", 'icon_Settings.png')
        self.add_action(
            icon_path,
            text=self.tr('Settings'),
            callback=self.showSettingsWindow,
            parent=self.iface.mainWindow()
        )

        # Détermination de l'icône native QGIS pour l'aide
        icon_help = QgsApplication.getThemeIcon("mActionHelpContents.svg")
        self.action_aide = QAction(
            icon_help,
            self.tr("Help / User manual"),
            self.iface.mainWindow()
        )
        self.action_aide.setObjectName("rimba_sketsa_action_aide")
        self.action_aide.triggered.connect(self.afficher_aide)
        # On ajoute l’action EN BAS du menu
        self.iface.addPluginToMenu(self.menu, self.action_aide)
        # On garde une trace pour unload()
        self.actions.append(self.action_aide)

    # --- Fonction principale d'affichage de la table d’attributs ---
    def showAttributesTable(self, name):
        """Affiche la table d’attributs pour toutes les couches visibles contenant une sélection."""

        tab = AttributesTable(name, self.iface)

        # stays on top : OK (PyQt5/6). Évite setWindowFlags(..., True) => erreur.
        # try:
        #     tab.setWindowFlag(WINDOW_STAYS_ON_TOP_HINT, True)
        # except Exception:
            # fallback: réappliquer via flags complets
            # try:
            #     tab.setWindowFlags(tab.windowFlags() | WINDOW_STAYS_ON_TOP_HINT)
            # except Exception:
            #     pass

        layers = self.project.mapLayers().values()
        selected_found = False

        for layer in layers:
            try:
                if layer.type() == scoped_enum(QgsMapLayer, "LayerType", "VectorLayer") and QgsProject.instance().layerTreeRoot().findLayer(layer.id()).isVisible():
                    cells = layer.selectedFeatures()
                    if not cells:
                        continue

                    selected_found = True

                    columns = layer.attributeTableConfig().columns()
                    fields_name = []
                    fields_type = []
                    idx_visible = []

                    for col in columns:
                        if col.hidden:
                            continue
                        idx = layer.fields().indexOf(col.name)
                        alias = layer.attributeAlias(idx)
                        fields_name.append(alias if alias else col.name)
                        fields_type.append(col.type)
                        idx_visible.append(idx)

                    tab.addLayer(layer, fields_name, fields_type, cells, idx_visible)

            except Exception as e:
                QgsMessageLog.logMessage(f"Erreur dans showAttributesTable : {e}", "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))

        # ✅ Si aucune sélection : fermer tout de suite et ne PAS enregistrer
        if not selected_found:
            try:
                tab.force_close_now() if hasattr(tab, "force_close_now") else tab.close()
            except Exception:
                log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
            QMessageBox.information(
                self.iface.mainWindow(),
                self.tr("No selection"),
                self.tr("No selected items found in visible vector layers."),
            )
            return

        # ✅ seulement maintenant : enregistrement weakref + destroyed
        self.registerAttributesTable(tab)

        def is_url_item(item):
            if not item:
                return False
            txt = item.text().strip().lower()
            return txt.startswith("http://") or txt.startswith("https://")

        for idx in range(tab.tabWidget.count()):
            widget = tab.tabWidget.widget(idx)
            table_widget = next((child for child in widget.children() if isinstance(child, QTableWidget)), None)
            if not table_widget:
                continue

            for col in range(table_widget.columnCount()):
                if all(
                        is_url_item(table_widget.item(row, col))
                        for row in range(table_widget.rowCount())
                        if table_widget.item(row, col)
                ):
                    table_widget.setItemDelegateForColumn(col, UrlDelegate(table_widget))

        tab.loadingWindow.close()
        tab.show()
        tab.activateWindow()
        tab.showNormal()

        self.unselectAll()

    def unselectAll(self):
        # Récupérer toutes les couches du projet
        layers = QgsProject.instance().mapLayers().values()
        # Parcourir chaque couche
        for layer in layers:
            if layer.type() == scoped_enum(QgsMapLayer, "LayerType", "VectorLayer"):  # Vérifier si c'est une couche vectorielle
                layer.removeSelection()  # Désélectionner tous les éléments
        # Mettre à jour l'affichage de la carte
        self.iface.mapCanvas().refresh()

    def closeAttributesTable(self, tab=None, force: bool = False, flush: bool = True):
        """
        Variante encore plus sûre:
        - dédoublonne par (id, objectName)
        - ignore explicitement ceux déjà "_qdraw_closing"
        - évite la réentrance (si close déclenche destroyed en cascade)
        """
        if getattr(self, "_qdraw_close_in_progress", False):
            return
        self._qdraw_close_in_progress = True

        try:
            self._cleanup_results()

            def _safe_key(w):
                try:
                    return (int(id(w)), str(getattr(w, "objectName", lambda: "")() or ""))
                except Exception:
                    return (int(id(w)), "")

            def _is_deleted(obj) -> bool:
                try:
                    _ = obj.objectName()
                    return False
                except RuntimeError:
                    return True
                except Exception:
                    return False

            seen = set()

            def _close_one(w):
                if w is None or _is_deleted(w):
                    return

                k = _safe_key(w)
                if k in seen:
                    return
                seen.add(k)

                if bool(getattr(w, "_qdraw_closing", False)):
                    return
                try:
                    w._qdraw_closing = True
                except Exception:
                    log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

                try:
                    if force:
                        try:
                            w._force_close = True
                        except Exception:
                            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
                        try:
                            w.setAttribute(WA_DELETE_ON_CLOSE, True)
                        except Exception:
                            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
                        try:
                            w.hide()
                        except Exception:
                            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
                        try:
                            w.close()
                        except Exception:
                            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
                        try:
                            w.deleteLater()
                        except Exception:
                            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
                    else:
                        w.close()
                except Exception:
                    log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

            if tab is not None:
                _close_one(tab)
            else:
                for w in list(self._iter_live_results()):
                    _close_one(w)

            self._cleanup_results()

            if flush:
                try:
                    app = QApplication.instance()
                    if app:
                        app.processEvents()
                        QCoreApplication.sendPostedEvents(None, scoped_enum(QEvent, "Type", "DeferredDelete"))
                        app.processEvents()
                except Exception:
                    log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

            self._cleanup_results()

        finally:
            self._qdraw_close_in_progress = False

    def testGroups(self):
        # mise en variable des groupes a gérer pour la sélection
        self.group_no_select = []
        for group in self.root.children():
            test = ''.join(x for x in unicodedata.normalize('NFKD', group.name()) if unicodedata.category(x)[0] == 'L').upper()
            if test in lst_group_no_select:
                self.group_no_select.append(group)

        # --------------------------------------------------
        # Groupes Drawings
        # - priorité à la clé interne
        # - fallback legacy par nom (Drawings / Dessins)
        # --------------------------------------------------
        self.group_drawing = []
        # 1) Groupe Drawings tagué (CAS NORMAL)
        g_draw = self._find_group_by_key(DRAWINGS_GROUP_KEY)
        if g_draw is not None:
            self.group_drawing.append(g_draw)
            self.group_no_select.append(g_draw)
        # 2) Fallback legacy (anciens projets)
        else:
            for group in self.root.children():
                if not isinstance(group, QgsLayerTreeGroup):
                    continue

                test = normalize(group.name())

                if test in lst_group_drawing:
                    self.group_drawing.append(group)
                    self.group_no_select.append(group)


    def _activatePointClickTool(self):
        # (alat gambar)
        self.actions[1].setIcon(QIcon(plugin_file("resources", 'icon_DrawPt.png')))
        self.actions[1].menu().actions()[0].setIcon(QIcon(plugin_file("resources", 'icon_DrawPtXY.png')))
        self.actions[1].menu().actions()[1].setIcon(QIcon(plugin_file("resources", 'icon_DrawPtDMS.png')))
        try:
            self.actions[1].triggered.disconnect()
        except TypeError:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
        self.actions[1].triggered.connect(self.drawPoint)

        try:
            self.actions[1].menu().actions()[0].triggered.disconnect()
        except TypeError:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
        self.actions[1].menu().actions()[0].triggered.connect(self.drawXYPoint)

        try:
            self.actions[1].menu().actions()[1].triggered.disconnect()
        except TypeError:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
        self.actions[1].menu().actions()[1].triggered.connect(self.drawDMSPoint)
        if self.tool:
            self.tool.reset()
        self.tool = DrawPoint(self.iface, self.settings.getColor())
        self.tool.setAction(self.actions[1])
        self.tool.selectionDone.connect(self.draw)
        self.iface.mapCanvas().setMapTool(self.tool)
        self.drawShape = 'point'
        self.toolname = 'drawPoint'
        self.resetSB()

    def drawPoint(self):
        """Active l’outil point par clic carte.

        Les variantes par coordonnées restent disponibles dans le sous-menu :
        - drawXYPoint() : saisie X/Y avec choix du CRS ;
        - drawDMSPoint() : saisie latitude/longitude en DMS.
        """
        self._activatePointClickTool()

    def drawText(self):
        if self.tool:
            self.tool.reset()
        self.tool = DrawPoint(self.iface, self.settings.getColor())
        self.tool.setAction(self.actions[0])
        self.tool.selectionDone.connect(self.draw)
        self.iface.mapCanvas().setMapTool(self.tool)
        self.drawShape = 'text'
        self.toolname = 'drawText'
        # (alat gambar)
        self.resetSB()

    def _retry_coordinate_dialog_after_messagebox(self, retry_callback):
        """Rouvre la boîte de saisie après fermeture de la QMessageBox.

        Le token évite les réouvertures multiples si plusieurs erreurs sont
        déclenchées rapidement.
        """
        if retry_callback is None:
            return

        token = object()
        self._qdraw_coord_retry_token = token

        def _retry():
            try:
                if getattr(self, "_qdraw_coord_retry_token", None) is not token:
                    return
                self._qdraw_coord_retry_token = None
                QTimer.singleShot(0, retry_callback)
            except Exception:
                log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

        QTimer.singleShot(0, _retry)

    def _show_countdown_messagebox(self, title, message, seconds=5):
        """Affiche une QMessageBox au premier plan avec compte à rebours.

        La boîte est modale, reste au premier plan et se ferme automatiquement
        à la fin du compte à rebours. Le bouton OK permet de fermer plus vite.
        """
        try:
            seconds = int(seconds)
        except Exception:
            seconds = 5
        seconds = max(1, seconds)

        box = QMessageBox(self.iface.mainWindow())
        try:
            box.setIcon(MSGBOX_WARNING)
        except Exception:
            try:
                box.setIcon(MSGBOX_WARNING)
            except Exception:
                log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

        box.setWindowTitle(title)
        box.setText(message)
        box.setInformativeText(
            self.tr("The coordinate entry window will reopen automatically after the countdown, or immediately after OK.")
        )
        box.setStandardButtons(MSGBOX_OK)
        ok_button = box.button(MSGBOX_OK)

        remaining = {"value": seconds}

        def _update_button_text():
            try:
                if ok_button is not None:
                    ok_button.setText(self.tr("OK ({s})").format(s=remaining["value"]))
            except Exception:
                log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

        timer = QTimer(box)
        timer.setInterval(1000)
        _update_button_text()

        def _tick():
            try:
                remaining["value"] -= 1
                if remaining["value"] <= 0:
                    timer.stop()
                    box.accept()
                    return
                _update_button_text()
            except Exception:
                try:
                    timer.stop()
                    box.accept()
                except Exception:
                    log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

        timer.timeout.connect(_tick)

        try:
            box.setWindowModality(APPLICATION_MODAL)
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
        try:
            box.setWindowFlag(WINDOW_STAYS_ON_TOP_HINT, True)
        except Exception:
            try:
                box.setWindowFlags(box.windowFlags() | WINDOW_STAYS_ON_TOP_HINT)
            except Exception:
                log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

        try:
            box.show()
            box.raise_()
            box.activateWindow()
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

        timer.start()
        try:
            if hasattr(box, "exec"):
                box.exec()
            else:
                box.exec()
        finally:
            try:
                timer.stop()
            except Exception:
                log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

    def _warn_invalid_coordinate_transform(self, source_crs, dest_crs, point, error, retry_callback=None):
        """Affiche une erreur de projection explicite sans traceback QGIS.

        Une QMessageBox au premier plan explique l'erreur, affiche un compte à
        rebours, puis rouvre la boîte de saisie de coordonnées.
        """
        try:
            src_authid = source_crs.authid() if source_crs else self.tr("unknown CRS")
        except Exception:
            src_authid = self.tr("unknown CRS")

        try:
            dst_authid = dest_crs.authid() if dest_crs else self.tr("unknown CRS")
        except Exception:
            dst_authid = self.tr("unknown CRS")

        try:
            x_val = point.x()
            y_val = point.y()
            pt_txt = f"{x_val:.3f}, {y_val:.3f}"
        except Exception:
            pt_txt = str(point)

        msg = self.tr(
            "The entered coordinates ({pt}) are not valid for the selected source projection {src}.\n\n"
            "Choose the projection matching the coordinates, then try again.\n\n"
            "Project projection: {dst}."
        ).format(pt=pt_txt, src=src_authid, dst=dst_authid)

        try:
            self._show_countdown_messagebox(
                self.tr("Invalid coordinates or projection"),
                msg,
                seconds=5,
            )
            self._retry_coordinate_dialog_after_messagebox(retry_callback)
        except Exception:
            # Dernier recours : ne jamais laisser cette erreur remonter vers QGIS.
            try:
                QMessageBox.warning(
                    self.iface.mainWindow(),
                    self.tr("Invalid coordinates or projection"),
                    msg,
                )
                self._retry_coordinate_dialog_after_messagebox(retry_callback)
            except Exception:
                try:
                    QgsMessageLog.logMessage(msg, "Rimba Sketsa", scoped_enum(Qgis, "MessageLevel", "Warning"))
                except Exception:
                    log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

        try:
            QgsMessageLog.logMessage(
                f"Invalid coordinate transform {src_authid} -> {dst_authid} for ({pt_txt}): {error}",
                "Rimba Sketsa",
                scoped_enum(Qgis, "MessageLevel", "Warning")
            )
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

    def drawXYPoint(self):
        # (alat gambar)
        mc = self.iface.mapCanvas()
        ms = mc.mapSettings()
        # default for drawXYPoint data : WGS84 EPSG:4326
        crs = QgsCoordinateReferenceSystem(4326)
        ms.setDestinationCrs(crs)
        self.actions[1].setIcon(
            QIcon(plugin_file("resources", 'icon_DrawPt.png')))
        self.actions[1].menu().actions()[0].setIcon(
            QIcon(plugin_file("resources", 'icon_DrawPtXY.png')))
        self.actions[1].menu().actions()[1].setIcon(
            QIcon(plugin_file("resources", 'icon_DrawPtDMS.png')))
        self.actions[1].menu().actions()[0].setText(
            self.tr('XY Point drawing tool'))
        self.actions[1].menu().actions()[1].setText(
            self.tr('DMS Point drawing tool'))
        self.actions[1].menu().actions()[0].triggered.disconnect()
        self.actions[1].menu().actions()[0].triggered.connect(self.drawXYPoint)
        self.actions[1].menu().actions()[1].triggered.disconnect()
        self.actions[1].menu().actions()[1].triggered.connect(self.drawDMSPoint)
        try:
            xytuple, ok = XYDialog().getPoint(ms.destinationCrs())
        except Exception:
            try:
                self.iface.messageBar().pushMessage(
                    self.tr('Coordinate input cancelled or invalid'),
                    self.tr('No point was created.'),
                    scoped_enum(Qgis, "MessageLevel", "Info"),
                    4
                )
            except Exception:
                log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
            return

        if not ok:
            return

        # print('xytuple : ' + str(xytuple))
        # print('crs : ' + str(crs))
        point = xytuple[0]
        ptOrigin = point
        if xytuple[1] != crs:
            crsSrc = xytuple[1]  # projection choisie par l'utilisateur
        else:
            crsSrc = crs  # projection définie par défaut dans drawXYPoint() (4326)
        crsDest = QgsProject.instance().crs()
        crsTransform = QgsCoordinateTransform(crsSrc, crsDest, QgsProject.instance())
        # Transformation crsSrc -> crsDest
        try:
            point = crsTransform.transform(ptOrigin)
        except Exception as e:
            self._warn_invalid_coordinate_transform(crsSrc, crsDest, ptOrigin, e, self.drawXYPoint)
            ms.setDestinationCrs(crsDest)
            self.XYcrs = crsDest
            self._activatePointClickTool()
            return
        # Remplacé pour utilisation de la projection du projet en cours
        # crs = QgsCoordinateReferenceSystem(2154)
        # Ligne de remplacement
        crs = QgsProject.instance().crs()
        ms.setDestinationCrs(crs)
        self.XYcrs = crs
        if ok:
            if point.x() == 0 and point.y() == 0:
                MSGBOX_CRITICAL(
                    self.iface.mainWindow(),
                    self.tr('Error'), self.tr('Invalid input !'))
                if self.tool:
                    self.tool.reset()
                self.tool = DrawPoint(self.iface, self.settings.getColor())
                self.tool.setAction(self.actions[1])
                self.tool.selectionDone.connect(self.draw)
                self.iface.mapCanvas().setMapTool(self.tool)
                self.drawShape = 'point'
                self.toolname = 'drawPoint'
                self.resetSB()
                return
            else:
                self._activatePointClickTool()
                self.tool.rb = QgsRubberBand(
                    self.iface.mapCanvas(), scoped_enum(QgsWkbTypes, "GeometryType", "PointGeometry"))
                self.tool.rb.addPoint(point)
                self.tool.rb.setColor(self.settings.getColor())
                self.tool.rb.setWidth(4)
                self.drawShape = 'XYpoint'
                # print('self.tool.rb : ' + str(self.tool.rb))
                self.draw()
                mc.setCenter(point)
                mc.refresh()
#                # wait .5 seconds to simulate a flashing effect
#                QTimer.singleShot(500,self.resetSB)

    def drawDMSPoint(self):
        # (alat gambar)
        mc = self.iface.mapCanvas()
        ms = mc.mapSettings()
        # Gestion du changement d'aspact de l'icone d'outil
        self.actions[1].setIcon(
            QIcon(plugin_file("resources", 'icon_DrawPt.png')))
        self.actions[1].menu().actions()[0].setIcon(
            QIcon(plugin_file("resources", 'icon_DrawPtXY.png')))
        self.actions[1].menu().actions()[1].setIcon(
            QIcon(plugin_file("resources", 'icon_DrawPtDMS.png')))
        self.actions[1].menu().actions()[0].setText(
            self.tr('XY Point drawing tool'))
        self.actions[1].menu().actions()[1].setText(
            self.tr('DMS Point drawing tool'))
        self.actions[1].menu().actions()[0].triggered.disconnect()
        self.actions[1].menu().actions()[0].triggered.connect(self.drawXYPoint)
        self.actions[1].menu().actions()[1].triggered.disconnect()
        self.actions[1].menu().actions()[1].triggered.connect(self.drawDMSPoint)

        point, ok = DMSDialog().getPoint()
        if not ok:
            return

        # default for drawDMSPoint data : WGS84 EPSG:4326
        crsSrc = QgsCoordinateReferenceSystem(4326)
        crsDest = QgsProject.instance().crs()
        ptOrigin = point
        crsTransform = QgsCoordinateTransform(crsSrc, crsDest, QgsProject.instance())
        # Transformation crsSrc -> crsDest
        try:
            point = crsTransform.transform(ptOrigin)
        except Exception as e:
            self._warn_invalid_coordinate_transform(crsSrc, crsDest, ptOrigin, e, self.drawDMSPoint)
            ms.setDestinationCrs(crsDest)
            self.XYcrs = crsDest
            self._activatePointClickTool()
            return
        crs = QgsProject.instance().crs()
        ms.setDestinationCrs(crs)
        self.XYcrs = crs

        if ok:
            if point.x() == 0 and point.y() == 0:
                MSGBOX_CRITICAL(
                    self.iface.mainWindow(),
                    self.tr('Error'), self.tr('Invalid input !'))
            else:
                self._activatePointClickTool()
                self.tool.rb = QgsRubberBand(
                    self.iface.mapCanvas(), scoped_enum(QgsWkbTypes, "GeometryType", "PointGeometry"))
                self.tool.rb.setColor(self.settings.getColor())
                self.tool.rb.setWidth(3)
                self.tool.rb.addPoint(point)
                self.drawShape = 'XYpoint'
                self.draw()
                # centrer la carte sur le point
                mc.setCenter(point)
                mc.refresh()

    def drawLine(self):
        # (alat gambar)
        self.actions[2].setIcon(QIcon(plugin_file("resources", 'icon_DrawL.png')))
        if self.tool:
            self.tool.reset()
        self.request = 'intersects'
        self.tool = DrawLine(self.iface, self.settings.getColor())
        self.tool.setAction(self.actions[2])
        self.tool.selectionDone.connect(self.draw)
        self.tool.move.connect(self.updateSB)
        self.iface.mapCanvas().setMapTool(self.tool)
        self.drawShape = 'line'
        self.toolname = 'drawLine'
        self.resetSB()

    def drawRect(self):
        # (alat gambar)
        self.actions[3].setIcon(QIcon(plugin_file("resources", 'icon_DrawR.png')))
        if self.tool:
            self.tool.reset()
        self.request = 'intersects'
        self.tool = DrawRect(self.iface, self.settings.getColor())
        self.tool.setAction(self.actions[3])
        self.tool.selectionDone.connect(self.draw)
        self.tool.move.connect(self.updateSB)
        self.iface.mapCanvas().setMapTool(self.tool)
        self.drawShape = 'polygon'
        self.toolname = 'drawRect'
        self.resetSB()

    def drawCircle(self):
        # (alat gambar)
        self.actions[4].setIcon(QIcon(plugin_file("resources", 'icon_DrawC.png')))

        if self.tool:
            self.tool.reset()
        self.request = 'intersects'
        self.tool = DrawCircle(self.iface, self.settings.getColor(), 40)
        self.tool.setAction(self.actions[4])
        self.tool.selectionDone.connect(self.draw)
        self.tool.move.connect(self.updateSB)
        self.iface.mapCanvas().setMapTool(self.tool)
        self.drawShape = 'polygon'
        self.toolname = 'drawCircle'
        self.resetSB()

    def drawPolygon(self):
        # (alat gambar)
        self.actions[5].setIcon(QIcon(plugin_file("resources", 'icon_DrawP.png')))
        if self.tool:
            self.tool.reset()
        self.request = 'intersects'
        self.tool = DrawPolygon(self.iface, self.settings.getColor())
        self.tool.setAction(self.actions[5])
        self.tool.selectionDone.connect(self.draw)
        self.tool.move.connect(self.updateSB)
        self.iface.mapCanvas().setMapTool(self.tool)
        self.drawShape = 'polygon'
        self.toolname = 'drawPolygon'
        self.resetSB()

    def drawBuffer(self):
        self.bGeom = None
        if self.tool:
            self.tool.reset()
        self.request = 'intersects'
        self.tool = SelectPoint(self.iface, self.settings.getColor())
        self.actions[6].setIcon(
            QIcon(plugin_file("resources", 'icon_DrawT.png')))
        self.actions[6].menu().actions()[0].setIcon(
            QIcon(plugin_file("resources", 'icon_DrawTP.png')))
        self.actions[6].setText(
            self.tr('Buffer drawing tool on the selected layer'))
        self.actions[6].menu().actions()[0].setText(
            self.tr('Polygon buffer drawing tool on the selected layer'))
        self.actions[6].triggered.disconnect()
        self.actions[6].triggered.connect(self.drawBuffer)
        self.actions[6].menu().actions()[0].triggered.disconnect()
        self.actions[6].menu().actions()[0].triggered.connect(self.drawPolygonBuffer)
        self.tool.setAction(self.actions[6])

        # self.tool.select.connect(self.selectBuffer)
        # self.tool.selectionDone.connect(self.draw)
        self.tool.select.connect(self._on_buffer_left_click)
        # ❌ plus de selectionDone → draw() (on ne veut plus de clic droit)

        self.iface.mapCanvas().setMapTool(self.tool)
        self.drawShape = 'polygon'
        self.toolname = 'drawBuffer'
        self.resetSB()

    def _on_buffer_left_click(self) -> None:
        """
        Clic gauche en mode 'tampon sur objet du calque sélectionné':
        - calcule bGeom (union des géométries intersectées)
        - déclenche draw() immédiatement (boîte de dialogue du tampon)
        """
        self._buffer_log("INFO", "[Buffer] clic gauche détecté → selectBuffer(auto_draw=True)")
        self.selectBuffer(auto_draw=True)

    def drawPolygonBuffer(self):
        self.bGeom = None
        if self.tool:
            self.tool.reset()
        self.request = 'intersects'
        self.tool = DrawPolygon(self.iface, self.settings.getColor())
        self.actions[6].setIcon(
            QIcon(plugin_file("resources", 'icon_DrawTP.png')))
        self.actions[6].menu().actions()[0].setIcon(
            QIcon(plugin_file("resources", 'icon_DrawT.png')))
        self.actions[6].setText(
            self.tr('Polygon buffer drawing tool on the selected layer'))
        self.actions[6].menu().actions()[0].setText(
            self.tr('Buffer drawing tool on the selected layer'))
        self.actions[6].triggered.disconnect()
        self.actions[6].triggered.connect(self.drawPolygonBuffer)
        self.actions[6].menu().actions()[0].triggered.disconnect()
        self.actions[6].menu().actions()[0].triggered.connect(self.drawBuffer)
        self.tool.setAction(self.actions[6])
        self.tool.selectionDone.connect(self.selectBuffer)
        self.iface.mapCanvas().setMapTool(self.tool)
        self.drawShape = 'polygon'
        self.toolname = 'drawBuffer'
        self.resetSB()

    def showSettingsWindow(self):
        self.settings.settingsChanged.connect(self.settingsChangedSlot)
        self.settings.show()

    # triggered when a setting is changed
    def settingsChangedSlot(self):
        if self.tool:
            self.tool.rb.setColor(self.settings.getColor())

    def tr_messages(self):
        return {
            'drawText': self.tr('Left click to place a text.'),
            'drawPoint': self.tr('Left click to place a point.'),
            'drawLine': self.tr('Left click to place points. Right click to confirm.'),
            'drawRect': self.tr('Maintain the left click to draw a rectangle.'),
            'drawCircle': self.tr(
                'Maintain the left click to draw a circle. '
                'Simple left click to give a perimeter.'
            ),
            'drawPolygon': self.tr(
                'Left click to place points. Right click to confirm.'
            ),
            'drawBuffer': self.tr(
                'Select a vector layer in the Layer Tree, then select an entity on the map.'
            ),
        }

    def resetSB(self):
        self.sb.showMessage(self.tr_messages().get(self.toolname, ''))

    def updateSB(self):
        g = self.geomTransform(
            self.tool.rb.asGeometry(),
            self.iface.mapCanvas().mapSettings().destinationCrs(),
            QgsProject.instance().crs()
        )

        if self.toolname == "drawLine":
            length = max(0.0, float(g.length()))
            self.sb.showMessage(
                self.tr("Length: {value} m").format(value=f"{length:.2f}")
            )
        else:
            area = max(0.0, float(g.area()))
            self.sb.showMessage(
                self.tr("Area: {value} m²").format(value=f"{area:.2f}")
            )

        # (cette ligne ne fait rien, tu peux la supprimer)
        # self.iface.mapCanvas().mapSettings().destinationCrs().authid()

    def geomTransform(self, geom, crs_orig, crs_dest):
        g = QgsGeometry(geom)
        crsTransform = QgsCoordinateTransform(
            crs_orig, crs_dest, QgsCoordinateTransformContext())  # which context ?
        g.transform(crsTransform)
        return g

    def _find_first_visible_vector_layer_intersecting(self, geom: QgsGeometry) -> Optional[QgsVectorLayer]:
        """
        Cherche dans TOUTES les couches vectorielles visibles la première couche
        ayant au moins une entité qui intersecte `geom`.
        Retourne la couche trouvée, sinon None.
        """
        root = self.root  # QgsProject.instance().layerTreeRoot()
        for lyr in QgsProject.instance().mapLayers().values():
            try:
                if lyr.type() != scoped_enum(QgsMapLayer, "LayerType", "VectorLayer"):
                    continue
                node = root.findLayer(lyr.id())
                if node is None or not node.isVisible():
                    continue

                vlayer = lyr  # QgsVectorLayer
                # reprojection geom -> CRS couche
                g = self.geomTransform(
                    geom,
                    self.iface.mapCanvas().mapSettings().destinationCrs(),
                    vlayer.crs(),
                )

                # test rapide bbox + premier intersect
                for f in vlayer.getFeatures(QgsFeatureRequest(g.boundingBox())):
                    try:
                        if g.intersects(f.geometry()):
                            return vlayer
                    except Exception:
                        return vlayer
            except Exception:
                log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
                continue
        return None

    def selectBuffer(self, auto_draw: bool = False) -> None:
        rb = self.tool.rb

        if isinstance(self.tool, DrawPolygon):
            rbSelect = self.tool.rb
        else:
            rbSelect = self.tool.rbSelect

        # ✅ couche vectorielle visible robuste (OK même si clic item de légende)
        layer = self.get_current_visible_vector_layer()

        # ------------------------------------------------------------------
        # ✅ PATCH: si aucune couche active/visible, on détecte sous le clic
        # ------------------------------------------------------------------
        if layer is None:
            canvas_pos = self._canvas_pos_from_tool()

            if canvas_pos is not None:
                hit = self.identify_topmost_vector_feature(canvas_pos)

                if hit is not None:
                    layer, feat = hit

                    # on force la couche active + sélection
                    try:
                        self.iface.setActiveLayer(layer)
                    except Exception:
                        log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
                    try:
                        layer.selectByIds([feat.id()])
                    except Exception:
                        log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

                    self._buffer_log(
                        "INFO",
                        f"[Buffer] auto-layer='{layer.name()}', fid={feat.id()} (aucune couche active)"
                    )
                else:
                    self._buffer_log(
                        "WARN",
                        "[Buffer] Aucun objet vectoriel détecté sous le clic (aucune couche active)."
                    )
                    return
            else:
                self._buffer_log(
                    "WARN",
                    "[Buffer] Impossible de récupérer la position du clic (QPoint) pour identify()."
                )
                return

        self._buffer_log("INFO", f"[Buffer] layer='{layer.name()}' auto_draw={auto_draw}")

        # Reprojection rubberband -> CRS layer
        g = self.geomTransform(
            rbSelect.asGeometry(),
            self.iface.mapCanvas().mapSettings().destinationCrs(),
            layer.crs(),
        )

        try:
            features = layer.getFeatures(QgsFeatureRequest(g.boundingBox()))
        except Exception as e:
            self._buffer_log("ERROR", f"[Buffer] getFeatures() a échoué: {e}")
            return

        rbGeom = []
        for feature in features:
            geom = feature.geometry()
            try:
                if g.intersects(geom):
                    rbGeom.append(feature.geometry())
            except Exception:
                # fallback: on garde si intersects plante (géométries invalides)
                rbGeom.append(feature.geometry())

        if not rbGeom:
            self._buffer_log("WARN", "[Buffer] Aucun objet intersecté → bGeom reste None")

            if not self._buffer_warned_no_intersection:
                QMessageBox.warning(
                    self.iface.mainWindow(),
                    self.tr("No object selected"),
                    self.tr(
                        "No object was found under the click.\n\n"
                        "Please click directly on an object of the active layer."
                    ),
                )
                self._buffer_warned_no_intersection = True

            self.bGeom = None
            return
        else:
            self._buffer_warned_no_intersection = False

        # Union des géométries intersectées (ton algo original)
        self.bGeom = None
        for geometry in rbGeom:
            try:
                if rbGeom[0].combine(geometry) is not None:
                    if self.bGeom is None:
                        self.bGeom = geometry
                    else:
                        self.bGeom = self.bGeom.combine(geometry)
            except Exception:
                # combine peut échouer sur géom invalides → fallback simple
                if self.bGeom is None:
                    self.bGeom = geometry

        if self.bGeom is None or self.bGeom.isEmpty():
            self._buffer_log("WARN", "[Buffer] Union vide après combine()")
            return

        # Affiche la géom sélectionnée dans la rubberband
        try:
            rb.setToGeometry(self.bGeom, layer)
        except Exception as e:
            self._buffer_log("ERROR", f"[Buffer] rb.setToGeometry() a échoué: {e}")
            return

        self._buffer_log("INFO", "[Buffer] bGeom OK → rubberband mise à jour")

        # ✅ Mode SelectPoint: déclenchement immédiat
        if auto_draw and not isinstance(self.tool, DrawPolygon):
            # draw() s'appuie sur self.layer dans certains chemins → on synchronise
            self.layer = layer
            self._buffer_try_trigger_draw(reason="auto_draw_left_click")
            return

        # ✅ Mode polygonal: on garde ton fonctionnement existant
        if isinstance(self.tool, DrawPolygon):
            self._buffer_log("INFO", "[Buffer] Mode DrawPolygon: draw() via fin de polygone")
            self.draw()

    def _apply_text_labeling(self, layer, field_name: str):
        """
        Labeling texte robuste multi-QGIS (3.22 → 3.42)
        Spécialement corrigé pour QGIS 3.40.x (Bratislava).
        """

        layer_settings = QgsPalLayerSettings()

        # --------------------------------------------------
        # Format texte
        # --------------------------------------------------
        text_format = QgsTextFormat()
        text_format.setFont(self.settings.getFont())
        text_format.setSize(self.settings.getFont().pointSize())
        text_format.setColor(self.settings.getColorFont())

        layer_settings.setFormat(text_format)
        layer_settings.fieldName = field_name

        # --------------------------------------------------
        # Placement "di atas titik" — enum berbeda antar versi QGIS:
        #   QGIS >= 3.26 / 4.x : Qgis.LabelPlacement.OverPoint
        #   QGIS <  3.26       : QgsPalLayerSettings.OverPoint
        # (versi asli memakai QgsPalLayerSettings.LabelPlacement yang tidak
        #  ada, sehingga alat teks crash di QGIS 3.30–3.38)
        # --------------------------------------------------
        try:
            placement = Qgis.LabelPlacement.OverPoint
        except AttributeError:
            placement = QgsPalLayerSettings.OverPoint
        try:
            layer_settings.placement = placement
        except Exception:
            log.debug("Ignored exception while setting label placement", exc_info=True)

        # Centrage strict sur le point (évite décalages)
        try:
            layer_settings.dist = 0
            layer_settings.xOffset = 0
            layer_settings.yOffset = 0
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

        labeling = QgsVectorLayerSimpleLabeling(layer_settings)
        layer.setLabeling(labeling)
        layer.setLabelsEnabled(True)

    def _geometry_from_click_point(self, rb_geom: QgsGeometry) -> QgsGeometry:
        """
        Retourne une géométrie Point EXACTE du clic si possible.
        Fallback : centroid.
        """
        try:
            if rb_geom and not rb_geom.isEmpty():
                if rb_geom.type() == scoped_enum(QgsWkbTypes, "GeometryType", "PointGeometry"):
                    # Cas standard : point
                    return QgsGeometry(rb_geom)
                # Si la rubberband a une géom "bizarre", on force le centroid
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
        return rb_geom.centroid() if rb_geom else rb_geom

    def _clear_tool_rubberbands(self):
        """Supprime immédiatement les rubberbands (points virtuels) du tool."""
        try:
            if self.tool and hasattr(self.tool, "rb") and self.tool.rb:
                self.tool.rb.reset(scoped_enum(QgsWkbTypes, "GeometryType", "PointGeometry"))
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
        try:
            if self.tool and hasattr(self.tool, "rbSelect") and self.tool.rbSelect:
                self.tool.rbSelect.reset(scoped_enum(QgsWkbTypes, "GeometryType", "PointGeometry"))
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
        try:
            self.iface.mapCanvas().refresh()
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

    def draw(self) -> None:
        """
        Draw handler (Rimba Sketsa) — version robuste + choix tampon / pas de tampon.

        ✅ Points clés :
        - utilise get_current_visible_vector_layer()
        - choix modale "tampon / pas de tampon / annuler"
        - adapte le titre/label de QDrawLayerDialog selon le choix
        - corrige le bug logique (double elif btn_buffer)
        """
        test_draw = None
        rb = self.tool.rb
        g = rb.asGeometry()
        # ✅ Géométrie stable pour la sélection (rb peut être reset plus tard)
        self._last_draw_geom = QgsGeometry(g) if g is not None else None

        # recentre/zoom
        mc = self.iface.mapCanvas()
        mc.setCenter(g.centroid().asPoint())
        if self.drawShape in ["point", "XYpoint", "text"]:
            mc.zoomScale(5000)
        else:
            mc.zoomToFeatureExtent(g.boundingBox())

        ok = True
        warning = False
        errBuffer_noAtt = False
        errBuffer_Vertices = False

        # ✅ couche visible robuste (au lieu de currentLayer)
        self.layer = self.get_current_visible_vector_layer()

        # >>> PATCH START (Buffer: choix tampon/pas tampon) -------------------------
        if self.toolname == "drawBuffer":
            if self.layer is None:
                self._buffer_log("WARN", "[Buffer] Aucune couche courante visible")
                return

            if self.bGeom is None or self.bGeom.isEmpty():
                warning = True
                errBuffer_noAtt = True
                return

            # --------------------------------------------------
            # ✅ QUESTION MODALE : créer un tampon ou non ?
            # --------------------------------------------------
            msg = QMessageBox(self.iface.mainWindow())
            msg.setWindowTitle(self.tr("Buffer creation"))
            msg.setIcon(MSGBOX_QUESTION)
            msg.setText(self.tr("Do you want to create a buffer around the selected object?"))
            msg.setInformativeText(
                self.tr("Choose whether the selection must use the object itself or a buffer around it.")
            )

            btn_buffer = msg.addButton(self.tr("Create buffer"), MSGBOX_ACCEPT_ROLE)
            btn_nobuffer = msg.addButton(self.tr("No buffer"), scoped_enum(QMessageBox, "ButtonRole", "DestructiveRole"))
            btn_cancel = msg.addButton(self.tr("Cancel"), MSGBOX_REJECT_ROLE)

            msg.setWindowModality(APPLICATION_MODAL)
            msg.setWindowFlags(msg.windowFlags() | WINDOW_STAYS_ON_TOP_HINT)

            msg.exec()
            clicked = msg.clickedButton()

            # ❌ Annulation
            if clicked == btn_cancel:
                self._buffer_log("INFO", "[Buffer] Annulé par l'utilisateur")
                return

            # ✅ PAS DE TAMPON
            if clicked == btn_nobuffer:
                self._buffer_mode = "polygon"
                self._buffer_log("INFO", "[Buffer] Mode POLYGON (sans tampon)")
                g = QgsGeometry(self.bGeom)

            # ✅ AVEC TAMPON
            elif clicked == btn_buffer:
                self._buffer_mode = "buffer"
                self._buffer_log("INFO", "[Buffer] Mode BUFFER → demande distance")

                perim, ok = QInputDialog.getDouble(
                    self.iface.mainWindow(),
                    self.tr("Buffer size"),
                    self.tr(
                        "Enter the buffer size in meters:\n"
                        "(works only with a metric coordinate reference system)"
                    ),
                    min=0,
                )

                if not ok or perim <= 0:
                    warning = True
                    errBuffer_Vertices = True
                    return

                g = self.bGeom.buffer(perim, 40)

                rb.setToGeometry(
                    g,
                    QgsVectorLayer(
                        "Polygon?crs=" + self.layer.crs().authid(),
                        "",
                        "memory",
                    ),
                )
        # <<< PATCH END ------------------------------------------------------------

        if self.toolname == "drawCopies":
            errBuffer_noAtt = True

        name_draw = ""
        add = False

        self.testGroups()

        if ok and not warning:
            self.index = 0
            self.layers = []

            # --------------------------------------------------
            # Adaptation du texte selon l'outil (circle, buffer, etc.)
            # --------------------------------------------------
            dialog_title = None
            dialog_label = None
            dialog_placeholder = None  # optionnel (si tu l'ajoutes au dialog)

            if self.toolname == "drawCircle":
                dialog_title = self.tr("Circle name")
                dialog_label = self.tr("Enter a name for the circle:")
                dialog_placeholder = self.tr("Circle…")

            elif self.toolname == "drawRect":
                dialog_title = self.tr("Rectangle name")
                dialog_label = self.tr("Enter a name for the rectangle:")
                dialog_placeholder = self.tr("Rectangle…")

            elif self.toolname == "drawPolygon":
                dialog_title = self.tr("Polygon name")
                dialog_label = self.tr("Enter a name for the polygon:")
                dialog_placeholder = self.tr("Polygon…")

            # (garde ton bloc drawBuffer ici, comme tu l'as déjà)
            if self.toolname == "drawBuffer":
                if self._buffer_mode == "buffer":
                    dialog_title = self.tr("Buffer name")
                    dialog_label = self.tr("Enter a name for the buffer:")
                    dialog_placeholder = self.tr("Buffer…")
                elif self._buffer_mode == "polygon":
                    dialog_title = self.tr("Polygon name")
                    dialog_label = self.tr("Enter a name for the polygon:")
                    dialog_placeholder = self.tr("Polygon…")

            # Appel robuste : uniquement des arguments positionnels pour rester
            # SketsaLayerDialog.getName()
            try:
                name_draw, add, self.index, self.layers, ok = SketsaLayerDialog.getName(
                    self.iface,
                    self.drawShape,
                    toolname=self.toolname,
                    title_override=dialog_title,
                    label_override=dialog_label,
                    placeholder_override=dialog_placeholder,
                )
            except Exception:
                log.debug("SketsaLayerDialog.getName failed", exc_info=True)
                ok = False

            # -------------------------------------------------------------------------
            # Le reste de draw() reste IDENTIQUE (ajout entités, attributs, etc.)
            # -------------------------------------------------------------------------

            if ok and not warning:
                group = self._get_or_create_drawings_group()

                test_draw = 1
                if add:
                    self.layer = self.layers[self.index]
                    if self.drawShape in ["point", "XYpoint", "text"]:
                        g = self._geometry_from_click_point(g)

                else:
                    if self.drawShape in ["point", "text"]:
                        self.layer = QgsVectorLayer(
                            f"Point?crs={self.iface.mapCanvas().mapSettings().destinationCrs().authid()}&field={DRAWINGS_FIELD_NAME}:string(255)",
                            name_draw,
                            "memory",
                        )
                        g = self._geometry_from_click_point(g)

                    elif self.drawShape == "XYpoint":
                        self.layer = QgsVectorLayer(
                            f"Point?crs={self.XYcrs.authid()}&field={DRAWINGS_FIELD_NAME}:string(255)",
                            name_draw,
                            "memory",
                        )
                        g = self._geometry_from_click_point(g)

                    elif self.drawShape == "line":
                        self.layer = QgsVectorLayer(
                            f"LineString?crs={self.iface.mapCanvas().mapSettings().destinationCrs().authid()}&field={DRAWINGS_FIELD_NAME}:string(255)",
                            name_draw,
                            "memory",
                        )

                    else:
                        self.layer = QgsVectorLayer(
                            f"Polygon?crs={self.iface.mapCanvas().mapSettings().destinationCrs().authid()}&field={DRAWINGS_FIELD_NAME}:string(255)",
                            name_draw,
                            "memory",
                        )

                self._apply_drawings_field_alias(self.layer)

                self.layer.startEditing()
                symbols = self.layer.renderer().symbols(QgsRenderContext())
                symbols[0].setColor(self.settings.getColor())

                self.feature = QgsFeature(self.layer.fields())
                self.feature.setGeometry(g)
                self.feature.setAttributes([name_draw])
                self.layer.dataProvider().addFeatures([self.feature])
                self.featureid = self.feature.id()

                self._clear_tool_rubberbands()

                if self.drawShape == "text":
                    symbols[0].setSize(0)
                    self._apply_text_labeling(layer=self.layer, field_name=DRAWINGS_FIELD_NAME)
                    self.layer.renderer().symbol().symbolLayer(0).setShape(
                        scoped_enum(QgsSimpleMarkerSymbolLayerBase, "Shape", "Star")
                    )
                    self.layer.triggerRepaint()
                    self.iface.layerTreeView().refreshLayerSymbology(self.layer.id())
                    self.iface.mapCanvas().refresh()

                if not add:
                    self.project.addMapLayer(self.layer, False)
                    group.insertLayer(0, self.layer)

                self.iface.layerTreeView().refreshLayerSymbology(self.layer.id())
                self.iface.mapCanvas().refresh()

            # -------------------------------------------------------------------------
            # ... (le reste de ton draw() continue ensuite sans changement)
            # -------------------------------------------------------------------------

            # (IMPORTANT : je n’ai pas recopié la fin complète ici si elle est identique,
            # mais tu peux coller ce draw() en remplaçant ton bloc initial + garder ta fin.)

        # Modification pour ajout de la sélection des couches intersectant
        # une ligne ou un polygone, avec cochage automatique puis décochage du groupe sélectionné
        if self.drawShape not in ['point', 'XYpoint', 'text'] and test_draw == 1:
            # Définition du choix d'une sélection en intersection
            box = QMessageBox()
            box.setWindowTitle(self.tr('Choosing a selection'))
            box.setIcon(MSGBOX_INFORMATION)
            box.setText(self.tr("{name} drawn. Make a selection within its extent?").format(name=name_draw))
            box.setStandardButtons(MSGBOX_YES | MSGBOX_NO)
            box.setDefaultButton(MSGBOX_YES)
            buttonYes = box.button(MSGBOX_YES)
            buttonNo = box.button(MSGBOX_NO)
            box.setWindowModality(WINDOW_MODAL)
            box.setWindowFlags(WINDOW_STAYS_ON_TOP_HINT)
            box.exec()

            self.groupes_coches = []
            test_coche = self.verifCocheGroupes()

            if box.clickedButton() == buttonYes:

                # ------------------------------------------------------------------
                # PATCH : Aucun groupe existant → création d'un groupe + choix des couches
                # ------------------------------------------------------------------

                root = QgsProject.instance().layerTreeRoot()

                # Construire la liste des groupes exclus
                excluded_groups = self.group_no_select + self.group_drawing

                # Construire la liste des couches exclues (pour ne pas les proposer dans la boîte)
                excluded_layer_ids = set()
                for grp in excluded_groups:
                    for child in grp.children():
                        if isinstance(child, QgsLayerTreeLayer):
                            excluded_layer_ids.add(child.layerId())

                # Groupes existants (hors groupes exclus)
                groupes_existants = [
                    g for g in root.children()
                    if isinstance(g, QgsLayerTreeGroup) and g not in excluded_groups
                ]

                if len(groupes_existants) == 0:
                    # Aucun groupe exploitable → proposer création d’un nouveau
                    dlg = QDialog()
                    dlg.setWindowTitle(self.tr("No group found"))
                    layout = QVBoxLayout(dlg)

                    label = QLabel(self.tr(
                        "No group exists in the project.\n"
                        "Create a group and choose the layers to put in it:"
                    ))
                    layout.addWidget(label)

                    # Nom du groupe
                    name_edit = QLineEdit()
                    name_edit.setPlaceholderText(self.tr("New group name"))
                    layout.addWidget(name_edit)

                    # Couches disponibles (hors groupes exclus)
                    layers_box = QGroupBox(self.tr("Available layers"))
                    vbox_layers = QVBoxLayout(layers_box)

                    checkboxes = {}

                    for layer in QgsProject.instance().mapLayers().values():
                        # On exclut :
                        # 1) les couches non vectorielles
                        # 2) les couches contenues dans les groupes exclus
                        if layer.type() == scoped_enum(QgsMapLayer, "LayerType", "VectorLayer") and layer.id() not in excluded_layer_ids:
                            cb = QCheckBox(layer.name())
                            vbox_layers.addWidget(cb)
                            checkboxes[cb] = layer

                    layout.addWidget(layers_box)

                    # Boutons OK / Annuler
                    buttons = QDialogButtonBox(BUTTONBOX_OK | BUTTONBOX_CANCEL)
                    layout.addWidget(buttons)

                    def accept():
                        if not name_edit.text().strip():
                            QMessageBox.warning(
                                dlg, self.tr("Error"),
                                self.tr("You must name the group.")
                            )
                            return
                        dlg.accept()

                    buttons.accepted.connect(accept)
                    buttons.rejected.connect(dlg.reject)

                    res = dlg.exec()

                    # L’utilisateur annule
                    if res != DIALOG_ACCEPTED:
                        self._discard_unconfirmed_drawing(add)
                        self.msgForgottenTick()
                        return

                    # Création du groupe
                    new_group = QgsLayerTreeGroup(name_edit.text().strip())
                    root.insertChildNode(0, new_group)

                    # ----------------------------------------------------------
                    # Nouveau déplacement des couches cochées
                    # ----------------------------------------------------------
                    layers_to_move = [
                        layer
                        for cb, layer in checkboxes.items()
                        if cb.isChecked()
                    ]

                    # Appel de l’algo robuste
                    self.moveLayersIntoGroup(layers_to_move, new_group)
                    # ----------------------------------------------------------

                    new_group.setItemVisibilityChecked(True)

                    self.iface.messageBar().pushMessage(
                        self.tr("Group created"),
                        self.tr("The {new_group_name} group has been created and the selected layers have been moved.").format(new_group_name=new_group.name()),
                        scoped_enum(Qgis, "MessageLevel", "Success"),
                        3
                    )

                    self.groupe_selectionne = new_group
                    self.groupes_coches = [new_group]
                    test_coche = True

                else:
                    # Il existe au moins un groupe exploitable
                    # 1) Si aucun groupe n’est coché, on propose le choix des groupes non cochés
                    if not test_coche:
                        groupe_selectionne = self.askUncheckedGroup()
                        if groupe_selectionne:
                            # L’utilisateur a choisi un groupe : on le mémorise
                            self.groupe_selectionne = groupe_selectionne
                            test_coche = True
                            self.groupes_coches = [groupe_selectionne]
                        else:
                            # L’utilisateur n’a rien choisi → annulation comme avant
                            self._discard_unconfirmed_drawing(add)
                            self.msgForgottenTick()
                            return
                    # 2) À partir d’ici, on est sûr d’avoir un groupe exploitable coché
                    warning = False
                    ok = True
                    errBuffer_noAtt = False
                    errBuffer_Vertices = False
                    buffer_geom = None
                    buffer_geom_crs = None

                    # Masquer les groupes non sélectionnables (on mémorise
                    # ceux qui étaient cochés pour les restaurer ensuite)
                    self._hidden_groups = []
                    for group in self.root.children():
                        if group in self.group_no_select:
                            if group.itemVisibilityChecked():
                                self._hidden_groups.append(group)
                            group.setItemVisibilityChecked(False)
                        if group in self.group_drawing:
                            group.setItemVisibilityCheckedRecursive(False)

                    # Vérifie qu’au moins une couche visible existe
                    for layer in QgsProject().instance().mapLayers().values():
                        try:
                            if self.root.findLayer(layer.id()).isVisible():
                                warning = False
                                break
                        except Exception:
                            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

                    # Création d’un buffer sur la couche courante (si demandé)
                    if self.request == 'buffer':

                        layer = self.get_current_visible_vector_layer()
                        # layer = self.iface.layerTreeView().currentLayer()

                        if layer is not None and layer.type() == scoped_enum(QgsMapLayer, "LayerType", "VectorLayer") and QgsProject.instance().layerTreeRoot().findLayer(
                                layer.id()).isVisible():

                            g = self.geomTransform(rb.asGeometry(),
                                                   self.iface.mapCanvas().mapSettings().destinationCrs(), layer.crs())
                            features = layer.getFeatures(QgsFeatureRequest(g.boundingBox()))
                            style = layer.renderer()
                            rbGeom = []
                            for feature in features:
                                geom = feature.geometry()
                                if g.intersects(geom):
                                    rbGeom.append(QgsGeometry(feature.geometry()))
                            if len(rbGeom) > 0:
                                union_geoms = rbGeom[0]
                                for geometry in rbGeom:
                                    if union_geoms.combine(geometry) is not None:
                                        union_geoms = union_geoms.combine(geometry)

                                rb.setToGeometry(union_geoms, layer)
                                perim, ok = QInputDialog.getDouble(
                                    self.iface.mainWindow(),
                                    self.tr('Perimeter'),
                                    self.tr('Give a perimeter in m:\n(works only with metric crs)'),
                                    min=0)
                                buffer_geom_crs = layer.crs()
                                buffer_geom = union_geoms.buffer(perim, 40)
                                rb.setToGeometry(buffer_geom,
                                                 QgsVectorLayer("Polygon?crs=" + layer.crs().authid(), "", "memory"))
                                rb.setRenderer(style)
                                if buffer_geom.length == 0:
                                    warning = True
                                    errBuffer_Vertices = True
                            else:
                                warning = True
                                errBuffer_noAtt = True
                        else:
                            warning = True

                    # --- Sélection des entités intersectantes ---
                    if len(QgsProject().instance().mapLayers().values()) > 0 and not warning and ok:
                        self.loadingWindow.show()
                        self.loadingWindow.activateWindow()
                        self.loadingWindow.showNormal()

                        for layer in QgsProject().instance().mapLayers().values():
                            try:
                                if layer.type() == scoped_enum(QgsMapLayer, "LayerType", "VectorLayer") and QgsProject.instance().layerTreeRoot().findLayer(
                                        layer.id()).isVisible():
                                    if self.request == 'buffer' and self.iface.layerTreeView().currentLayer() == layer:
                                        layer.selectByIds([])
                                        continue
                                    self.loadingWindow.reset()
                                    self.loadingWindow.setWindowTitle(self.tr('Selecting...'))
                                    self.loadingWindow.setLabelText(layer.name())

                                    # rubberband reprojection
                                    if self.request == 'buffer':
                                        if buffer_geom_crs.authid() != layer.crs().authid():
                                            g = self.geomTransform(buffer_geom, buffer_geom_crs, layer.crs())
                                        else:
                                            g = self.geomTransform(buffer_geom, buffer_geom_crs, layer.crs())
                                    else:
                                        sel_geom = getattr(self, "_last_draw_geom", None)
                                        if sel_geom is None or sel_geom.isEmpty():
                                            # fallback ultime : on essaie rb, mais normalement sel_geom suffit
                                            sel_geom = rb.asGeometry()

                                        g = self.geomTransform(
                                            sel_geom,
                                            self.iface.mapCanvas().mapSettings().destinationCrs(),
                                            layer.crs()
                                        )

                                    feat_id = []
                                    features = layer.getFeatures(QgsFeatureRequest(g.boundingBox()))
                                    count = layer.getFeatures(QgsFeatureRequest(g.boundingBox()))

                                    nbfeatures = 0
                                    for feature in count:
                                        nbfeatures += 1

                                    index = 0
                                    for feature in features:
                                        geom = feature.geometry()
                                        try:
                                            if g.intersects(geom):
                                                feat_id.append(feature.id())
                                        except Exception:
                                            feat_id.append(feature.id())
                                        index += 1
                                        self.loadingWindow.setValue(int((float(index) / nbfeatures) * 100))
                                        if self.loadingWindow.wasCanceled():
                                            self.loadingWindow.reset()
                                            break
                                        QApplication.processEvents()
                                    layer.selectByIds(feat_id)
                            except Exception:
                                log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

                        self.loadingWindow.close()
                        self.showAttributesTable(name_draw)

                        # Une fois la sélection terminée → décochage du groupe
                        if self.groupe_selectionne:
                            if self.groupExists(self.groupe_selectionne):
                                self.groupe_selectionne.setItemVisibilityChecked(False)
                            else:
                                self.groupe_selectionne = None

                            QApplication.processEvents()
                            self.iface.messageBar().pushMessage(
                                self.tr("End of selection"),
                                self.tr("The {sel_group} group has been unchecked.").format(sel_group=self.groupe_selectionne.name()),
                                scoped_enum(Qgis, "MessageLevel", "Info"),
                                2
                            )
                            self._groupe_msg_affiche = False
                            self._groupe_msg_nul = False
                    else:
                        # Avertissements en cas d’erreur
                        if errBuffer_noAtt:
                            self.iface.messageBar().pushWarning(
                                self.tr('Warning'),
                                self.tr("You didn't click on a layer's attribute !"))
                        elif errBuffer_Vertices:
                            self.iface.messageBar().pushWarning(
                                self.tr('Warning'),
                                self.tr("You must give a non-null value for a point's or line's perimeter!"))
                        else:
                            self.iface.messageBar().pushWarning(
                                self.tr('Warning'),
                                self.tr('There is no selected layer, or it is not vector nor visible!'))

            elif box.clickedButton() == buttonNo:
                pass

        else:
            pass

        # Pulihkan grup yang disembunyikan selama seleksi
        self._restore_hidden_groups()
        for group in self.group_drawing:
            try:
                group.setItemVisibilityCheckedRecursive(True)
            except Exception:
                log.debug("Ignored exception while restoring drawings group", exc_info=True)
        if not self.groupes_coches:
            return
        try:
            self.layer.commitChanges()
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)
        self.tool.reset()
        self.resetSB()
        self.bGeom = None

    def _discard_unconfirmed_drawing(self, added_to_existing: bool) -> None:
        """Batalkan gambar yang belum dikonfirmasi.

        - Gambar pada layer baru (memory) -> layer dihapus dari proyek.
        - Gambar yang ditambahkan ke layer milik pengguna -> layer TIDAK
          dihapus (versi asli menghapus layer pengguna di kasus ini).
        """
        if self.layer is None or added_to_existing:
            return
        try:
            if self.project.mapLayer(self.layer.id()) is not None:
                self.project.removeMapLayer(self.layer.id())
        except Exception:
            log.debug("Ignored exception while discarding drawing", exc_info=True)

    def _restore_hidden_groups(self) -> None:
        """Centang kembali grup peta dasar/administrasi yang disembunyikan."""
        for group in getattr(self, "_hidden_groups", []) or []:
            try:
                if self.groupExists(group):
                    group.setItemVisibilityChecked(True)
            except Exception:
                log.debug("Ignored exception while restoring group", exc_info=True)
        self._hidden_groups = []

    # --------------------------------------------------------------
    # Fonction pour vérifier si un groupe existe
    # --------------------------------------------------------------
    def groupExists(self, group):
        """Vérifie si un QgsLayerTreeGroup existe encore dans l'arbre."""
        if group is None:
            return False
        try:
            # Accès à une propriété simple : si l'objet est deleted → RuntimeError
            _ = group.name()
            return True
        except RuntimeError:
            return False

    def _now_ms(self) -> int:
        """Timestamp ms (Qt) stable multi-plateformes."""
        return int(QDateTime.currentMSecsSinceEpoch())

    def _buffer_log(self, level: str, msg: str) -> None:
        """
        Log un message de debug buffer (via ton logger + fallback QgsMessageLog).
        level: 'INFO' | 'WARN' | 'ERROR'
        """
        try:
            if level == "WARN":
                log.warning(msg)
            elif level == "ERROR":
                log.error(msg)
            else:
                log.info(msg)
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

        # Optionnel: aussi dans le log QGIS (pratique en prod)
        try:
            qlvl = scoped_enum(Qgis, "MessageLevel", "Info")
            if level == "WARN":
                qlvl = scoped_enum(Qgis, "MessageLevel", "Warning")
            elif level == "ERROR":
                qlvl = scoped_enum(Qgis, "MessageLevel", "Critical")
            QgsMessageLog.logMessage(msg, "Rimba Sketsa", qlvl)
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

    def _buffer_try_trigger_draw(self, reason: str) -> None:
        """
        Déclenche draw() de manière robuste :
        - debounce (anti double signal)
        - lock (anti ré-entrance)
        - exécution différée (QTimer.singleShot) pour laisser QGIS finir l'UI event.
        """
        now = self._now_ms()

        if self._buffer_draw_lock:
            self._buffer_log("INFO", f"[Buffer] draw() ignoré (lock actif) — reason={reason}")
            return

        if (now - self._buffer_draw_last_ms) < self._buffer_draw_debounce_ms:
            self._buffer_log(
                "INFO",
                f"[Buffer] draw() ignoré (debounce {now - self._buffer_draw_last_ms}ms) — reason={reason}",
            )
            return

        if self.bGeom is None or self.bGeom.isEmpty():
            self._buffer_log("WARN", f"[Buffer] draw() non déclenché (bGeom vide) — reason={reason}")
            return

        self._buffer_draw_lock = True
        self._buffer_draw_last_ms = now
        self._buffer_log("INFO", f"[Buffer] draw() planifié — reason={reason}")

        def _do():
            try:
                # Sécurité : si le tool a changé entre-temps, on annule
                if self.toolname != "drawBuffer":
                    self._buffer_log("WARN", "[Buffer] draw() annulé (toolname a changé)")
                    return

                self._buffer_log("INFO", "[Buffer] draw() EXEC")
                self.draw()
            except Exception as e:
                self._buffer_log("ERROR", f"[Buffer] Exception draw(): {e}")
            finally:
                # libère le lock légèrement plus tard pour éviter la rafale de signaux
                QTimer.singleShot(self._buffer_draw_debounce_ms, self._buffer_release_draw_lock)

        QTimer.singleShot(0, _do)

    def _buffer_release_draw_lock(self) -> None:
        self._buffer_draw_lock = False
        self._buffer_log("INFO", "[Buffer] lock relâché")

    # -------------------------------------------------------------------------------------
    # Fonction pour sélectionner la couche en cliquant sur un item de l'analyse thématique
    # -------------------------------------------------------------------------------------

    def get_current_visible_vector_layer(self) -> Optional[QgsVectorLayer]:
        """
        Return the currently selected *visible* vector layer in the Layer Tree.

        Works even when the user clicked a legend/thematic item (categorized rule, etc.),
        where `layerTreeView().currentNode()` can be None or not a layer node.

        Returns:
            QgsVectorLayer if the current layer is a visible vector layer, else None.
        """
        view = self.iface.layerTreeView()
        layer = view.currentLayer()

        if layer is None or layer.type() != scoped_enum(QgsMapLayer, "LayerType", "VectorLayer"):
            return None

        vlayer = cast(QgsVectorLayer, layer)

        node = self._layer_tree_node_for_layer(vlayer)
        if node is None:
            return None

        if self._is_layer_tree_node_visible(node):
            return vlayer

        return None

    def _layer_tree_node_for_layer(self, layer: QgsMapLayer) -> Optional[QgsLayerTreeLayer]:
        """
        Return the real Layer Tree node for a map layer, or None if not found.
        """
        root = QgsProject.instance().layerTreeRoot()
        try:
            node = root.findLayer(layer.id())
        except Exception:
            return None

        if node is None:
            return None

        # In practice, findLayer returns QgsLayerTreeLayer; we keep it safe/typed.
        try:
            return cast(QgsLayerTreeLayer, node)
        except Exception:
            return None

    def _is_layer_tree_node_visible(self, node: QgsLayerTreeLayer) -> bool:
        """
        Robust visibility test across QGIS 3.x.

        Prefer `isVisible()` (effective visibility), fallback to `itemVisibilityChecked()`.
        """
        try:
            return bool(node.isVisible())
        except Exception:
            log.debug("Ignored exception in rimba_sketsa.py", exc_info=True)

        try:
            return bool(node.itemVisibilityChecked())
        except Exception:
            return False

    # --------------------------------------------------------------
    # Fonction pour afficher les groupes non cochés (sélection unique)
    # --------------------------------------------------------------
    def askUncheckedGroup(self):
        # Mise à jour des groupes interdits / Drawings
        self.testGroups()
        unchecked_groups = []
        # --- Récupération des groupes non cochés dans l’arbre ---
        root = QgsProject.instance().layerTreeRoot()
        for child in root.children():
            if isinstance(child, QgsLayerTreeGroup):
                if not child.isVisible() and normalize(child.name()) not in lst_group_no_select and normalize(child.name()) not in lst_group_drawing:
                    unchecked_groups.append(child)
        if not unchecked_groups:
            QMessageBox.information(
                self.iface.mainWindow(),
                self.tr("No groups"),
                self.tr("All groups are already checked.")
            )
            return None

        # --- Création de la boîte de dialogue ---
        self.dlg = QDialog(self.iface.mainWindow())
        dlg = self.dlg
        title = self.tr("Choose a group for selection")
        dlg.setWindowTitle(title)

        # Supprime les boutons système (fermer, réduire, agrandir)
        dlg.setWindowFlags(WINDOW | CUSTOMIZE_WINDOW_HINT | WINDOW_TITLE_HINT | WINDOW_STAYS_ON_TOP_HINT)
        dlg.setWindowModality(APPLICATION_MODAL)

        dlg_layout = QVBoxLayout(dlg)
        label = QLabel(self.tr("Choose a group from the list:"))
        dlg_layout.addWidget(label)

        # Groupe exclusif de boutons radio
        button_group = QButtonGroup(dlg)
        button_group.setExclusive(True)

        # Fonction appelée dès qu'un groupe est choisi
        def on_selection(group):
            self.groupe_selectionne = group
            group.setItemVisibilityChecked(True)
            dlg.done(DIALOG_ACCEPTED)

        # --- Calcul de la largeur maximale parmi les noms de groupes ---
        font_metrics = dlg.fontMetrics()
        max_group_width = 0
        for group in unchecked_groups:
            text_width = font_metrics.boundingRect(group.name()).width()
            if text_width > max_group_width:
                max_group_width = text_width

        # Ajout des boutons radio
        for group in unchecked_groups:
            rb = QRadioButton(group.name())
            dlg_layout.addWidget(rb)
            button_group.addButton(rb)
            rb.toggled.connect(lambda checked, g=group: on_selection(g) if checked else None)

        # --- Ajustement automatique de la largeur ---
        title_width = font_metrics.boundingRect(title).width()
        dlg.adjustSize()
        dlg_width = max(title_width, max_group_width) + 120  # 120 px marge visuelle
        dlg.setFixedWidth(dlg_width)
        dlg.setSizeGripEnabled(False)

        result = dlg.exec()
        if result == DIALOG_ACCEPTED:
            return self.groupe_selectionne
        return None

    def verifCocheGroupes(self):
        # Toujours réinitialiser
        self.groupes_coches = []
        for group in self.root.children():
            # Exclure tous les groupes non sélectionnables
            if group not in self.group_no_select and group not in self.group_drawing:
                if isinstance(group, QgsLayerTreeGroup):
                    node = self.root.findGroup(group.name())
                else:
                    lyr = self.project.mapLayersByName(group.name())[0]
                    node = self.root.findLayer(lyr.id())
                if node and node.isVisible():
                    self.groupes_coches.append(group)
        return bool(self.groupes_coches)

    def moveLayersIntoGroup(self, layers_to_move, target_group):
        """
        Déplace proprement une liste de QgsVectorLayer dans un groupe donné.
        On utilise l'API layer tree standard : root.findLayer(), parent.removeChildNode().
        """
        root = self.root

        for lyr in layers_to_move:
            if lyr is None:
                continue

            # Node correspondant à la couche dans l'arbre
            node = root.findLayer(lyr.id())
            if node is None:
                continue

            parent = node.parent()
            if parent is None:
                # cas très rare, mais on évite de crasher
                continue

            # On clone le node, on insère le clone dans le groupe,
            # puis on supprime l'ancien du parent.
            cloned = node.clone()
            target_group.insertChildNode(0, cloned)
            parent.removeChildNode(node)

    def findLayerNodeAnywhere(self, root, layer_id):
        """Recherche un node de couche dans tout l'arbre."""
        stack = [root]
        while stack:
            node = stack.pop()
            if isinstance(node, QgsLayerTreeLayer) and node.layerId() == layer_id:
                return node
            for child in node.children():
                stack.append(child)
        return None

    def msgForgottenTick(self):
        msgBox = QMessageBox()
        msgBox.setIcon(MSGBOX_CRITICAL)
        msgBox.setWindowTitle(self.tr("WARNING!"))
        msgBox.setText(self.tr("No layer or group is selected. Start again."))
        msgBox.setStandardButtons(MSGBOX_YES)
        msgBox.setDefaultButton(MSGBOX_YES)
        buttonYes = msgBox.button(MSGBOX_YES)
        buttonYes.setText(self.tr('Start again'))
        # Pour que la fenêtre reste au premier plan de toutes les applications en cours
        msgBox.setWindowModality(WINDOW_MODAL)
        msgBox.setWindowFlags(WINDOW_STAYS_ON_TOP_HINT)
        returnValue = msgBox.exec()
        if returnValue == buttonYes:
            # print('OK clicked')
            pass

    def msgForgottenPolygon(self):
        msgBox = QMessageBox()
        msgBox.setIcon(MSGBOX_WARNING)
        msgBox.setWindowTitle(self.tr("WARNING!"))
        # msgBox.setText(self.tr("Selection not possible. the checked layer is not a polygon."))
        msgBox.setText(self.tr("Selection not possible. The checked layer is not a polygon."))
        msgBox.setStandardButtons(MSGBOX_YES)
        msgBox.setDefaultButton(MSGBOX_YES)
        buttonYes = msgBox.button(MSGBOX_YES)
        buttonYes.setText(self.tr('Start again'))
        # Pour que la fenêtre reste au premier plan de toutes les applications en cours
        msgBox.setWindowModality(WINDOW_MODAL)
        msgBox.setWindowFlags(WINDOW_STAYS_ON_TOP_HINT)
        returnValue = msgBox.exec()
        if returnValue == buttonYes:
            # print('OK clicked')
            pass

    def msgNoSelect(self):
        msgBox = QMessageBox()
        msgBox.setIcon(MSGBOX_WARNING)
        msgBox.setWindowTitle(self.tr("WARNING!"))
        # msgBox.setText(self.tr("Selection not possible. No layers are selected in the Layer Manager."))
        msgBox.setText(self.tr("Selection not possible. No layer is selected in the Layer Manager."))
        msgBox.setStandardButtons(MSGBOX_YES)
        msgBox.setDefaultButton(MSGBOX_YES)
        buttonYes = msgBox.button(MSGBOX_YES)
        buttonYes.setText(self.tr('Start again'))
        # Pour que la fenêtre reste au premier plan de toutes les applications en cours
        msgBox.setWindowModality(WINDOW_MODAL)
        msgBox.setWindowFlags(WINDOW_STAYS_ON_TOP_HINT)
        returnValue = msgBox.exec()
        if returnValue == buttonYes:
            # print('OK clicked')
            pass

    def afficher_aide(self):
        """Affiche le fichier d'aide (HTML / Markdown / TXT) dans une boîte de dialogue."""

        # --- 1) Bahasa mengikuti bahasa UI QGIS ---
        lang = getattr(self, "locale", None) or self._current_locale()

        help_dir = PLUGIN_DIR / "help"

        # --- 2) Urutan pencarian file bantuan (bahasa aktif, lalu Inggris) ---
        candidats = []
        for code in (lang, "en"):
            for ext in ("html", "htm", "md", "txt"):
                candidats.append(help_dir / f"readme_{code}.{ext}")
        fichier = None
        for cand in candidats:
            if cand.is_file():
                fichier = cand
                break
        # Si aucun fichier trouvé : message simple
        if fichier is None:
            QMessageBox.warning(
                self.iface.mainWindow(),
                self.tr("Rimba Sketsa Help"),
                self.tr("No help file was found in the 'help' folder."),
            )
            return
        # --- 3) Lecture du contenu ---
        try:
            contenu = fichier.read_text(encoding="utf-8")
        except Exception as e:
            QMessageBox.critical(
                self.iface.mainWindow(),
                self.tr("Rimba Sketsa Help"),
                self.tr("Unable to read the help file: {error}").format(error=str(e)),
            )
            return
        suffix = fichier.suffix.lower()
        # --- 4) Préparation HTML / Markdown / Texte brut ---
        html = ""
        if suffix in (".html", ".htm"):
            # On suppose que le contenu est déjà du HTML
            html = contenu
        elif suffix == ".md":
            # Conversion très simple Markdown -> HTML (sans dépendance externe)
            # - # Titre -> <h1>, ## -> <h2>, etc.
            # - lignes normales -> <p>
            lines = contenu.splitlines()
            html_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("###### "):
                    html_lines.append("<h6>{}</h6>".format(stripped[7:]))
                elif stripped.startswith("##### "):
                    html_lines.append("<h5>{}</h5>".format(stripped[6:]))
                elif stripped.startswith("#### "):
                    html_lines.append("<h4>{}</h4>".format(stripped[5:]))
                elif stripped.startswith("### "):
                    html_lines.append("<h3>{}</h3>".format(stripped[4:]))
                elif stripped.startswith("## "):
                    html_lines.append("<h2>{}</h2>".format(stripped[3:]))
                elif stripped.startswith("# "):
                    html_lines.append("<h1>{}</h1>".format(stripped[2:]))
                elif stripped == "":
                    html_lines.append("<br>")
                else:
                    # on échappe juste les < et > pour éviter de casser le HTML
                    safe = stripped.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    html_lines.append("<p>{}</p>".format(safe))
            html = "<html><body>{}</body></html>".format("\n".join(html_lines))
        else:
            # TXT : conversion propre en HTML avec wrapping automatique
            safe = contenu.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            safe = safe.replace("\n", "<br>")
            html = f"""
                <html>
                <head>
                    <style>
                        body {{
                            font-family: 'Segoe UI', Arial, sans-serif;
                            font-size: 11pt;
                            line-height: 1.4;
                            white-space: normal;
                            word-wrap: break-word;
                            margin: 8px;
                        }}
                    </style>
                </head>
                <body>{safe}</body>
                </html>
                """
        # --- 5) Création de la boîte de dialogue ---
        dlg = QDialog(self.iface.mainWindow())
        dlg.setWindowTitle(self.tr("Rimba Sketsa Help"))
        dlg.resize(800, 600)

        layout = QVBoxLayout(dlg)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)  # liens cliquables vers le web, si présents
        browser.setHtml(html)
        layout.addWidget(browser)
        # --- 6) Boutons en bas (Fermer) ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)

        btn_close = QPushButton(self.tr("Close"))
        btn_close.clicked.connect(dlg.accept)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

        dlg.exec()
