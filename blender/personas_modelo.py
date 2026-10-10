"""Personas articuladas: hombre y mujer con camisa celeste manga corta + jean o polo plomo + jean,
con casco o con cofia. Cada persona tiene un esqueleto (Armature) y cada pieza del cuerpo esta
emparentada a su hueso, asi se pueden posar en Pose Mode (rotar brazos, codos, rodillas, cabeza...).
Unicos modelos con colores. Metros, piso z=0, miran hacia -Y. Uso: python3 blender/personas_modelo.py"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import *

nueva_escena("Personas")
AQUI = os.path.dirname(os.path.abspath(__file__))

PIEL = mat("Piel", (0.80, 0.58, 0.44), 0.5)
CELESTE = mat("Tela_Celeste", (0.55, 0.76, 0.95), 0.8)
PLOMO = mat("Tela_Plomo", (0.42, 0.44, 0.47), 0.8)
JEAN = mat("Tela_Jean", (0.10, 0.17, 0.35), 0.9)
CUERO = mat("Cuero_Negro", (0.04, 0.04, 0.04), 0.4)
PELO = mat("Pelo_Castano", (0.07, 0.04, 0.02), 0.6)
OJO = mat("Ojo", (0.02, 0.02, 0.02), 0.2)
CASCO = mat("Casco_Blanco", (0.92, 0.92, 0.90), 0.3)
COFIA = mat("Cofia_Blanca", (0.95, 0.95, 0.97), 0.9)
BOTON = mat("Boton", (0.85, 0.85, 0.85), 0.3)


def domo(name, r, loc, escala=(1, 1, 1), corte=0.0, m=None):
    """Media esfera (casco, cofia, pelo): se borran los vertices bajo z = corte*r."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=r)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < corte * r - 1e-6], context="VERTS")
    bmesh.ops.scale(bm, vec=Vector(escala), verts=bm.verts)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(m)
    ob = link(bpy.data.objects.new(name, me))
    ob.location = loc
    md = ob.modifiers.new("Espesor", "SOLIDIFY")
    md.thickness = 0.006
    return ob


TRONCO_H = [(1.49, 0.065, 0.060), (1.46, 0.150, 0.085), (1.42, 0.185, 0.105), (1.34, 0.178, 0.115), (1.24, 0.163, 0.108),
            (1.12, 0.150, 0.100), (1.02, 0.155, 0.102), (0.94, 0.165, 0.108), (0.84, 0.150, 0.100), (0.80, 0.080, 0.070)]
TRONCO_M = [(1.49, 0.060, 0.055), (1.46, 0.135, 0.080), (1.42, 0.165, 0.095), (1.31, 0.152, 0.128), (1.22, 0.140, 0.100),
            (1.10, 0.132, 0.092), (1.02, 0.150, 0.100), (0.94, 0.175, 0.112), (0.84, 0.158, 0.104), (0.80, 0.085, 0.072)]


def tronco(name, X, s, tabla, z0, z1, m):
    """Tramo del tronco entre z0 y z1: anillos superelipticos interpolados de la tabla."""
    n, nz, verts, faces = 28, 12, [], []
    for i in range(nz + 1):
        z = z0 + (z1 - z0) * i / nz
        rx, ry = lerp_table(tabla, z)
        for k in range(n):
            a = k * math.tau / n
            c, d = math.cos(a), math.sin(a)
            verts.append((X + s * rx * math.copysign(abs(c) ** 0.8, c), s * ry * math.copysign(abs(d) ** 0.8, d), s * z))
    for i in range(nz):
        for k in range(n):
            k2 = (k + 1) % n
            faces.append((i * n + k, i * n + k2, (i + 1) * n + k2, (i + 1) * n + k))
    faces.append(tuple(range(n))[::-1])
    faces.append(tuple(range(nz * n, (nz + 1) * n)))
    return from_pydata(name, verts, faces, m=m)


def persona(tag, X, mujer, camisa, gorro):
    s = 0.93 if mujer else 1.0
    P = lambda x, y, z: Vector((X + x * s, y * s, z * s))
    hom = 0.170 if mujer else 0.190          # medio ancho de hombros
    cad = 0.100 if mujer else 0.092          # separacion de caderas
    tela = CELESTE if camisa == "celeste" else PLOMO
    piezas = []                               # (objeto, hueso)

    def add(ob, hueso):
        piezas.append((ob, hueso))
        return ob

    J = {}   # articulaciones
    J["Raiz"] = P(0, 0, 0)
    J["Cadera"], J["Columna"], J["Pecho"] = P(0, 0, 0.95), P(0, 0, 1.10), P(0, 0, 1.30)
    J["Cuello"], J["Cabeza"], J["Coronilla"] = P(0, 0, 1.47), P(0, 0, 1.56), P(0, 0, 1.80)
    for k, sx in (("Izq", 1), ("Der", -1)):
        J["Hombro_" + k] = P(sx * hom, 0.0, 1.43)
        J["Codo_" + k] = P(sx * (hom + 0.055), 0.01, 1.15)
        J["Muneca_" + k] = P(sx * (hom + 0.090), -0.02, 0.90)
        J["Dedos_" + k] = P(sx * (hom + 0.100), -0.03, 0.80)
        J["Cadera_" + k] = P(sx * cad, 0, 0.93)
        J["Rodilla_" + k] = P(sx * (cad + 0.005), -0.01, 0.51)
        J["Tobillo_" + k] = P(sx * (cad + 0.005), 0.02, 0.09)
        J["Punta_" + k] = P(sx * (cad + 0.015), -0.14, 0.03)

    # ---------------- esqueleto ----------------
    arm_d = bpy.data.armatures.new(f"{tag}_Esqueleto")
    arm = link(bpy.data.objects.new(f"{tag}_Esqueleto", arm_d))
    arm.show_in_front = True
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_d.edit_bones

    def hueso(n, a, b, padre=None, conectado=False):
        h = eb.new(n)
        h.head, h.tail = a, b
        if padre:
            h.parent = eb[padre]
            h.use_connect = conectado
        return h

    hueso("Raiz", J["Raiz"], J["Raiz"] + Vector((0, 0.25, 0)))
    hueso("Cadera", J["Cadera"], J["Columna"], "Raiz")
    hueso("Columna", J["Columna"], J["Pecho"], "Cadera", True)
    hueso("Pecho", J["Pecho"], J["Cuello"], "Columna", True)
    hueso("Cuello", J["Cuello"], J["Cabeza"], "Pecho", True)
    hueso("Cabeza", J["Cabeza"], J["Coronilla"], "Cuello", True)
    for k in ("Izq", "Der"):
        hueso("Clavicula_" + k, J["Cuello"] + Vector((0, 0, -0.03)), J["Hombro_" + k], "Pecho")
        hueso("Brazo_" + k, J["Hombro_" + k], J["Codo_" + k], "Clavicula_" + k, True)
        hueso("Antebrazo_" + k, J["Codo_" + k], J["Muneca_" + k], "Brazo_" + k, True)
        hueso("Mano_" + k, J["Muneca_" + k], J["Dedos_" + k], "Antebrazo_" + k, True)
        hueso("Muslo_" + k, J["Cadera_" + k], J["Rodilla_" + k], "Cadera")
        hueso("Pierna_" + k, J["Rodilla_" + k], J["Tobillo_" + k], "Muslo_" + k, True)
        hueso("Pie_" + k, J["Tobillo_" + k], J["Punta_" + k], "Pierna_" + k, True)
    bpy.ops.object.mode_set(mode="OBJECT")

    # ---------------- cuerpo ----------------
    # tronco
    T = TRONCO_M if mujer else TRONCO_H
    add(tronco(f"{tag}_Pantalon_Cadera", X, s, T, 0.80, 1.03, JEAN), "Cadera")
    rx, ry = lerp_table(T, 1.02)
    add(curve_tube(f"{tag}_Correa", [P(rx * 1.02 * math.cos(a), ry * 1.04 * math.sin(a), 1.02) for a in
                                    [k * math.tau / 32 for k in range(32)]], 0.013 * s, m=CUERO, cyclic=True), "Cadera")
    add(box(f"{tag}_Hebilla_Correa", (0.05 * s, 0.012, 0.035 * s), P(0, -ry * 1.04 - 0.008, 1.02), m=BOTON), "Cadera")
    add(tronco(f"{tag}_Camisa_Abdomen", X, s, T, 1.02, 1.24, tela), "Columna")
    add(tronco(f"{tag}_Camisa_Torso", X, s, T, 1.23, 1.49, tela), "Pecho")
    for sx, k in ((1, "Izq"), (-1, "Der")):
        add(esfera(f"{tag}_Camisa_Hombro_{k}", 0.052 * s, J["Hombro_" + k] + Vector((-sx * 0.012, 0, -0.012)), m=tela), "Clavicula_" + k)
    # detalle de camisa o polo
    if camisa == "celeste":
        for sx, k in ((1, "Izq"), (-1, "Der")):
            add(beam(f"{tag}_Camisa_Solapa_Cuello_{k}", P(sx * 0.02, -0.075, 1.43), P(sx * 0.075, -0.045, 1.475), 0.012,
                     t2=0.045, m=CELESTE), "Pecho")
        add(box(f"{tag}_Camisa_Bolsillo", (0.075 * s, 0.006, 0.08 * s), P(0.075, -lerp_table(T, 1.36)[1] + 0.004, 1.36), rot=(math.radians(-8), 0, 0), m=CELESTE), "Pecho")
        for j in range(5):
            z = 1.40 - j * 0.085
            par = "Pecho" if z > 1.24 else "Columna" if z > 1.06 else "Cadera"
            yy = -lerp_table(T, z)[1] - 0.002
            add(cyl(f"{tag}_Camisa_Boton", 0.006 * s, 0.004, P(0, yy, z), axis="Y", verts=12, m=BOTON), par)
    else:
        add(curve_tube(f"{tag}_Polo_Cuello", [P(0.065 * math.cos(a), 0.055 * math.sin(a) + 0.005, 1.46 + 0.012 * math.sin(a)) for a in
                                              [k * math.tau / 24 for k in range(24)]], 0.014 * s, m=PLOMO, cyclic=True), "Pecho")
        add(box(f"{tag}_Polo_Tapeta", (0.032 * s, 0.006, 0.12 * s), P(0, -lerp_table(T, 1.40)[1] - 0.001, 1.40), rot=(math.radians(-20), 0, 0), m=PLOMO), "Pecho")
        for j in range(2):
            add(cyl(f"{tag}_Polo_Boton", 0.0055 * s, 0.004, P(0, -lerp_table(T, 1.42 - j * 0.04)[1] - 0.004, 1.42 - j * 0.04), axis="Y", verts=12, m=BOTON), "Pecho")
    # cuello y cabeza
    add(capsula(f"{tag}_Cuello", J["Cuello"] + Vector((0, 0, -0.04)), J["Cabeza"] + Vector((0, 0, 0.03)), 0.048 * s, m=PIEL), "Cuello")
    cab = P(0, 0.0, 1.665)
    add(esfera(f"{tag}_Cabeza", 1, cab, (0.080 * s, 0.096 * s, 0.112 * s), m=PIEL), "Cabeza")
    add(esfera(f"{tag}_Mandibula", 1, cab + Vector((0, -0.015, -0.055 * s)), (0.068 * s, 0.075 * s, 0.06 * s), m=PIEL), "Cabeza")
    add(capsula(f"{tag}_Nariz", cab + Vector((0, -0.088 * s, 0.005)), cab + Vector((0, -0.102 * s, -0.025 * s)), 0.012 * s, m=PIEL), "Cabeza")
    for sx, k in ((1, "Izq"), (-1, "Der")):
        add(esfera(f"{tag}_Ojo_{k}", 0.010 * s, cab + Vector((sx * 0.032 * s, -0.083 * s, 0.018 * s)), m=OJO), "Cabeza")
        add(box(f"{tag}_Ceja_{k}", (0.032 * s, 0.008, 0.007), cab + Vector((sx * 0.033 * s, -0.087 * s, 0.040 * s)), m=PELO), "Cabeza")
        add(esfera(f"{tag}_Oreja_{k}", 1, cab + Vector((sx * 0.080 * s, 0.005, 0.0)), (0.012 * s, 0.022 * s, 0.032 * s), m=PIEL), "Cabeza")
    add(box(f"{tag}_Boca", (0.034 * s, 0.006, 0.006), cab + Vector((0, -0.084 * s, -0.045 * s)), m=OJO), "Cabeza")
    # pelo
    if gorro == "casco" or not mujer:
        add(domo(f"{tag}_Pelo", 0.105 * s, cab + Vector((0, 0.008, 0.01)), (0.80, 0.97, 1.0), corte=-0.15, m=PELO), "Cabeza")
    if mujer:
        if gorro == "casco":
            add(capsula(f"{tag}_Pelo_Cola", cab + Vector((0, 0.095 * s, 0.0)), cab + Vector((0, 0.12 * s, -0.20 * s)), 0.030 * s, 0.018 * s, m=PELO), "Cabeza")
        else:
            add(domo(f"{tag}_Pelo", 0.105 * s, cab + Vector((0, 0.008, 0.01)), (0.80, 0.97, 1.0), corte=-0.15, m=PELO), "Cabeza")
    # casco o cofia
    if gorro == "casco":
        add(domo(f"{tag}_Casco_Copa", 0.125 * s, cab + Vector((0, 0.004, 0.035 * s)), (0.88, 1.05, 0.95), corte=0.0, m=CASCO), "Cabeza")
        add(beam(f"{tag}_Casco_Nervio", cab + Vector((0, -0.12 * s, 0.05 * s)), cab + Vector((0, 0.12 * s, 0.05 * s)), 0.02 * s, m=CASCO), "Cabeza")
        add(curve_tube(f"{tag}_Casco_Ala", [cab + Vector((0.112 * s * math.cos(a), 0.132 * s * math.sin(a), 0.035 * s)) for a in
                                            [k * math.tau / 32 for k in range(32)]], 0.008 * s, m=CASCO, cyclic=True), "Cabeza")
        add(domo(f"{tag}_Casco_Visera", 0.06 * s, cab + Vector((0, -0.125 * s, 0.035 * s)), (1.3, 0.8, 0.12), corte=0.0, m=CASCO), "Cabeza")
        add(curve_tube(f"{tag}_Casco_Suspension", [cab + Vector((0.083 * s * math.cos(a), 0.10 * s * math.sin(a), 0.045 * s)) for a in
                                                   [k * math.tau / 24 for k in range(24)]], 0.006 * s, m=CUERO, cyclic=True), "Cabeza")
    else:
        add(domo(f"{tag}_Cofia", 0.130 * s, cab + Vector((0, 0.025, 0.02 * s)), (1.0, 1.12, 0.78), corte=-0.30, m=COFIA), "Cabeza")
        # el elastico baja por la frente y sube por la nuca
        anillo = [cab + Vector((0.124 * s * math.cos(a), 0.139 * s * math.sin(a) + 0.025, -0.01 * s))
                  for a in [k * math.tau / 32 for k in range(32)]]
        add(curve_tube(f"{tag}_Cofia_Elastico", anillo, 0.009 * s, m=COFIA, cyclic=True), "Cabeza")
    # brazos
    for sx, k in ((1, "Izq"), (-1, "Der")):
        h, c, w, d = J["Hombro_" + k], J["Codo_" + k], J["Muneca_" + k], J["Dedos_" + k]
        add(capsula(f"{tag}_Manga_Corta_{k}", h + (h - c).normalized() * 0.02, h.lerp(c, 0.50), 0.052 * s, 0.048 * s, m=tela), "Brazo_" + k)
        add(capsula(f"{tag}_Brazo_{k}", h, c, 0.046 * s, 0.039 * s, m=PIEL), "Brazo_" + k)
        add(capsula(f"{tag}_Antebrazo_{k}", c, w, 0.039 * s, 0.028 * s, m=PIEL), "Antebrazo_" + k)
        add(capsula(f"{tag}_Mano_Palma_{k}", w, w.lerp(d, 0.55), 0.030 * s, 0.032 * s, m=PIEL), "Mano_" + k)
        add(capsula(f"{tag}_Mano_Dedos_{k}", w.lerp(d, 0.55), d, 0.026 * s, 0.018 * s, m=PIEL), "Mano_" + k)
        add(capsula(f"{tag}_Mano_Pulgar_{k}", w + Vector((0, -0.025 * s, -0.02 * s)), w + Vector((-sx * 0.005, -0.04 * s, -0.07 * s)), 0.012 * s, 0.010 * s, m=PIEL), "Mano_" + k)
    # piernas
    for sx, k in ((1, "Izq"), (-1, "Der")):
        hp, kn, an, tp = J["Cadera_" + k], J["Rodilla_" + k], J["Tobillo_" + k], J["Punta_" + k]
        add(capsula(f"{tag}_Pantalon_Muslo_{k}", hp + Vector((0, 0, 0.03)), kn, 0.082 * s, 0.058 * s, m=JEAN), "Muslo_" + k)
        add(capsula(f"{tag}_Pantalon_Pierna_{k}", kn, an + Vector((0, 0, 0.03)), 0.056 * s, 0.050 * s, m=JEAN), "Pierna_" + k)
        add(esfera(f"{tag}_Zapato_{k}", 1, an.lerp(tp, 0.42) + Vector((0, 0.01, -0.045 * s)), (0.048 * s, 0.135 * s, 0.045 * s), m=CUERO), "Pie_" + k)
        add(box(f"{tag}_Suela_{k}", (0.09 * s, 0.27 * s, 0.018), Vector((an.x, (an.y + tp.y) / 2 + 0.01, 0.009)), bevel=0.008, m=CUERO), "Pie_" + k)

    # emparentar cada pieza a su hueso conservando su posicion
    bpy.context.view_layer.update()
    for ob, hb in piezas:
        mw = ob.matrix_world.copy()
        ob.parent = arm
        ob.parent_type = "BONE"
        ob.parent_bone = hb
        bpy.context.view_layer.update()
        ob.matrix_world = mw


GENTE = []
for mujer in (False, True):
    for camisa in ("celeste", "plomo"):
        for gorro in ("casco", "cofia"):
            GENTE.append((("Mujer" if mujer else "Hombre") + "_" + ("Camisa_Celeste" if camisa == "celeste" else "Polo_Plomo")
                          + "_" + ("Casco" if gorro == "casco" else "Cofia"), mujer, camisa, gorro))
for i, (tag, mujer, camisa, gorro) in enumerate(GENTE):
    grupo(f"{i + 1:02d}_{tag}")
    persona(tag, i * 0.9, mujer, camisa, gorro)

finalizar("personas_modelo.blend", AQUI)
