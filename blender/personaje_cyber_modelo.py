"""
Personaje "cyber" articulado: joven de cabello castano ondulado con gabardina larga de cuero negro,
polera negra, pantalon cargo negro, guantes de cuero, botas militares altas con pasadores, rodilleras,
mochila de energia en la espalda, modulos en las caderas, munequeras con pantalla y cables / tiras
que brillan en cian (lineas en mangas, cables en la espalda y laterales, botas).

El cuerpo es la malla humana de MakeHuman (CC0) con su esqueleto completo de 163 huesos
(columna, cuello, cabeza, mandibula, ojos, brazos, dedos, piernas, dedos de los pies).
Toda la ropa y el equipo estan pesados al esqueleto (copiando los pesos del cuerpo mas cercano)
o emparentados a un hueso, asi que se deforman / siguen al posar en Pose Mode.
Queda en pose A (la de reposo), como la hoja de personaje de referencia.

Metros, piso z=0, mira hacia -Y.  Uso: python3 blender/personaje_cyber_modelo.py [--render]
"""
import math
import os
import sys

import numpy as np
import bpy
import bmesh
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import mh_humano as mh  # noqa: E402
import personas_modelo as pm  # noqa: E402

T = "Cyber"
P = dict(tag=T, mujer=False, camisa="plomo", gorro="ninguno", edad=26, altura_m=1.80, peso=0.50, musculo=0.60,
         razas=dict(asian=0.0, caucasian=0.95, african=0.05), tez=(0.44, 0.28, 0.20), pelo=(0.97, 0.06),
         peinado="ondulado", iris=(0.06, 0.9))

BRAZO = ("upperarm", "lowerarm", "wrist", "finger", "metacarpal")
MANO = ("wrist", "finger", "metacarpal")


# ----------------------------------------------------------------------------- materiales
def mat_cuero(nombre, rgb, gastado=(0.07, 0.06, 0.05), rough=(0.38, 0.62), escala=6.0, bump=0.25):
    """Cuero con desgaste: zonas mas claras y mas asperas, grano fino en relieve."""
    m, nt, b = pm.nodos(nombre)
    N, L = nt.nodes, nt.links
    tc = N.new("ShaderNodeTexCoord")
    ns = N.new("ShaderNodeTexNoise")
    ns.inputs["Scale"].default_value = escala
    ns.inputs["Detail"].default_value = 8.0
    ns.inputs["Roughness"].default_value = 0.6
    L.new(tc.outputs["Object"], ns.inputs["Vector"])
    rp = N.new("ShaderNodeValToRGB")
    rp.color_ramp.elements[0].position = 0.45
    rp.color_ramp.elements[1].position = 0.75
    L.new(ns.outputs["Fac"], rp.inputs["Fac"])
    mx = N.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    mx.inputs[6].default_value = (*rgb, 1)
    mx.inputs[7].default_value = (*gastado, 1)
    L.new(rp.outputs["Color"], mx.inputs["Factor"])
    L.new(mx.outputs[2], b.inputs["Base Color"])
    mr = N.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = rough
    L.new(rp.outputs["Color"], mr.inputs["Value"])
    L.new(mr.outputs["Result"], b.inputs["Roughness"])
    gr = N.new("ShaderNodeTexVoronoi")
    gr.inputs["Scale"].default_value = 900.0
    L.new(tc.outputs["Object"], gr.inputs["Vector"])
    bp = N.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = bump
    bp.inputs["Distance"].default_value = 0.0004
    L.new(gr.outputs["Distance"], bp.inputs["Height"])
    L.new(bp.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Specular IOR Level"].default_value = 0.5
    m.diffuse_color = (*rgb, 1)
    return m


def mat_brillo(nombre, rgb=(0.10, 0.80, 1.0), fuerza=7.0):
    m, nt, b = pm.nodos(nombre)
    b.inputs["Base Color"].default_value = (rgb[0] * 0.4, rgb[1] * 0.6, rgb[2] * 0.6, 1)
    b.inputs["Emission Color"].default_value = (*rgb, 1)
    b.inputs["Emission Strength"].default_value = fuerza
    b.inputs["Roughness"].default_value = 0.2
    m.diffuse_color = (*rgb, 1)
    return m


# ----------------------------------------------------------------------------- geometria
def malla(nombre, verts, caras, col, m, smooth=True):
    ob = pm.malla_desde(nombre, [tuple(v) for v in verts], caras, col, smooth=smooth)
    ob.data.materials.append(m)
    return ob


def rejilla(filas, cerrada):
    """Caras de una rejilla de filas con el mismo numero de puntos (cerrada = anillo)."""
    nf, nc = len(filas), len(filas[0])
    verts = [p for f in filas for p in f]
    caras = []
    for i in range(nf - 1):
        for j in range(nc if cerrada else nc - 1):
            j2 = (j + 1) % nc
            caras.append((i * nc + j, i * nc + j2, (i + 1) * nc + j2, (i + 1) * nc + j))
    return verts, caras


def suave(pts, sub=6):
    """Catmull-Rom por los puntos de control."""
    pts = [Vector(p) for p in pts]
    q = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]
    out = []
    for i in range(1, len(q) - 2):
        p0, p1, p2, p3 = q[i - 1], q[i], q[i + 1], q[i + 2]
        for k in range(sub):
            t = k / sub
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(pts[-1])
    return out


def marcos(pts, arriba=Vector((0, 0, 1))):
    """Tangentes y normales con transporte paralelo a lo largo de una polilinea."""
    tg = []
    for i in range(len(pts)):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        tg.append((b - a).normalized())
    n = arriba - tg[0] * arriba.dot(tg[0])
    if n.length < 1e-4:
        n = Vector((1, 0, 0)) - tg[0] * tg[0].x
    n.normalize()
    ns = [n]
    for i in range(1, len(pts)):
        r = tg[i - 1].rotation_difference(tg[i])
        n = (r @ n)
        n = (n - tg[i] * n.dot(tg[i])).normalized()
        ns.append(n)
    return tg, ns


def tubo(nombre, pts, radio, col, m, seg=10, ancho=None, normal=None, tapas=True):
    """Tubo a lo largo de pts. Con ancho (y normal(p) = direccion hacia afuera) queda una correa plana."""
    pts = [Vector(p) for p in pts]
    tg, ns = marcos(pts)
    filas = []
    for p, t, n in zip(pts, tg, ns):
        if normal is not None:
            n = normal(p)
            n = (n - t * n.dot(t)).normalized()
        b = t.cross(n)
        fila = []
        for j in range(seg):
            a = j * math.tau / seg
            ra, rb = radio, (ancho if ancho else radio)
            fila.append(p + n * math.cos(a) * ra + b * math.sin(a) * rb)
        filas.append(fila)
    verts, caras = rejilla(filas, True)
    if tapas:
        caras.append(tuple(range(seg))[::-1])
        k = (len(filas) - 1) * seg
        caras.append(tuple(range(k, k + seg)))
    return malla(nombre, verts, caras, col, m)


def caja(nombre, tam, col, m, bisel=0.004, seg=2):
    me = bpy.data.meshes.new(nombre)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=tam, verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(nombre, me)
    col.objects.link(ob)
    me.materials.append(m)
    if bisel:
        bv = ob.modifiers.new("Bisel", "BEVEL")
        bv.width = bisel
        bv.segments = seg
        bv.limit_method = "NONE"
    return ob


def cilindro(nombre, r, h, col, m, seg=16):
    me = bpy.data.meshes.new(nombre)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=h)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(nombre, me)
    col.objects.link(ob)
    me.materials.append(m)
    for p in me.polygons:
        p.use_smooth = len(p.vertices) == 4
    return ob


def base_local(origen, z_loc, y_loc):
    """Matriz con eje Z local = z_loc, eje Y local ~ y_loc, en origen."""
    z = Vector(z_loc).normalized()
    y = Vector(y_loc)
    y = (y - z * y.dot(z)).normalized()
    x = y.cross(z)
    M = Matrix((x, y, z)).transposed().to_4x4()
    M.translation = origen
    return M


def colocar(ob, M, local=(0, 0, 0)):
    ob.matrix_world = M @ Matrix.Translation(local)
    return ob


# ----------------------------------------------------------------------------- pesos
class Fuente:
    """Vertices (en reposo) con sus pesos de hueso, para copiar pesos al objeto mas cercano."""

    def __init__(self, co, W):
        self.co, self.W = co, W
        self.kd = KDTree(len(co))
        for i, p in enumerate(co):
            self.kd.insert(p, i)
        self.kd.balance()

    @staticmethod
    def de_objetos(obs, huesos):
        hi = {h: k for k, h in enumerate(huesos)}
        cos, Ws = [], []
        for ob in obs:
            me = ob.data
            co = np.array([ob.matrix_world @ v.co for v in me.vertices])
            Wm = np.zeros((len(co), len(huesos)), dtype=np.float32)
            nombres = [g.name for g in ob.vertex_groups]
            for v in me.vertices:
                for g in v.groups:
                    k = hi.get(nombres[g.group])
                    if k is not None:
                        Wm[v.index, k] = g.weight
            cos.append(co)
            Ws.append(Wm)
        return Fuente(np.concatenate(cos), np.concatenate(Ws))


def pesar(ob, fuente, arm, huesos, k=4, mezcla=None):
    """Copia pesos de la fuente (promedio de los k vertices mas cercanos) y arma el objeto al esqueleto."""
    co = np.array([ob.matrix_world @ v.co for v in ob.data.vertices])
    filas = np.zeros((len(co), len(huesos)), dtype=np.float32)
    for i, p in enumerate(co):
        r = fuente.kd.find_n(Vector(p), k)
        w = np.array([1.0 / (d + 1e-3) for _, _, d in r])
        filas[i] = (fuente.W[[j for _, j, _ in r]] * w[:, None]).sum(axis=0) / w.sum()
        if mezcla is not None:
            filas[i] = mezcla(p, filas[i])
    # 4 huesos por vertice como maximo, normalizado
    top = np.argsort(-filas, axis=1)[:, :4]
    final = np.zeros_like(filas)
    for i in range(len(co)):
        final[i, top[i]] = filas[i, top[i]]
    final /= np.maximum(final.sum(axis=1, keepdims=True), 1e-8)
    grupos = {}
    for i in range(len(co)):
        for kb in top[i]:
            val = float(final[i, kb])
            if val < 1e-3:
                continue
            g = grupos.get(kb) or ob.vertex_groups.new(name=huesos[kb])
            grupos[kb] = g
            g.add([i], val, "REPLACE")
    md = ob.modifiers.new("Esqueleto", "ARMATURE")
    md.object = arm
    ob.modifiers.move(len(ob.modifiers) - 1, 0)
    mw = ob.matrix_world.copy()
    ob.parent = arm
    ob.matrix_world = mw
    return Fuente(co, final)


# ----------------------------------------------------------------------------- personaje
def construir(col):
    base = mh.leer_obj(mh.ruta("3dobjs", "base.obj"))
    W = mh.pesos()
    # en el repositorio solo estan los targets de rostro usados: sortear entre esos
    for carpeta, ds in pm.LISTA_ROSTRO.items():
        pm.LISTA_ROSTRO[carpeta] = [f for f in ds if mh.existe_target(f"{carpeta}/{f}") and
                                    (not f.startswith("l-") or mh.existe_target(f"{carpeta}/r-{f[2:]}"))]
    arm = pm.persona(P, 0.0, col, W, base)
    arm.name = f"{T}_Esqueleto"
    O = bpy.data.objects
    for ob in list(col.objects):
        if any(k in ob.name for k in ("_Cuello_Polo", "_Tapeta_Polo", "_Boton")):
            O.remove(ob)
    # pose de reposo (pose A, como la hoja de referencia)
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    bpy.context.view_layer.update()

    B = arm.data.bones
    huesos = [b.name for b in B]

    def J(n, cola=False):
        return Vector(B[n].tail_local if cola else B[n].head_local)

    cuerpo, polo, jean = O[f"{T}_Cuerpo"], O[f"{T}_Polo"], O[f"{T}_Jean"]
    F = Fuente.de_objetos([cuerpo, polo, jean], huesos)
    dom = np.array([huesos[i] for i in F.W.argmax(axis=1)], dtype=object)
    es_brazo = np.array([d.startswith(BRAZO) for d in dom])
    es_cabeza = np.array([d in ("head", "jaw") or d.startswith(("oris", "oculi", "levator", "orbicularis", "risorius",
                                                                 "temporalis", "special", "eye", "tongue")) for d in dom])
    tronco = ~es_brazo & ~es_cabeza

    # ---------------------------------------------------------------- materiales
    cuero = mat_cuero("Cuero_Gabardina", (0.016, 0.016, 0.018), gastado=(0.07, 0.06, 0.05))
    cuero_bota = mat_cuero("Cuero_Botas", (0.010, 0.010, 0.011), gastado=(0.04, 0.04, 0.04), rough=(0.25, 0.5), escala=10)
    guante_m = mat_cuero("Cuero_Guantes", (0.075, 0.052, 0.030), gastado=(0.05, 0.04, 0.025), rough=(0.45, 0.7), escala=30)
    correa_m = mat_cuero("Cuero_Correas", (0.025, 0.024, 0.023), gastado=(0.05, 0.05, 0.05), rough=(0.5, 0.7))
    metal = pm.mat_simple("Metal_Oscuro", (0.07, 0.075, 0.08), 0.42, 0.7)
    placa = pm.mat_simple("Plastico_Gris", (0.07, 0.075, 0.08), 0.5, 0.3)
    goma = pm.mat_simple("Goma_Negra", (0.012, 0.012, 0.012), 0.75)
    brillo = mat_brillo("Brillo_Cian")
    brillo_suave = mat_brillo("Brillo_Cian_Suave", (0.12, 0.75, 0.95), 3.0)
    polo.data.materials[0] = pm.mat_tela("Tela_Polera_Negra", (0.022, 0.022, 0.024), escala=1400, sheen=0.5)
    jean.data.materials[0] = pm.mat_tela("Tela_Pantalon_Cargo_Negro", (0.014, 0.014, 0.015), escala=1600, rough=0.9, sheen=0.3)
    polo.name, jean.name = f"{T}_Polera", f"{T}_Pantalon_Cargo"
    for ob in col.objects:
        if "_Correa" in ob.name:
            ob.data.materials[0] = correa_m
        if "_Hebilla" in ob.name:
            ob.data.materials[0] = metal

    # ---------------------------------------------------------------- gabardina (anillos alrededor del tronco)
    NA = 96
    ang = np.linspace(0, math.tau, NA, endpoint=False)
    hombro = J("upperarm01.L")
    z_top = hombro.z + 0.035
    z_cuello = z_top + 0.06
    z_pecho = J("spine01").z + 0.05
    z_ingle = J("upperleg02.L").z
    z_bajo = J("lowerleg01.L").z - 0.21
    zs = np.arange(z_top, z_bajo - 1e-6, -0.02)

    def seccion(z, mask, banda=0.018):
        sel = mask & (np.abs(F.co[:, 2] - z) < banda)
        return F.co[sel]

    Rt, cys = [], []
    prev = None
    cy_ingle = None
    for z in zs:
        pts = seccion(z, tronco)
        cy = (pts[:, 1].min() + pts[:, 1].max()) / 2 if len(pts) else cys[-1]
        if z < z_ingle:
            cy = cy_ingle if cy_ingle is not None else cy
        elif z < z_ingle + 0.03:
            cy_ingle = cy
        a = np.arctan2(pts[:, 0], -(pts[:, 1] - cy))
        r = np.hypot(pts[:, 0], pts[:, 1] - cy)
        R = np.full(NA, np.nan)
        cub = np.round(a / math.tau * NA).astype(int) % NA
        for k in range(NA):
            m_ = (np.abs((cub - k + NA // 2) % NA - NA // 2) <= 1)
            if m_.any():
                R[k] = r[m_].max()
        ok = ~np.isnan(R)
        R = np.interp(np.arange(NA), np.arange(NA)[ok], R[ok], period=NA)
        R = R + 0.022
        if prev is not None:
            if z < z_ingle:
                R = np.maximum(R, prev + 0.0032)          # vuelo de la falda
            elif z < z_pecho:
                R = np.maximum(R, prev * 0.985)           # caida recta, sin entallar
        prev = R
        Rt.append(R)
        cys.append(cy)
    Rt, cys = np.array(Rt), np.array(cys)
    for _ in range(4):                                     # suavizado alrededor y a lo alto
        Rt = (np.roll(Rt, 1, axis=1) + 2 * Rt + np.roll(Rt, -1, axis=1)) / 4
        Rt[1:-1] = (Rt[:-2] + 2 * Rt[1:-1] + Rt[2:]) / 4
    for _ in range(3):
        cys[1:-1] = (cys[:-2] + 2 * cys[1:-1] + cys[2:]) / 4
    zs_up, Rt_up, cys_up = zs[::-1], Rt[::-1], cys[::-1]

    def R_de(phi, z):
        k = (phi % math.tau) / math.tau * NA
        k0 = int(math.floor(k)) % NA
        f = k - math.floor(k)
        col_ = Rt_up[:, k0] * (1 - f) + Rt_up[:, (k0 + 1) % NA] * f
        return float(np.interp(z, zs_up, col_)), float(np.interp(z, zs_up, cys_up))

    def sup(phi, z, off=0.0):
        r, cy = R_de(phi, z)
        return Vector(((r + off) * math.sin(phi), cy - (r + off) * math.cos(phi), z))

    abertura = lambda z: float(np.interp(z, [z_bajo, z_ingle, J("spine04").z, z_pecho, z_top, z_cuello + 0.14],
                                         [0.24, 0.13, 0.10, 0.08, 0.055, 0.075]))
    M_ = 80

    def phi0(z, R_frente):
        return math.asin(min(0.95, abertura(z) / R_frente))

    # filas de abajo hacia arriba: falda + torso, canesu (hombros) y cuello alto
    filas = []
    for z, R, cy in zip(zs_up, Rt_up, cys_up):
        f0 = phi0(z, R[0])
        fila = []
        for j in range(M_):
            ph = f0 + (math.tau - 2 * f0) * j / (M_ - 1)
            r, _ = R_de(ph, z)
            fila.append(Vector((r * math.sin(ph), cy - r * math.cos(ph), z)))
        filas.append(fila)
    cy_c = J("neck01").y + 0.008
    tr = F.co[tronco]

    def sobre_cuerpo(p, holgura=0.016):
        m_ = (np.abs(tr[:, 0] - p.x) < 0.018) & (np.abs(tr[:, 1] - p.y) < 0.018) & (tr[:, 2] > p.z - 0.15)
        if m_.any():
            p.z = max(p.z, float(tr[m_, 2].max()) + holgura)
        return p

    perfiles_cuello = [  # (z, rx, ry): canesu (rx=0) y aros del cuello alto
        (None, None, None), (z_top + 0.022, 0.0, 0.0), (z_top + 0.045, 0.0, 0.0),
        (z_cuello, 0.090, 0.082), (z_cuello + 0.035, 0.094, 0.087), (z_cuello + 0.07, 0.104, 0.095),
        (z_cuello + 0.10, 0.118, 0.108)]
    top = filas[-1]
    f_top = phi0(z_top, Rt_up[-1][0])
    for i, (zc, rx, ry) in enumerate(perfiles_cuello[1:], start=1):
        f0 = math.asin(min(0.95, abertura(zc) / (ry if ry else 0.1))) if rx else f_top
        fila = []
        for j in range(M_):
            ph = f0 + (math.tau - 2 * f0) * j / (M_ - 1)
            if rx:                                         # aro del cuello (elipse)
                p = Vector((rx * math.sin(ph), cy_c - ry * math.cos(ph), zc))
                p.z += 0.01 * max(0.0, -math.cos(ph))      # el cuello sube un poco atras y baja adelante
                p.z -= 0.025 * max(0.0, math.cos(ph)) ** 3 * (zc - z_cuello) / 0.14
            else:                                          # canesu: de los hombros al cuello, sobre el cuerpo
                t = 0.4 if i == 1 else 0.75
                pc = Vector((0.090 * math.sin(ph), cy_c - 0.082 * math.cos(ph), z_cuello))
                pt = top[j]
                p = pt.lerp(pc, t)
                p.z = pt.z + (z_cuello - pt.z) * t + 0.012
                p = sobre_cuerpo(p)
            fila.append(p)
        filas.append(fila)
    verts, caras = rejilla(filas, False)
    gab = malla(f"{T}_Gabardina", verts, caras, col, cuero)

    def mezcla_falda(p, fila):
        if p[2] >= z_ingle:
            return fila
        a = min(1.0, (z_ingle - p[2]) / (z_ingle - z_bajo)) * 0.55
        out = fila * (1 - a)
        out[huesos.index("root")] += a
        return out

    Fg = pesar(gab, F, arm, huesos, k=10, mezcla=mezcla_falda)
    s_ = gab.modifiers.new("Espesor", "SOLIDIFY")
    s_.thickness = 0.006
    s_.offset = 1.0
    gab.modifiers.new("Suavizado", "SUBSURF").levels = 1

    # solapas sobre el pecho
    for lado in (1, -1):
        fl = []
        z_fin = z_top - 0.30
        for z in np.linspace(z_top + 0.01, z_fin, 14):
            R0, _ = R_de(0.0, z)
            f0 = phi0(z, R0)
            t = (z_top + 0.01 - z) / (z_top + 0.01 - z_fin)
            ancho = 0.085 * (1 - t) ** 1.2 + 0.004
            fila = []
            for c in np.linspace(0, 1, 7):
                ph = f0 + c * ancho / R0
                ph = ph if lado > 0 else -ph
                fila.append(sup(ph, z, 0.007 + 0.006 * c * (1 - t)))
            fl.append(fila)
        v_, c_ = rejilla(fl, False)
        so = malla(f"{T}_Solapa_{'Izq' if lado > 0 else 'Der'}", v_, c_, col, cuero)
        pesar(so, Fg, arm, huesos)
        so.modifiers.new("Espesor", "SOLIDIFY").thickness = 0.004
        so.modifiers.new("Suavizado", "SUBSURF").levels = 1

    # ---------------------------------------------------------------- mangas, munequeras, guantes, lineas de brillo
    ar = F.co[es_brazo]
    for lado, en in ((1, "L"), (-1, "R")):
        A, E, Wr = J(f"upperarm01.{en}"), J(f"lowerarm01.{en}"), J(f"wrist.{en}")
        S = A + (A - E).normalized() * 0.035 + Vector((-lado * 0.01, 0, 0.0))
        fin = Wr - (Wr - E).normalized() * 0.045
        ctrl = [S, S.lerp(E, 0.5), E, E.lerp(fin, 0.5), fin]
        eje = suave(ctrl, 5)
        tg, ns = marcos(eje)
        NS = 28
        anillos, Rs = [], []
        for p, t, n in zip(eje, tg, ns):
            b = t.cross(n)
            rel = ar - np.array(p)
            ax = rel @ np.array(t)
            m_ = (np.abs(ax) < 0.016) & (np.linalg.norm(rel - ax[:, None] * np.array(t), axis=1) < 0.11)
            q = rel[m_]
            R = np.full(NS, np.nan)
            if len(q):
                an = np.arctan2(q @ np.array(b), q @ np.array(n))
                rr = np.hypot(q @ np.array(b), q @ np.array(n))
                cub = np.round(an / math.tau * NS).astype(int) % NS
                for k in range(NS):
                    mm = np.abs((cub - k + NS // 2) % NS - NS // 2) <= 1
                    if mm.any():
                        R[k] = rr[mm].max()
            if np.isnan(R).all():
                R[:] = 0.05
            ok = ~np.isnan(R)
            R = np.interp(np.arange(NS), np.arange(NS)[ok], R[ok], period=NS) + 0.017
            Rs.append(R)
        Rs = np.array(Rs)
        L_ = len(eje)
        for i in range(L_):
            t = i / (L_ - 1)
            Rs[i] = np.maximum(Rs[i], 0.062 - 0.02 * t)
        for _ in range(3):
            Rs = (np.roll(Rs, 1, axis=1) + 2 * Rs + np.roll(Rs, -1, axis=1)) / 4
            Rs[1:-1] = (Rs[:-2] + 2 * Rs[1:-1] + Rs[2:]) / 4
        for p, t, n, R in zip(eje, tg, ns, Rs):
            b = t.cross(n)
            anillos.append([p + (n * math.cos(k * math.tau / NS) + b * math.sin(k * math.tau / NS)) * R[k] for k in range(NS)])
        v_, c_ = rejilla(anillos, True)
        mg = malla(f"{T}_Manga_{'Izq' if lado > 0 else 'Der'}", v_, c_, col, cuero)
        pesar(mg, F, arm, huesos, k=6)
        s_ = mg.modifiers.new("Espesor", "SOLIDIFY")
        s_.thickness = 0.005
        s_.offset = 1.0
        mg.modifiers.new("Suavizado", "SUBSURF").levels = 1
        # puno de la manga
        pu = tubo(f"{T}_Puno_Manga_{en}", [eje[-3], eje[-1] + tg[-1] * 0.004], float(Rs[-1].mean()) + 0.004, col, cuero, seg=24, tapas=False)
        pesar(pu, F, arm, huesos, k=6)
        pu.modifiers.new("Espesor", "SOLIDIFY").thickness = 0.006
        # linea de brillo por el lado de afuera de la manga, del hombro a la munequera
        lin = [eje[i] + ns[i] * (Rs[i][0] + 0.007) for i in range(1, L_)]
        lb = tubo(f"{T}_Linea_Brillo_Manga_{en}", suave(lin[::2], 4), 0.0045, col, brillo, seg=8)
        pesar(lb, F, arm, huesos, k=6)

        # munequera (brazal) desde el puno hasta la muneca, con dos hebillas y pantalla
        dW = (Wr - E).normalized()
        mu_ax = [fin - dW * 0.03, Wr + dW * 0.012]
        rel = ar - np.array(Wr)
        mm = np.linalg.norm(rel, axis=1) < 0.09
        r_mu = 0.044
        if mm.any():
            q = rel[mm]
            axq = q @ np.array(dW)
            r_mu = float(np.percentile(np.linalg.norm(q - axq[:, None] * np.array(dW), axis=1)[np.abs(axq) < 0.04], 95)) + 0.012
        bz = tubo(f"{T}_Munequera_{en}", suave(mu_ax, 3), r_mu, col, correa_m, seg=24, tapas=False)
        pesar(bz, F, arm, huesos, k=6)
        bz.modifiers.new("Espesor", "SOLIDIFY").thickness = 0.006
        bz.modifiers.new("Suavizado", "SUBSURF").levels = 1
        n_w = ns[-1]
        for k_, d_ in enumerate((0.0, 0.035)):
            c0 = mu_ax[0] + dW * (0.012 + d_)
            ring = tubo(f"{T}_Munequera_Hebilla_{en}_{k_}", [c0 - dW * 0.006, c0 + dW * 0.006], r_mu + 0.004, col, metal, seg=24)
            pesar(ring, F, arm, huesos, k=6)
        M_d = base_local(mu_ax[0].lerp(mu_ax[1], 0.55) + n_w * (r_mu + 0.012), n_w, dW)
        dv = colocar(caja(f"{T}_Pantalla_Muneca_{en}", (0.05, 0.065, 0.018), col, metal, 0.003), M_d)
        pa = colocar(caja(f"{T}_Pantalla_Muneca_Brillo_{en}", (0.032, 0.040, 0.004), col, brillo, 0.001), M_d, (0, 0.004, 0.009))
        for k_ in range(3):
            colocar(caja(f"{T}_Pantalla_Muneca_Led_{en}_{k_}", (0.008, 0.006, 0.004), col, brillo, 0.0), M_d,
                    (-0.012 + k_ * 0.012, -0.024, 0.009))
        for ob in list(col.objects):
            if ob.name.startswith(f"{T}_Pantalla_Muneca") and ob.name.endswith(tuple(f"_{en}{s}" for s in ("", "_0", "_1", "_2"))) and ob.parent is None:
                pm.a_hueso(ob, arm, f"lowerarm02.{en}")

    # guantes: copia de la piel de las manos, inflada un poco
    gu = cuerpo.copy()
    gu.data = cuerpo.data.copy()
    gu.name = f"{T}_Guantes"
    col.objects.link(gu)
    gu.data.materials.clear()
    gu.data.materials.append(guante_m)
    for a_ in list(gu.data.color_attributes):
        gu.data.color_attributes.remove(a_)
    nombres = [g.name for g in gu.vertex_groups]
    bm = bmesh.new()
    bm.from_mesh(gu.data)
    dl = bm.verts.layers.deform.active
    Wr_L, Wr_R = J("wrist.L"), J("wrist.R")
    E_L, E_R = J("lowerarm01.L"), J("lowerarm01.R")

    def en_mano(v):
        d = v[dl]
        if not d:
            return False
        g = max(d.items(), key=lambda kv: kv[1])[0]
        nm = nombres[g]
        if nm.startswith(MANO):
            return True
        for Wx, Ex in ((Wr_L, E_L), (Wr_R, E_R)):     # un poco de antebrazo (cana del guante)
            ax = (Wx - Ex).normalized()
            if -0.035 < (v.co - Wx).dot(ax) < 0.02 and (v.co - Wx).length < 0.07:
                return True
        return False

    dentro = {v.index for v in bm.verts if en_mano(v)}
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if not all(v.index in dentro for v in f.verts)], context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.normal_update()
    for v in bm.verts:
        v.co += v.normal * 0.0028
    bm.to_mesh(gu.data)
    bm.free()

    # ---------------------------------------------------------------- botas: pie (zapato) + cana alta con pasadores
    pierna = F.co[np.array([d.startswith(("lowerleg", "foot")) for d in dom])]
    z_bota = J("lowerleg01.L").z - 0.19
    for lado, en, nom in ((1, "L", "Izq"), (-1, "R", "Der")):
        zp = O[f"{T}_Zapato_Seguridad_{nom}"]
        zp.name = f"{T}_Bota_Pie_{nom}"
        zp.data.materials[0] = cuero_bota
        O[f"{T}_Suela_{nom}"].name = f"{T}_Bota_Suela_{nom}"
        O[f"{T}_Bota_Suela_{nom}"].modifiers["Espesor"].thickness = 0.022
        K, Ak = J(f"lowerleg01.{en}"), J(f"foot.{en}")
        z0 = Ak.z - 0.01
        filas_b, NB = [], 32
        cents = []
        for z in np.linspace(z0, z_bota, 16):
            t = (z - Ak.z) / (K.z - Ak.z)
            c = Ak.lerp(K, max(0.0, t))
            c.z = z
            sel = pierna[(np.abs(pierna[:, 2] - z) < 0.015) & (np.hypot(pierna[:, 0] - c.x, pierna[:, 1] - c.y) < 0.11)]
            R = np.full(NB, 0.06)
            if len(sel):
                a = np.arctan2(sel[:, 0] - c.x, -(sel[:, 1] - c.y))
                r = np.hypot(sel[:, 0] - c.x, sel[:, 1] - c.y)
                cub = np.round(a / math.tau * NB).astype(int) % NB
                for k in range(NB):
                    mm = np.abs((cub - k + NB // 2) % NB - NB // 2) <= 1
                    if mm.any():
                        R[k] = max(r[mm].max(), 0.05)
            R = R + 0.014 + 0.012 * max(0.0, 1 - (z - z0) / 0.05)
            for _ in range(6):
                R = (np.roll(R, 1) + 2 * R + np.roll(R, -1)) / 4
            cents.append(c)
            filas_b.append([Vector((c.x + R[k] * math.sin(k * math.tau / NB), c.y - R[k] * math.cos(k * math.tau / NB), z))
                            for k in range(NB)])
        arr = np.array([[tuple(p) for p in f] for f in filas_b])
        for _ in range(3):
            arr[1:-1, :, :2] = (arr[:-2, :, :2] + 2 * arr[1:-1, :, :2] + arr[2:, :, :2]) / 4
        filas_b = [[Vector(p) for p in f] for f in arr]
        v_, c_ = rejilla(filas_b, True)
        ca = malla(f"{T}_Bota_Cana_{nom}", v_, c_, col, cuero_bota)
        pesar(ca, F, arm, huesos, k=6)
        s_ = ca.modifiers.new("Espesor", "SOLIDIFY")
        s_.thickness = 0.005
        ca.modifiers.new("Suavizado", "SUBSURF").levels = 1
        Fb = Fuente(np.array([p for f in filas_b for p in f]), Fuente.de_objetos([ca], huesos).W)

        def en_cana(i_fila, phi, off):
            f = filas_b[i_fila]
            k = phi / math.tau * NB
            k0 = int(math.floor(k)) % NB
            p = f[k0].lerp(f[(k0 + 1) % NB], k - math.floor(k))
            c = cents[i_fila]
            d = Vector((p.x - c.x, p.y - c.y, 0)).normalized()
            return p + d * off
        # borde superior
        rim = [en_cana(len(filas_b) - 1, k * math.tau / 48, 0.004) for k in range(49)]
        bo = tubo(f"{T}_Bota_Borde_{nom}", rim, 0.006, col, cuero_bota, seg=8)
        pesar(bo, Fb, arm, huesos)
        # pasadores cruzados al frente
        for i in range(1, len(filas_b) - 1, 2):
            for s_a in (1, -1):
                a0, a1 = (s_a * 0.38) % math.tau, (-s_a * 0.38) % math.tau
                ps = [en_cana(i, a0, 0.004), en_cana(min(i + 2, len(filas_b) - 1), a1, 0.004)]
                ps.insert(1, (ps[0] + ps[1]) / 2 + (ps[0] - Vector((cents[i].x, cents[i].y, ps[0].z))).normalized() * 0.003)
                ln = tubo(f"{T}_Bota_Pasador_{nom}", ps, 0.0022, col, goma, seg=6)
                pesar(ln, Fb, arm, huesos)
            for s_a in (1, -1):
                oj = cilindro(f"{T}_Bota_Ojal_{nom}", 0.0035, 0.003, col, metal, seg=10)
                pt = en_cana(i, (s_a * 0.42) % math.tau, 0.002)
                c = cents[i]
                colocar(oj, base_local(pt, Vector((pt.x - c.x, pt.y - c.y, 0)), Vector((0, 0, 1))))
                pesar(oj, Fb, arm, huesos, k=2)
        # linea de brillo vertical al frente-afuera de la cana y aro de brillo en el tobillo
        ph = (lado * 0.55) % math.tau
        lin = [en_cana(i, ph, 0.006) for i in range(1, len(filas_b) - 1)]
        lb = tubo(f"{T}_Bota_Linea_Brillo_{nom}", lin, 0.004, col, brillo, seg=8)
        pesar(lb, Fb, arm, huesos)
        ph2 = (lado * math.pi / 2) % math.tau
        c_tob = en_cana(2, ph2, 0.004)
        cc_ = cents[2]
        n_t = Vector((c_tob.x - cc_.x, c_tob.y - cc_.y, 0)).normalized()
        anillo = [c_tob + (base_local(c_tob, n_t, Vector((0, 0, 1))).to_3x3() @ Vector((math.cos(a) * 0.012, math.sin(a) * 0.012, 0)))
                  for a in np.linspace(0, math.tau, 25)]
        ab = tubo(f"{T}_Bota_Aro_Brillo_{nom}", anillo, 0.0025, col, brillo, seg=6)
        pesar(ab, Fb, arm, huesos, k=2)
        # brillo en la puntera (sigue al hueso del pie)
        me_z = zp.data
        cz = np.array([v.co for v in me_z.vertices])
        bvz = BVHTree.FromPolygons([tuple(v) for v in cz], [tuple(p.vertices) for p in me_z.polygons])
        y_punta = cz[:, 1].min()
        xc = float(cz[cz[:, 1] < y_punta + 0.03][:, 0].mean())
        for dx in (-0.012, 0.012):
            pts = []
            for yy in np.linspace(y_punta + 0.012, y_punta + 0.06, 6):
                hit = bvz.ray_cast(Vector((xc + dx, yy, 0.4)), Vector((0, 0, -1)))
                if hit[0] is not None:
                    pts.append(hit[0] + Vector((0, 0, 0.002)))
            if len(pts) > 2:
                pt_ = tubo(f"{T}_Bota_Puntera_Brillo_{nom}", pts, 0.0028, col, brillo, seg=6)
                pm.a_hueso(pt_, arm, f"foot.{en}")

    # ---------------------------------------------------------------- rodilleras y correas del muslo
    bvj = BVHTree.FromPolygons([tuple(v) for v in (jean.matrix_world @ v.co for v in jean.data.vertices)],
                               [tuple(p.vertices) for p in jean.data.polygons])
    for en, nom in (("L", "Izq"), ("R", "Der")):
        K = J(f"lowerleg01.{en}")
        hit = bvj.ray_cast(Vector((K.x, K.y - 0.3, K.z - 0.01)), Vector((0, 1, 0)))
        if hit[0] is not None:
            M_k = base_local(hit[0] + Vector((0, -0.010, 0)), Vector((0, -1, 0)), Vector((0, 0, 1)))
            rd = colocar(caja(f"{T}_Rodillera_{nom}", (0.095, 0.125, 0.03), col, placa, 0.0), M_k)
            rd.modifiers.new("Suavizado", "SUBSURF").levels = 3
            pm.a_hueso(rd, arm, f"lowerleg01.{en}")
            for dz in (0.045, -0.05):
                hb = colocar(caja(f"{T}_Rodillera_Correa_{nom}", (0.11, 0.016, 0.012), col, correa_m, 0.002), M_k, (0, dz, -0.01))
                pm.a_hueso(hb, arm, f"lowerleg01.{en}")
    # dos correas (funda) en el muslo derecho
    Hd, Kd = J("upperleg02.R"), J("lowerleg01.R")
    jco = np.array([jean.matrix_world @ v.co for v in jean.data.vertices])
    for t in (0.22, 0.42):
        c = Hd.lerp(Kd, t)
        sel = jco[(np.abs(jco[:, 2] - c.z) < 0.012) & (jco[:, 0] < -0.02)]
        a = np.arctan2(sel[:, 0] - c.x, -(sel[:, 1] - c.y))
        r = np.hypot(sel[:, 0] - c.x, sel[:, 1] - c.y)
        pts = []
        for k in range(41):
            ph = k * math.tau / 40
            mm = np.abs((a - ph + math.pi) % math.tau - math.pi) < 0.25
            rr = (r[mm].max() if mm.any() else r.mean()) + 0.006
            pts.append(Vector((c.x + rr * math.sin(ph), c.y - rr * math.cos(ph), c.z)))
        cm = tubo(f"{T}_Correa_Muslo", pts, 0.004, col, correa_m, seg=8, ancho=0.012,
                  normal=lambda p, c=c: Vector((p.x - c.x, p.y - c.y, 0)))
        pesar(cm, F, arm, huesos)

    # ---------------------------------------------------------------- bolsillos tacticos en el pecho
    bvp = BVHTree.FromPolygons([tuple(v) for v in (polo.matrix_world @ v.co for v in polo.data.vertices)],
                               [tuple(p.vertices) for p in polo.data.polygons])
    for k_, z in enumerate((J("spine02").z + 0.05, J("spine02").z - 0.045)):
        for dx in (-0.042, 0.042):
            hit = bvp.ray_cast(Vector((dx, -0.5, z)), Vector((0, 1, 0)))
            if hit[0] is None:
                continue
            M_p = base_local(hit[0] + hit[1] * 0.016, hit[1], Vector((0, 0, 1)))
            bo = colocar(caja(f"{T}_Bolsillo_Pecho", (0.058, 0.085, 0.026), col, correa_m, 0.006, 3), M_p)
            tp = colocar(caja(f"{T}_Bolsillo_Pecho_Tapa", (0.062, 0.03, 0.006), col, correa_m, 0.003), M_p, (0, 0.03, 0.014))
            pm.a_hueso(bo, arm, "spine02")
            pm.a_hueso(tp, arm, "spine02")

    # ---------------------------------------------------------------- mochila de energia en la espalda
    z_m = z_top - 0.19
    y_esp = max(sup(math.pi + d, z, 0.0).y for d in (-0.2, 0, 0.2) for z in (z_m - 0.15, z_m, z_m + 0.15))
    M_m = Matrix.Translation(Vector((0, y_esp + 0.048, z_m)))
    lado_y = lambda ob, loc, ejez=Vector((0, 1, 0)): colocar(ob, M_m @ base_local(Vector(loc), ejez, Vector((0, 0, 1))))
    mo = colocar(caja(f"{T}_Mochila", (0.30, 0.09, 0.36), col, metal, 0.012, 3), M_m)
    lado_y(caja(f"{T}_Mochila_Placa", (0.25, 0.30, 0.016), col, placa, 0.006, 2), (0, 0.046, 0))
    lado_y(caja(f"{T}_Mochila_Placa_Centro", (0.10, 0.12, 0.01), col, metal, 0.003), (0, 0.056, -0.04))
    lado_y(caja(f"{T}_Mochila_Brillo_Superior", (0.085, 0.022, 0.006), col, brillo, 0.002), (0, 0.056, 0.115))
    for sx in (-1, 1):
        lado_y(caja(f"{T}_Mochila_Brillo_Lateral", (0.016, 0.075, 0.006), col, brillo, 0.002), (sx * 0.095, 0.056, 0.085))
        lado_y(caja(f"{T}_Mochila_Marco", (0.008, 0.20, 0.008), col, brillo_suave, 0.002), (sx * 0.118, 0.054, -0.03))
        for sz in (-1, 1):
            b_ = cilindro(f"{T}_Mochila_Perno", 0.007, 0.006, col, placa, seg=12)
            lado_y(b_, (sx * 0.135, 0.05, sz * 0.165))
    lado_y(caja(f"{T}_Mochila_Brillo_Pantalla", (0.035, 0.022, 0.006), col, brillo, 0.002), (-0.075, 0.056, -0.05))
    for k in range(5):
        lado_y(caja(f"{T}_Mochila_Indicador", (0.022, 0.007, 0.006), col, brillo, 0.0), (0.08, 0.056, -0.025 - k * 0.014))
    puertos = []
    for k, sx in enumerate((-0.11, -0.05, 0.05, 0.11)):
        pt = cilindro(f"{T}_Mochila_Puerto", 0.012, 0.03, col, placa, seg=14)
        lado_y(pt, (sx, 0.01, -0.185), Vector((0, 0, 1)))
        puertos.append(M_m @ Vector((sx, 0.01, -0.20)))
    for ob in list(col.objects):
        if ob.name.startswith(f"{T}_Mochila") and ob.parent is None:
            pm.a_hueso(ob, arm, "spine01")

    # tirantes de la mochila: de la mochila, por encima del hombro, hasta el pecho y de vuelta bajo el brazo
    def radial(p):
        c = Vector((0, float(np.interp(p.z, zs_up, cys_up)) if p.z < z_top else cy_c, min(p.z, z_top - 0.12)))
        return (p - c).normalized()

    for s in (1, -1):
        hb = J(f"upperarm01.{'L' if s > 0 else 'R'}")
        sobre = sobre_cuerpo(Vector((s * 0.12, cy_c + 0.01, z_top)), 0.03)
        ctrl = [M_m @ Vector((s * 0.09, -0.04, 0.16)), sup(math.pi - s * 0.45, z_top - 0.02, 0.012),
                sobre, sup(s * 0.62, z_top - 0.06, 0.012), sup(s * 0.60, z_top - 0.22, 0.012),
                sup(s * 0.95, z_top - 0.33, 0.010), sup(s * 1.35, z_top - 0.33, 0.010), sup(math.pi - s * 0.9, z_m - 0.16, 0.010),
                M_m @ Vector((s * 0.15, -0.04, -0.14))]
        ti = tubo(f"{T}_Tirante_Mochila", suave(ctrl, 6), 0.004, col, correa_m, seg=8, ancho=0.018, normal=radial)
        pesar(ti, Fg, arm, huesos, k=6)
        hk = colocar(caja(f"{T}_Tirante_Hebilla", (0.03, 0.036, 0.008), col, metal, 0.002),
                     base_local(sup(s * 0.61, z_top - 0.15, 0.02), radial(sup(s * 0.61, z_top - 0.15)), Vector((0, 0, 1))))
        pm.a_hueso(hk, arm, "spine02")

    # ---------------------------------------------------------------- modulos de las caderas
    z_mod = z_ingle - 0.07
    mods = {}
    for s in (1, -1):
        ph = s * math.pi / 2
        p0 = sup(ph, z_mod, 0.026)
        nrm = Vector((s, 0, 0))
        M_h = base_local(p0, nrm, Vector((0, 0, 1)))
        partes = [colocar(caja(f"{T}_Modulo_Cadera", (0.08, 0.18, 0.045), col, metal, 0.008, 3), M_h),
                  colocar(caja(f"{T}_Modulo_Cadera_Placa", (0.062, 0.15, 0.008), col, placa, 0.003), M_h, (0, 0, 0.024))]
        for sx in (-1, 1):
            partes.append(colocar(caja(f"{T}_Modulo_Cadera_Brillo", (0.008, 0.11, 0.004), col, brillo, 0.0), M_h, (sx * 0.024, 0.0, 0.029)))
        partes.append(colocar(caja(f"{T}_Modulo_Cadera_Brillo", (0.036, 0.008, 0.004), col, brillo, 0.0), M_h, (0, 0.058, 0.029)))
        partes.append(colocar(caja(f"{T}_Modulo_Cadera_Brillo", (0.036, 0.008, 0.004), col, brillo, 0.0), M_h, (0, -0.058, 0.029)))
        for k in range(4):     # indicadores en el canto delantero (mira a -Y)
            led = caja(f"{T}_Modulo_Cadera_Led", (0.012, 0.008, 0.004), col, brillo, 0.0)
            led.matrix_world = Matrix.Translation(p0 + Vector((0, -0.041, -0.03 + k * 0.02))) @ Matrix.Rotation(math.pi / 2, 4, "X")
            partes.append(led)
        conector = cilindro(f"{T}_Modulo_Cadera_Conector", 0.012, 0.025, col, placa, seg=14)
        colocar(conector, M_h, (0, -0.1, 0))
        partes.append(conector)
        for ob in partes:      # siguen a la gabardina (mismos pesos que el faldon en ese punto)
            pesar(ob, Fg, arm, huesos, k=8)
        mods[s] = (p0, M_h)

    # ---------------------------------------------------------------- cables de brillo
    def cable(nombre, ctrl, r=0.0065):
        pts = suave(ctrl, 8)
        nucleo = tubo(nombre, pts, r, col, brillo, seg=10)
        pesar(nucleo, Fg, arm, huesos, k=6)
        return nucleo

    for s in (1, -1):
        p0, M_h = mods[s]
        bajo = M_h @ Vector((0, -0.105, 0))
        lado_m = lambda d: math.pi - s * d
        # cable interior largo: baja por la espalda casi hasta el ruedo y sube al modulo
        cable(f"{T}_Cable_Espalda_Largo", [puertos[1 if s < 0 else 2], sup(lado_m(0.06), z_m - 0.25, 0.014),
                                          sup(lado_m(0.10), 0.78, 0.014), sup(lado_m(0.14), z_bajo + 0.09, 0.014),
                                          sup(lado_m(0.34), z_bajo + 0.05, 0.014), sup(lado_m(0.62), z_bajo + 0.12, 0.014),
                                          sup(lado_m(0.95), z_mod - 0.24, 0.016), sup(lado_m(1.3), z_mod - 0.16, 0.022), bajo])
        # cable exterior: lazo mas corto por el costado
        cable(f"{T}_Cable_Espalda_Corto", [puertos[0 if s < 0 else 3], sup(lado_m(0.22), z_m - 0.26, 0.014),
                                          sup(lado_m(0.30), z_ingle + 0.08, 0.014), sup(lado_m(0.40), z_ingle - 0.12, 0.014),
                                          sup(lado_m(0.62), z_ingle - 0.18, 0.016), sup(lado_m(0.85), z_ingle - 0.10, 0.02),
                                          sup(lado_m(1.15), z_mod + 0.02, 0.03), p0 + Vector((0, 0.04, 0.07))])
        # lazo delantero que cuelga del modulo
        fr = lambda d: s * (math.pi / 2 - d)
        cable(f"{T}_Cable_Lazo_Delantero", [bajo, sup(fr(0.10), z_mod - 0.17, 0.03), sup(fr(0.22), z_mod - 0.27, 0.025),
                                           sup(fr(0.36), z_mod - 0.22, 0.02), sup(fr(0.42), z_mod - 0.08, 0.015),
                                           sup(fr(0.40), z_mod + 0.02, 0.012)], 0.0055)
    bpy.context.view_layer.objects.active = arm
    for ob in col.objects:
        ob.select_set(False)
    return arm


# ----------------------------------------------------------------------------- vista previa
def render(arm, salida):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = int(os.environ.get("MUESTRAS", 48))
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = 720, 1240
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    w = bpy.data.worlds.new("Fondo")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.20, 0.18, 0.16, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.6
    sc.world = w
    tmp = bpy.data.collections.new("Vista_Previa")
    sc.collection.children.link(tmp)
    bpy.ops.mesh.primitive_plane_add(size=12)
    piso = bpy.context.active_object
    for c in piso.users_collection:
        c.objects.unlink(piso)
    tmp.objects.link(piso)
    piso.data.materials.append(pm.mat_simple("Piso_Previa", (0.17, 0.155, 0.14), 0.8))
    for nombre, loc, en, tam in (("Clave", (-2.5, -3.5, 4.0), 900, 3.0), ("Relleno", (3.5, -2.5, 2.0), 350, 4.0),
                                 ("Contra", (0.5, 3.5, 3.5), 700, 2.0)):
        ld = bpy.data.lights.new(nombre, "AREA")
        ld.energy, ld.size = en, tam
        lo = bpy.data.objects.new(nombre, ld)
        tmp.objects.link(lo)
        lo.location = loc
        lo.rotation_euler = (Vector((0, 0, 1.0)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cd = bpy.data.cameras.new("Cam")
    cd.lens = 85
    cam = bpy.data.objects.new("Cam", cd)
    tmp.objects.link(cam)
    sc.camera = cam
    cam.location = (0, -6.3, 1.0)
    cam.rotation_euler = (math.radians(90), 0, 0)
    imgs = []
    for k, ang in enumerate((-35, 0, 180)):
        arm.rotation_euler = (0, 0, math.radians(ang))
        sc.render.filepath = f"{salida}_{k}.png"
        bpy.ops.render.render(write_still=True)
        imgs.append(sc.render.filepath)
    arm.rotation_euler = (0, 0, 0)
    from PIL import Image
    ims = [Image.open(f) for f in imgs]
    hoja = Image.new("RGB", (sum(i.width for i in ims), ims[0].height))
    x = 0
    for i in ims:
        hoja.paste(i, (x, 0))
        x += i.width
    hoja.save(salida + ".png")
    for f in imgs:
        os.remove(f)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    col = bpy.data.collections.new("Personaje_Cyber")
    sc.collection.children.link(col)
    arm = construir(col)
    for m in bpy.data.meshes:
        if m.users == 0:
            bpy.data.meshes.remove(m)
    out = os.path.join(AQUI, "personaje_cyber_modelo.blend")
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("Guardado", out, len(bpy.data.objects), "objetos", flush=True)
    if "--render" in sys.argv:
        render(arm, os.path.join(AQUI, "..", "renders", "personaje_cyber_preview"))


if __name__ == "__main__":
    main()
