import ezdxf, sys, pickle
from ezdxf import bbox
doc = ezdxf.readfile(sys.argv[1]); msp = doc.modelspace()
res = {}
for e in msp:
    l = e.dxf.layer
    if l.startswith(('60_','70_')): continue
    try:
        b = bbox.extents([e], fast=True)
        if not b.has_data: continue
        r = (round(b.extmin.x,2), round(b.extmin.y,2), round(b.extmax.x,2), round(b.extmax.y,2))
    except Exception as ex: continue
    nombre = e.dxf.name if e.dxftype()=='INSERT' else ''
    res.setdefault(l, []).append((e.dxftype(), nombre, r, round(getattr(e.dxf,'rotation',0) or 0,1)))
pickle.dump(res, open(sys.argv[2],'wb'))
for l, v in sorted(res.items()):
    xs = [r[2][0] for r in v] + [r[2][2] for r in v]; ys = [r[2][1] for r in v] + [r[2][3] for r in v]
    print(f'{l:45s} {len(v):5d}  x {min(xs):9.1f}..{max(xs):9.1f}  y {min(ys):9.1f}..{max(ys):9.1f}')
