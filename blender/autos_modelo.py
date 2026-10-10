"""Cinco autos de modelos reales comunes en Peru (sin logos ni textos):
  01 Toyota Corolla sedan (E210)      02 Suzuki Swift hatchback (2024)
  03 Toyota RAV4 SUV (XA50)           04 Toyota Hilux doble cabina (AN120)
  05 Toyota Hiace Commuter techo alto (H300)
Medidas exteriores reales (largo, ancho, alto, distancia entre ejes, trocha, neumaticos).
Solo los vehiculos: sin materiales, sin animacion, sin piso, luces ni camaras.
Metros, piso z=0, frente hacia +X; cada auto en su coleccion, separados 3 m en Y.

La carroceria se arma como una sola superficie densa de secciones transversales
(perfil lateral, ancho en planta, caida de costados y techo redondeado propios de cada modelo);
los arcos de rueda se recortan con booleana y las piezas finas (vidrios, faros, parrillas,
juntas de puertas, molduras) se proyectan sobre la carroceria para seguir su curvatura.
Uso: python3 blender/autos_modelo.py"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import *

AQUI = os.path.dirname(os.path.abspath(__file__))
nueva_escena("Autos")


# ---------------------------------------------------------------------------
# Superficie de la carroceria
# ---------------------------------------------------------------------------
def tabla(pts):
    return curva(pts)


def ancho_planta(tab, xF, xR, Lf, ef, Lr, er):
    """Medio ancho en planta con esquinas redondeadas (elipticas) adelante y atras."""
    base = tabla(tab)

    def W(x):
        w = base(x)
        d = xF - x
        if d < Lf:
            w *= ef + (1 - ef) * math.sqrt(max(0.0, 1 - (1 - d / Lf) ** 2))
        d = x - xR
        if d < Lr:
            w *= er + (1 - er) * math.sqrt(max(0.0, 1 - (1 - d / Lr) ** 2))
        return w
    return W


def seccion(P, x, NH):
    """Medio perfil transversal (y>=0) desde el centro inferior hasta el centro del techo."""
    zb, zs, zt, W = P["zb"](x), P["zs"](x), P["zt"](x), P["W"](x)
    zt = max(zt, zs + 0.012)
    n, kf, gz = P["n"](x), P["kf"](x), P["gz"]
    rbx, rbz = P.get("rb", (0.05, 0.07))
    side = []
    M = 30
    for i in range(M + 1):
        t = 0.5 - 0.5 * math.cos(math.pi * i / M)
        z = zb + (zs - zb) * t
        d = z - zb
        y = W * gz(z)
        if d < rbz:
            y -= rbx * (1 - math.sqrt(max(0.0, 1 - (1 - d / rbz) ** 2)))
        side.append((y, z))
    Ws = side[-1][0]
    top = []
    K = 44
    for i in range(1, K + 1):
        th = (math.pi / 2) * (0.5 - 0.5 * math.cos(math.pi * i / K))
        c, s = math.cos(th), math.sin(th)
        v = s ** (2 / n)
        h = c ** (2 / n) if c > 1e-9 else 0.0
        top.append((Ws * h * (1 - (1 - kf) * v), zs + (zt - zs) * v))
    half = [(0.0, zb), (side[0][0] * 0.5, zb)] + side + top
    return remuestrear(half, NH, peso_giro=0.05)


def estaciones(xF, xR, paso=0.03, fino=0.12, extra=()):
    xs = set()
    n = int((xF - xR) / paso)
    for i in range(n + 1):
        xs.add(round(xF - (xF - xR) * i / n, 5))
    for k in range(1, 14):
        f = fino * (1 - math.cos(math.pi / 2 * k / 14))
        xs.add(round(xF - f, 5))
        xs.add(round(xR + f, 5))
    for e in extra:
        xs.add(round(e, 5))
    return sorted(xs, reverse=True)


def solido_secciones(name, P, xs, NH=72):
    """Malla cerrada: anillos de secciones + tapas en escalera en los extremos."""
    R = 2 * NH - 2
    verts = []
    for x in xs:
        h = seccion(P, x, NH)
        verts += [(x, y, z) for y, z in h] + [(x, -h[i][0], h[i][1]) for i in range(NH - 2, 0, -1)]
    faces = []
    for r in range(len(xs) - 1):
        for j in range(R):
            j2 = (j + 1) % R
            faces.append((r * R + j, r * R + j2, (r + 1) * R + j2, (r + 1) * R + j))

    def m(i):
        return i if i in (0, NH - 1) else R - i
    for r in (0, len(xs) - 1):
        b = r * R
        for i in range(NH - 1):
            q = []
            for v in (b + i, b + i + 1, b + m(i + 1), b + m(i)):
                if v not in q:
                    q.append(v)
            faces.append(tuple(q))
    ob = from_pydata(name, verts, faces)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def contorno_arco(xa, za, R, n=2.0, a0=-14.0, k=56, abajo=-0.3):
    pts = []
    for i in range(k + 1):
        a = math.radians(a0 + (180 - 2 * a0) * i / k)
        c, s = math.cos(a), math.sin(a)
        pts.append((xa + R * math.copysign(abs(c) ** (2 / n), c), za + R * math.copysign(abs(s) ** (2 / n), s)))
    return pts + [(pts[-1][0], abajo), (pts[0][0], abajo)]


def cortar_arcos(ob, arcos):
    for (xa, za, R, n) in arcos:
        cut = prisma_y("aux_corte", contorno_arco(xa, za, R, n), -3, 3)
        recortar(ob, cut)
    aristas_vivas(ob, 50)
    return ob


# ---------------------------------------------------------------------------
# Piezas proyectadas sobre la carroceria
# ---------------------------------------------------------------------------
def aleta_arco(name, bvh, s, xa, za, R, n, ancho, sale, a0=-10, k=44):
    """Moldura / guardafango ensanchado que sigue el arco de rueda."""
    filas = []
    for dr, off in ((-0.006, sale), (ancho * 0.3, sale * 0.92), (ancho * 0.7, sale * 0.5), (ancho, 0.003)):
        fila = []
        for i in range(k + 1):
            a = math.radians(a0 + (180 - 2 * a0) * i / k)
            c, sn = math.cos(a), math.sin(a)
            rr = R + dr
            x = xa + rr * math.copysign(abs(c) ** (2 / n), c)
            z = za + rr * math.copysign(abs(sn) ** (2 / n), sn)
            pt, _ = proyectar(bvh, (x, s * 3, z), (0, -s, 0), off)
            if pt is None:
                pt = Vector((x, s * 0.9, z))
            fila.append(pt)
        filas.append(fila)
    labio = [Vector((p.x, p.y - s * 0.05, p.z)) for p in filas[0]]
    ob = malla_rejilla(name, [labio] + filas, espesor=0.006)
    return ob


def vidrio_lado(name, bvh, s, x0, x1, zbot, ztop, nx=30, nz=6, desp=0.006):
    filas = []
    for j in range(nz + 1):
        fila = []
        for i in range(nx + 1):
            x = x0 + (x1 - x0) * i / nx
            zb, zt = zbot(x), ztop(x)
            z = zb + max(0.0, zt - zb) * j / nz
            pt, _ = proyectar(bvh, (x, s * 3, z), (0, -s, 0), desp)
            fila.append(pt if pt is not None else Vector((x, s * 0.5, z)))
        filas.append(fila)
    return malla_rejilla(name, filas, espesor=0.005)


def vidrio_arriba(name, bvh, x0, x1, ylim, nx=16, ny=20, desp=0.006):
    filas = []
    for i in range(nx + 1):
        x = x0 + (x1 - x0) * i / nx
        yl = ylim(x)
        fila = []
        for j in range(ny + 1):
            y = -yl + 2 * yl * j / ny
            pt, _ = proyectar(bvh, (x, y, 5), (0, 0, -1), desp)
            fila.append(pt if pt is not None else Vector((x, y, 1)))
        filas.append(fila)
    return malla_rejilla(name, filas, espesor=0.005)


def vidrio_atras(name, bvh, z0, z1, ylim, xo, nz=14, ny=20, desp=0.006, frente=False):
    d = (-1, 0, 0) if frente else (1, 0, 0)
    filas = []
    for i in range(nz + 1):
        z = z0 + (z1 - z0) * i / nz
        yl = ylim(z)
        fila = []
        for j in range(ny + 1):
            y = -yl + 2 * yl * j / ny
            pt, _ = proyectar(bvh, (xo, y, z), d, desp)
            fila.append(pt if pt is not None else Vector((xo, y, z)))
        filas.append(fila)
    return malla_rejilla(name, filas, espesor=0.005)


def plano_oblicuo(bvh, centro, d):
    """Punto de la carroceria visto desde la direccion d y base (e1 hacia afuera, e2 hacia arriba)."""
    d = Vector(d).normalized()
    hit, _ = proyectar(bvh, Vector(centro) - d * 2.0, d)
    if hit is None:
        hit = Vector(centro)
    e1 = d.cross(Vector((0, 0, 1)))
    if e1.length < 1e-6:
        e1 = Vector((0, 1, 0))
    e1.normalize()
    if e1.y * (1 if centro[1] >= 0 else -1) < 0:
        e1 = -e1
    e2 = e1.cross(d).normalized()
    if e2.z < 0:
        e2 = -e2
    return hit, e1, e2, d


def pieza_oblicua(name, bvh, centro, d, uv, desp=0.004, espesor=0.01, abombado=0.0, anillos=5):
    hit, e1, e2, d = plano_oblicuo(bvh, centro, d)
    org = [hit - d * 1.0 + e1 * u + e2 * v for u, v in uv]
    return calco(name, bvh, org, d, desp=desp, espesor=espesor, anillos=anillos, abombado=abombado)


def frontal(name, bvh, xo, yz, desp=0.004, espesor=0.01, atras=False, abombado=0.0):
    d = (1, 0, 0) if atras else (-1, 0, 0)
    return calco(name, bvh, [(xo, y, z) for y, z in yz], d, desp=desp, espesor=espesor, abombado=abombado)


def lateral(name, bvh, s, xz, desp=0.004, espesor=0.008, abombado=0.0):
    return calco(name, bvh, [(x, s * 3, z) for x, z in xz], (0, -s, 0), desp=desp, espesor=espesor,
                 abombado=abombado)


def superior(name, bvh, xy, desp=0.004, espesor=0.008):
    return calco(name, bvh, [(x, y, 5) for x, y in xy], (0, 0, -1), desp=desp, espesor=espesor)


def tubos(name, polilineas, r, res=2):
    """Una sola curva con varios tramos (barras de parrilla, rieles)."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = r
    cu.bevel_resolution = 2
    cu.resolution_u = res
    for pts in polilineas:
        if len(pts) < 2:
            continue
        sp = cu.splines.new("POLY")
        sp.points.add(len(pts) - 1)
        for q, v in zip(sp.points, pts):
            q.co = (v[0], v[1], v[2], 1)
    return link(bpy.data.objects.new(name, cu))


def sobre(bvh, puntos, d, desp=0.0, paso=0.025):
    P = [Vector(p) for p in puntos]
    dens = []
    for a, b in zip(P, P[1:]):
        k = max(1, int((b - a).length / paso))
        dens += [a + (b - a) * (i / k) for i in range(k)]
    dens.append(P[-1])
    out = []
    for o in dens:
        pt, _ = proyectar(bvh, o, d, desp)
        if pt is not None:
            out.append(pt)
    return out


def barras_parrilla(name, bvh, xo, yz, niveles, r=0.006, desp=0.011, vertical=False, margen=0.015):
    """Barras horizontales (o verticales) recortadas al contorno de la parrilla."""
    pol = list(yz)
    lineas = []
    for lv in niveles:
        cortes = []
        for (a, b) in zip(pol, pol[1:] + pol[:1]):
            ia, ib = (0, 1) if vertical else (1, 0)
            if (a[ia] - lv) * (b[ia] - lv) < 0:
                t = (lv - a[ia]) / (b[ia] - a[ia])
                cortes.append(a[ib] + (b[ib] - a[ib]) * t)
        if len(cortes) < 2:
            continue
        c0, c1 = min(cortes) + margen, max(cortes) - margen
        if c1 <= c0:
            continue
        if vertical:
            pts = [(xo, lv, c0), (xo, lv, c1)]
        else:
            pts = [(xo, c0, lv), (xo, c1, lv)]
        lineas.append(sobre(bvh, pts, (-1, 0, 0), desp))
    return tubos(name, lineas, r)


def superelipsoide(name, c, abc, n=3.0, seg=24, rot=None):
    """Caja redondeada suave (espejos, manijas, neblineros)."""
    a, b, cc = abc
    e = 2.0 / n
    vs, fs = [], []
    nu, nv = seg, seg // 2
    for j in range(nv + 1):
        ph = -math.pi / 2 + math.pi * j / nv
        cp, sp = math.cos(ph), math.sin(ph)
        for i in range(nu):
            th = math.tau * i / nu
            ct, st = math.cos(th), math.sin(th)
            f = lambda q: math.copysign(abs(q) ** e, q)
            vs.append((a * f(cp) * f(ct), b * f(cp) * f(st), cc * f(sp)))
    for j in range(nv):
        for i in range(nu):
            i2 = (i + 1) % nu
            fs.append((j * nu + i, j * nu + i2, (j + 1) * nu + i2, (j + 1) * nu + i))
    ob = from_pydata(name, vs, fs)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    ob.location = c
    if rot:
        ob.rotation_euler = rot
    return ob


def sobre_normal(bvh, origen, d, desp):
    pt, n = proyectar(bvh, origen, d, desp)
    return pt, n


def manija(name, bvh, s, x, z, largo=0.13, alto=0.028):
    pt, n = proyectar(bvh, (x, s * 3, z), (0, -s, 0), 0.010)
    if pt is None:
        return
    ob = superelipsoide(name, pt, (largo / 2, 0.016, alto / 2), n=3.2, seg=20)
    ob.rotation_euler = (0, 0, math.atan2(n.y, n.x) - math.copysign(math.pi / 2, s))
    return ob


# ---------------------------------------------------------------------------
# Ruedas
# ---------------------------------------------------------------------------
def rueda_auto(pref, c, s, ancho_mm, perfil, aro, estilo):
    """Neumatico con medida real (p. ej. 205/55 R16) y llanta con rayos segun el modelo."""
    w = ancho_mm / 1000.0
    rb = aro * 0.0254 / 2
    ro = rb + w * perfil / 100.0
    h = ro - rb
    cx, cy, cz = c

    def T(p):
        return (cx + p[0], cy + s * p[1], cz + p[2])

    # neumatico: perfil con flanco abombado y ranuras en la banda
    prof = [(rb + 0.004, -0.40 * w), (rb + 0.25 * h, -0.49 * w), (rb + 0.6 * h, -0.50 * w),
            (ro - 0.03, -0.48 * w), (ro - 0.008, -0.44 * w)]
    banda = []
    for a in (-0.42, -0.30, -0.26, -0.10, -0.06, 0.06, 0.10, 0.26, 0.30, 0.42):
        banda.append(a)
    for k, a in enumerate(banda):
        rr = ro - (0.009 if k in (2, 3, 6, 7) else 0.0)
        prof.append((rr, a * w))
    prof += [(ro - 0.008, 0.44 * w), (ro - 0.03, 0.48 * w), (rb + 0.6 * h, 0.50 * w), (rb + 0.25 * h, 0.49 * w),
             (rb + 0.004, 0.40 * w), (rb - 0.004, 0.0)]
    A = Acum()
    A.revolver(prof, seg=64)
    A.objeto(f"{pref}_Neumatico", T, angulo=60)

    # aro (barril) de la llanta
    B = Acum()
    barril = [(rb - 0.012, -0.40 * w), (rb + 0.010, -0.42 * w), (rb + 0.012, -0.37 * w), (rb - 0.006, -0.33 * w),
              (rb - 0.010, 0.28 * w), (rb + 0.002, 0.36 * w), (rb + 0.014, 0.41 * w), (rb + 0.010, 0.45 * w),
              (rb - 0.010, 0.44 * w), (rb - 0.024, 0.36 * w), (rb - 0.024, -0.36 * w)]
    B.revolver(barril, seg=64)
    # cubo central
    B.revolver([(0.0, 0.20 * w), (0.085, 0.20 * w), (0.085, 0.33 * w), (0.06, 0.36 * w), (0.0, 0.36 * w)], seg=32,
               cerrado=True)
    ri, re = 0.07, rb - 0.012
    ai, ae = 0.36 * w, 0.42 * w     # cara exterior de los rayos (centro hundido hacia el borde)

    def rayo(f1, f2, r1, r2, w1, w2, esp=0.022):
        A2 = Vector((r1 * math.cos(f1), r1 * math.sin(f1)))
        B2 = Vector((r2 * math.cos(f2), r2 * math.sin(f2)))
        dd = (B2 - A2).normalized()
        pp = Vector((-dd.y, dd.x))
        cs = [(A2 + pp * w1, ai), (B2 + pp * w2, ae), (B2 - pp * w2, ae), (A2 - pp * w1, ai)]
        base = [(q.x, a, q.y) for q, a in cs]
        B.prisma(base, (0, -1, 0), esp)

    if estilo == "v10":        # Corolla: 5 pares de rayos finos en V
        for k in range(5):
            f = math.tau * k / 5
            for dlt in (-0.16, 0.16):
                rayo(f, f + dlt, ri, re, 0.012, 0.014)
    elif estilo == "multi":    # Swift: 8 rayos dobles delgados
        for k in range(8):
            f = math.tau * k / 8
            for dlt in (-0.07, 0.07):
                rayo(f + dlt * 0.3, f + dlt, ri, re, 0.008, 0.011)
    elif estilo == "5d":       # RAV4: 5 rayos dobles anchos
        for k in range(5):
            f = math.tau * k / 5
            for dlt in (-0.13, 0.13):
                rayo(f + dlt * 0.4, f + dlt, ri, re, 0.020, 0.024, esp=0.03)
    elif estilo == "6":        # Hilux: 6 rayos gruesos
        for k in range(6):
            f = math.tau * k / 6
            rayo(f, f, ri, re, 0.030, 0.042, esp=0.035)
    else:                       # Hiace: llanta de acero con disco y ventanas
        B.revolver([(0.07, 0.34 * w), (rb - 0.02, 0.30 * w), (rb - 0.02, 0.26 * w), (0.07, 0.30 * w)], seg=48)
        for k in range(8):
            f = math.tau * (k + 0.5) / 8
            rayo(f, f, rb * 0.42, rb * 0.62, 0.01, 0.01, esp=0.005)
    B.objeto(f"{pref}_Llanta", T, angulo=40)

    # tapa central, pernos, disco y mordaza de freno
    nper = 6 if estilo in ("6", "acero") else 5
    C = Acum()
    C.revolver([(0.0, 0.37 * w), (0.040, 0.37 * w), (0.036, 0.385 * w), (0.0, 0.39 * w)], seg=24)
    C.objeto(f"{pref}_Tapa_Centro", T, angulo=50)
    D = Acum()
    rp = 0.057 if nper == 5 else 0.063
    for k in range(nper):
        f = math.tau * k / nper + 0.3
        px, pz = rp * math.cos(f), rp * math.sin(f)
        pts = [(px + 0.010 * math.cos(math.tau * i / 6), 0.36 * w, pz + 0.010 * math.sin(math.tau * i / 6))
               for i in range(6)]
        D.prisma(pts, (0, 1, 0), 0.016)
    D.objeto(f"{pref}_Pernos", T, smooth=False)
    E = Acum()
    rd = rb * 0.80
    E.revolver([(0.06, -0.08 * w), (rd, -0.08 * w), (rd, 0.04 * w), (0.06, 0.04 * w)], seg=48)
    E.objeto(f"{pref}_Disco_Freno", T, angulo=40)
    F = Acum()
    ang0 = math.radians(150)      # mordaza detras del eje, arriba
    pts = []
    for i in range(7):
        f = ang0 - 0.45 + 0.9 * i / 6
        pts.append((rd * 1.06 * math.cos(f), 0.06 * w, rd * 1.06 * math.sin(f)))
    for i in range(7):
        f = ang0 + 0.45 - 0.9 * i / 6
        pts.append((rd * 0.72 * math.cos(f), 0.06 * w, rd * 0.72 * math.sin(f)))
    F.prisma(pts, (0, -1, 0), 0.14 * w + 0.03)
    F.objeto(f"{pref}_Mordaza_Freno", T, angulo=40)


# ---------------------------------------------------------------------------
# Auto generico parametrizado
# ---------------------------------------------------------------------------
class Auto:
    def __init__(self, pref, d):
        self.p = pref
        self.d = d
        self.xF, self.xR = d["L"] / 2, -d["L"] / 2
        self.xfa = self.xF - d["vf"]
        self.xra = self.xfa - d["eje"]
        P = {k: tabla(d[k]) for k in ("zt", "zs", "zb", "n", "kf")}
        P["gz"] = tabla(d["gz"])
        P["W"] = ancho_planta(d["W"], self.xF if "xFc" not in d else d["xFc"], self.xR if "xRc" not in d else d["xRc"],
                              *d["esq"])
        P["rb"] = d.get("rb", (0.05, 0.07))
        self.P = P
        self.r = (d["aro"] * 0.0254 / 2 + d["neu"][0] / 1000 * d["neu"][1] / 100)

    def n(self, s):
        return "Izq" if s > 0 else "Der"

    def carroceria(self, nombre="Carroceria", xF=None, xR=None, arcos=None):
        xF = self.xF if xF is None else xF
        xR = self.xR if xR is None else xR
        xs = estaciones(xF, xR)
        ob = solido_secciones(f"{self.p}_{nombre}", self.P, xs)
        self.bvh = bvh_de([ob])
        if arcos is None:
            arcos = [(x, self.r, self.r + self.d["holgura"], self.d.get("forma_arco", 2.0))
                     for x in (self.xfa, self.xra)]
        cortar_arcos(ob, arcos)
        self.body = ob
        return ob

    # perfiles utiles
    def ws(self, x):
        return self.P["W"](x) * self.P["gz"](self.P["zs"](x))

    def we(self, x):
        return self.ws(x) * self.P["kf"](x)

    def z_ventana(self, x, f, da, dc):
        zs, zt = self.P["zs"], self.P["zt"]
        return zs(x) + f * (min(zt(x + da), zt(x - dc)) - zs(x))

    def ruedas(self, estilo):
        d = self.d
        for x, nm, tr in ((self.xfa, "Delantera", d["trocha"][0]), (self.xra, "Trasera", d["trocha"][1])):
            for s in (1, -1):
                rueda_auto(f"{self.p}_Rueda_{nm}_{self.n(s)}", (x, s * tr / 2, self.r - 0.004), s,
                           d["neu"][0], d["neu"][1], d["aro"], estilo)

    def aletas(self, ancho, sale, n=None, a0=-10):
        for x, nm in ((self.xfa, "Delantera"), (self.xra, "Trasera")):
            for s in (1, -1):
                aleta_arco(f"{self.p}_Moldura_Arco_{nm}_{self.n(s)}", self.bvh, s, x, self.r,
                           self.r + self.d["holgura"], n or self.d.get("forma_arco", 2.0), ancho, sale, a0=a0)

    def ventanas(self, cortes, f=0.86, da=0.10, dc=0.10, nombres=None, zmin=0.02):
        """cortes: lista de (x_ini, x_fin) por ventana (de adelante hacia atras)."""
        zs = self.P["zs"]
        zbot = lambda x: zs(x) + zmin
        ztop = lambda x: self.z_ventana(x, f, da, dc) - 0.0
        nombres = nombres or [f"Ventana_{i + 1}" for i in range(len(cortes))]
        for s in (1, -1):
            for (x0, x1), nm in zip(cortes, nombres):
                vidrio_lado(f"{self.p}_{nm}_{self.n(s)}", self.bvh, s, x1, x0, zbot, ztop)

    def juntas_puerta(self, puertas, f=0.86, da=0.10, dc=0.10, off=0.028, zr=None, nombre="Junta_Puerta"):
        """Lineas de corte de puertas proyectadas (borde delantero, marco de ventana, borde trasero)."""
        zs = self.P["zs"]
        zr = zr if zr is not None else self.P["zb"](0) + 0.07
        for s in (1, -1):
            for k, pu in enumerate(puertas):
                x0, x1, marco = pu[:3]
                x0t = pu[3] if len(pu) > 3 else x0
                pts = [(x0, zr), (x0t, zs(x0t) + 0.0)]
                x0 = x0t
                if marco:
                    n = 40
                    for i in range(n + 1):
                        x = x0 - (x0 - x1) * i / n
                        zt = self.z_ventana(x, f, da, dc) + off
                        if zt > zs(x) + 0.02:
                            pts.append((x, zt))
                pts += [(x1, zs(x1))]
                # borde inferior: sigue el arco de rueda cuando la puerta lo alcanza
                n = 40
                for i in range(n + 1):
                    x = x1 + (pu[0] - x1) * i / n
                    pts.append((x, self.z_bajo(x, zr)))
                pts = [(x, max(z, self.z_bajo(x, zr))) for x, z in pts]
                lin = sobre(self.bvh, [(x, s * 3, z) for x, z in pts], (0, -s, 0), 0.0)
                tubos(f"{self.p}_{nombre}_{k + 1}_{self.n(s)}", [lin], 0.0035)

    def z_bajo(self, x, zr):
        """Altura minima de una junta: sobre el umbral o por encima del arco de rueda."""
        R = self.r + self.d["holgura"] + 0.035
        n = self.d.get("forma_arco", 2.0)
        z = zr
        for xa in (self.xfa, self.xra):
            dx = abs(x - xa) / R
            if dx < 1:
                z = max(z, self.r + R * (1 - dx ** n) ** (1 / n))
        return z

    def espejos(self, x, z, largo=0.20, alto=0.13, prof=0.09):
        for s in (1, -1):
            pt, n = proyectar(self.bvh, (x, s * 3, z), (0, -s, 0), 0.0)
            if pt is None:
                continue
            c = pt + Vector((-0.03, s * (largo / 2 + 0.06), 0.04))
            ob = superelipsoide(f"{self.p}_Espejo_Retrovisor_{self.n(s)}", c, (prof / 2, largo / 2, alto / 2), n=3.2)
            ob.rotation_euler = (0, 0, -s * 0.08)
            superelipsoide(f"{self.p}_Espejo_Luna_{self.n(s)}", c + Vector((-prof / 2 + 0.004, 0, 0)),
                           (0.006, largo / 2 - 0.012, alto / 2 - 0.012), n=4, seg=16).rotation_euler = (0, 0, -s * 0.08)
            beam(f"{self.p}_Espejo_Brazo_{self.n(s)}", pt + Vector((0.01, -s * 0.01, 0.0)),
                 c + Vector((0.0, -s * largo * 0.3, -0.03)), 0.05, t2=0.025)

    def mover(self, Y):
        for ob in CUR[0].objects:
            ob.location.y += Y


# ---------------------------------------------------------------------------
# 01 Toyota Corolla sedan E210 (2019-2025)
# 4630 x 1780 x 1435 mm, entre ejes 2700, trocha 1530, despeje 130, 205/55 R16
# ---------------------------------------------------------------------------
COROLLA = dict(
    L=4.63, vf=0.93, eje=2.70, trocha=(1.53, 1.53), neu=(205, 55), aro=16, holgura=0.045,
    zt=[(2.315, 0.60), (2.305, 0.655), (2.28, 0.69), (2.20, 0.715), (2.0, 0.755), (1.6, 0.83), (1.2, 0.88),
        (0.85, 0.91), (0.72, 0.935), (0.40, 1.075), (0.10, 1.235), (-0.15, 1.355), (-0.35, 1.41), (-0.65, 1.435),
        (-0.95, 1.425), (-1.20, 1.385), (-1.45, 1.275), (-1.70, 1.125), (-1.88, 1.04), (-2.05, 1.03),
        (-2.20, 1.035), (-2.26, 1.02), (-2.295, 0.98), (-2.31, 0.93), (-2.315, 0.87)],
    zs=[(2.315, 0.55), (2.305, 0.61), (2.27, 0.655), (2.0, 0.73), (1.6, 0.805), (1.2, 0.855), (0.85, 0.89),
        (0.5, 0.915), (0.0, 0.94), (-0.8, 0.97), (-1.5, 0.995), (-1.9, 1.005), (-2.2, 1.015), (-2.27, 1.0),
        (-2.30, 0.95), (-2.315, 0.84)],
    zb=[(2.315, 0.36), (2.30, 0.30), (2.25, 0.25), (2.10, 0.225), (1.8, 0.215), (1.0, 0.175), (-0.9, 0.175),
        (-1.8, 0.22), (-2.15, 0.27), (-2.28, 0.33), (-2.315, 0.40)],
    W=[(2.3, 0.865), (1.4, 0.89), (0.4, 0.878), (-1.3, 0.89), (-2.3, 0.872)],
    esq=(0.50, 0.68, 0.60, 0.68),
    gz=[(0.15, 0.94), (0.30, 0.975), (0.50, 0.994), (0.68, 1.0), (0.74, 0.998), (0.78, 0.99), (0.90, 0.975),
        (1.02, 0.955)],
    kf=[(2.3, 0.80), (0.9, 0.80), (0.5, 0.79), (0.0, 0.75), (-1.5, 0.75), (-1.95, 0.85), (-2.3, 0.85)],
    n=[(2.3, 2.2), (0.85, 2.4), (0.3, 4.2), (-1.4, 4.2), (-1.9, 2.4), (-2.3, 2.2)],
)


def corolla(Y):
    A = Auto("Corolla", COROLLA)
    p, bvh_ = A.p, None
    A.carroceria()
    bvh = A.bvh
    A.ruedas("v10")
    # vidrios
    vidrio_arriba(f"{p}_Parabrisas", bvh, 0.70, -0.30, lambda x: A.we(x) * 0.90)
    vidrio_arriba(f"{p}_Luneta_Trasera", bvh, -1.17, -1.82, lambda x: A.we(x) * 0.88)
    xB = -0.32
    A.ventanas([(0.62, xB + 0.05), (xB - 0.05, -1.08), (-1.13, -1.62)], f=0.84, da=0.10, dc=0.12,
               nombres=["Ventana_Delantera", "Ventana_Trasera", "Ventana_Cuarto"])
    A.juntas_puerta([(0.88, xB, True, 0.64), (xB - 0.012, -1.15, True)], f=0.84, da=0.10, dc=0.12)
    A.espejos(0.52, 0.955)
    for s in (1, -1):
        manija(f"{p}_Manija_Puerta_{A.n(s)}", bvh, s, xB + 0.12, 0.88)
        manija(f"{p}_Manija_Puerta_{A.n(s)}", bvh, s, -0.95, 0.90)
        # faro: alargado, afilado hacia la parrilla y subiendo hacia el guardafango
        pieza_oblicua(f"{p}_Faro_Delantero_{A.n(s)}", bvh, (2.2, s * 0.62, 0.68), (-1, -s * 0.55, -0.12),
                      [(-0.26, 0.015), (-0.12, -0.035), (0.06, -0.05), (0.20, -0.03), (0.26, 0.02),
                       (0.16, 0.045), (-0.05, 0.04), (-0.22, 0.03)], desp=0.004, espesor=0.012, abombado=0.004)
        # calavera: horizontal, envolvente, entra en la tapa de maletera
        pieza_oblicua(f"{p}_Faro_Posterior_{A.n(s)}", bvh, (-2.26, s * 0.60, 0.93), (1, -s * 0.6, -0.1),
                      [(-0.30, 0.025), (-0.12, -0.035), (0.12, -0.06), (0.30, -0.035), (0.31, 0.04),
                       (0.05, 0.06), (-0.30, 0.055)], desp=0.004, espesor=0.012, abombado=0.003)
        # neblineros en las tomas laterales del parachoque
        frontal(f"{p}_Toma_Lateral_{A.n(s)}", bvh, 3.0,
                [(s * 0.56, 0.47), (s * 0.70, 0.46), (s * 0.73, 0.31), (s * 0.60, 0.33)], desp=0.003, espesor=0.01)
        pt, _ = proyectar(bvh, (3.0, s * 0.64, 0.40), (-1, 0, 0), 0.015)
        if pt:
            superelipsoide(f"{p}_Neblinero_{A.n(s)}", pt, (0.015, 0.045, 0.02), n=3)
    lateral(f"{p}_Tapa_Combustible", bvh, 1, [(-1.50, 0.82), (-1.33, 0.82), (-1.33, 0.95), (-1.50, 0.95)],
            desp=0.002, espesor=0.004)
    # parrilla superior delgada entre faros y gran parrilla inferior trapezoidal
    sup = [(-0.40, 0.655), (0.40, 0.655), (0.30, 0.615), (-0.30, 0.615)]
    frontal(f"{p}_Parrilla_Superior", bvh, 3.0, sup, desp=0.003, espesor=0.01)
    inf = [(-0.52, 0.52), (0.52, 0.52), (0.40, 0.30), (-0.40, 0.30)]
    frontal(f"{p}_Parrilla_Inferior", bvh, 3.0, inf, desp=0.002, espesor=0.006)
    barras_parrilla(f"{p}_Parrilla_Inferior_Barras", bvh, 3.0, inf, [0.33 + 0.03 * k for k in range(7)],
                    r=0.005, desp=0.009)
    pt, _ = proyectar(bvh, (3.0, 0, 0.415), (-1, 0, 0), 0.02)
    box(f"{p}_Placa_Delantera", (0.012, 0.34, 0.11), pt)
    pt, _ = proyectar(bvh, (-3.0, 0, 0.70), (1, 0, 0), 0.01)
    box(f"{p}_Placa_Posterior", (0.012, 0.34, 0.11), pt)
    # maletera: junta de tapa, moldura cromada entre calaveras y linea del parachoque
    junta_superior(A, "Junta_Maletera", [(-1.86, -0.62), (-2.10, -0.68), (-2.26, -0.66)])
    junta_superior(A, "Junta_Maletera_Lado", [(-1.86, 0.62), (-2.10, 0.68), (-2.26, 0.66)])
    junta_trasera(A, "Junta_Maletera_Trasera", [(-0.62, 0.95), (-0.45, 0.83), (0.45, 0.83), (0.62, 0.95)])
    frontal(f"{p}_Moldura_Maletera", bvh, -3.0, [(-0.42, 0.915), (0.42, 0.915), (0.42, 0.895), (-0.42, 0.895)],
            desp=0.004, espesor=0.006, atras=True)
    junta_trasera(A, "Junta_Parachoque_Posterior", [(-0.80, 0.66), (0.80, 0.66)])
    # parachoque posterior: difusor inferior y escape
    frontal(f"{p}_Difusor_Posterior", bvh, -3.0, [(-0.70, 0.42), (0.70, 0.42), (0.66, 0.34), (-0.66, 0.34)],
            desp=0.003, espesor=0.01, atras=True)
    cyl(f"{p}_Tubo_Escape", 0.032, 0.16, (-2.20, -0.45, 0.31), axis="X", verts=20)
    # aleta de tiburon y limpiaparabrisas
    pt, _ = proyectar(bvh, (-1.05, 0, 5), (0, 0, -1), 0.0)
    superelipsoide(f"{p}_Antena_Aleta", pt + Vector((0, 0, 0.03)), (0.08, 0.025, 0.035), n=2.2)
    for s in (1, -1):
        a, _ = proyectar(bvh, (0.73, s * 0.05, 5), (0, 0, -1), 0.012)
        b, _ = proyectar(bvh, (0.62, s * 0.55, 5), (0, 0, -1), 0.012)
        beam(f"{p}_Limpiaparabrisas", a, b, 0.016, t2=0.010)
    # moldura de techo (canaletas) y alerón integrado
    for s in (1, -1):
        lin = sobre(bvh, [(x, s * A.we(x) * 0.97, 5) for x in (0.0, -0.4, -0.8, -1.15)], (0, 0, -1), 0.0)
        tubos(f"{p}_Moldura_Techo_{A.n(s)}", [lin], 0.006)
    A.mover(Y)




def pilar(A, nombre, x0, x1, f, da, dc, extra=0.03):
    """Moldura negra de pilar entre dos ventanas (proyectada sobre el costado)."""
    zs = A.P["zs"]
    for s in (1, -1):
        xs = [x0 + (x1 - x0) * i / 6 for i in range(7)]
        top = [(x, A.z_ventana(x, f, da, dc) + extra) for x in xs]
        bot = [(x, zs(x) + 0.01) for x in reversed(xs)]
        lateral(f"{A.p}_{nombre}_{A.n(s)}", A.bvh, s, top + bot, desp=0.003, espesor=0.004)


def junta_superior(A, nombre, pts_xy):
    lin = sobre(A.bvh, [(x, y, 5) for x, y in pts_xy], (0, 0, -1), 0.0)
    tubos(f"{A.p}_{nombre}", [lin], 0.0035)


def junta_trasera(A, nombre, pts_yz, xo=-6.0):
    lin = sobre(A.bvh, [(xo, y, z) for y, z in pts_yz], (1, 0, 0), 0.0)
    tubos(f"{A.p}_{nombre}", [lin], 0.0035)


# ---------------------------------------------------------------------------
# 02 Suzuki Swift hatchback (2024, 7a generacion)
# 3860 x 1735 x 1495 mm, entre ejes 2450, trocha 1520, 185/55 R16
# ---------------------------------------------------------------------------
SWIFT = dict(
    L=3.86, vf=0.73, eje=2.45, trocha=(1.52, 1.52), neu=(185, 55), aro=16, holgura=0.045,
    zt=[(1.93, 0.58), (1.915, 0.64), (1.88, 0.69), (1.80, 0.73), (1.5, 0.82), (1.15, 0.895), (0.95, 0.93),
        (0.80, 0.965), (0.50, 1.11), (0.20, 1.26), (-0.05, 1.37), (-0.30, 1.45), (-0.65, 1.495), (-1.0, 1.485),
        (-1.40, 1.455), (-1.55, 1.43), (-1.62, 1.40), (-1.68, 1.31), (-1.75, 1.18), (-1.80, 1.08),
        (-1.86, 1.01), (-1.90, 0.96), (-1.92, 0.89), (-1.93, 0.80)],
    zs=[(1.93, 0.54), (1.915, 0.60), (1.85, 0.66), (1.5, 0.775), (1.15, 0.855), (0.90, 0.90), (0.5, 0.925),
        (0.0, 0.95), (-0.8, 0.985), (-1.4, 1.015), (-1.70, 1.025), (-1.80, 1.015), (-1.88, 0.975),
        (-1.915, 0.92), (-1.93, 0.80)],
    zb=[(1.93, 0.36), (1.91, 0.30), (1.85, 0.25), (1.6, 0.20), (1.0, 0.165), (-1.0, 0.165), (-1.6, 0.21),
        (-1.85, 0.27), (-1.93, 0.36)],
    W=[(1.9, 0.85), (1.2, 0.8675), (0.2, 0.85), (-1.25, 0.8675), (-1.9, 0.85)],
    esq=(0.45, 0.62, 0.45, 0.70),
    gz=[(0.15, 0.93), (0.3, 0.97), (0.5, 0.995), (0.68, 1.0), (0.8, 0.99), (0.9, 0.97), (1.05, 0.93)],
    kf=[(1.9, 0.80), (0.85, 0.80), (0.4, 0.75), (-1.2, 0.74), (-1.6, 0.70), (-1.9, 0.76)],
    n=[(1.9, 2.2), (0.9, 2.4), (0.4, 4.2), (-1.65, 4.2), (-1.9, 3.0)],
)


def swift(Y):
    A = Auto("Swift", SWIFT)
    p = A.p
    A.carroceria()
    bvh = A.bvh
    A.ruedas("multi")
    A.aletas(0.03, 0.010)
    vidrio_arriba(f"{p}_Parabrisas", bvh, 0.77, 0.03, lambda x: A.we(x) * 0.90)
    vidrio_atras(f"{p}_Luneta_Trasera", bvh, 1.11, 1.36, lambda z: 0.52 - 0.35 * (z - 1.11), -4.0)
    f, da, dc = 0.88, 0.09, 0.10
    xB = -0.28
    A.ventanas([(0.70, xB + 0.05), (xB - 0.05, -1.02), (-1.08, -1.45)], f=f, da=da, dc=dc,
               nombres=["Ventana_Delantera", "Ventana_Trasera", "Ventana_Cuarto"])
    pilar(A, "Pilar_B", xB + 0.05, xB - 0.05, f, da, dc)
    for s in (1, -1):
        lateral(f"{p}_Pilar_C_{A.n(s)}", bvh, s, [(-1.45, 1.05), (-1.45, 1.33), (-1.55, 1.33), (-1.62, 1.24),
                                                  (-1.65, 1.10), (-1.60, 1.06)], desp=0.003, espesor=0.004)
    A.juntas_puerta([(0.95, xB, True, 0.72), (xB - 0.012, -1.10, True)], f=f, da=da, dc=dc)
    A.espejos(0.62, 0.98, largo=0.19, alto=0.12)
    for s in (1, -1):
        manija(f"{p}_Manija_Puerta_{A.n(s)}", bvh, s, xB + 0.12, 0.86)
        manija(f"{p}_Manija_Puerta_{A.n(s)}", bvh, s, -0.90, 0.90)
        # faros grandes llevados hacia el guardafango
        pieza_oblicua(f"{p}_Faro_Delantero_{A.n(s)}", bvh, (1.78, s * 0.62, 0.70), (-1, -s * 0.75, -0.12),
                      [(-0.17, 0.03), (-0.15, -0.035), (0.0, -0.06), (0.18, -0.05), (0.25, 0.0), (0.22, 0.05),
                       (0.05, 0.065), (-0.12, 0.06)], desp=0.004, espesor=0.012, abombado=0.006)
        # calaveras envolventes en las esquinas traseras
        pieza_oblicua(f"{p}_Faro_Posterior_{A.n(s)}", bvh, (-1.88, s * 0.56, 1.02), (1, -s * 0.4, -0.05),
                      [(-0.10, 0.07), (-0.12, -0.02), (-0.04, -0.06), (0.14, -0.05), (0.17, 0.0), (0.12, 0.08),
                       (0.0, 0.09)], desp=0.003, espesor=0.008, abombado=0.0)
        frontal(f"{p}_Toma_Lateral_{A.n(s)}", bvh, 3.0,
                [(s * 0.52, 0.43), (s * 0.66, 0.44), (s * 0.68, 0.32), (s * 0.55, 0.30)], desp=0.003, espesor=0.01)
        pt, _ = proyectar(bvh, (3.0, s * 0.61, 0.38), (-1, 0, 0), 0.014)
        if pt:
            superelipsoide(f"{p}_Neblinero_{A.n(s)}", pt, (0.014, 0.035, 0.03), n=2.2)
        # capo tipo almeja: la junta corre sobre el guardafango
        junta_superior(A, f"Junta_Capo_{A.n(s)}", [(1.86, s * 0.60), (1.6, s * 0.74), (1.2, s * 0.76),
                                                    (0.82, s * 0.70)])
    junta_superior(A, "Junta_Capo_Base", [(0.82, -0.70), (0.84, 0.0), (0.82, 0.70)])
    # parrilla horizontal ovalada tipo panal y toma inferior
    pr = [(-0.40, 0.585), (0.40, 0.585), (0.50, 0.53), (0.46, 0.44), (-0.46, 0.44), (-0.50, 0.53)]
    frontal(f"{p}_Parrilla", bvh, 3.0, pr, desp=0.002, espesor=0.006)
    barras_parrilla(f"{p}_Parrilla_Panal", bvh, 3.0, pr, [0.46 + 0.025 * k for k in range(6)], r=0.004, desp=0.009)
    barras_parrilla(f"{p}_Parrilla_Panal_V", bvh, 3.0, pr, [-0.42 + 0.06 * k for k in range(15)], r=0.004,
                    desp=0.009, vertical=True)
    frontal(f"{p}_Toma_Inferior", bvh, 3.0, [(-0.34, 0.39), (0.34, 0.39), (0.29, 0.32), (-0.29, 0.32)],
            desp=0.003, espesor=0.01)
    pt, _ = proyectar(bvh, (3.0, 0, 0.40), (-1, 0, 0), 0.016)
    box(f"{p}_Placa_Delantera", (0.012, 0.34, 0.10), pt)
    # portalon trasero: junta, placa, aleron y difusor
    junta_trasera(A, "Junta_Portalon", [(-0.56, 1.40), (-0.64, 1.0), (-0.46, 0.80), (0.46, 0.80), (0.64, 1.0),
                                        (0.56, 1.40)])
    pt, _ = proyectar(bvh, (-4.0, 0, 0.88), (1, 0, 0), 0.01)
    box(f"{p}_Placa_Posterior", (0.012, 0.34, 0.11), pt)
    superior(f"{p}_Aleron_Trasero", bvh, [(-1.46, -0.56), (-1.46, 0.56), (-1.64, 0.58), (-1.64, -0.58)],
             desp=0.008, espesor=0.012)
    frontal(f"{p}_Difusor_Posterior", bvh, -4.0, [(-0.66, 0.42), (0.66, 0.42), (0.60, 0.33), (-0.60, 0.33)],
            desp=0.003, espesor=0.01, atras=True)
    cyl(f"{p}_Tubo_Escape", 0.028, 0.14, (-1.86, -0.42, 0.30), axis="X", verts=20)
    pt, _ = proyectar(bvh, (-1.30, 0, 5), (0, 0, -1), 0.0)
    beam(f"{p}_Antena", pt, pt + Vector((-0.14, 0, 0.16)), 0.012, round_=True)
    for s in (1, -1):
        a, _ = proyectar(bvh, (0.80, s * 0.05, 5), (0, 0, -1), 0.012)
        b, _ = proyectar(bvh, (0.70, s * 0.52, 5), (0, 0, -1), 0.012)
        beam(f"{p}_Limpiaparabrisas", a, b, 0.016, t2=0.010)
    lateral(f"{p}_Tapa_Combustible", bvh, -1, [(-1.40, 0.84), (-1.26, 0.84), (-1.26, 0.96), (-1.40, 0.96)],
            desp=0.002, espesor=0.004)
    A.mover(Y)


# ---------------------------------------------------------------------------
# 03 Toyota RAV4 (XA50, 2019-2025)
# 4600 x 1855 x 1685 mm, entre ejes 2690, trocha 1600/1620, despeje 200, 225/60 R18
# ---------------------------------------------------------------------------
RAV4 = dict(
    L=4.60, vf=0.925, eje=2.69, trocha=(1.60, 1.62), neu=(225, 60), aro=18, holgura=0.05, forma_arco=3.2,
    zt=[(2.30, 0.90), (2.295, 0.96), (2.27, 1.0), (2.18, 1.025), (1.9, 1.045), (1.4, 1.065), (1.0, 1.09),
        (0.85, 1.115), (0.55, 1.29), (0.25, 1.46), (0.0, 1.575), (-0.25, 1.63), (-0.7, 1.64), (-1.4, 1.635),
        (-1.95, 1.62), (-2.06, 1.60), (-2.13, 1.50), (-2.20, 1.32), (-2.25, 1.17), (-2.28, 1.07),
        (-2.30, 0.95)],
    zs=[(2.30, 0.86), (2.295, 0.93), (2.26, 0.97), (1.9, 1.00), (1.4, 1.025), (1.0, 1.05), (0.6, 1.065),
        (0.0, 1.08), (-1.0, 1.10), (-1.9, 1.12), (-2.15, 1.12), (-2.25, 1.10), (-2.285, 1.02), (-2.30, 0.90)],
    zb=[(2.30, 0.44), (2.28, 0.40), (2.2, 0.36), (1.9, 0.30), (1.6, 0.26), (1.0, 0.235), (-0.9, 0.235),
        (-1.7, 0.27), (-2.1, 0.34), (-2.3, 0.46)],
    W=[(2.25, 0.90), (1.375, 0.9275), (0.0, 0.915), (-1.315, 0.9275), (-2.25, 0.91)],
    esq=(0.40, 0.70, 0.30, 0.82),
    gz=[(0.2, 0.955), (0.4, 0.985), (0.6, 1.0), (0.85, 0.995), (1.0, 0.975), (1.12, 0.955)],
    kf=[(2.3, 0.85), (0.9, 0.85), (0.4, 0.80), (-1.9, 0.80), (-2.3, 0.85)],
    n=[(2.3, 2.6), (1.0, 2.8), (0.4, 5.0), (-2.0, 5.0), (-2.3, 3.5)],
    rb=(0.06, 0.09),
)


def rav4(Y):
    A = Auto("RAV4", RAV4)
    p = A.p
    A.carroceria()
    bvh = A.bvh
    A.ruedas("5d")
    A.aletas(0.075, 0.022)
    vidrio_arriba(f"{p}_Parabrisas", bvh, 0.82, -0.02, lambda x: A.we(x) * 0.90)
    vidrio_atras(f"{p}_Luneta_Trasera", bvh, 1.24, 1.56, lambda z: 0.62 - 0.15 * (z - 1.24), -4.0)
    f, da, dc = 0.88, 0.09, 0.12
    xB = -0.30
    A.ventanas([(0.74, xB + 0.05), (xB - 0.05, -1.20), (-1.27, -1.92)], f=f, da=da, dc=dc,
               nombres=["Ventana_Delantera", "Ventana_Trasera", "Ventana_Cuarto"])
    pilar(A, "Pilar_B", xB + 0.05, xB - 0.05, f, da, dc)
    pilar(A, "Pilar_C", -1.20, -1.27, f, da, dc)
    A.juntas_puerta([(0.92, xB, True, 0.76), (xB - 0.012, -1.24, True)], f=f, da=da, dc=dc, zr=0.42)
    A.espejos(0.66, 1.13, largo=0.21, alto=0.14)
    for s in (1, -1):
        manija(f"{p}_Manija_Puerta_{A.n(s)}", bvh, s, xB + 0.12, 1.00)
        manija(f"{p}_Manija_Puerta_{A.n(s)}", bvh, s, -1.05, 1.02)
        # revestimiento negro inferior entre arcos (cuadrado y robusto)
        x0, x1 = A.xfa - A.r - 0.05, A.xra + A.r + 0.05
        lateral(f"{p}_Moldura_Estribo_{A.n(s)}", bvh, s, [(x0, 0.24), (x0, 0.42), (x1, 0.42), (x1, 0.24)],
                desp=0.008, espesor=0.012)
        # faros angulosos y delgados
        pieza_oblicua(f"{p}_Faro_Delantero_{A.n(s)}", bvh, (2.17, s * 0.66, 0.93), (-1, -s * 0.6, -0.12),
                      [(-0.26, 0.03), (-0.24, -0.02), (-0.05, -0.05), (0.16, -0.05), (0.24, -0.01), (0.22, 0.05),
                       (-0.05, 0.045)], desp=0.004, espesor=0.012, abombado=0.003)
        pieza_oblicua(f"{p}_Faro_Posterior_{A.n(s)}", bvh, (-2.22, s * 0.64, 1.12), (1, -s * 0.45, -0.05),
                      [(-0.20, 0.04), (-0.18, -0.03), (0.05, -0.055), (0.20, -0.045), (0.22, 0.04), (0.0, 0.06)],
                      desp=0.004, espesor=0.012, abombado=0.003)
        # tomas laterales verticales del parachoque con neblinero
        frontal(f"{p}_Toma_Lateral_{A.n(s)}", bvh, 3.0,
                [(s * 0.63, 0.70), (s * 0.76, 0.66), (s * 0.76, 0.46), (s * 0.66, 0.46)], desp=0.003, espesor=0.01)
        pt, _ = proyectar(bvh, (3.0, s * 0.70, 0.52), (-1, 0, 0), 0.014)
        if pt:
            superelipsoide(f"{p}_Neblinero_{A.n(s)}", pt, (0.014, 0.035, 0.035), n=3)
        # barras de techo
        pts = sobre(bvh, [(x, s * 0.60, 5) for x in (-0.05, -0.5, -1.0, -1.5, -1.95)], (0, 0, -1), 0.045)
        tubos(f"{p}_Barra_Techo_{A.n(s)}", [pts], 0.016)
        for k in (0, -1):
            q = pts[k]
            superelipsoide(f"{p}_Soporte_Barra_Techo_{A.n(s)}", q + Vector((0, 0, -0.022)), (0.06, 0.02, 0.025), n=3)
    # parrilla octogonal superior/inferior y protector de carter
    sup = [(-0.40, 0.91), (0.40, 0.91), (0.34, 0.85), (-0.34, 0.85)]
    frontal(f"{p}_Parrilla_Superior", bvh, 3.0, sup, desp=0.003, espesor=0.01)
    inf = [(-0.52, 0.78), (0.52, 0.78), (0.60, 0.66), (0.50, 0.50), (-0.50, 0.50), (-0.60, 0.66)]
    frontal(f"{p}_Parrilla_Inferior", bvh, 3.0, inf, desp=0.002, espesor=0.006)
    barras_parrilla(f"{p}_Parrilla_Inferior_Barras", bvh, 3.0, inf, [0.53 + 0.035 * k for k in range(7)], r=0.006,
                    desp=0.011)
    frontal(f"{p}_Protector_Carter_Delantero", bvh, 3.0, [(-0.46, 0.47), (0.46, 0.47), (0.36, 0.40), (-0.36, 0.40)],
            desp=0.006, espesor=0.01)
    pt, _ = proyectar(bvh, (3.0, 0, 0.64), (-1, 0, 0), 0.03)
    box(f"{p}_Placa_Delantera", (0.012, 0.34, 0.11), pt)
    junta_superior(A, "Junta_Capo", [(2.20, -0.70), (1.5, -0.80), (0.86, -0.78), (0.88, 0.0), (0.86, 0.78),
                                     (1.5, 0.80), (2.20, 0.70)])
    # portalon, parachoque posterior con protector
    junta_trasera(A, "Junta_Portalon", [(-0.72, 1.58), (-0.76, 1.05), (-0.52, 0.82), (0.52, 0.82), (0.76, 1.05),
                                        (0.72, 1.58)])
    pt, _ = proyectar(bvh, (-4.0, 0, 0.95), (1, 0, 0), 0.01)
    box(f"{p}_Placa_Posterior", (0.012, 0.34, 0.11), pt)
    frontal(f"{p}_Protector_Carter_Posterior", bvh, -4.0, [(-0.55, 0.56), (0.55, 0.56), (0.48, 0.47), (-0.48, 0.47)],
            desp=0.006, espesor=0.01, atras=True)
    superior(f"{p}_Aleron_Trasero", bvh, [(-1.86, -0.64), (-1.86, 0.64), (-2.06, 0.66), (-2.06, -0.66)],
             desp=0.008, espesor=0.012)
    for yy in (0.45, -0.45):
        cyl(f"{p}_Tubo_Escape", 0.034, 0.14, (-2.22, yy, 0.40), axis="X", verts=20)
    pt, _ = proyectar(bvh, (-1.75, 0, 5), (0, 0, -1), 0.0)
    superelipsoide(f"{p}_Antena_Aleta", pt + Vector((0, 0, 0.03)), (0.08, 0.025, 0.035), n=2.2)
    for s in (1, -1):
        a, _ = proyectar(bvh, (0.85, s * 0.05, 5), (0, 0, -1), 0.012)
        b, _ = proyectar(bvh, (0.74, s * 0.58, 5), (0, 0, -1), 0.012)
        beam(f"{p}_Limpiaparabrisas", a, b, 0.016, t2=0.010)
    lateral(f"{p}_Tapa_Combustible", bvh, 1, [(-1.82, 0.95), (-1.66, 0.95), (-1.66, 1.08), (-1.82, 1.08)],
            desp=0.002, espesor=0.004)
    A.mover(Y)


# ---------------------------------------------------------------------------
# 04 Toyota Hilux doble cabina 4x4 (AN120, 2021-2025)
# 5325 x 1855 x 1815 mm, entre ejes 3085, trocha 1535/1550, tolva 1555 mm, 265/65 R17
# ---------------------------------------------------------------------------
HILUX = dict(
    L=5.325, vf=0.92, eje=3.085, trocha=(1.535, 1.55), neu=(265, 65), aro=17, holgura=0.06,
    zt=[(2.6625, 1.08), (2.655, 1.12), (2.63, 1.14), (2.5, 1.16), (2.0, 1.18), (1.40, 1.195), (1.15, 1.215),
        (0.85, 1.40), (0.55, 1.585), (0.30, 1.72), (0.05, 1.785), (-0.4, 1.805), (-0.9, 1.80), (-0.98, 1.795),
        (-1.02, 1.77), (-1.05, 1.72), (-1.06, 1.66)],
    zs=[(2.6625, 1.05), (2.655, 1.09), (2.62, 1.11), (2.3, 1.13), (1.8, 1.15), (1.2, 1.17), (0.5, 1.20),
        (-0.5, 1.23), (-1.06, 1.24)],
    zb=[(2.6625, 0.60), (2.64, 0.53), (2.55, 0.47), (2.3, 0.44), (1.9, 0.46), (1.2, 0.47), (-1.06, 0.47)],
    W=[(2.6, 0.89), (1.74, 0.9275), (0.5, 0.905), (-1.06, 0.905)],
    xRc=-1.06, esq=(0.36, 0.80, 0.04, 0.97),
    gz=[(0.4, 0.97), (0.6, 0.99), (0.85, 1.0), (1.05, 0.99), (1.2, 0.965), (1.26, 0.955)],
    kf=[(2.6, 0.86), (1.25, 0.86), (0.7, 0.80), (-1.06, 0.80)],
    n=[(2.6, 2.6), (1.2, 2.8), (0.6, 5.0), (-1.06, 5.0)],
    rb=(0.05, 0.08),
)
TOLVA = dict(
    zt=[(-1.0, 1.292), (-2.7, 1.292)], zs=[(-1.0, 1.28), (-2.7, 1.28)], zb=[(-1.0, 0.55), (-2.7, 0.55)],
    n=[(0, 2.2), (-3, 2.2)], kf=[(0, 0.97), (-3, 0.97)],
    gz=HILUX["gz"], rb=(0.04, 0.06),
)


def hilux(Y):
    A = Auto("Hilux", HILUX)
    p = A.p
    xc = -1.06
    A.carroceria(nombre="Cabina_Carroceria", xR=xc)
    bvh = A.bvh
    A.ruedas("6")
    # tolva (caja de carga): solido exterior ahuecado, compuerta y parachoque aparte
    xt0, xt1 = -1.10, -2.60
    T = {k: tabla(TOLVA[k]) for k in ("zt", "zs", "zb", "n", "kf")}
    T["gz"] = tabla(TOLVA["gz"])
    T["W"] = ancho_planta([(-1.0, 0.915), (-1.345, 0.9275), (-2.7, 0.92)], xt0, xt1, 0.04, 0.96, 0.06, 0.94)
    T["rb"] = TOLVA["rb"]
    tolva = solido_secciones(f"{p}_Tolva_Carroceria", T, estaciones(xt0, xt1))
    bvh_t = bvh_de([tolva])
    hueco = prisma_y("aux", [(xt0 - 0.045, 0.82), (xt1 - 0.5, 0.82), (xt1 - 0.5, 2.0), (xt0 - 0.045, 2.0)],
                     -0.85, 0.85)
    recortar(tolva, hueco)
    cortar_arcos(tolva, [(A.xra, A.r, A.r + 0.06, 2.0)])
    T2 = dict(T)
    T2["zb"] = tabla([(-2, 0.62), (-3, 0.62)])
    T2["W"] = ancho_planta([(-2.5, 0.92), (-2.7, 0.92)], xt1 - 0.005, xt1 - 0.05, 0.02, 0.96, 0.02, 0.96)
    solido_secciones(f"{p}_Compuerta_Trasera", T2, estaciones(xt1 - 0.005, xt1 - 0.05, paso=0.01, fino=0.01))
    bvh_all = bvh_de([A.body, tolva])
    A.bvh = bvh_all
    for s in (1, -1):
        for x, nm in ((A.xfa, "Delantera"), (A.xra, "Trasera")):
            aleta_arco(f"{p}_Guardafango_Ensanche_{nm}_{A.n(s)}", bvh_all if nm == "Trasera" else bvh, s, x, A.r,
                       A.r + 0.06, 2.0, 0.085, 0.04, a0=-6)
    A.bvh = bvh
    # interior de tolva
    box(f"{p}_Tolva_Piso", (abs(xt1 - xt0) - 0.05, 1.56, 0.02), ((xt0 + xt1) / 2, 0, 0.83))
    for k in range(-5, 6):
        box(f"{p}_Tolva_Nervio_Piso", (abs(xt1 - xt0) - 0.12, 0.035, 0.012), ((xt0 + xt1) / 2, k * 0.13, 0.846),
            bevel=0.004)
    for s in (1, -1):
        superelipsoide(f"{p}_Tolva_Paso_Rueda_{A.n(s)}", (A.xra, s * 0.66, 0.86), (0.46, 0.16, 0.17), n=3.0)
        box(f"{p}_Tolva_Riel_Superior_{A.n(s)}", (abs(xt1 - xt0), 0.075, 0.018), ((xt0 + xt1) / 2, s * 0.87, 1.30),
            bevel=0.006)
        for x in (-1.35, -2.40):
            cyl(f"{p}_Tolva_Gancho_{A.n(s)}", 0.018, 0.03, (x, s * 0.80, 1.18), axis="Y", verts=12)
    box(f"{p}_Tolva_Pared_Frontal", (0.04, 1.70, 0.46), (xt0 - 0.06, 0, 1.06), bevel=0.01)
    box(f"{p}_Compuerta_Manija", (0.03, 0.22, 0.05), (xt1 - 0.055, 0, 1.20), bevel=0.008)
    # barra antivuelco tubular
    xb = xt0 - 0.12
    arco = []
    for k in range(13):
        a = math.pi * k / 12
        arco.append((xb, 0.74 * math.cos(a), 1.30 + 0.22 * min(1.0, 2.2 * math.sin(a))))
    curve_tube(f"{p}_Barra_Antivuelco", arco, 0.03, res=4)
    for s in (1, -1):
        curve_tube(f"{p}_Barra_Antivuelco_Tirante_{A.n(s)}", [(xb, s * 0.74, 1.48), (xb - 0.55, s * 0.82, 1.30)], 0.022)
    # vidrios
    vidrio_arriba(f"{p}_Parabrisas", bvh, 1.10, 0.32, lambda x: A.we(x) * 0.90)
    vidrio_atras(f"{p}_Luneta_Trasera", bvh, 1.38, 1.66, lambda z: 0.56, -4.0)
    f, da, dc = 0.88, 0.09, 0.07
    xB = -0.06
    A.ventanas([(1.02, xB + 0.05), (xB - 0.05, -0.97)], f=f, da=da, dc=dc,
               nombres=["Ventana_Delantera", "Ventana_Trasera"])
    pilar(A, "Pilar_B", xB + 0.05, xB - 0.05, f, da, dc)
    A.juntas_puerta([(1.24, xB, True, 1.06), (xB - 0.012, -0.90, True)], f=f, da=da, dc=dc, zr=0.55)
    A.espejos(0.98, 1.27, largo=0.24, alto=0.17, prof=0.10)
    for s in (1, -1):
        manija(f"{p}_Manija_Puerta_{A.n(s)}", bvh, s, xB + 0.12, 1.12, largo=0.15)
        manija(f"{p}_Manija_Puerta_{A.n(s)}", bvh, s, -0.78, 1.14, largo=0.15)
        # estribos laterales
        superelipsoide(f"{p}_Estribo_{A.n(s)}", (0.18, s * 0.86, 0.40), (0.95, 0.10, 0.025), n=4)
        for x in (0.85, 0.18, -0.50):
            beam(f"{p}_Estribo_Soporte_{A.n(s)}", (x, s * 0.70, 0.47), (x, s * 0.84, 0.40), 0.04, t2=0.02)
        # faros delgados con proyector, unidos a la parrilla
        pieza_oblicua(f"{p}_Faro_Delantero_{A.n(s)}", bvh, (2.58, s * 0.67, 1.00), (-1, -s * 0.45, -0.05),
                      [(-0.20, 0.06), (-0.19, -0.05), (0.05, -0.07), (0.25, -0.045), (0.25, 0.05), (0.0, 0.07)],
                      desp=0.004, espesor=0.012, abombado=0.004)
        # calaveras verticales en las esquinas de la tolva
        pieza_oblicua(f"{p}_Faro_Posterior_{A.n(s)}", bvh_t, (-2.58, s * 0.88, 1.06), (1, -s * 0.45, 0),
                      [(-0.04, 0.17), (-0.05, -0.15), (0.03, -0.18), (0.07, -0.12), (0.07, 0.14), (0.03, 0.18)],
                      desp=0.004, espesor=0.014, abombado=0.003)
        frontal(f"{p}_Marco_Neblinero_{A.n(s)}", bvh, 4.0,
                [(s * 0.60, 0.72), (s * 0.72, 0.71), (s * 0.72, 0.59), (s * 0.62, 0.60)], desp=0.003, espesor=0.01)
        pt, _ = proyectar(bvh, (4.0, s * 0.71, 0.65), (-1, 0, 0), 0.014)
        if pt:
            superelipsoide(f"{p}_Neblinero_{A.n(s)}", pt, (0.014, 0.05, 0.025), n=3)
        pt, _ = proyectar(bvh, (0.95, s * 0.80, 5), (0, 0, -1), 0.0)
        if s > 0 and pt is not None:
            beam(f"{p}_Antena", pt, pt + Vector((-0.30, 0.0, 0.55)), 0.008, round_=True)
    # parrilla trapezoidal grande con marco cromado y barras gruesas
    pr = [(-0.58, 1.07), (0.58, 1.07), (0.55, 0.78), (0.40, 0.70), (-0.40, 0.70), (-0.55, 0.78)]
    frontal(f"{p}_Parrilla", bvh, 4.0, pr, desp=0.002, espesor=0.006)
    marco = sobre(bvh, [(4.0, y, z) for y, z in pr + pr[:1]], (-1, 0, 0), 0.008)
    tubos(f"{p}_Parrilla_Marco", [marco], 0.014)
    barras_parrilla(f"{p}_Parrilla_Barras", bvh, 4.0, pr, [0.76 + 0.065 * k for k in range(5)], r=0.009, desp=0.014)
    frontal(f"{p}_Protector_Carter", bvh, 4.0, [(-0.50, 0.62), (0.50, 0.62), (0.40, 0.50), (-0.40, 0.50)],
            desp=0.006, espesor=0.012)
    pt, _ = proyectar(bvh, (4.0, 0, 0.66), (-1, 0, 0), 0.03)
    box(f"{p}_Placa_Delantera", (0.012, 0.34, 0.11), pt)
    junta_superior(A, "Junta_Capo", [(2.58, -0.72), (1.9, -0.82), (1.17, -0.80), (1.19, 0.0), (1.17, 0.80),
                                     (1.9, 0.82), (2.58, 0.72)])
    # parachoque trasero escalon, placa, tiro y escape
    superelipsoide(f"{p}_Parachoque_Posterior", (-2.61, 0, 0.58), (0.06, 0.92, 0.07), n=4)
    box(f"{p}_Parachoque_Escalon", (0.10, 0.50, 0.012), (-2.62, 0, 0.652), bevel=0.004)
    box(f"{p}_Placa_Posterior", (0.012, 0.34, 0.11), (-2.672, 0, 0.58))
    box(f"{p}_Enganche_Remolque", (0.36, 0.06, 0.06), (-2.56, 0, 0.47), bevel=0.01)
    cyl(f"{p}_Tubo_Escape", 0.032, 0.16, (-2.45, -0.55, 0.45), axis="X", verts=20)
    for s in (1, -1):
        a, _ = proyectar(bvh, (1.15, s * 0.05, 5), (0, 0, -1), 0.012)
        b, _ = proyectar(bvh, (1.05, s * 0.60, 5), (0, 0, -1), 0.012)
        beam(f"{p}_Limpiaparabrisas", a, b, 0.016, t2=0.010)
    # chasis visible y diferenciales
    for s in (1, -1):
        box(f"{p}_Chasis_Larguero_{A.n(s)}", (4.6, 0.07, 0.16), (-0.05, s * 0.42, 0.50))
    cyl(f"{p}_Eje_Trasero", 0.04, 1.40, (A.xra, 0, A.r), axis="Y", verts=16)
    esfera(f"{p}_Diferencial_Trasero", 0.13, (A.xra, 0.0, A.r), escala=(1, 0.8, 1))
    A.mover(Y)


# ---------------------------------------------------------------------------
# 05 Toyota Hiace Commuter techo alto, chasis super largo (H300, 2019-2025)
# 5915 x 1950 x 2280 mm, entre ejes 3860, trocha 1670, 235/65 R16
# ---------------------------------------------------------------------------
HIACE = dict(
    L=5.915, vf=1.00, eje=3.86, trocha=(1.67, 1.67), neu=(235, 65), aro=16, holgura=0.05,
    zt=[(2.9575, 0.72), (2.95, 0.80), (2.92, 0.87), (2.86, 0.965), (2.78, 1.05), (2.66, 1.11), (2.45, 1.145),
        (2.25, 1.165),
        (2.05, 1.40), (1.80, 1.72), (1.55, 1.975), (1.30, 2.155), (1.0, 2.245), (0.5, 2.275), (-2.7, 2.28),
        (-2.85, 2.265), (-2.92, 2.23), (-2.95, 2.15), (-2.9575, 2.05)],
    zs=[(2.9575, 0.68), (2.95, 0.76), (2.92, 0.83), (2.86, 0.93), (2.78, 1.01), (2.66, 1.06), (2.45, 1.085),
        (2.25, 1.095), (1.8, 1.10),
        (1.0, 1.11), (-2.8, 1.13), (-2.92, 1.12), (-2.95, 1.08), (-2.9575, 1.0)],
    zb=[(2.9575, 0.42), (2.93, 0.36), (2.85, 0.31), (2.5, 0.28), (1.5, 0.245), (-1.5, 0.245), (-2.6, 0.30),
        (-2.9575, 0.36)],
    W=[(2.9, 0.93), (2.0, 0.975), (0.0, 0.97), (-2.9, 0.975)],
    esq=(0.50, 0.72, 0.12, 0.90),
    gz=[(0.2, 0.96), (0.5, 0.99), (0.8, 1.0), (1.1, 0.995), (1.5, 0.985), (2.0, 0.975)],
    kf=[(2.9, 0.88), (2.3, 0.88), (1.6, 0.95), (-2.9, 0.95)],
    n=[(2.9, 2.6), (2.3, 2.8), (1.6, 7.0), (-2.9, 7.0)],
    rb=(0.05, 0.08),
)


def hiace(Y):
    A = Auto("Hiace", HIACE)
    p = A.p
    A.carroceria()
    bvh = A.bvh
    A.ruedas("acero")
    vidrio_arriba(f"{p}_Parabrisas", bvh, 2.20, 1.34, lambda x: A.we(x) * 0.92, nx=18)
    vidrio_atras(f"{p}_Luneta_Trasera", bvh, 1.30, 2.02, lambda z: 0.74, -5.0)
    f, da, dc = 0.90, 0.08, 0.10
    zs = A.P["zs"]
    zbot = lambda x: zs(x) + 0.04
    ztop = lambda x: A.z_ventana(x, f, da, dc)
    for s in (1, -1):
        vidrio_lado(f"{p}_Ventana_Puerta_Delantera_{A.n(s)}", bvh, s, 1.24, 2.10, lambda x: zs(x) + 0.02, ztop)
        cortes = [(1.12, 0.10), (0.02, -1.02), (-1.10, -2.10), (-2.18, -2.82)]
        for k, (x0, x1) in enumerate(cortes):
            vidrio_lado(f"{p}_Ventana_Lateral_{k + 1}_{A.n(s)}", bvh, s, x1, x0, zbot, ztop, nx=20)
    for k, (x0, x1) in enumerate([(1.24, 1.12), (0.10, 0.02), (-1.02, -1.10), (-2.10, -2.18)]):
        pilar(A, f"Pilar_{'BCDE'[k]}", x0, x1, f, da, dc)
    # puertas delanteras (ambos lados) y puerta corrediza (lado derecho, acera en Peru)
    for s in (1, -1):
        pts = [(1.55, 0.36), (1.55, 1.10)] + [(x, A.z_ventana(x, f, da, dc) + 0.03) for x in
                                              [1.9 - 0.025 * i for i in range(28)] if A.z_ventana(x, f, da, dc) > 1.13] \
              + [(1.20, 1.10), (1.20, 0.36), (1.55, 0.36)]
        lin = sobre(bvh, [(x, s * 3, z) for x, z in pts], (0, -s, 0), 0.0)
        tubos(f"{p}_Junta_Puerta_Delantera_{A.n(s)}", [lin], 0.0035)
        manija(f"{p}_Manija_Puerta_Delantera_{A.n(s)}", bvh, s, 1.30, 1.02, largo=0.15)
    corr = [(1.16, 0.33), (1.16, 1.95), (-0.02, 1.95), (-0.02, 0.33), (1.16, 0.33)]
    lin = sobre(bvh, [(x, -3, z) for x, z in corr], (0, 1, 0), 0.0)
    tubos(f"{p}_Junta_Puerta_Corrediza_Der", [lin], 0.0035)
    lin = sobre(bvh, [(x, -3, 1.07) for x in (-0.02, -0.6, -1.2)], (0, 1, 0), 0.004)
    tubos(f"{p}_Riel_Puerta_Corrediza_Der", [lin], 0.010)
    manija(f"{p}_Manija_Puerta_Corrediza_Der", bvh, -1, 0.05, 1.02, largo=0.18, alto=0.04)
    A.espejos(1.95, 1.16, largo=0.24, alto=0.26, prof=0.11)
    for s in (1, -1):
        # faros grandes envolventes
        pieza_oblicua(f"{p}_Faro_Delantero_{A.n(s)}", bvh, (2.85, s * 0.62, 0.97), (-1, -s * 0.35, -0.25),
                      [(-0.17, 0.045), (-0.16, -0.05), (0.05, -0.065), (0.22, -0.04), (0.24, 0.04), (0.10, 0.065),
                       (-0.06, 0.06)], desp=0.004, espesor=0.012, abombado=0.006)
        # calaveras verticales bajas en las esquinas traseras
        pieza_oblicua(f"{p}_Faro_Posterior_{A.n(s)}", bvh, (-2.95, s * 0.90, 0.92), (1, -s * 0.35, 0),
                      [(-0.05, 0.20), (-0.06, -0.18), (0.04, -0.20), (0.09, -0.12), (0.09, 0.16), (0.04, 0.21)],
                      desp=0.004, espesor=0.014, abombado=0.003)
        frontal(f"{p}_Marco_Neblinero_{A.n(s)}", bvh, 4.0,
                [(s * 0.60, 0.60), (s * 0.72, 0.59), (s * 0.72, 0.47), (s * 0.62, 0.48)], desp=0.003, espesor=0.01)
        pt, _ = proyectar(bvh, (4.0, s * 0.66, 0.535), (-1, 0, 0), 0.012)
        if pt:
            superelipsoide(f"{p}_Neblinero_{A.n(s)}", pt, (0.012, 0.04, 0.03), n=3)
        manija(f"{p}_Escalon_Lateral_{A.n(s)}", bvh, s, 1.38, 0.30, largo=0.30, alto=0.03)
    pr = [(-0.40, 0.99), (0.40, 0.99), (0.44, 0.88), (-0.44, 0.88)]
    frontal(f"{p}_Parrilla", bvh, 4.0, pr, desp=0.002, espesor=0.006)
    barras_parrilla(f"{p}_Parrilla_Barras", bvh, 4.0, pr, [0.91, 0.965], r=0.007, desp=0.012)
    marco = sobre(bvh, [(4.0, y, 0.94) for y in (-0.44, 0.44)], (-1, 0, 0), 0.012)
    tubos(f"{p}_Parrilla_Barra_Cromada", [marco], 0.014)
    inf = [(-0.56, 0.66), (0.56, 0.66), (0.46, 0.46), (-0.46, 0.46)]
    frontal(f"{p}_Toma_Inferior", bvh, 4.0, inf, desp=0.002, espesor=0.006)
    barras_parrilla(f"{p}_Toma_Inferior_Barras", bvh, 4.0, inf, [0.50 + 0.04 * k for k in range(4)], r=0.005,
                    desp=0.009)
    pt, _ = proyectar(bvh, (4.0, 0, 0.75), (-1, 0, 0), 0.02)
    box(f"{p}_Placa_Delantera", (0.012, 0.34, 0.11), pt)
    junta_superior(A, "Junta_Capo", [(2.77, -0.62), (2.55, -0.80), (2.28, -0.82), (2.29, 0.0), (2.28, 0.82),
                                     (2.55, 0.80), (2.77, 0.62), (2.79, 0.0), (2.77, -0.62)])
    # portalon trasero, parachoque, placa y escape
    junta_trasera(A, "Junta_Portalon", [(-0.80, 2.18), (-0.82, 0.62), (0.82, 0.62), (0.80, 2.18), (-0.80, 2.18)])
    pt, _ = proyectar(bvh, (-5.0, 0, 0.98), (1, 0, 0), 0.01)
    box(f"{p}_Placa_Posterior", (0.012, 0.34, 0.11), pt)
    pt, _ = proyectar(bvh, (-5.0, 0, 1.12), (1, 0, 0), 0.012)
    box(f"{p}_Manija_Portalon", (0.02, 0.24, 0.04), pt, bevel=0.006)
    frontal(f"{p}_Parachoque_Posterior_Escalon", bvh, -5.0,
            [(-0.90, 0.50), (0.90, 0.50), (0.88, 0.38), (-0.88, 0.38)], desp=0.03, espesor=0.02, atras=True)
    cyl(f"{p}_Tubo_Escape", 0.032, 0.16, (-2.85, -0.60, 0.33), axis="X", verts=20)
    pt, _ = proyectar(bvh, (-2.65, 0, 5), (0, 0, -1), 0.0)
    box(f"{p}_Tercera_Luz_Freno", (0.06, 0.40, 0.03), pt + Vector((-0.02, 0, 0.0)), bevel=0.01)
    for s in (1, -1):
        a, _ = proyectar(bvh, (2.20, s * 0.05, 5), (0, 0, -1), 0.012)
        b, _ = proyectar(bvh, (2.12, s * 0.66, 5), (0, 0, -1), 0.012)
        beam(f"{p}_Limpiaparabrisas", a, b, 0.016, t2=0.010)
    A.mover(Y)


# ---------------------------------------------------------------------------
MODELOS = [(corolla, "Toyota_Corolla"), (swift, "Suzuki_Swift"), (rav4, "Toyota_RAV4"),
           (hilux, "Toyota_Hilux"), (hiace, "Toyota_Hiace")]
SOLO = os.environ.get("SOLO")
for i, (fn, nom) in enumerate(MODELOS):
    if SOLO and str(i + 1) not in SOLO.split(","):
        continue
    grupo(f"{i + 1:02d}_{nom}")
    fn(i * 3.0)

finalizar(os.environ.get("SALIDA", "autos_modelo.blend"), AQUI)
