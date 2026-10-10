"""
Personas realistas y articuladas para la planta, hechas con la malla humana de MakeHuman (CC0).

8 personas: hombres y mujeres con distinta tez, rasgos y color de cabello; camisa celeste manga corta
o polo plomo, jean, zapatos de seguridad; con casco o con cofia.
Cada persona tiene un esqueleto completo (163 huesos: columna, cuello, cabeza, mandibula, ojos,
brazos, dedos, piernas, dedos de los pies) y el cuerpo y la ropa se deforman con el (pesos de MakeHuman),
asi que se pueden posar en Pose Mode. El cabello, cejas, casco y cofia siguen al hueso de la cabeza.

Metros, piso z=0, miran hacia -Y. Uso: python3 blender/personas_modelo.py
"""
import json
import math
import os
import random
import sys

import numpy as np
import bpy
import bmesh
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import mh_humano as mh  # noqa: E402

# ----------------------------------------------------------------------------- personas
# tez: color base de la piel (lineal); pelo: (melanina, rojizo); razas: mezcla MakeHuman
GENTE = [
    dict(tag="Hombre_01", mujer=False, camisa="celeste", gorro="casco", edad=30, altura_m=1.70, peso=0.55, musculo=0.60,
         razas=dict(asian=0.55, caucasian=0.35, african=0.10), tez=(0.21, 0.11, 0.065), pelo=(0.95, 0.05), peinado="corto",
         iris=(0.0, 1.0)),
    dict(tag="Hombre_02", mujer=False, camisa="celeste", gorro="cofia", edad=42, altura_m=1.76, peso=0.62, musculo=0.50,
         razas=dict(asian=0.05, caucasian=0.90, african=0.05), tez=(0.46, 0.29, 0.21), pelo=(0.62, 0.12), peinado="corto",
         iris=(0.10, 1.2)),
    dict(tag="Hombre_03", mujer=False, camisa="plomo", gorro="casco", edad=27, altura_m=1.78, peso=0.50, musculo=0.70,
         razas=dict(asian=0.0, caucasian=0.15, african=0.85), tez=(0.055, 0.03, 0.019), pelo=(1.0, 0.0), peinado="afro",
         iris=(0.0, 0.8)),
    dict(tag="Hombre_04", mujer=False, camisa="plomo", gorro="cofia", edad=50, altura_m=1.66, peso=0.68, musculo=0.45,
         razas=dict(asian=0.65, caucasian=0.25, african=0.10), tez=(0.18, 0.095, 0.055), pelo=(0.85, 0.05), peinado="corto",
         iris=(0.0, 1.0)),
    dict(tag="Mujer_01", mujer=True, camisa="celeste", gorro="casco", edad=26, altura_m=1.60, peso=0.48, musculo=0.45,
         razas=dict(asian=0.05, caucasian=0.90, african=0.05), tez=(0.52, 0.34, 0.26), pelo=(0.25, 0.25), peinado="cola",
         iris=(0.55, 1.4)),
    dict(tag="Mujer_02", mujer=True, camisa="celeste", gorro="cofia", edad=35, altura_m=1.55, peso=0.58, musculo=0.45,
         razas=dict(asian=0.60, caucasian=0.30, african=0.10), tez=(0.20, 0.105, 0.062), pelo=(0.95, 0.05), peinado="cola",
         iris=(0.0, 1.0)),
    dict(tag="Mujer_03", mujer=True, camisa="plomo", gorro="casco", edad=31, altura_m=1.63, peso=0.52, musculo=0.50,
         razas=dict(asian=0.0, caucasian=0.20, african=0.80), tez=(0.075, 0.04, 0.025), pelo=(1.0, 0.0), peinado="moño_afro",
         iris=(0.0, 0.8)),
    dict(tag="Mujer_04", mujer=True, camisa="plomo", gorro="cofia", edad=24, altura_m=1.58, peso=0.45, musculo=0.45,
         razas=dict(asian=0.35, caucasian=0.60, african=0.05), tez=(0.34, 0.20, 0.13), pelo=(0.60, 0.65), peinado="cola",
         iris=(0.07, 1.1)),
]

DEDO_X, DEDO_Z = float(os.environ.get("DEDO_X", 8)), float(os.environ.get("DEDO_Z", 1))
# catalogo completo de targets de rostro de MakeHuman (fijo, para que la seleccion al azar sea reproducible)
LISTA_ROSTRO = json.load(open(os.path.join(AQUI, "makehuman_cc0", "rostro_targets.json")))
ROSTRO = ["nose", "mouth", "chin", "cheek", "eyes", "ears", "forehead", "head", "neck", "eyebrows"]


# ----------------------------------------------------------------------------- materiales
def nodos(nombre):
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    nt = m.node_tree
    return m, nt, nt.nodes["Principled BSDF"]


def mat_piel(nombre, tez, seed):
    m, nt, b = nodos(nombre)
    N, L = nt.nodes, nt.links
    tc = N.new("ShaderNodeTexCoord")
    # manchas suaves y poros
    ns = N.new("ShaderNodeTexNoise")
    ns.inputs["Scale"].default_value = 60.0
    ns.inputs["Detail"].default_value = 6.0
    ns.noise_dimensions = "4D"
    ns.inputs["W"].default_value = seed
    L.new(tc.outputs["Object"], ns.inputs["Vector"])
    ramp = N.new("ShaderNodeValToRGB")
    t = Vector(tez)
    ramp.color_ramp.elements[0].color = (*(t * 0.86), 1)
    ramp.color_ramp.elements[1].color = (*(t * 1.08), 1)
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[1].position = 0.65
    L.new(ns.outputs["Fac"], ramp.inputs["Fac"])
    # labios y mejillas: atributo de color "Rubor" (0..1) hacia un tono rojizo
    at = N.new("ShaderNodeAttribute")
    at.attribute_name = "Rubor"
    mx = N.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    L.new(at.outputs["Fac"], mx.inputs["Factor"])
    L.new(ramp.outputs["Color"], mx.inputs[6])
    mx.inputs[7].default_value = (t.x * 0.95, t.y * 0.55, t.z * 0.58, 1)
    L.new(mx.outputs[2], b.inputs["Base Color"])
    b.inputs["Subsurface Weight"].default_value = 1.0
    b.inputs["Subsurface Radius"].default_value = (1.0, 0.38, 0.22)
    b.inputs["Subsurface Scale"].default_value = 0.006
    b.inputs["Roughness"].default_value = 0.48
    b.inputs["Specular IOR Level"].default_value = 0.45
    poro = N.new("ShaderNodeTexNoise")
    poro.inputs["Scale"].default_value = 1400.0
    poro.inputs["Detail"].default_value = 2.0
    L.new(tc.outputs["Object"], poro.inputs["Vector"])
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.12
    bump.inputs["Distance"].default_value = 0.0004
    L.new(poro.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def mat_tela(nombre, rgb, escala=900.0, rough=0.85, sheen=0.4, diagonal=False):
    m, nt, b = nodos(nombre)
    N, L = nt.nodes, nt.links
    tc = N.new("ShaderNodeTexCoord")
    tx = N.new("ShaderNodeTexWave")
    tx.wave_type = "BANDS"
    tx.bands_direction = "DIAGONAL" if diagonal else "X"
    tx.inputs["Scale"].default_value = escala
    tx.inputs["Distortion"].default_value = 1.5
    L.new(tc.outputs["Object"], tx.inputs["Vector"])
    ramp = N.new("ShaderNodeValToRGB")
    c = Vector(rgb)
    ramp.color_ramp.elements[0].color = (*(c * 0.80), 1)
    ramp.color_ramp.elements[1].color = (*(c * 1.10), 1)
    L.new(tx.outputs["Fac"], ramp.inputs["Fac"])
    ns = N.new("ShaderNodeTexNoise")
    ns.inputs["Scale"].default_value = 25.0
    L.new(tc.outputs["Object"], ns.inputs["Vector"])
    mx = N.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    mx.blend_type = "MULTIPLY"
    mx.inputs["Factor"].default_value = 0.25
    L.new(ramp.outputs["Color"], mx.inputs[6])
    L.new(ns.outputs["Color"], mx.inputs[7])
    L.new(mx.outputs[2], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    b.inputs["Sheen Weight"].default_value = sheen
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.25
    bump.inputs["Distance"].default_value = 0.0003
    L.new(tx.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def mat_simple(nombre, rgb, rough=0.5, metal=0.0, coat=0.0):
    m, nt, b = nodos(nombre)
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Coat Weight"].default_value = coat
    m.diffuse_color = (*rgb, 1)
    return m


def mat_pelo(nombre, melanina, rojizo):
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    h = nt.nodes.new("ShaderNodeBsdfHairPrincipled")
    h.parametrization = "MELANIN"
    h.inputs["Melanin"].default_value = melanina
    h.inputs["Melanin Redness"].default_value = rojizo
    h.inputs["Roughness"].default_value = 0.32
    h.inputs["Radial Roughness"].default_value = 0.4
    h.inputs["Random Color"].default_value = 0.12
    h.inputs["Random Roughness"].default_value = 0.2
    nt.links.new(h.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    return m


def mat_ojo(nombre, tinte):
    m, nt, b = nodos(nombre)
    N, L = nt.nodes, nt.links
    t = N.new("ShaderNodeTexImage")
    img = bpy.data.images.get("brown_eye.png")
    if img is None:
        img = bpy.data.images.load(mh.ruta("eyes", "materials", "brown_eye.png"))
        img.pack()
    t.image = img
    hs = N.new("ShaderNodeHueSaturation")
    hs.inputs["Hue"].default_value = (0.5 + tinte[0]) % 1.0
    hs.inputs["Saturation"].default_value = 0.75
    hs.inputs["Value"].default_value = tinte[1] * 0.6
    L.new(t.outputs["Color"], hs.inputs["Color"])
    L.new(hs.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.15
    b.inputs["Coat Weight"].default_value = 1.0
    b.inputs["Coat Roughness"].default_value = 0.02
    b.inputs["Subsurface Weight"].default_value = 0.3
    b.inputs["Subsurface Scale"].default_value = 0.002
    return m


# ----------------------------------------------------------------------------- utilidades
def malla_desde(nombre, co, caras, col, uv=None, smooth=True):
    me = bpy.data.meshes.new(nombre)
    me.from_pydata([tuple(p) for p in co], [], caras)
    if uv is not None:
        lay = me.uv_layers.new(name="UVMap")
        lay.data.foreach_set("uv", np.asarray(uv, dtype=np.float32).ravel())
    for p in me.polygons:
        p.use_smooth = smooth
    ob = bpy.data.objects.new(nombre, me)
    col.objects.link(ob)
    return ob


def normales(co, caras):
    """Normales por vertice (promedio de caras) para todos los vertices de la base."""
    n = np.zeros_like(co)
    for f in caras:
        p = co[f]
        if len(f) == 4:
            fn = np.cross(p[2] - p[0], p[3] - p[1])
        else:
            fn = np.cross(p[1] - p[0], p[2] - p[0])
        n[f] += fn
    ln = np.linalg.norm(n, axis=1)
    ln[ln == 0] = 1
    return n / ln[:, None]


def vecinos(caras, nv):
    ady = [set() for _ in range(nv)]
    for f in caras:
        for i in range(len(f)):
            a, b = f[i], f[(i + 1) % len(f)]
            ady[a].add(b)
            ady[b].add(a)
    return ady


def suavizar(co, idx, ady, it, fijos=()):
    """Laplaciano sobre los vertices idx (suaviza detalles del cuerpo bajo la ropa)."""
    co = co.copy()
    idx = [i for i in idx if i not in fijos]
    vec = {i: [j for j in ady[i]] for i in idx}
    for _ in range(it):
        nuevo = {i: co[vec[i]].mean(axis=0) for i in idx if vec[i]}
        for i, p in nuevo.items():
            co[i] = co[i] * 0.4 + p * 0.6
    return co


def taubin(co, idx, ady, it, lam=0.5, mu=-0.53):
    """Suavizado que conserva el volumen: quita detalles pequenos sin encoger la forma."""
    co = co.copy()
    vec = {i: list(ady[i]) for i in idx if ady[i]}
    for k in range(it * 2):
        f = lam if k % 2 == 0 else mu
        nuevo = {i: co[v].mean(axis=0) for i, v in vec.items()}
        for i, p in nuevo.items():
            co[i] = co[i] + (p - co[i]) * f
    return co


def armar(ob, arm, w, subdiv=1):
    mh.asignar_pesos(ob, w)
    md = ob.modifiers.new("Esqueleto", "ARMATURE")
    md.object = arm
    ob.parent = arm
    if subdiv:
        s = ob.modifiers.new("Suavizado", "SUBSURF")
        s.levels = 1
        s.render_levels = subdiv


def a_hueso(ob, arm, hueso):
    mw = ob.matrix_world.copy()
    ob.parent = arm
    ob.parent_type = "BONE"
    ob.parent_bone = hueso
    bpy.context.view_layer.update()
    ob.matrix_world = mw


def curvas(nombre, hebras, radio, col, m):
    """Objeto de pelo (Curves) a partir de una lista de hebras (listas de puntos)."""
    cu = bpy.data.hair_curves.new(nombre)
    cu.add_curves([len(h) for h in hebras])
    pos = np.array([p for h in hebras for p in h], dtype=np.float32)
    cu.position_data.foreach_set("vector", pos.ravel())
    rad = cu.attributes.get("radius") or cu.attributes.new("radius", "FLOAT", "POINT")
    r = []
    for h in hebras:
        n = len(h)
        r += [radio * (1.0 - 0.75 * (k / (n - 1))) for k in range(n)]
    rad.data.foreach_set("value", np.array(r, dtype=np.float32))
    cu.materials.append(m)
    ob = bpy.data.objects.new(nombre, cu)
    col.objects.link(ob)
    return ob


def muestrear(co, caras, n, rng):
    """Puntos al azar sobre caras (por area): devuelve (punto, normal)."""
    tri = []
    for f in caras:
        tri.append((f[0], f[1], f[2]))
        if len(f) == 4:
            tri.append((f[0], f[2], f[3]))
    tri = np.array(tri)
    a, b, c = co[tri[:, 0]], co[tri[:, 1]], co[tri[:, 2]]
    cr = np.cross(b - a, c - a)
    ar = np.linalg.norm(cr, axis=1)
    sel = rng.choice(len(tri), size=n, p=ar / ar.sum())
    u, v = rng.random(n), rng.random(n)
    flip = u + v > 1
    u[flip], v[flip] = 1 - u[flip], 1 - v[flip]
    pts = a[sel] + (b[sel] - a[sel]) * u[:, None] + (c[sel] - a[sel]) * v[:, None]
    nr = cr[sel] / ar[sel][:, None]
    return pts, nr


# ----------------------------------------------------------------------------- una persona
def persona(p, X, col, W, base):
    rng = np.random.default_rng(abs(hash(p["tag"])) % 2 ** 32)
    random.seed(p["tag"])
    tag = p["tag"]
    mujer = p["mujer"]

    # ---------- forma del cuerpo: macro + rasgos de rostro al azar (simetricos)
    lst = mh.targets_macro(0.0 if mujer else 1.0, p["edad"] / 70 if p["edad"] <= 25 else 0.5 + (p["edad"] - 25) / 130,
                           p["musculo"], p["peso"], 0.5, 0.6, p["razas"])
    for carpeta in ROSTRO:
        ds = LISTA_ROSTRO[carpeta]
        ds = [f for f in ds if not f.startswith("r-")]
        for f in random.sample(ds, min(len(ds), 4)):
            w = random.uniform(0.1, 0.45)
            lst.append((f"{carpeta}/{f}", w))
            if f.startswith("l-"):
                lst.append((f"{carpeta}/r-{f[2:]}", w))
    co_mh = mh.aplicar(base[0], lst)
    co = mh.mh_a_blender(co_mh)
    caras_todas = base[2]
    cuerpo_f = [c[0] for c in caras_todas if c[2] == "body"]
    idx_c = np.unique(np.concatenate([np.array(f) for f in cuerpo_f]))
    z0 = co[idx_c, 2].min()
    esc = p["altura_m"] / (co[idx_c, 2].max() - z0)
    co[:, 2] -= z0
    co *= esc
    co[:, 0] += X
    co_mh_esc = co_mh  # para proxies (se reescalan igual despues)

    # ---------- esqueleto
    arm = mh.esqueleto(f"{tag}_Esqueleto", co, col)
    arm.data.display_type = "STICK"
    B = arm.data.bones
    J = lambda n, cola=False: Vector(B[n].tail_local if cola else B[n].head_local)

    # ---------- piel: atributo de rubor (labios y mejillas)
    nrm = normales(co, cuerpo_f)
    rub = np.zeros(len(co))
    bm_ = J("oris05")
    dx = (co[:, 0] - bm_.x) / (0.026 * esc / 0.98)
    dz = (co[:, 2] - (bm_.z - 0.002)) / 0.0125
    labio = np.clip(1.15 - (dx ** 2 + dz ** 2), 0, 1) * (co[:, 1] < bm_.y + 0.012)
    rub = np.maximum(rub, labio ** 0.6 * (0.55 if mujer else 0.35))
    for s in (1, -1):
        ojo = J("eye.L" if s > 0 else "eye.R")
        d = np.linalg.norm(co - (ojo + Vector((s * 0.01, -0.01, -0.035)))[:], axis=1)
        rub = np.maximum(rub, np.clip(1 - d / 0.03, 0, 1) * 0.18 * (co[:, 1] < ojo.y))

    # ---------- regiones de ropa por hueso dominante y posicion
    dom = np.full(len(co), "", dtype=object)
    best = np.zeros(len(co))
    for bn, lista in W.items():
        for i, val in lista:
            if val > best[i]:
                best[i], dom[i] = val, bn
    cint_z = J("spine04").z + 0.005          # cintura (correa)
    tob_z = J("foot.L").z + 0.035             # borde del pantalon
    hom_l, codo_l = J("upperarm01.L"), J("lowerarm01.L")
    tronco_b = {"spine01", "spine02", "spine03", "spine04", "spine05", "clavicle.L", "clavicle.R", "breast.L",
                "breast.R", "shoulder01.L", "shoulder01.R", "root", "special01"}
    brazo_b = {"upperarm01.L", "upperarm01.R", "upperarm02.L", "upperarm02.R"}
    pierna_b = {"root", "pelvis.L", "pelvis.R", "upperleg01.L", "upperleg01.R", "upperleg02.L", "upperleg02.R",
                "lowerleg01.L", "lowerleg01.R", "lowerleg02.L", "lowerleg02.R", "spine05", "spine04"}
    cuello_z = J("neck01").z - 0.015
    camisa, pantalon, zapato = set(), set(), set()
    largo_brazo = (codo_l - hom_l).length
    for i in idx_c:
        x, y, z = co[i]
        d = dom[i]
        if z >= cint_z - 0.02 and (d in tronco_b or d in brazo_b or d.startswith("neck")):
            if d in brazo_b or d.startswith("shoulder"):
                s = 1 if x - X > 0 else -1
                h = Vector((X + s * (hom_l.x - X), hom_l.y, hom_l.z))
                c = Vector((X + s * (codo_l.x - X), codo_l.y, codo_l.z))
                t = (Vector((x, y, z)) - h).dot((c - h).normalized()) / largo_brazo
                if t < 0.48:
                    camisa.add(i)
            elif d.startswith("neck"):
                if z < cuello_z and y > J("neck01").y - 0.02:
                    camisa.add(i)
            elif z < cuello_z + 0.01 or y > J("neck01").y + 0.04:
                camisa.add(i)
        if tob_z <= z <= cint_z + 0.02 and d in pierna_b:
            pantalon.add(i)
        if z < tob_z + 0.03 and (d.startswith("foot") or d.startswith("toe") or d.startswith("lowerleg02")):
            zapato.add(i)
    ady = vecinos(cuerpo_f, len(co))

    def prenda(nombre, region, off, m, iters, extra=None, post=None):
        cs = [f for f in cuerpo_f if all(v in region for v in f)]
        idxp = sorted({v for f in cs for v in f})
        borde = {v for v in idxp if any(u not in region for u in ady[v])}
        cp = co.copy()
        o = np.full(len(co), off)
        if extra is not None:
            o = o + extra(co)
        cp[idxp] = co[idxp] + nrm[idxp] * o[idxp][:, None]
        cp = suavizar(cp, idxp, ady, iters, fijos=())
        # devolver por fuera del cuerpo despues de suavizar
        d = ((cp[idxp] - co[idxp]) * nrm[idxp]).sum(axis=1)
        falta = np.clip(o[idxp] * 0.8 - d, 0, None)
        cp[idxp] += nrm[idxp] * falta[:, None]
        if post is not None:
            cp = post(cp, idxp)
        ob = malla_desde(nombre, cp, cs, col)
        ob.data.materials.append(m)
        sol = ob.modifiers.new("Espesor", "SOLIDIFY")
        sol.thickness = 0.0025
        sol.offset = 1.0
        return ob, cp, cs, borde

    # ---------- cuerpo visible (sin las caras tapadas por la ropa)
    tapado = camisa | pantalon | zapato
    erosion = {v for v in tapado if all(u in tapado for u in ady[v])}
    erosion = {v for v in erosion if all(u in erosion for u in ady[v])}
    caras_vis = [f for f in cuerpo_f if not all(v in erosion for v in f)]
    ob = malla_desde(f"{tag}_Cuerpo", co, caras_vis, col)
    uvs = []
    for c in caras_todas:
        if c[2] == "body" and not all(v in erosion for v in c[0]):
            uvs += [base[1][u] for u in c[1]]
    ob.data.uv_layers.new(name="UVMap").data.foreach_set("uv", np.array(uvs, dtype=np.float32).ravel())
    at = ob.data.color_attributes.new("Rubor", "FLOAT_COLOR", "POINT")
    at.data.foreach_set("color", np.repeat(rub[:, None], 4, axis=1).astype(np.float32).ravel())
    piel = mat_piel(f"Piel_{tag}", p["tez"], rng.random() * 10)
    ob.data.materials.append(piel)
    armar(ob, arm, W, subdiv=2)
    mh.limpiar_sueltos(ob)
    cuerpo = ob

    # pestanas (ayudantes de MakeHuman) y ojos
    eco, evt, ecaras, _ = mh.ajustar_proxy("eyes/high-poly/high-poly.mhclo", co_mh_esc)
    ecb = mh.mh_a_blender(eco)
    ecb[:, 2] -= z0
    ecb *= esc
    ecb[:, 0] += X
    uv = [evt[u] for c in ecaras for u in c[1]]
    ob = malla_desde(f"{tag}_Ojos", ecb, [c[0] for c in ecaras], col, uv=uv)
    ob.data.materials.append(mat_ojo(f"Ojo_{tag}", p["iris"]))
    cornea = bpy.data.materials.get("Cornea")
    if cornea is None:
        cornea, _, cb_ = nodos("Cornea")
        cb_.inputs["Transmission Weight"].default_value = 1.0
        cb_.inputs["Roughness"].default_value = 0.0
        cb_.inputs["IOR"].default_value = 1.376
    ob.data.materials.append(cornea)
    for k, c in enumerate(ecaras):          # la capa externa (cornea) usa la zona azul de la textura
        u = np.mean([evt[i] for i in c[1]], axis=0)
        if u[0] > 0.85 and u[1] < 0.15:
            ob.data.polygons[k].material_index = 1
    for s, bn in ((1, "eye.L"), (-1, "eye.R")):
        g = ob.vertex_groups.new(name=bn)
        g.add([i for i, v in enumerate(ecb) if (v[0] - X) * s > 0], 1.0, "REPLACE")
    md = ob.modifiers.new("Esqueleto", "ARMATURE")
    md.object = arm
    ob.parent = arm

    # ---------- ropa
    tela = mat_tela(f"Tela_Camisa_Celeste_{tag}", (0.33, 0.52, 0.78), escala=1800) if p["camisa"] == "celeste" else \
        mat_tela(f"Tela_Polo_Plomo_{tag}", (0.085, 0.09, 0.096), escala=1400, sheen=0.6)
    pecho = [i for i in camisa if not dom[i].startswith("upperarm") and abs(co[i][0] - X) < 0.15
             and co[i][1] < J("spine02").y - 0.03 and cint_z + 0.04 < co[i][2] < J("clavicle.L").z - 0.03]

    def pecho_liso(cp, idxp):
        """Tela tensa sobre el pecho: alisa el detalle del cuerpo y la separa un poco mas."""
        sel = [i for i in pecho if i in set(idxp)]
        n_it = 40 if mujer else 25
        lisa = taubin(co, sel, ady, n_it)            # cuerpo alisado como referencia (el cuerpo tapado se borra)
        nl = taubin(nrm, sel, ady, n_it)
        nl[sel] /= np.linalg.norm(nl[sel], axis=1)[:, None]
        cp[sel] = lisa[sel] + nl[sel] * 0.008
        return cp

    sh, shc, shf, shb = prenda(f"{tag}_Camisa" if p["camisa"] == "celeste" else f"{tag}_Polo", camisa, 0.007, tela, 6,
                               post=pecho_liso)
    armar(sh, arm, W)
    mh.limpiar_sueltos(sh)

    def ensanche_pierna(c):
        # pierna recta: mas holgura bajo la rodilla, holgura extra en la cintura para cubrir la camisa
        rod = J("lowerleg01.L").z
        e = np.clip((rod - c[:, 2]) / (rod - tob_z), 0, 1) * 0.024 + 0.008
        e += np.clip(1 - np.abs(c[:, 2] - cint_z) / 0.05, 0, 1) * 0.004
        ent = Vector((X, J("root").y - 0.02, J("upperleg02.L").z - 0.01))      # entrepierna holgada
        e += np.clip(1 - np.linalg.norm(c - np.array(ent), axis=1) / 0.09, 0, 1) * 0.014
        return e

    def pierna_recta(cp, idxp):
        """Corte recto: cada pierna del jean es un tubo que no baja de un radio minimo."""
        f = 0.93 if mujer else 1.0
        for en, s_ in (("L", 1), ("R", -1)):
            H, K, A = J(f"upperleg02.{en}"), J(f"lowerleg01.{en}"), J(f"foot.{en}")
            for v in idxp:
                q = Vector(cp[v])
                if (q.x - X) * s_ <= 0.01 or q.z > H.z:
                    continue
                if q.z > K.z:
                    t = (H.z - q.z) / (H.z - K.z)
                    a, R = H.lerp(K, t), (0.084 + (0.068 - 0.084) * t) * f
                else:
                    t = (K.z - q.z) / (K.z - A.z)
                    a, R = K.lerp(A, t), (0.068 + (0.063 - 0.068) * t) * f
                r = Vector((q.x - a.x, q.y - a.y, 0))
                if 1e-6 < r.length < R:
                    q = Vector((a.x, a.y, q.z)) + r.normalized() * R
                    cp[v] = q
        return cp

    jean = mat_tela(f"Tela_Jean_{tag}", (0.018, 0.032, 0.075), escala=2200, rough=0.9, sheen=0.2, diagonal=True)
    pj, pjc, pjf, pjb = prenda(f"{tag}_Jean", pantalon, 0.008, jean, 8, extra=ensanche_pierna, post=pierna_recta)
    armar(pj, arm, W)
    mh.limpiar_sueltos(pj)

    def zap_extra(c):
        return np.clip(0.03 - c[:, 2], 0, None) * 0.3

    cuero = bpy.data.materials.get("Cuero_Zapato") or mat_simple("Cuero_Zapato", (0.012, 0.011, 0.010), 0.35, coat=0.3)
    # zapatos de seguridad: envolvente cerrada del pie (sin dedos), unida al hueso del pie
    for en, s_ in (("L", 1), ("R", -1)):
        pie = np.array([co[i] for i in zapato if (co[i][0] - X) * s_ > 0])
        tob = J(f"foot.{en}")
        punta = pie[np.argmin(pie[:, 1])]
        talon = pie[np.argmax(pie[:, 1])]
        eje_u = Vector((punta[0] - talon[0], punta[1] - talon[1], 0)).normalized()
        eje_v = Vector((-eje_u.y, eje_u.x, 0))
        o = Vector((talon[0], talon[1], 0)) - eje_u * 0.012
        rel = pie - np.array(o)
        uu = rel @ np.array(eje_u)
        vv = rel @ np.array(eje_v)
        largo = uu.max() + 0.016
        n_st, n_r = 18, 28
        secc = []
        for k in range(n_st + 1):
            t = k / n_st
            u = largo * (0.5 - 0.5 * math.cos(t * math.pi))
            m = np.abs(uu - u) < 0.014
            if m.sum() < 3:
                m = np.abs(uu - u) < 0.03
            vmin, vmax = (vv[m].min(), vv[m].max()) if m.any() else (-0.03, 0.03)
            top = pie[m, 2].max() if m.any() else 0.05
            top = min(top, tob_z + 0.045)
            secc.append([u, vmin - 0.009, vmax + 0.009, top + 0.010])
        # suavizar el perfil a lo largo del pie y redondear la punta y el talon
        arr = np.array(secc)
        for _ in range(3):
            arr[1:-1, 1:] = (arr[:-2, 1:] + 2 * arr[1:-1, 1:] + arr[2:, 1:]) / 4
        for k in (0, n_st):
            c = (arr[k, 1] + arr[k, 2]) / 2
            arr[k, 1:3] = c + (arr[k, 1:3] - c) * 0.35
        verts, faces = [], []
        for u, v0, v1, top in arr:
            cv, av = (v0 + v1) / 2, (v1 - v0) / 2
            for j in range(n_r):
                a_ = j * math.tau / n_r
                ca, sa = math.cos(a_), math.sin(a_)
                vy = cv + av * math.copysign(abs(ca) ** 0.55, ca)
                zz = top / 2 + top / 2 * math.copysign(abs(sa) ** 0.55, sa)
                zz = max(zz, 0.0)
                verts.append(o + eje_u * u + eje_v * vy + Vector((0, 0, zz)))
        for k in range(n_st):
            for j in range(n_r):
                j2 = (j + 1) % n_r
                faces.append((k * n_r + j, k * n_r + j2, (k + 1) * n_r + j2, (k + 1) * n_r + j))
        faces.append(tuple(range(n_r))[::-1])
        faces.append(tuple(range(n_st * n_r, (n_st + 1) * n_r)))
        zp = malla_desde(f"{tag}_Zapato_Seguridad_{'Izq' if en == 'L' else 'Der'}", verts, faces, col)
        zp.data.materials.append(cuero)
        zp.modifiers.new("Suavizado", "SUBSURF").levels = 2
        a_hueso(zp, arm, f"foot.{en}")
        # suela
        sv = [o + eje_u * u + eje_v * v + Vector((0, 0, 0)) for u, v0, v1, _ in arr for v in (v0 - 0.003, v1 + 0.003)]
        sf = [(2 * k, 2 * k + 1, 2 * k + 3, 2 * k + 2) for k in range(n_st)]
        su = malla_desde(f"{tag}_Suela_{'Izq' if en == 'L' else 'Der'}", sv, sf, col, smooth=False)
        sm = su.modifiers.new("Espesor", "SOLIDIFY")
        sm.thickness = 0.014
        sm.offset = 1.0
        su.data.materials.append(bpy.data.materials.get("Suela") or mat_simple("Suela", (0.02, 0.02, 0.02), 0.8))
        a_hueso(su, arm, f"foot.{en}")

    # correa y hebilla siguiendo el borde superior del jean
    banda = np.array([pjc[i] for i in pantalon if abs(co[i][2] - (cint_z - 0.01)) < 0.012])
    if len(banda):
        c0 = Vector(banda.mean(axis=0))
        ang_b = np.arctan2(banda[:, 1] - c0.y, banda[:, 0] - c0.x)
        rad_b = np.hypot(banda[:, 0] - c0.x, banda[:, 1] - c0.y)
        pts = []
        for a in np.linspace(-math.pi, math.pi, 49)[:-1]:
            dd = np.abs((ang_b - a + math.pi) % math.tau - math.pi)
            r = rad_b[dd < 0.25].max() if (dd < 0.25).any() else rad_b.mean()
            pts.append(Vector((c0.x + math.cos(a) * (r + 0.004), c0.y + math.sin(a) * (r + 0.004), cint_z - 0.018)))
        cu = bpy.data.curves.new(f"{tag}_Correa", "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth = 0.0
        cu.extrude = 0.016
        sp = cu.splines.new("POLY")
        sp.points.add(len(pts) - 1)
        for q, pp in zip(sp.points, pts):
            q.co = (*pp, 1)
        sp.use_cyclic_u = True
        cr = bpy.data.objects.new(f"{tag}_Correa", cu)
        col.objects.link(cr)
        cu.materials.append(cuero)
        sol = cr.modifiers.new("Espesor", "SOLIDIFY")
        sol.thickness = 0.003
        frente = min(pts, key=lambda q: q.y)
        hb = bpy.data.meshes.new(f"{tag}_Hebilla")
        bmh = bmesh.new()
        bmesh.ops.create_cube(bmh, size=1.0)
        bmesh.ops.scale(bmh, vec=(0.05, 0.006, 0.038), verts=bmh.verts)
        bmh.to_mesh(hb)
        bmh.free()
        hbo = bpy.data.objects.new(f"{tag}_Hebilla", hb)
        col.objects.link(hbo)
        hbo.location = frente + Vector((0, -0.004, 0))
        hb.materials.append(bpy.data.materials.get("Metal_Hebilla") or mat_simple("Metal_Hebilla", (0.6, 0.6, 0.6), 0.25, 1.0))
        a_hueso(cr, arm, "spine04")
        a_hueso(hbo, arm, "spine04")

    # cuello de la camisa / polo: banda + solapa doblada a partir del borde del cuello
    borde_c = [shc[i] for i in shb if shc[i][2] > J("clavicle.L").z - 0.06 and abs(shc[i][0] - X) < 0.1]
    if borde_c:
        c0 = Vector(np.mean(borde_c, axis=0))
        borde_c.sort(key=lambda q: math.atan2(q[0] - c0.x, (q[1] - c0.y)))
        n = 40
        ang = np.linspace(-math.pi * 0.93, math.pi * 0.93, n)          # abierto adelante
        ring = []
        for a in ang:
            dirv = Vector((math.sin(a), math.cos(a), 0))
            best_q = max(borde_c, key=lambda q: (Vector(q) - c0).normalized().dot(dirv))
            r = (Vector(best_q) - c0)
            r.z = 0
            ring.append((c0 + dirv * r.length, dirv, best_q[2]))
        alto = 0.030 if p["camisa"] == "plomo" else 0.034
        verts, faces = [], []
        for k, (q, dv, zq) in enumerate(ring):
            b0 = Vector((q.x, q.y, zq)) + dv * 0.004
            b1 = b0 + Vector((0, 0, alto)) - dv * 0.004
            frente = max(0.0, -math.cos(ang[k]))                     # 1 al frente
            punta = 0.03 * frente ** 6 if p["camisa"] == "celeste" else 0.0
            b2 = b1 + dv * 0.012 + Vector((0, 0, 0.002))
            b3 = b0 + dv * (0.016 + punta * 0.4) + Vector((0, 0, -0.012 - punta))
            verts += [b0, b1, b2, b3]
        for k in range(n - 1):
            for j in range(3):
                a0, a1 = k * 4 + j, k * 4 + j + 1
                faces.append((a0, a1, a1 + 4, a0 + 4))
        cuello = malla_desde(f"{tag}_Cuello_{'Camisa' if p['camisa'] == 'celeste' else 'Polo'}", verts, faces, col)
        cuello.data.materials.append(tela)
        cuello.modifiers.new("Espesor", "SOLIDIFY").thickness = 0.002
        cuello.modifiers.new("Suavizado", "SUBSURF").levels = 1
        a_hueso(cuello, arm, "spine01")

    # botones, tapeta y bolsillo
    boton_m = bpy.data.materials.get("Boton") or mat_simple("Boton", (0.85, 0.85, 0.82), 0.3)
    frente_idx = [i for i in range(len(shc)) if i in camisa and abs(co[i][0] - X) < 0.006 and co[i][1] < J("spine02").y - 0.05]
    if frente_idx:
        zs = [J("clavicle.L").z - 0.015 - k * (0.085 if p["camisa"] == "celeste" else 0.035)
              for k in range(6 if p["camisa"] == "celeste" else 3)]
        for z in zs:
            if z < cint_z + 0.03:
                continue
            i = min(frente_idx, key=lambda j: abs(shc[j][2] - z))
            pos = Vector(shc[i]) + Vector(nrm[i]) * 0.0062
            bmb = bmesh.new()
            bmesh.ops.create_cone(bmb, cap_ends=True, segments=16, radius1=0.0058, radius2=0.0058, depth=0.0025)
            meb = bpy.data.meshes.new(f"{tag}_Boton")
            bmb.to_mesh(meb)
            bmb.free()
            bo = bpy.data.objects.new(f"{tag}_Boton", meb)
            col.objects.link(bo)
            bo.location = pos
            bo.rotation_euler = Vector((0, 0, 1)).rotation_difference(Vector(nrm[i])).to_euler()
            meb.materials.append(boton_m)
            a_hueso(bo, arm, "spine01" if z > J("spine01").z else "spine02" if z > J("spine02").z else "spine03")
        bvh_c = BVHTree.FromPolygons([tuple(q) for q in shc], shf)

        def parche(nombre, x0, x1, z0, z1, off, punta=0.0, nx=6, nz=10):
            """Rejilla proyectada sobre la camisa (tapeta, bolsillo)."""
            vb, fb = [], []
            for kz in range(nz + 1):
                for kx in range(nx + 1):
                    x = X + x0 + (x1 - x0) * kx / nx
                    z = z0 - (z0 - z1) * kz / nz - (punta * (1 - abs(kx / nx - 0.5) * 2) if kz == nz else 0)
                    hit = bvh_c.ray_cast(Vector((x, -0.5, z)), Vector((0, 1, 0)))
                    vb.append(hit[0] + hit[1] * off if hit[0] is not None else Vector((x, -0.12, z)))
            for kz in range(nz):
                for kx in range(nx):
                    a0 = kz * (nx + 1) + kx
                    fb.append((a0, a0 + 1, a0 + nx + 2, a0 + nx + 1))
            ob_p = malla_desde(nombre, vb, fb, col)
            ob_p.data.materials.append(tela)
            ob_p.modifiers.new("Espesor", "SOLIDIFY").thickness = 0.0015
            a_hueso(ob_p, arm, "spine01")
            return ob_p

        ztap = J("clavicle.L").z - 0.005
        parche(f"{tag}_Tapeta_{'Camisa' if p['camisa'] == 'celeste' else 'Polo'}", -0.015, 0.015, ztap,
               cint_z if p["camisa"] == "celeste" else ztap - 0.13, 0.0022, nx=3, nz=24)
        if p["camisa"] == "celeste":
            zb = J("clavicle.L").z - 0.05
            parche(f"{tag}_Bolsillo_Camisa", 0.05, 0.125, zb, zb - 0.095, 0.0035, punta=0.012, nx=7, nz=8)

    # ---------- cabello, cejas
    cabeza_f = [f for f in cuerpo_f if all(dom[v] in ("head", "jaw", "neck03", "neck02") or dom[v].startswith(("oculi", "temporalis", "levator", "oris", "orbicularis", "risorius", "special"))
                                           for v in f)]
    bvh = BVHTree.FromPolygons([tuple(q) for q in co], cabeza_f)
    cab_top = co[idx_c, 2].max()
    hc = [c[0] for c in caras_todas if c[2] == "helper-hair"]
    gorro = p["gorro"]
    ojo_l = J("eye.L")
    cr_idx = [i for i in idx_c if dom[i] == "head" and co[i][2] > ojo_l.z + 0.01]
    cr_min, cr_max = co[cr_idx].min(axis=0), co[cr_idx].max(axis=0)
    cc = Vector(((cr_min + cr_max) / 2))
    rx, ry = (cr_max[0] - cr_min[0]) / 2, (cr_max[1] - cr_min[1]) / 2
    oreja_z = ojo_l.z - 0.012

    def es_cuero(q):
        """Zona con cabello: frente desde la linea del pelo, patillas, nuca; sin orejas ni cara."""
        frente_y = cc.y - ry * 0.35
        if q.z < J("neck03").z - 0.005:
            return False
        for sx in (1, -1):
            oc = Vector((cc.x + sx * (rx + 0.004), cc.y + 0.006, oreja_z))
            if ((q - oc) * Vector((1.0, 0.75, 0.6))).length < 0.026:
                return False
        if q.y < frente_y:                                # zona frontal
            lado = abs(q.x - cc.x) / rx
            return q.z > ojo_l.z + 0.058 - 0.02 * lado ** 2
        if q.y < cc.y + ry * 0.2:                         # costados (patillas hasta la oreja)
            return q.z > oreja_z - 0.015
        return True
    pelo_m = mat_pelo(f"Pelo_{tag}", *p["pelo"])
    craneo = J("head") + Vector((0, 0.015, 0.09 * esc / 1.0))
    hebras = []

    def crecer(r0, n0, largo, segs, peine, gravedad, rizo, capa, levanta=0.25, pegado=False):
        pts = [Vector(r0) - Vector(n0) * 0.0015]
        q = Vector(r0)
        d = (Vector(n0) * levanta + peine(q)).normalized()
        paso = largo / segs
        fase = rng.random() * 6.28
        for k in range(segs):
            g = Vector((0, 0, -1)) * gravedad * (k + 1) / segs
            cr = Vector((math.sin(fase + k * 1.9), math.cos(fase + k * 2.3), math.sin(fase * 0.7 + k * 1.7))) * rizo
            d = (d + g + cr + peine(q) * 0.4).normalized()
            q = q + d * paso
            loc, nr, _, dist = bvh.find_nearest(q)
            if loc is not None:
                h = (q - loc).dot(nr)
                if h < capa or pegado:
                    q = loc + nr * (capa + (h - capa) * 0.15 if pegado and h > capa else capa)
                    d = (d - nr * d.dot(nr)).normalized()
            pts.append(q.copy())
        return pts

    if gorro == "casco" or p["peinado"] == "corto":
        estilo = p["peinado"]
        if estilo == "corto":
            n, largo, segs = 45000, 0.035, 6
        elif estilo == "afro":
            n, largo, segs = 60000, 0.014, 7
        elif estilo == "cola":
            n, largo, segs = 40000, 0.20, 18
        else:                          # moño afro recogido
            n, largo, segs = 60000, 0.016, 7
        if gorro == "cofia":
            n = n // 3
        hco = co.copy()
        raices, normales_r = muestrear(hco, hc, n, rng)
        nuca = J("neck03") + Vector((0, 0.06, -0.01))
        coleta = J("head") + Vector((0, 0.115 * esc, 0.07 * esc))
        if estilo == "moño_afro":                      # moño bajo en la nuca, visible bajo el casco
            coleta = Vector((cc.x, cc.y + ry + 0.01, oreja_z - 0.005))
        for r0, n0 in zip(raices, normales_r):
            loc, nr, _, _ = bvh.find_nearest(Vector(r0))
            if loc is None:
                continue
            if Vector(n0).dot(nr) < 0:
                n0 = -n0
            r0 = loc + nr * 0.0005
            n0 = nr
            if not es_cuero(r0):
                continue
            if estilo == "corto":
                def peine(q):
                    v = q - craneo
                    v.z *= 0.3
                    if q.y < craneo.y - 0.04:      # flequillo hacia un lado y adelante
                        v = Vector((0.8, -0.6, -0.3))
                    return v.normalized() * 0.8
                pts = crecer(r0, n0, largo * rng.uniform(0.6, 1.1), segs, peine, 0.35, 0.05, 0.0015 + rng.random() * 0.0035, 0.15, True)
            elif estilo in ("afro", "moño_afro"):
                def peine(q):
                    return Vector((0, 0, 0))
                pts = crecer(r0, n0, largo * rng.uniform(0.7, 1.3), segs, peine, 0.05, 0.9, 0.002 + rng.random() * 0.006, 0.8)
            else:  # cola de caballo: peinado hacia la coleta y luego cae
                def peine(q):
                    return (coleta - q).normalized() * 1.2
                pts = [Vector(r0) - Vector(n0) * 0.0015]
                q = Vector(r0)
                for k in range(10):
                    q = q + (coleta - q) * 0.22
                    loc, nr, _, _ = bvh.find_nearest(q)
                    if loc is not None and (q - loc).dot(nr) < 0.003:
                        q = loc + nr * (0.003 + rng.random() * 0.002)
                    pts.append(q.copy())
                jit = Vector((rng.normal(0, 0.01), rng.normal(0, 0.01), 0))
                cola_l = rng.uniform(0.18, 0.30)
                for k in range(1, 9):
                    t = k / 8
                    pts.append(coleta + jit * (1 + t) + Vector((0, 0.03 * math.sin(t * 2.2), -cola_l * t)))
            hebras.append([tuple(v) for v in pts])
        if estilo == "cola" and gorro == "casco":
            ligas = bpy.data.meshes.new(f"{tag}_Liga_Cabello")
            bml = bmesh.new()
            bmesh.ops.create_cone(bml, cap_ends=False, segments=16, radius1=0.013, radius2=0.013, depth=0.012)
            bml.to_mesh(ligas)
            bml.free()
            lg = bpy.data.objects.new(f"{tag}_Liga_Cabello", ligas)
            col.objects.link(lg)
            lg.location = coleta + Vector((0, 0.005, -0.01))
            ligas.materials.append(bpy.data.materials.get("Liga") or mat_simple("Liga", (0.02, 0.02, 0.02), 0.5))
            a_hueso(lg, arm, "head")
        if estilo == "moño_afro" and gorro == "casco":
            mo = bpy.data.meshes.new(f"{tag}_Moño")
            bmm = bmesh.new()
            bmesh.ops.create_uvsphere(bmm, u_segments=16, v_segments=10, radius=0.045)
            bmm.to_mesh(mo)
            bmm.free()
            mob = bpy.data.objects.new(f"{tag}_Moño_Base", mo)
            col.objects.link(mob)
            mob.location = coleta + Vector((0, 0.035, 0.0))
            mo.materials.append(bpy.data.materials.get("Pestanas"))
            a_hueso(mob, arm, "head")
            r2, n2 = [], []
            for k in range(9000):
                v = Vector(rng.normal(size=3)).normalized()
                r2.append(mob.location + v * 0.045)
                n2.append(v)
            for r0, n0 in zip(r2, n2):
                pts = [Vector(r0)]
                q = Vector(r0)
                d = Vector(n0)
                for k in range(6):
                    d = (d + Vector(rng.normal(size=3)) * 0.8).normalized()
                    q = q + d * 0.004
                    pts.append(q.copy())
                hebras.append([tuple(v) for v in pts])
    # cejas
    cejas = []
    for s, en in ((1, "L"), (-1, "R")):
        ojo = J(f"eye.{en}")
        for k in range(450):
            t = rng.random()
            x = ojo.x + s * (-0.018 + t * 0.044)
            z = ojo.z + 0.019 + 0.008 * math.sin(t * math.pi) - 0.006 * t + rng.normal(0, 0.0022)
            o = Vector((x, ojo.y - 0.06, z))
            loc, nr, _, _ = bvh.ray_cast(o, Vector((0, 1, 0)))
            if loc is None:
                continue
            tang = Vector((s * (0.4 + t), 0, 0.5 - t * 0.8)).normalized()
            tang = (tang - nr * tang.dot(nr)).normalized()
            pts = [loc - nr * 0.0005]
            q = loc.copy()
            for j in range(4):
                q = q + tang * 0.0022 + nr * 0.0006 * (1 if j < 2 else -0.5)
                pts.append(q.copy())
            cejas.append([tuple(v) for v in pts])
    ceja = curvas(f"{tag}_Cejas", cejas, 0.00009, col, pelo_m)
    # pestañas: pequeñas hebras desde las tarjetas de pestañas de MakeHuman
    pest = []
    for lado, en in (("l", "L"), ("r", "R")):
        oc = J(f"eye.{en}")
        for fila, n_p, lp in (("1", 110, 0.0075), ("2", 50, 0.0045)):
            fc = [c[0] for c in caras_todas if c[2] == f"helper-{lado}-eyelashes-{fila}"]
            if not fc:
                continue
            rr, _ = muestrear(co, fc, n_p, rng)
            arriba = 1 if rr[:, 2].mean() > oc.z else -1
            for r0 in rr:
                q = Vector(r0)
                d = (q - oc)
                d.z = 0
                d = (d.normalized() * 0.4 + Vector((0, -1, 0)) * 0.6).normalized()
                pts = [q, q + d * lp * 0.5 + Vector((0, 0, arriba * lp * 0.25)), q + d * lp + Vector((0, 0, arriba * lp * 0.6))]
                pest.append([tuple(v) for v in pts])
    if pest:
        pe = curvas(f"{tag}_Pestanas", pest, 0.00005, col, pelo_m)
        a_hueso(pe, arm, "head")
    a_hueso(ceja, arm, "head")
    if hebras:
        cab = curvas(f"{tag}_Cabello", hebras, 0.00011 if p["peinado"] not in ("afro", "moño_afro") else 0.00013, col, pelo_m)
        a_hueso(cab, arm, "head")
    # barba incipiente para algunos hombres
    if not mujer and p["edad"] > 35:
        barba = []
        bf = [f for f in cabeza_f if all(co[v][2] < J("oris05").z + 0.03 and co[v][1] < J("jaw").y - 0.03 and co[v][2] > J("jaw", True).z - 0.03 for v in f)]
        if bf:
            rr, nn = muestrear(co, bf, 5000, rng)
            for r0, n0 in zip(rr, nn):
                q = Vector(r0)
                barba.append([tuple(q - Vector(n0) * 0.0003), tuple(q + Vector(n0) * 0.0016 + Vector((0, 0, -0.0006)))])
            bo = curvas(f"{tag}_Barba_Incipiente", barba, 0.00006, col, pelo_m)
            a_hueso(bo, arm, "head")

    # ---------- casco o cofia
    if gorro == "casco":
        casco_m = bpy.data.materials.get("Casco_Blanco") or mat_simple("Casco_Blanco", (0.85, 0.85, 0.82), 0.25, coat=0.6)
        bmc = bmesh.new()
        seg_u, seg_v = 48, 18
        z_ala = ojo_l.z + 0.052
        cent = Vector((cc.x, cc.y + 0.004, z_ala))
        filas = []
        for j in range(seg_v + 1):
            t = j / seg_v                          # 0 = borde, 1 = cumbre
            fila = []
            for i in range(seg_u):
                a = i * math.tau / seg_u
                ca, sa = math.cos(a), math.sin(a)
                tt = max(0.0, (t - 0.12) / 0.88)        # 0..0.12 = ala, resto = copa elipsoidal
                rr = math.cos(tt * math.pi / 2)
                ex = (rx + 0.014) * rr
                ey = (ry + 0.016) * rr
                zz = (cab_top + 0.024 - z_ala) * math.sin(tt * math.pi / 2)
                ala = max(0.0, 1 - t / 0.12)
                vis = max(0.0, -sa) ** 2.5 * ala
                pnt = Vector((cent.x + ca * (ex + ala * 0.016), cent.y + sa * (ey + ala * 0.016 + vis * 0.040),
                              cent.z + zz + ala * 0.004 - vis * 0.010))
                fila.append(bmc.verts.new(pnt))
            filas.append(fila)
        for j in range(seg_v):
            for i in range(seg_u):
                i2 = (i + 1) % seg_u
                bmc.faces.new((filas[j][i], filas[j][i2], filas[j + 1][i2], filas[j + 1][i]))
        tope = bmc.verts.new(Vector((cent.x, cent.y, cab_top + 0.022 + 0.001)))
        for i in range(seg_u):
            bmc.faces.new((filas[-1][i], filas[-1][(i + 1) % seg_u], tope))
        bmesh.ops.recalc_face_normals(bmc, faces=bmc.faces)
        mec = bpy.data.meshes.new(f"{tag}_Casco_Copa")
        bmc.to_mesh(mec)
        bmc.free()
        for pl in mec.polygons:
            pl.use_smooth = True
        casco = bpy.data.objects.new(f"{tag}_Casco_Copa", mec)
        col.objects.link(casco)
        casco.modifiers.new("Espesor", "SOLIDIFY").thickness = 0.003
        casco.modifiers.new("Suavizado", "SUBSURF").levels = 2
        mec.materials.append(casco_m)
        a_hueso(casco, arm, "head")
        # nervios superiores
        for dxn in (-0.018, 0.0, 0.018):
            pts = []
            for k in range(25):
                t = k / 24
                yv = cc.y - (ry + 0.03) + t * 2 * (ry + 0.03)
                u = (yv - cc.y) / (ry + 0.026)
                zz = z_ala + (cab_top + 0.022 - z_ala) * max(0.0, 1 - u * u) ** 0.5 + 0.002
                pts.append((cc.x + dxn, yv, zz))
            cu = bpy.data.curves.new(f"{tag}_Casco_Nervio", "CURVE")
            cu.dimensions = "3D"
            cu.bevel_depth = 0.004 if dxn == 0 else 0.0025
            sp = cu.splines.new("POLY")
            sp.points.add(len(pts) - 1)
            for q, pp in zip(sp.points, pts):
                q.co = (*pp, 1)
            nv = bpy.data.objects.new(f"{tag}_Casco_Nervio", cu)
            col.objects.link(nv)
            cu.materials.append(casco_m)
            a_hueso(nv, arm, "head")
        # suspension (cinta interior y banda de sudor)
        susp_m = bpy.data.materials.get("Suspension_Casco") or mat_simple("Suspension_Casco", (0.03, 0.03, 0.03), 0.6)
        anillo = [(cc.x + (rx + 0.004) * math.cos(a), cc.y + 0.004 + (ry + 0.006) * math.sin(a), z_ala + 0.012)
                  for a in np.linspace(0, math.tau, 40)]
        cu = bpy.data.curves.new(f"{tag}_Casco_Banda_Sudor", "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth = 0.0
        cu.extrude = 0.012
        sp = cu.splines.new("POLY")
        sp.points.add(len(anillo) - 1)
        for q, pp in zip(sp.points, anillo):
            q.co = (*pp, 1)
        sp.use_cyclic_u = True
        bs = bpy.data.objects.new(f"{tag}_Casco_Banda_Sudor", cu)
        col.objects.link(bs)
        cu.materials.append(susp_m)
        a_hueso(bs, arm, "head")
    else:
        cofia_m = bpy.data.materials.get("Cofia") or mat_tela("Cofia", (0.80, 0.82, 0.86), escala=3000, rough=0.95, sheen=0.8)
        bmc = bmesh.new()
        seg_u, seg_v = 64, 16
        filas = []
        z_b = J("eye.L").z + 0.040
        z_n = J("neck03").z + 0.01
        for j in range(seg_v + 1):
            t = j / seg_v
            fila = []
            for i in range(seg_u):
                a = i * math.tau / seg_u
                ca, sa = math.cos(a), math.sin(a)
                zb = z_b + (z_n - z_b) * max(0.0, sa) ** 1.5 + 0.02 * ca * ca * (sa > -0.3)
                rr = math.cos(t * math.pi / 2) ** 0.8
                pliegue = 0.004 * math.sin(a * 22 + j) * (1 - t) ** 2 + 0.006 * math.sin(a * 5 + t * 4)
                ex = (rx + 0.022 + 0.008 * math.sin(t * math.pi)) * rr + pliegue
                ey = (ry + 0.026 + 0.012 * math.sin(t * math.pi)) * rr + pliegue
                zz = zb + (cab_top + 0.020 - zb) * math.sin(t * math.pi / 2) ** 0.8
                if t == 0:                         # elastico pegado a la cabeza
                    ex, ey = rx + 0.006, ry + 0.008
                fila.append(bmc.verts.new(Vector((cc.x + ca * ex, cc.y + 0.006 + sa * ey, zz))))
            filas.append(fila)
        for j in range(seg_v):
            for i in range(seg_u):
                i2 = (i + 1) % seg_u
                bmc.faces.new((filas[j][i], filas[j][i2], filas[j + 1][i2], filas[j + 1][i]))
        tope = bmc.verts.new(Vector((cc.x, cc.y + 0.006, cab_top + 0.021)))
        for i in range(seg_u):
            bmc.faces.new((filas[-1][i], filas[-1][(i + 1) % seg_u], tope))
        bmesh.ops.recalc_face_normals(bmc, faces=bmc.faces)
        mec = bpy.data.meshes.new(f"{tag}_Cofia")
        bmc.to_mesh(mec)
        bmc.free()
        for pl in mec.polygons:
            pl.use_smooth = True
        cof = bpy.data.objects.new(f"{tag}_Cofia", mec)
        col.objects.link(cof)
        tx = bpy.data.textures.new(f"Arrugas_{tag}", "CLOUDS")
        tx.noise_scale = 0.03
        dp = cof.modifiers.new("Arrugas", "DISPLACE")
        dp.texture = tx
        dp.strength = 0.006
        cof.modifiers.new("Espesor", "SOLIDIFY").thickness = 0.0012
        cof.modifiers.new("Suavizado", "SUBSURF").levels = 2
        mec.materials.append(cofia_m)
        a_hueso(cof, arm, "head")
        # elastico
        el = [Vector(v.co) for v in mec.vertices[:seg_u]]
        cu = bpy.data.curves.new(f"{tag}_Cofia_Elastico", "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth = 0.004
        sp = cu.splines.new("POLY")
        sp.points.add(len(el) - 1)
        for q, pp in zip(sp.points, el):
            q.co = (*pp, 1)
        sp.use_cyclic_u = True
        elo = bpy.data.objects.new(f"{tag}_Cofia_Elastico", cu)
        col.objects.link(elo)
        cu.materials.append(cofia_m)
        a_hueso(elo, arm, "head")

    # ---------- pose natural (brazos abajo); el esqueleto queda listo para posar
    pb = arm.pose.bones
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    for s, en in ((1, "L"), (-1, "R")):
        b = pb[f"upperarm01.{en}"]
        b.rotation_mode = "XYZ"
        # bajar el brazo: rotacion alrededor del eje Y global llevada al espacio del hueso
        eje = arm.matrix_world.to_3x3().inverted() @ Vector((0, 1, 0))
        m_ = (b.bone.matrix_local.to_3x3().inverted() @ Matrix.Rotation(math.radians(s * 33), 3, eje)
              @ b.bone.matrix_local.to_3x3())
        b.rotation_euler = m_.to_euler()
        lb = pb[f"lowerarm01.{en}"]
        lb.rotation_mode = "XYZ"
        eje2 = Vector((1, 0, 0))
        m2 = (lb.bone.matrix_local.to_3x3().inverted() @ Matrix.Rotation(math.radians(28), 3, eje2)
              @ lb.bone.matrix_local.to_3x3())
        lb.rotation_euler = m2.to_euler()
        for f in range(1, 6):
            for k in (1, 2, 3):
                fb = pb.get(f"finger{f}-{k}.{en}")
                if fb:
                    fb.rotation_mode = "XYZ"
                    junta = {2: 6, 3: 0, 4: -6, 5: -12}.get(f, 0) if k == 1 else 0
                    fb.rotation_euler = (math.radians(DEDO_X * (0.6 if k == 1 else 1.0)), 0, math.radians(DEDO_Z * junta))
    bpy.ops.object.mode_set(mode="OBJECT")
    return arm


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    raiz = bpy.data.collections.new("Personas")
    sc.collection.children.link(raiz)
    base = mh.leer_obj(mh.ruta("3dobjs", "base.obj"))
    W = mh.pesos()
    for k, p in enumerate(GENTE[:int(os.environ.get("LIMITE", len(GENTE)))]):
        desc = {"celeste": "Camisa_Celeste", "plomo": "Polo_Plomo"}[p["camisa"]] + "_" + p["gorro"].capitalize()
        col = bpy.data.collections.new(f"{k + 1:02d}_{p['tag']}_{desc}")
        raiz.children.link(col)
        persona(p, k * 0.85, col, W, base)
        print("listo", p["tag"], flush=True)
    for m in bpy.data.meshes:
        if m.users == 0:
            bpy.data.meshes.remove(m)
    out = os.path.join(AQUI, "personas_modelo.blend")
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    with open(os.path.join(AQUI, "makehuman_cc0", "USADOS.txt") if os.path.isdir(os.path.join(AQUI, "makehuman_cc0")) else os.devnull, "w") as fh:
        fh.write("\n".join(sorted(mh.USADOS)))
    print("Guardado", out, len(bpy.data.objects), "objetos", flush=True)


if __name__ == "__main__":
    main()
