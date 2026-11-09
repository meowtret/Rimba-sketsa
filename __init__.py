# -*- coding: utf-8 -*-
# Rimba Sketsa: alat gambar dan seleksi cepat untuk QGIS
#
# Dikembangkan oleh Alfian (meowtret) dari plugin qdrawEVT 2.74
# karya François Thévand, yang berbasis QDraw karya Jérémy Kalsron.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.


def classFactory(iface):
    from .rimba_sketsa import RimbaSketsa
    return RimbaSketsa(iface)
