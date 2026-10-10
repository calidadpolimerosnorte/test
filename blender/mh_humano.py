"""
Cargador minimo de MakeHuman (activos CC0) para Blender/bpy:
malla base hm08, morfologias (targets) macro y de rostro, esqueleto 'default' (163 huesos)
con sus pesos, y ojos high-poly ajustados con su .mhclo.

Los datos van en blender/makehuman_cc0/ (copiados del repositorio oficial de MakeHuman, licencia CC0).
"""
import json
import os

import numpy as np
import bpy
from mathutils import Vector

MH = os.environ.get("MH_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "makehuman_cc0"))
USADOS = set()          # archivos de MakeHuman usados (para copiarlos al repositorio)


def ruta(*p):
    f = os.path.join(MH, *p)
    USADOS.add(os.path.relpath(f, MH))
    return f


# ----------------------------------------------------------------- lectura de archivos
_CACHE = {}


def leer_obj(path):
    if path in _CACHE:
        return _CACHE[path]
    v, vt, caras, grupo = [], [], [], None
    with open(path) as fh:
        for ln in fh:
            if ln.startswith("v "):
                v.append([float(a) for a in ln.split()[1:4]])
            elif ln.startswith("vt "):
                vt.append([float(a) for a in ln.split()[1:3]])
            elif ln.startswith("g "):
                grupo = ln.split()[1]
            elif ln.startswith("f "):
                idx, uv = [], []
                for tok in ln.split()[1:]:
                    p = tok.split("/")
                    idx.append(int(p[0]) - 1)
                    uv.append(int(p[1]) - 1 if len(p) > 1 and p[1] else -1)
                caras.append((idx, uv, grupo))
    r = (np.array(v, dtype=np.float64), np.array(vt), caras)
    _CACHE[path] = r
    return r


def leer_target(rel):
    f = ruta("targets", rel)
    if f in _CACHE:
        return _CACHE[f]
    idx, d = [], []
    with open(f) as fh:
        for ln in fh:
            if ln[0] in "#\n":
                continue
            p = ln.split()
            idx.append(int(p[0]))
            d.append([float(p[1]), float(p[2]), float(p[3])])
    r = (np.array(idx, dtype=np.int64), np.array(d, dtype=np.float64).reshape(-1, 3))
    _CACHE[f] = r
    return r


def existe_target(rel):
    return os.path.exists(os.path.join(MH, "targets", rel))


# ----------------------------------------------------------------- macro modificadores
def _tri(v, a, b, c):
    """Pesos min/avg/max de un parametro 0..1 como en MakeHuman."""
    mx = max(0.0, v * 2 - 1)
    mn = max(0.0, 1 - v * 2)
    return {a: mn, b: 1 - (mx + mn), c: mx}


def _edad(a):
    if a < 0.5:
        young = max(0.0, (a - 0.1875) * 3.2)
        baby = max(0.0, 1 - a * 5.333)
        child = max(0.0, min(1.0, 5.333 * a) - young)
        return {"baby": baby, "child": child, "young": young, "old": 0.0}
    old = max(0.0, a * 2 - 1)
    return {"baby": 0.0, "child": 0.0, "young": 1 - old, "old": old}


def targets_macro(genero, edad, musculo, peso, altura, proporciones, razas):
    g = {"female": 1 - genero, "male": genero}
    e = _edad(edad)
    m = _tri(musculo, "minmuscle", "averagemuscle", "maxmuscle")
    w = _tri(peso, "minweight", "averageweight", "maxweight")
    h = _tri(altura, "minheight", "averageheight", "maxheight")
    pr = {"uncommonproportions": max(0.0, 1 - proporciones * 2), "idealproportions": max(0.0, proporciones * 2 - 1)}
    out = []
    for gn, gv in g.items():
        for en, ev in e.items():
            if gv * ev == 0:
                continue
            for rn, rv in razas.items():
                if rv:
                    out.append((f"macrodetails/{rn}-{gn}-{en}.target", rv * gv * ev))
            for mn, mv in m.items():
                for wn, wv in w.items():
                    base = gv * ev * mv * wv
                    if base == 0:
                        continue
                    out.append((f"macrodetails/universal-{gn}-{en}-{mn}-{wn}.target", base))
                    for hn, hv in h.items():
                        if hn != "averageheight" and hv:
                            out.append((f"macrodetails/height/{gn}-{en}-{mn}-{wn}-{hn}.target", base * hv))
                    for pn, pv in pr.items():
                        if pv:
                            out.append((f"macrodetails/proportions/{gn}-{en}-{mn}-{wn}-{pn}.target", base * pv))
    return out


def aplicar(base, lista):
    co = base.copy()
    for rel, w in lista:
        if w == 0:
            continue
        idx, d = leer_target(rel)
        co[idx] += w * d
    return co


def mh_a_blender(co):
    """MakeHuman: decimetros, Y arriba, mira a +Z  ->  Blender: metros, Z arriba, mira a -Y."""
    return np.stack([co[:, 0], -co[:, 2], co[:, 1]], axis=1) * 0.1


# ----------------------------------------------------------------- construccion
def construir_malla(nombre, co_bl, base_obj, grupos, coleccion):
    """Malla con TODOS los vertices de la base (para conservar indices de pesos) y solo las caras
    de los grupos pedidos; los vertices sueltos se borran despues con limpiar_sueltos()."""
    _, vt, caras = base_obj
    sel = [c for c in caras if c[2] in grupos]
    me = bpy.data.meshes.new(nombre)
    me.from_pydata([tuple(p) for p in co_bl], [], [c[0] for c in sel])
    uvl = me.uv_layers.new(name="UVMap")
    k = 0
    for c in sel:
        for u in c[1]:
            uvl.data[k].uv = vt[u] if u >= 0 else (0, 0)
            k += 1
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(nombre, me)
    coleccion.objects.link(ob)
    return ob


def limpiar_sueltos(ob):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(ob.data)
    bm.free()


def esqueleto(nombre, co_bl, coleccion, nombres_es=None):
    d = json.load(open(ruta("rigs", "default.mhskel")))
    J = {k: Vector(co_bl[v].mean(axis=0)) for k, v in d["joints"].items()}
    arm_d = bpy.data.armatures.new(nombre)
    arm = bpy.data.objects.new(nombre, arm_d)
    coleccion.objects.link(arm)
    arm.show_in_front = True
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_d.edit_bones
    orden = []

    def visitar(n):
        if n in orden:
            return
        p = d["bones"][n]["parent"]
        if p:
            visitar(p)
        orden.append(n)

    for n in d["bones"]:
        visitar(n)
    for n in orden:
        b = d["bones"][n]
        h = eb.new(n)
        h.head, h.tail = J[b["head"]], J[b["tail"]]
        if (h.tail - h.head).length < 1e-4:
            h.tail = h.head + Vector((0, 0, 0.01))
        pl = d["planes"].get(b.get("rotation_plane") or "", None)
        if pl:
            a, bb, c = (J[x] for x in pl)
            nrm = (bb - a).cross(c - a)
            if nrm.length > 1e-8:
                h.align_roll(nrm.normalized())
        if b["parent"]:
            h.parent = eb[b["parent"]]
            h.use_connect = (h.parent.tail - h.head).length < 1e-4
    bpy.ops.object.mode_set(mode="OBJECT")
    return arm


def pesos():
    return json.load(open(ruta("rigs", "default_weights.mhw")))["weights"]


def asignar_pesos(ob, w, filtro=None):
    """Crea grupos de vertices con los pesos de MakeHuman (indices de la malla base)."""
    for bn, lista in w.items():
        g = ob.vertex_groups.new(name=bn)
        for i, val in lista:
            if filtro is None or i in filtro:
                g.add([i], val, "REPLACE")


def ajustar_proxy(mhclo_rel, co_mh):
    """Coloca la malla de un proxy (.mhclo) sobre la malla base deformada (coordenadas MakeHuman)."""
    f = ruta(*mhclo_rel.split("/"))
    carpeta = os.path.dirname(f)
    esc, refs, obj = {}, [], None
    leyendo = False
    for ln in open(f):
        p = ln.split()
        if not p or p[0].startswith("#"):
            continue
        if p[0] in ("x_scale", "y_scale", "z_scale"):
            esc[p[0][0]] = (int(p[1]), int(p[2]), float(p[3]))
        elif p[0] == "obj_file":
            obj = p[1]
        elif p[0] == "verts":
            leyendo = True
        elif leyendo and len(p) == 9:
            refs.append(p)
        elif leyendo and len(p) == 1:      # formato con un solo vertice de referencia
            refs.append([p[0], p[0], p[0], 1, 0, 0, 0, 0, 0])
        elif leyendo and p[0] in ("delete_verts",):
            leyendo = False
    s = {}
    for ax, k in (("x", 0), ("y", 1), ("z", 2)):
        a, b, dist = esc[ax]
        s[ax] = abs(co_mh[a][k] - co_mh[b][k]) / dist
    pv, pvt, pcaras = leer_obj(ruta(os.path.relpath(os.path.join(carpeta, obj), MH)))
    out = np.zeros((len(refs), 3))
    for i, r in enumerate(refs):
        v1, v2, v3 = int(r[0]), int(r[1]), int(r[2])
        w1, w2, w3, d1, d2, d3 = (float(x) for x in r[3:9])
        out[i] = w1 * co_mh[v1] + w2 * co_mh[v2] + w3 * co_mh[v3] + np.array([d1 * s["x"], d2 * s["y"], d3 * s["z"]])
    return out, pvt, pcaras, refs
