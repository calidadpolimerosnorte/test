import ezdxf, sys, math
from ezdxf.math import Vec3
from PIL import Image, ImageDraw, ImageFont
doc = ezdxf.readfile(sys.argv[1]); msp = doc.modelspace()
X0, Y0, X1, Y1, PX = [float(v) for v in sys.argv[3].split(',')]
W, H = int((X1 - X0) * PX), int((Y1 - Y0) * PX)
img = Image.new('RGB', (W, H), 'white'); g = ImageDraw.Draw(img)
try: fuente = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14)
except: fuente = ImageFont.load_default()
def P(x, y): return ((x - X0) * PX, (Y1 - y) * PX)
def color(l):
    if l.startswith('40_'): return (200, 30, 30)
    if l.startswith('10_'): return (30, 30, 30)
    if l.startswith('20_'): return (40, 90, 200)
    if l.startswith('30_'): return (20, 140, 60)
    if l.startswith('50_'): return (150, 0, 150)
    if l.startswith('170_'): return (230, 140, 0)
    return (150, 150, 150)
saltar = ('60_', '70_', '80_')
textos = []
def dibujar(e, capa=None, prof=0):
    l = capa if (capa and e.dxf.layer == '0') else e.dxf.layer
    if l.startswith(saltar): return
    t = e.dxftype(); c = color(l)
    try:
        if t == 'LINE':
            g.line([P(e.dxf.start.x, e.dxf.start.y), P(e.dxf.end.x, e.dxf.end.y)], fill=c, width=1)
        elif t in ('LWPOLYLINE', 'POLYLINE'):
            pts = [P(p[0], p[1]) for p in (e.get_points('xy') if t == 'LWPOLYLINE' else [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices])]
            if e.closed: pts.append(pts[0])
            if len(pts) > 1: g.line(pts, fill=c, width=1)
        elif t == 'CIRCLE':
            x, y = P(e.dxf.center.x, e.dxf.center.y); r = e.dxf.radius * PX
            g.ellipse([x - r, y - r, x + r, y + r], outline=c)
        elif t == 'ARC':
            pts = [P(*p[:2]) for p in e.flattening(0.02)]
            if len(pts) > 1: g.line(pts, fill=c, width=1)
        elif t in ('TEXT', 'MTEXT') and prof == 0:
            s = e.dxf.text if t == 'TEXT' else e.plain_text()
            textos.append((P(e.dxf.insert.x, e.dxf.insert.y), s.replace('\n', ' '), c))
        elif t == 'INSERT' and prof < 4:
            for v in e.virtual_entities(): dibujar(v, l, prof + 1)
        elif t == 'DIMENSION' and prof == 0:
            m = e.get_measurement()
            for v in e.virtual_entities(): dibujar(v, '170_', prof + 1)
    except Exception as ex: pass
for e in msp:
    if e.dxftype() in ('HATCH',): continue
    dibujar(e)
for (x, y), s, c in textos:
    if 0 <= x < W and 0 <= y < H: g.text((x, y), s[:40], fill=c, font=fuente)
# rejilla cada 5 m
for gx in range(int(X0) // 5 * 5, int(X1) + 1, 5):
    x, _ = P(gx, 0); g.line([(x, 0), (x, 12)], fill=(255, 0, 255)); g.text((x + 2, 0), str(gx), fill=(255, 0, 255), font=fuente)
for gy in range(int(Y0) // 5 * 5, int(Y1) + 1, 5):
    _, y = P(0, gy); g.line([(0, y), (12, y)], fill=(255, 0, 255)); g.text((2, y + 2), str(gy), fill=(255, 0, 255), font=fuente)
img.save(sys.argv[2])
print(W, H)
