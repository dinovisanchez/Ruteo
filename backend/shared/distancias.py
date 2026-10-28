"""Distancia y tiempo de desplazamiento entre dos puntos (para planear rutas y medir utilización)"""
import math
from typing import Dict, Optional, Tuple

from .models import GPSCoordinates, JornadaConfig, MatrizVial, ZonaTransito
from .utils import haversine_distance
from .zonas import recargo_transito

# Sin OSRM, los primeros km de cada desplazamiento son urbanos y el resto es carretera
KM_URBANOS = 15


class Distancias:
    """Distancia y tiempo de desplazamiento entre dos puntos.

    Con la matriz de OSRM se usan los km y minutos por las vías; sin ella (o para
    puntos que no están en la matriz), la línea recta × factor vial, con los primeros
    km a la velocidad promedio y el resto a la de carretera. Al tiempo se le suma el recargo de tránsito de la zona donde empieza
    o termina el desplazamiento (el mayor de las dos).
    """

    def __init__(self, jornada: JornadaConfig, matriz: Optional[MatrizVial] = None):
        self.factor = jornada.factor_vial
        self.velocidad = jornada.velocidad_promedio_kmh
        self.velocidad_carretera = jornada.velocidad_carretera_kmh
        self.zonas = jornada.zonas_transito
        self.matriz = matriz
        self._indice = {self._clave(lat, lon): i for i, (lat, lon) in enumerate(matriz.puntos)} if matriz else {}
        self._zona: Dict[Tuple[float, float], Optional[ZonaTransito]] = {}

    @staticmethod
    def _clave(lat: float, lon: float) -> Tuple[float, float]:
        return (round(lat, 5), round(lon, 5))

    def _vial(self, a: GPSCoordinates, b: GPSCoordinates, campo: str) -> Optional[float]:
        i = self._indice.get(self._clave(a.latitude, a.longitude))
        j = self._indice.get(self._clave(b.latitude, b.longitude))
        if i is None or j is None:
            return None
        return getattr(self.matriz, campo)[i][j]

    def zona(self, punto: GPSCoordinates) -> Optional[ZonaTransito]:
        clave_punto = self._clave(punto.latitude, punto.longitude)
        if clave_punto not in self._zona:
            self._zona[clave_punto] = recargo_transito(self.zonas, punto)
        return self._zona[clave_punto]

    def km(self, a: GPSCoordinates, b: GPSCoordinates) -> float:
        vial = self._vial(a, b, "km")
        return vial if vial is not None else haversine_distance(a, b) * self.factor

    def minutos(self, a: GPSCoordinates, b: GPSCoordinates) -> int:
        vial = self._vial(a, b, "minutos")
        if vial is not None:
            base = vial
        else:
            km = haversine_distance(a, b) * self.factor
            urbanos = min(km, KM_URBANOS)
            carretera = max(self.velocidad, self.velocidad_carretera)
            base = urbanos / self.velocidad * 60 + (km - urbanos) / carretera * 60
        if base <= 0:
            return 0
        zonas = [z for z in (self.zona(a), self.zona(b)) if z]
        if zonas:
            base = base * (1 + max(z.recargo_pct for z in zonas) / 100) + max(z.minutos_extra for z in zonas)
        return int(math.ceil(base))
