"""
Funciones comunes para los modelos procedurales (escena limpia, primitivas con nombre,
colecciones por grupo, aplicar modificadores, numerar nombres repetidos y guardar).
Se importa desde los scripts de esta carpeta: `from comun import *`.
"""
import math
import os

import bpy
import bmesh
from mathutils import Vector, Matrix

ROOT = [None]
CUR = [None]


def nueva_escena(nombre_raiz):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    r = bpy.data.collections.new(nombre_raiz)
    sc.collection.children.link(r)
    ROOT[0] = r
    CUR[0] = r
    sc.unit_settings.system = "METRIC"
    return sc


def grupo(nombre, padre=None):
    c = bpy.data.collections.get(nombre)
    if c is None:
        c = bpy.data.collections.new(nombre)
        (padre or ROOT[0]).children.link(c)
    CUR[0] = c
    return c


def link(ob):
    CUR[0].objects.link(ob)
    return ob


def mat(nombre, rgb, rough=0.6, metal=0.0):
    m = bpy.data.materials.get(nombre)
    if m is None:
        m = bpy.data.materials.new(nombre)
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (*rgb, 1)
        b.inputs["Roughness"].default_value = rough
        b.inputs["Metallic"].default_value = metal
        m.diffuse_color = (*rgb, 1)
    return m


def _obj(name, bm, smooth, m):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = link(bpy.data.objects.new(name, me))
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    if m is not None:
        me.materials.append(m)
    return ob


def box(name, size, loc, rot=(0, 0, 0), bevel=0.0, m=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    ob = _obj(name, bm, False, m)
    ob.location = loc
    ob.rotation_euler = rot
    if bevel:
        md = ob.modifiers.new("Bisel", "BEVEL")
        md.width = bevel
        md.segments = 3
    return ob


def cyl(name, r, depth, loc, axis="Z", verts=32, r2=None, rot=None, m=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=r, radius2=r if r2 is None else r2, depth=depth)
    if axis == "X":
        bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
    elif axis == "Y":
        bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
    ob = _obj(name, bm, False, m)
    for p in ob.data.polygons:
        p.use_smooth = len(p.vertices) == 4
    ob.location = loc
    if rot:
        ob.rotation_euler = rot
    return ob


def esfera(name, r, loc, escala=(1, 1, 1), m=None, seg=24):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=seg // 2, radius=r)
    bmesh.ops.scale(bm, vec=Vector(escala), verts=bm.verts)
    ob = _obj(name, bm, True, m)
    ob.location = loc
    return ob


def capsula(name, p1, p2, r1, r2=None, m=None, seg=16):
    """Segmento redondeado (cono con tapas esfericas) entre dos puntos; origen en p1."""
    r2 = r1 if r2 is None else r2
    p1, p2 = Vector(p1), Vector(p2)
    L = (p2 - p1).length
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=seg, radius1=r1, radius2=r2, depth=L)
    bmesh.ops.translate(bm, vec=(0, 0, L / 2), verts=bm.verts)
    for (r, z) in ((r1, 0.0), (r2, L)):
        s = bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=seg // 2, radius=r)
        bmesh.ops.translate(bm, vec=(0, 0, z), verts=s["verts"])
    ob = _obj(name, bm, True, m)
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = Vector((0, 0, 1)).rotation_difference((p2 - p1).normalized())
    ob.location = p1
    return ob


def beam(name, p1, p2, t, t2=None, round_=False, m=None):
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    if round_:
        ob = cyl(name, t / 2, d.length, (0, 0, 0), verts=12, m=m)
    else:
        ob = box(name, (t, t if t2 is None else t2, d.length), (0, 0, 0), m=m)
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
    ob.location = (p1 + p2) / 2
    return ob


def from_pydata(name, verts, faces, smooth=True, solidify=0.0, m=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    if m is not None:
        me.materials.append(m)
    ob = link(bpy.data.objects.new(name, me))
    if solidify:
        md = ob.modifiers.new("Espesor", "SOLIDIFY")
        md.thickness = solidify
    return ob


def lerp_table(table, x):
    if x >= table[0][0]:
        return table[0][1:]
    for a, b in zip(table, table[1:]):
        if a[0] >= x >= b[0]:
            t = (x - a[0]) / (b[0] - a[0]) if b[0] != a[0] else 0
            return tuple(va + (vb - va) * t for va, vb in zip(a[1:], b[1:]))
    return table[-1][1:]


def loft(name, stations, profile, m=None):
    """Superficie cerrada por secciones a lo largo de X; profile(x) da el medio perfil (y>=0, z)."""
    rings = []
    for x in stations:
        half = profile(x)
        full = half + [(-y, z) for (y, z) in reversed(half[1:-1])]
        rings.append([(x, y, z) for (y, z) in full])
    n = len(rings[0])
    verts = [v for r in rings for v in r]
    faces = []
    for i in range(len(rings) - 1):
        for j in range(n):
            j2 = (j + 1) % n
            faces.append((i * n + j, i * n + j2, (i + 1) * n + j2, (i + 1) * n + j))
    faces.append(tuple(range(n))[::-1])
    faces.append(tuple(range((len(rings) - 1) * n, len(rings) * n)))
    return from_pydata(name, verts, faces, m=m)


def curve_tube(name, pts, radius, res=8, m=None, cyclic=False):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 3
    cu.resolution_u = res
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for q, v in zip(sp.points, pts):
        q.co = (v[0], v[1], v[2], 1)
    sp.use_cyclic_u = cyclic
    if m is not None:
        cu.materials.append(m)
    return link(bpy.data.objects.new(name, cu))


def rueda(prefijo, c, r, w, eje="Y", rin=None, rayos=5, m_goma=None, m_llanta=None):
    """Rueda generica: neumatico (anillo grueso) + llanta con rayos."""
    rin = rin or r * 0.62
    ax = {"X": 0, "Y": 1}[eje]
    bm = bmesh.new()
    prof = []
    for k in range(13):
        a = math.pi * k / 12
        prof.append((r - 0.03 * r / 0.33 + 0.03 * r / 0.33 * math.sin(a), (w / 2) * -math.cos(a)))
    pts = [(rin, -w / 2 + 0.01)] + prof + [(rin, w / 2 - 0.01)]
    vs = [bm.verts.new((rr, yy, 0)) for rr, yy in pts]
    es = [bm.edges.new((vs[i], vs[i + 1])) for i in range(len(vs) - 1)] + [bm.edges.new((vs[-1], vs[0]))]
    bmesh.ops.spin(bm, geom=vs + es, cent=(0, 0, 0), axis=(0, 1, 0), angle=math.tau, steps=48, use_duplicate=False)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    if eje == "X":
        bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.pi / 2, 3, "Z"))
    t = _obj(f"{prefijo}_Neumatico", bm, True, m_goma)
    t.location = c
    cyl(f"{prefijo}_Llanta", rin, w * 0.75, c, axis=eje, verts=32, m=m_llanta)
    side = 1 if c[ax] >= 0 else -1
    off = Vector((0, 0, 0))
    off[ax] = side * w * 0.38
    cyl(f"{prefijo}_Tapa_Centro", rin * 0.30, 0.02, Vector(c) + off, axis=eje, verts=16, m=m_llanta)
    for k in range(rayos):
        a = k * math.tau / rayos
        if eje == "Y":
            d = Vector((math.cos(a), 0, math.sin(a)))
        else:
            d = Vector((0, math.cos(a), math.sin(a)))
        beam(f"{prefijo}_Rayo", Vector(c) + off + d * rin * 0.25, Vector(c) + off + d * rin * 0.95, rin * 0.18,
             t2=0.02, m=m_llanta)
    return t


def finalizar(nombre_archivo, aqui):
    """Aplica modificadores, borra auxiliares ocultos, numera repetidos y guarda el .blend."""
    dg = bpy.context.evaluated_depsgraph_get()
    for ob in list(bpy.data.objects):
        if ob.type == "MESH" and ob.modifiers and not ob.hide_render:
            me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
            old = ob.data
            mats = list(old.materials)
            ob.modifiers.clear()
            ob.data = me
            if not me.materials:
                for mm in mats:
                    me.materials.append(mm)
            bpy.data.meshes.remove(old)
    for ob in list(bpy.data.objects):
        if ob.hide_render and ob.type == "MESH":
            bpy.data.objects.remove(ob, do_unlink=True)
    grupos = {}
    for ob in bpy.data.objects:
        if ob.type == "ARMATURE":
            continue
        grupos.setdefault(ob.name.split(".")[0], []).append(ob)
    for base, obs in grupos.items():
        for ob in obs:
            ob.name = "__tmp__" + ob.name
    for base, obs in grupos.items():
        obs.sort(key=lambda o: (round(o.matrix_world.translation.x, 3), round(o.matrix_world.translation.y, 3),
                                round(o.matrix_world.translation.z, 3)))
        for k, ob in enumerate(obs):
            nm = base if len(obs) == 1 else f"{base}_{k + 1:02d}"
            ob.name = nm
            if ob.data is not None and ob.data.users == 1:
                ob.data.name = nm
    for blocks in (bpy.data.meshes, bpy.data.curves):
        for d in list(blocks):
            if d.users == 0:
                blocks.remove(d)
    out = os.path.join(aqui, nombre_archivo)
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print("Guardado", out, "-", len([o for o in bpy.data.objects if o.type != "ARMATURE"]), "piezas,",
          len(bpy.data.collections) - 1, "grupos", flush=True)


# ---------------------------------------------------------------------------
# Ayudas para superficies suaves (usadas por autos_modelo.py)
# ---------------------------------------------------------------------------
def curva(pts):
    """Interpolacion cubica monotona (PCHIP) por una tabla [(x, y), ...]; devuelve f(x)."""
    pts = sorted(pts)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    n = len(xs)
    if n == 1:
        return lambda x: ys[0]
    h = [xs[i + 1] - xs[i] for i in range(n - 1)]
    d = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]
    m = [0.0] * n
    m[0], m[-1] = d[0], d[-1]
    for i in range(1, n - 1):
        if d[i - 1] * d[i] <= 0:
            m[i] = 0.0
        else:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])

    def f(x):
        if x <= xs[0]:
            return ys[0]
        if x >= xs[-1]:
            return ys[-1]
        lo, hi = 0, n - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if xs[mid] <= x:
                lo = mid
            else:
                hi = mid
        t = (x - xs[lo]) / h[lo]
        t2, t3 = t * t, t * t * t
        return ((2 * t3 - 3 * t2 + 1) * ys[lo] + (t3 - 2 * t2 + t) * h[lo] * m[lo]
                + (-2 * t3 + 3 * t2) * ys[hi] + (t3 - t2) * h[lo] * m[hi])
    return f


def remuestrear(pts, n, peso_giro=0.0):
    """Reparte n puntos a lo largo de una polilinea 2D (por longitud, opcionalmente mas densos en curvas)."""
    acc = [0.0]
    for i in range(1, len(pts)):
        dx, dy = pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]
        L = math.hypot(dx, dy)
        g = 0.0
        if peso_giro and 0 < i < len(pts) - 1:
            ex, ey = pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]
            a1, a2 = math.atan2(dy, dx), math.atan2(ey, ex)
            g = abs((a2 - a1 + math.pi) % math.tau - math.pi) * peso_giro
        acc.append(acc[-1] + L + g)
    tot = acc[-1]
    out, j = [], 0
    for k in range(n):
        s = tot * k / (n - 1)
        while j < len(acc) - 2 and acc[j + 1] < s:
            j += 1
        seg = acc[j + 1] - acc[j]
        t = 0.0 if seg <= 1e-12 else (s - acc[j]) / seg
        a, b = pts[j], pts[j + 1]
        out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def aplicar_mods(ob):
    """Aplica los modificadores de un objeto malla (queda sin modificadores)."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    bpy.data.meshes.remove(old)
    return ob


def aristas_vivas(ob, ang=40.0):
    """Marca como aristas vivas (sharp) las que superan el angulo dado; el resto queda suave."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    lim = math.radians(ang)
    for e in bm.edges:
        if len(e.link_faces) == 2:
            e.smooth = e.calc_face_angle(0.0) < lim
        else:
            e.smooth = True
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def recortar(ob, cortador, operacion="DIFFERENCE"):
    """Booleana exacta aplicada al momento; el cortador auxiliar se elimina."""
    md = ob.modifiers.new("Corte", "BOOLEAN")
    md.object = cortador
    md.operation = operacion
    md.solver = "EXACT"
    aplicar_mods(ob)
    bpy.data.objects.remove(cortador, do_unlink=True)
    return ob


def prisma_y(name, contorno_xz, y0, y1):
    """Extruye un contorno cerrado (x, z) a lo largo de Y entre y0 e y1 (sirve de cortador)."""
    n = len(contorno_xz)
    vs = [(x, y0, z) for x, z in contorno_xz] + [(x, y1, z) for x, z in contorno_xz]
    fs = [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
    fs += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    ob = from_pydata(name, vs, fs, smooth=False)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def bvh_de(obs):
    """Arbol BVH (en coordenadas de mundo) de uno o varios objetos malla, para proyectar piezas."""
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    vs, fs = [], []
    for ob in obs:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        M = ob.matrix_world
        base = len(vs)
        vs += [M @ v.co for v in me.vertices]
        fs += [[base + i for i in p.vertices] for p in me.polygons]
        ev.to_mesh_clear()
    return BVHTree.FromPolygons(vs, fs)


def proyectar(bvh, origen, d, desp=0.0):
    """Lanza un rayo desde origen en direccion d; devuelve el punto de impacto desplazado por la normal."""
    d = Vector(d).normalized()
    hit = bvh.ray_cast(Vector(origen), d)
    if hit[0] is None:
        return None, None
    n = hit[1]
    if n.dot(d) > 0:
        n = -n
    return hit[0] + n * desp, n


def malla_rejilla(name, filas, cerrada_u=False, smooth=True, espesor=0.0):
    """Malla a partir de una rejilla de puntos filas[i][j] (todas las filas del mismo largo)."""
    nf, nc = len(filas), len(filas[0])
    vs = [tuple(p) for f in filas for p in f]
    fs = []
    for i in range(nf - 1):
        for j in range(nc if cerrada_u else nc - 1):
            j2 = (j + 1) % nc
            fs.append((i * nc + j, i * nc + j2, (i + 1) * nc + j2, (i + 1) * nc + j))
    ob = from_pydata(name, vs, fs, smooth=smooth)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-5)
    bm.to_mesh(ob.data)
    bm.free()
    if espesor:
        md = ob.modifiers.new("Espesor", "SOLIDIFY")
        md.thickness = espesor
        md.offset = 0.0
    return ob


def calco(name, bvh, contorno, d, desp=0.006, espesor=0.006, anillos=5, abombado=0.0):
    """Pieza delgada que copia la superficie de la carroceria dentro de un contorno.
    contorno: puntos 3D de origen de rayo (fuera del auto); d: direccion de proyeccion."""
    d = Vector(d).normalized()
    cont = [Vector(p) for p in contorno]
    c = sum(cont, Vector()) / len(cont)
    filas = []
    for k in range(anillos + 1):
        f = 1.0 - k / anillos
        fila = []
        for p in cont:
            o = c + (p - c) * f
            pt, n = proyectar(bvh, o, d, desp + abombado * (1 - f * f))
            if pt is None:
                # el rayo no toca: punto mas cercano de la carroceria a la altura del contorno
                hc = bvh.ray_cast(c, d)
                dist = hc[3] if hc[0] is not None else 1.0
                q = bvh.find_nearest(o + d * dist)
                pt = q[0] + q[1] * desp if q[0] is not None else o + d * dist
            fila.append(pt)
        filas.append(fila)
    return malla_rejilla(name, filas, cerrada_u=True, smooth=True, espesor=espesor)


def linea_sobre(name, bvh, puntos, d, r=0.004, desp=0.0, paso=0.03, cerrada=False):
    """Tubo fino que sigue la superficie (juntas de puertas, molduras); puntos = origenes de rayo."""
    P = [Vector(p) for p in puntos]
    if cerrada:
        P.append(P[0])
    dens = []
    for a, b in zip(P, P[1:]):
        k = max(1, int((b - a).length / paso))
        dens += [a + (b - a) * (i / k) for i in range(k)]
    dens.append(P[-1])
    hits = []
    for o in dens:
        pt, _ = proyectar(bvh, o, d, desp)
        if pt is not None:
            hits.append(pt)
    if len(hits) < 2:
        return None
    return curve_tube(name, hits, r, res=2)


class Acum:
    """Acumula vertices y caras en coordenadas locales para crear una sola malla."""

    def __init__(self):
        self.v, self.f = [], []

    def add(self, vs, fs):
        b = len(self.v)
        self.v += [tuple(p) for p in vs]
        self.f += [tuple(b + i for i in f) for f in fs]

    def revolver(self, prof, seg=48, cerrado=True):
        """Gira un perfil [(radio, axial)] alrededor del eje Y local."""
        n = len(prof)
        vs = []
        for k in range(seg):
            a = math.tau * k / seg
            ca, sa = math.cos(a), math.sin(a)
            vs += [(r * ca, y, r * sa) for r, y in prof]
        fs = []
        for k in range(seg):
            k2 = (k + 1) % seg
            for j in range(n if cerrado else n - 1):
                j2 = (j + 1) % n
                fs.append((k * n + j, k * n + j2, k2 * n + j2, k2 * n + j))
        self.add(vs, fs)

    def prisma(self, base, alto_dir, alto):
        """Prisma desde un poligono convexo 3D (lista) extruido alto*alto_dir."""
        n = len(base)
        top = [tuple(Vector(p) + Vector(alto_dir) * alto) for p in base]
        fs = [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
        fs += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
        self.add(list(base) + top, fs)

    def objeto(self, name, transf=None, espejo=False, smooth=True, angulo=35.0):
        vs = [transf(p) for p in self.v] if transf else self.v
        ob = from_pydata(name, vs, self.f, smooth=smooth)
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(ob.data)
        bm.free()
        if smooth:
            aristas_vivas(ob, angulo)
        return ob
