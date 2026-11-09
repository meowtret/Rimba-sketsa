from __future__ import unicode_literals

from zipfile import ZipFile
from ..logger import log
import decimal
import datetime

# ----------------------------------------------------------------------
# XML DOM Qt : le modèle ODS est une constante interne au plugin.
# Aucun contenu XML externe/non fiable n'est analysé ici.
# ----------------------------------------------------------------------
from qgis.PyQt.QtXml import QDomDocument

from . import ods_components
from .formula import Formula


# ----------------------------------------------------------------------
# Compatibilité Python 2 / Python 3
# ----------------------------------------------------------------------
try:
    long
except NameError:
    long = int

try:
    unicode
except NameError:
    unicode = str


class ODSWriter(object):
    """
    Utility for writing OpenDocument Spreadsheets.

    Exemple :

        with ods.writer(open("fichier.ods", "wb")) as odsfile:
            odsfile.writerow(["A", "B"])
    """

    def __init__(self, odsfile):
        self.zipf = ZipFile(odsfile, "w")

        # Le XML de départ est un modèle interne constant.
        self.dom = QDomDocument("qdrawEVT_ods")
        parse_result = self.dom.setContent(ods_components.content_xml)
        # PyQt5 peut retourner un tuple (ok, message, ligne, colonne),
        # tandis que PyQt6 expose selon la version un booléen/objet résultat.
        if isinstance(parse_result, tuple):
            xml_ok = bool(parse_result[0])
        else:
            xml_ok = bool(parse_result)
        if not xml_ok:
            raise ValueError("Invalid internal ODS XML template")

        # Fichiers de base ODS
        self.zipf.writestr(
            "mimetype",
            ods_components.mimetype.encode("utf-8")
        )

        self.zipf.writestr(
            "META-INF/manifest.xml",
            ods_components.manifest_xml.encode("utf-8")
        )

        self.zipf.writestr(
            "styles.xml",
            ods_components.styles_xml.encode("utf-8")
        )

        self.default_sheet = None
        self.sheets = []
        self._closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Ferme proprement le fichier même si une exception survient.
        """
        try:
            self.close()
        except Exception:
            log.debug("Ignored exception in odswriter/__init__.py:76", exc_info=True)

    def close(self):
        """
        Finalise le document et ferme le ZIP proprement.
        Peut être appelé plusieurs fois sans erreur.
        """
        if self._closed:
            return

        try:
            self.zipf.writestr(
                "content.xml",
                self.dom.toString().encode("utf-8")
            )

        except Exception:
            log.debug("Ignored exception in odswriter/__init__.py:93", exc_info=True)

        finally:
            try:
                if getattr(self, "zipf", None):
                    self.zipf.close()
            except Exception:
                log.debug("Ignored exception in odswriter/__init__.py:100", exc_info=True)

            self._closed = True

    def writerow(self, cells):
        """
        Écrit une ligne dans la feuille par défaut.
        """
        if self.default_sheet is None:
            self.default_sheet = self.new_sheet()

        self.default_sheet.writerow(cells)

    def writerows(self, rows):
        """
        Écrit plusieurs lignes.
        """
        for row in rows:
            self.writerow(row)

    def new_sheet(self, name=None, cols=None):
        """
        Crée une nouvelle feuille.
        """
        sheet = Sheet(self.dom, name, cols)
        self.sheets.append(sheet)
        return sheet


class Sheet(object):

    def __init__(self, dom, name="Sheet 1", cols=None):

        self.dom = dom
        self.cols = cols

        spreadsheet_nodes = self.dom.elementsByTagName("office:spreadsheet")
        if spreadsheet_nodes.count() == 0:
            raise ValueError("Missing office:spreadsheet in internal ODS template")
        spreadsheet = spreadsheet_nodes.at(0).toElement()

        self.table = self.dom.createElement("table:table")

        if name:
            self.table.setAttribute("table:name", name)

        self.table.setAttribute("table:style-name", "ta1")

        if self.cols is not None:
            col = self.dom.createElement("table:table-column")
            col.setAttribute(
                "table:number-columns-repeated",
                unicode(self.cols)
            )
            self.table.appendChild(col)

        spreadsheet.appendChild(self.table)

    def writerow(self, cells):

        row = self.dom.createElement("table:table-row")

        content_cells = len(cells)

        if self.cols is not None:

            padding_cells = self.cols - content_cells

            if content_cells > self.cols:
                raise Exception("More cells than cols.")

            cells += [None] * padding_cells

        for cell_data in cells:

            cell = self.dom.createElement("table:table-cell")

            text = None

            # ----------------------------------------------------------
            # Dates
            # ----------------------------------------------------------
            if isinstance(cell_data, (datetime.date, datetime.datetime)):

                cell.setAttribute("office:value-type", "date")

                date_str = cell_data.isoformat()

                cell.setAttribute(
                    "office:date-value",
                    date_str
                )

                cell.setAttribute(
                    "table:style-name",
                    "cDateISO"
                )

                text = date_str

            # ----------------------------------------------------------
            # Heure
            # ----------------------------------------------------------
            elif isinstance(cell_data, datetime.time):

                cell.setAttribute(
                    "office:value-type",
                    "time"
                )

                cell.setAttribute(
                    "office:time-value",
                    cell_data.strftime("PT%HH%MM%SS")
                )

                cell.setAttribute(
                    "table:style-name",
                    "cTime"
                )

                text = cell_data.strftime("%H:%M:%S")

            # ----------------------------------------------------------
            # Booléens
            # ----------------------------------------------------------
            elif isinstance(cell_data, bool):

                cell.setAttribute(
                    "office:value-type",
                    "boolean"
                )

                cell.setAttribute(
                    "office:boolean-value",
                    "true" if cell_data else "false"
                )

                cell.setAttribute(
                    "table:style-name",
                    "cBool"
                )

                text = "TRUE" if cell_data else "FALSE"

            # ----------------------------------------------------------
            # Numériques
            # ----------------------------------------------------------
            elif isinstance(
                cell_data,
                (float, int, decimal.Decimal, long)
            ):

                cell.setAttribute(
                    "office:value-type",
                    "float"
                )

                float_str = unicode(cell_data)

                cell.setAttribute(
                    "office:value",
                    float_str
                )

                text = float_str

            # ----------------------------------------------------------
            # Formules
            # ----------------------------------------------------------
            elif isinstance(cell_data, Formula):

                cell.setAttribute(
                    "table:formula",
                    str(cell_data)
                )

            # ----------------------------------------------------------
            # Cellule vide
            # ----------------------------------------------------------
            elif cell_data is None:
                pass

            # ----------------------------------------------------------
            # Texte
            # ----------------------------------------------------------
            else:

                cell.setAttribute(
                    "office:value-type",
                    "string"
                )

                text = unicode(cell_data)

            # ----------------------------------------------------------
            # Texte cellule
            # ----------------------------------------------------------
            if text:

                p = self.dom.createElement("text:p")

                p.appendChild(
                    self.dom.createTextNode(text)
                )

                cell.appendChild(p)

            row.appendChild(cell)

        self.table.appendChild(row)

    def writerows(self, rows):

        for row in rows:
            self.writerow(row)


def writer(odsfile, *args, **kwargs):
    """
    Retourne un ODSWriter utilisable comme context manager.

    Exemple :

        with open("fichier.ods", "wb") as f:
            with ods.writer(f) as odsfile:
                odsfile.writerow(["Nom", "Valeur"])
    """
    return ODSWriter(odsfile, *args, **kwargs)
