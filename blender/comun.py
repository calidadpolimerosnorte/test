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
