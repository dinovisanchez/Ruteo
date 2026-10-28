"""Metabase y OSRM simulados para las pruebas de navegador (puerto 3010).

La pregunta 44 trae lo mismo que la pregunta real (docs/pregunta_metabase.sql), con fechas relativas a
hoy: pendientes sin fecha y con fecha, asignadas a técnicos de Bia y a contratistas, visitas cerradas
de los últimos 30 días, una OT con varias visitas, OTs cercanas entre sí y asignadas cerca de pendientes.
Los clientes, direcciones y coordenadas son inventados.
"""
import math
import random
from datetime import date, timedelta
from typing import Optional

from fastapi import FastAPI, Header, HTTPException

app = FastAPI()
HOY = date.today()
AYER, MANANA, PASADO = HOY - timedelta(days=1), HOY + timedelta(days=1), HOY + timedelta(days=2)
TIPOS = [("Instalación", "INST", "DIRECT"), ("Emergencia", "ALRT", "DIRECT"), ("Visita previa", "VIPE", None),
         ("Normalización medida", "NORM", "INDIRECT"), ("Desconexión", "DESX", "SEMI_DIRECT"),
         ("Normalización Telemedidas", "NOTE", "DIRECT")]
IDS = {"JORGE GELVEZ": "E-JG", "Jhonatan Rudas": "E-JR", "Juan Jaramillo": "E-JJ", "Edicson Lopez": "E-EL",
       "Pedro Nuevo": "E-PN"}
FILAS = []


def agregar(codigo, orden, situacion, fecha, electricistas, contratista, tipo, ciudad, lat, lon, operador="Enel", **extra):
    pendiente = situacion.startswith("Pend")
    bogota = ciudad == "Bogotá"
    FILAS.append({
        "Bia Code": codigo, "Orden de trabajo": orden, "Situación": situacion,
        "Estado": extra.pop("estado", "Por asignar" if pendiente else "Asignada"),
        "Estado app": "PENDING_ASSIGNMENT" if pendiente else ("COMPLETED" if situacion == "Cerrada" else "ASSIGNED"),
        "Fecha de la visita": fecha, "Contratista asignado": contratista, "Electricistas asignados": electricistas,
        "Id electricista": IDS.get(electricistas), "Tipo de OT": tipo[0], "Código tipo OT": tipo[1],
        "Tipo de medida": tipo[2], "Cliente": extra.pop("cliente", f"Cliente {codigo}"), "OR": operador,
        "Dirección": extra.pop("direccion", f"CL {len(FILAS) % 90 + 10} # {len(FILAS) % 40 + 5}-20"),
        "Ciudad": ciudad, "Departamento": extra.pop("departamento", "Bogotá D.C." if bogota else "Atlántico"),
        "Latitud": lat, "Longitud": lon, **extra,
    })


random.seed(7)
# Bogotá y Barranquilla: pendientes sin fecha, asignadas hoy y mañana a técnicos de Bia y a contratistas
plan = ([("Pendiente por asignar", None, None)] * 10 + [("Asignada", "CARLOS ANDRES SALAS, Juan Reyes", "Bia Energy")] * 3
        + [("Asignada", "Luis Bermudez", "Bia Energy")] * 2 + [("Asignada", "Pedro Gómez", "MONTAJES MTE S.A.S")]
        + [("Asignada", "Andrés Ruiz", "Eléctricos del Norte")] + [("Asignada", "Edicson Lopez", "Bia Energy")] * 2)
for k, (situacion, gente, contratista) in enumerate(plan):
    fecha = None if situacion.startswith("Pend") else (MANANA if gente == "Edicson Lopez" else HOY)
    agregar(f"CO02000{k:05d}", 950000 + k, situacion, f"{fecha}T{8 + k % 8:02d}:00:00" if fecha else None, gente, contratista,
            TIPOS[k % len(TIPOS)], "Bogotá", round(4.65 + random.uniform(-.06, .06), 6), round(-74.1 + random.uniform(-.06, .06), 6))
for k in range(18, 21):
    agregar(f"CO02000{k:05d}", 950000 + k, "Pendiente por asignar", None, None, None, TIPOS[k % len(TIPOS)], "Barranquilla",
            round(10.98 + random.uniform(-.06, .06), 6), round(-74.81 + random.uniform(-.06, .06), 6), "Air-e")
agregar("CO0200000021", 950021, "Asignada", f"{HOY}T13:00:00", "Jhonatan Rudas", "Bia Energy", TIPOS[3], "Barranquilla",
        10.97, -74.80, "Air-e")

# Costa fuera de Barranquilla (zona del equipo Costa) y Valledupar (fuera de zona)
for k, (ciudad, departamento, operador, lat, lon, tipo) in enumerate([
        ("Cartagena", "Bolívar", "Afinia", 10.405, -75.505, TIPOS[2]),
        ("Cartagena", "Bolívar", "AFINIA - CARIBEMAR DE LA COSTA", 10.39, -75.48, TIPOS[0]),
        ("Santa Marta", "Magdalena", "Air-e", 11.235, -74.2, ("Toma de Lectura In Situ", None, None)),
        ("Valledupar", "Cesar", "Afinia", 10.47, -73.25, TIPOS[2])]):
    agregar(f"CO03000{k:05d}", 960000 + k, "Pendiente por asignar", None, None, None, tipo, ciudad, lat, lon, operador,
            departamento=departamento)

# Pendientes con fecha: dos de mañana y una vencida de ayer
for k, (fecha, lat, lon) in enumerate([(MANANA, 4.70, -74.05), (MANANA, 4.61, -74.12), (AYER, 4.68, -74.09)]):
    agregar(f"CO04000{k:05d}", 970000 + k, "Pendiente por asignar", f"{fecha}T09:00:00", None, None, TIPOS[2], "Bogotá", lat, lon)

# Una OT de hoy sin ubicación
agregar("CO0500000001", 980001, "Asignada", f"{HOY}T15:00:00", "LUIS BERMUDEZ", "Bia Energy", TIPOS[3], "", None, None,
        direccion="", departamento="")

# Tres pendientes sin fecha a menos de 1 km entre sí (Chicó): van juntas
for k, (lat, lon) in enumerate([(4.6760, -74.0480), (4.6795, -74.0455), (4.6738, -74.0442)]):
    agregar(f"CO07000{k:05d}", 975000 + k, "Pendiente por asignar", None, None, None, TIPOS[2], "Bogotá", lat, lon)

# Pasado mañana, como en Olibia: 3 pendientes y 1 asignada de Enel (escrito de dos formas) y 1 de Air-e
for k, (situacion, gente, contratista, ciudad, lat, lon, operador) in enumerate([
        ("Pendiente por asignar", None, None, "Bogotá", 4.645, -74.075, "ENEL COLOMBIA S.A. E.S.P."),
        ("Pendiente por asignar", None, None, "Bogotá", 4.690, -74.060, "Enel"),
        ("Asignada", "Carlos Andres Salas", "Bia Energy", "Bogotá", 4.610, -74.090, "Enel"),
        ("Pendiente por asignar", None, None, "Bogotá", 4.720, -74.110, "Enel"),
        ("Pendiente por asignar", None, None, "Barranquilla", 10.990, -74.800, "Air-e")]):
    agregar(f"CO08000{k:05d}", 985000 + k, situacion, f"{PASADO}T{9 + k:02d}:00:00", gente, contratista, TIPOS[5], ciudad,
            lat, lon, operador)

# Asignadas cerca de pendientes: pasado mañana junto a CO0800000000, hoy junto al grupo de Chicó
for k, (fecha, persona, lat, lon) in enumerate([(f"{PASADO}T15:00:00", "Luis Bermudez", 4.6500, -74.0720),
                                               (f"{HOY}T14:00:00", "Edicson Lopez", 4.6780, -74.0460),
                                               (f"{MANANA}T08:00:00", "Pedro Gómez", 4.6770, -74.0470)]):
    agregar(f"CO1000000{k:03d}", 995000 + k, "Asignada", fecha, persona,
            "MONTAJES MTE S.A.S" if persona == "Pedro Gómez" else "Bia Energy", TIPOS[5], "Bogotá", lat, lon)

# Visitas anteriores de dos OTs de pasado mañana (una fila por visita, como visitas_general)
for codigo, orden, segunda in (("CO0800000000", 985000, "Pendiente por asignar"), ("CO0800000001", 985001, "Cerrada")):
    agregar(codigo, orden, "Pendiente por asignar", f"{HOY - timedelta(days=20)}T08:00:00", None, None, TIPOS[5], "Bogotá",
            4.645, -74.075)
    agregar(codigo, orden, segunda, f"{HOY - timedelta(days=10)}T08:00:00",
            "Luis Bermudez" if segunda == "Cerrada" else None, "Bia Energy" if segunda == "Cerrada" else None,
            TIPOS[5], "Bogotá", 4.690, -74.060, estado="Cierre Fallido" if segunda == "Cerrada" else "Por asignar")

# Historial: visitas cerradas de los técnicos de Bia en los últimos 30 días (para la utilización)
random.seed(11)
GENTE = [("JORGE GELVEZ", 10.98, -74.80), ("Jhonatan Rudas", 10.98, -74.80), ("CARLOS ANDRES SALAS, Juan Reyes", 4.65, -74.1),
         ("Juan Jaramillo", 4.65, -74.1), ("Edicson Lopez", 4.65, -74.1), ("Pedro Nuevo", 4.65, -74.1)]
for dias_atras in range(1, 31):
    fecha = HOY - timedelta(days=dias_atras)
    if fecha.weekday() == 6:
        continue
    for i, (persona, lat, lon) in enumerate(GENTE):
        bogota = lat < 5
        for n in range(random.randint(1, 4)):
            agregar(f"CO09{dias_atras:02d}{i}{n}", None, "Cerrada", f"{fecha}T{8 + 2 * n:02d}:30:00", persona, "Bia Energy",
                    (random.choice(["Visita previa", "Normalización medida", "Desconexión"]), None, None),
                    "Bogotá" if bogota else "Barranquilla", round(lat + random.uniform(-.06, .06), 6),
                    round(lon + random.uniform(-.06, .06), 6), "Enel" if bogota else "Air-e", estado="Cierre Exitoso")

# Quién creó cada OT y cuándo
for n, fila in enumerate(FILAS):
    fila["Creado por"] = ["Ana María Torres", "Camilo Rojas", "Diana Pérez"][n % 3]
    fila["Fecha de creación"] = f"{HOY - timedelta(days=1 + n % 9)}T10:15:00"


@app.post("/api/card/{card_id}/query/json")
def pregunta(card_id: int, x_api_key: Optional[str] = Header(None)):
    if x_api_key != "test-key":
        raise HTTPException(401, "Unauthenticated")
    if card_id != 44:
        raise HTTPException(404, "Not found")
    return FILAS


@app.get("/search")
def nominatim(q: str):
    """Nominatim: solo conoce el centro de algunas ciudades"""
    centros = {"Bogotá": ("4.6097", "-74.0817"), "Barranquilla": ("10.9639", "-74.7964")}
    return [{"lat": lat, "lon": lon} for ciudad, (lat, lon) in centros.items() if q.startswith(ciudad)]


def _km(a, b):
    (lon1, lat1), (lon2, lat2) = a, b
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


@app.get("/route/v1/driving/{coordenadas}")
def osrm_ruta(coordenadas: str):
    """Ruta por «calles»: una escalera entre cada par de puntos, para que no sea una recta"""
    puntos = [tuple(map(float, c.split(","))) for c in coordenadas.split(";")]
    linea = []
    for (lon1, lat1), (lon2, lat2) in zip(puntos, puntos[1:]):
        medio = lon1 + (lon2 - lon1) * 0.5
        linea += [[lon1, lat1], [medio, lat1], [medio, lat1 + (lat2 - lat1) * 0.6], [lon2, lat1 + (lat2 - lat1) * 0.6]]
    linea.append(list(puntos[-1]))
    km = sum(_km(a, b) for a, b in zip(puntos, puntos[1:])) * 1.25
    return {"code": "Ok", "routes": [{"distance": km * 1000, "geometry": {"type": "LineString", "coordinates": linea}}]}


@app.get("/table/v1/driving/{coordenadas}")
def osrm_tabla(coordenadas: str, sources: Optional[str] = None, destinations: Optional[str] = None, annotations: str = ""):
    """Tabla de tiempos: km por vía = línea recta × 1,25, a 55 km/h de promedio"""
    puntos = [tuple(map(float, c.split(","))) for c in coordenadas.split(";")]
    origenes = [int(i) for i in sources.split(";")] if sources else list(range(len(puntos)))
    destinos = [int(i) for i in destinations.split(";")] if destinations else list(range(len(puntos)))
    km = [[_km(puntos[i], puntos[j]) * 1.25 for j in destinos] for i in origenes]
    return {"code": "Ok", "distances": [[k * 1000 for k in fila] for fila in km],
            "durations": [[k / 55 * 3600 for k in fila] for fila in km]}
