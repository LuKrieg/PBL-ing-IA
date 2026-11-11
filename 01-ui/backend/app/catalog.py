"""Stations and defect catalog for the three IMACASA stations.

Viability / task / capture are filled ONLY for PC10 (this team's station, preliminary: the team report
must confirm them). PC08 and PC12 belong to other subgroups, so those fields are left empty.
`handle_misalignment` (Desface de cacha) is ONE code shared by PC10 and PC12 on purpose.
"""

STATIONS = [
    {"code": "PC08", "name": "Enderezado", "name_en": "Straightening", "implemented": False},
    {"code": "PC10", "name": "Montaje", "name_en": "Assembly", "implemented": True},
    {"code": "PC12", "name": "Inyectado", "name_en": "Injection", "implemented": False},
]

# viability: cv_2d | special_capture | instrument | None (not analyzed here)
# task: classification | detection | segmentation | anomaly | measurement | None
_PC10 = [
    ("length_out_of_tolerance", "Largo fuera de tolerancia", "special_capture", "measurement",
     "Vista cenital + referencia de escala (regla/patrón) y calibración píxel→mm."),
    ("width_out_of_tolerance", "Ancho fuera de tolerancia", "special_capture", "measurement",
     "Misma captura cenital calibrada; el ancho se mide en una sección fija de la hoja."),
    ("thickness_out_of_range", "Espesor fuera de medida", "instrument", None,
     "No se ve desde una vista superior. Se queda con calibrador / micrómetro; el resultado se registra manualmente."),
    ("poor_finish", "Mal acabado", "cv_2d", "anomaly",
     "Foto 2D con iluminación difusa; detección de anomalías o segmentación según la definición de 'mal acabado'."),
    ("poor_assembly_fit", "Mal ajuste", "special_capture", "detection",
     "Holgura en la unión hoja-cacha: requiere vista cercana/lateral con luz controlada."),
    ("bad_riveting", "Mal remachado", "cv_2d", "detection",
     "Remaches pequeños: resolución suficiente y detección + clasificación sobre recortes."),
    ("rusty_rivets", "Remaches con óxido", "cv_2d", "classification",
     "Color/textura visible en foto 2D; clasificación sobre recorte de cada remache."),
    ("handle_misalignment", "Desface de cacha", "special_capture", "measurement",
     "Desalineación geométrica entre cacha y hoja: vista cenital calibrada (y de perfil si es en altura)."),
]
_PC08 = [
    ("dents", "Golpes"), ("fingerprints", "Huellas"), ("pores", "Poros"), ("spine_waviness", "Ondulado del lomo"),
    ("chipping", "Enconchados"), ("bent_blade", "Torcido"), ("poor_polish", "Mal pulido"),
    ("blistered_blade", "Hoja ampollada/quemada"),
]
_PC12 = [
    ("handle_misalignment", "Desface de cacha"), ("dimensions_out_of_spec", "Dimensiones fuera de especificación"),
    ("bad_injection", "Mal inyectado"), ("blocked_skirt", "Pollera tapada"), ("blade_rust", "Óxido en hoja"),
    ("poor_deburring", "Mal desbarbado"),
]


def _entry(code, label, stations, viability=None, task=None, capture=None):
    return {"code": code, "label": label, "stations": stations, "viability": viability, "task": task, "capture": capture}


def build_catalog() -> list[dict]:
    out: dict[str, dict] = {}
    for code, label, v, t, cap in _PC10:
        out[code] = _entry(code, label, ["PC10"], v, t, cap)
    for code, label in _PC08:
        out[code] = _entry(code, label, ["PC08"])
    for code, label in _PC12:
        if code in out:
            out[code]["stations"].append("PC12")
        else:
            out[code] = _entry(code, label, ["PC12"])
    return list(out.values())


CATALOG = build_catalog()
BY_CODE = {d["code"]: d for d in CATALOG}


def defects_for(station: str) -> list[dict]:
    return [d for d in CATALOG if station in d["stations"]]
