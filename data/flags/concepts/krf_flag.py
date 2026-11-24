import math, io, resvg_py
from PIL import Image
RED,BLUE,GOLD,DK,WH="#BA0C2F","#00205B","#E0B33A","#3a2a05","#FFFFFF"
# Norwegian flag 22:16, cross 6+1+2+1+12 x 6+1+2+1+6, unit=50
U=50; FW,FH=22*U,16*U; X0=7*U+U//1; X0=8*U; Y0=8*U   # cross centre (400,400)
d=88; R=104; W=22
ang={'A':-90,'B':150,'C':30}
# centre emblem's bounding box on the cross (top lobe reaches d+R, lower lobes d/2+R)
oy=(d-d/2)/2
cx,cy=X0,Y0+oy
C={k:(cx+d*math.cos(math.radians(a)),cy+d*math.sin(math.radians(a))) for k,a in ang.items()}
def ring(k,clip=None):
    x,y=C[k]; c=f' clip-path="url(#{clip})"' if clip else ''
    return (f'<g{c}><circle cx="{x:.2f}" cy="{y:.2f}" r="{R}" fill="none" stroke="{DK}" stroke-width="{W+8}"/>'
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{R}" fill="none" stroke="{GOLD}" stroke-width="{W}"/></g>')
def inter(a,b):
    (x0,y0),(x1,y1)=C[a],C[b]; dd=math.hypot(x1-x0,y1-y0); h=math.sqrt(R*R-dd*dd/4)
    mx,my=(x0+x1)/2,(y0+y1)/2; ux,uy=(x1-x0)/dd,(y1-y0)/dd
    p=[(mx-uy*h,my+ux*h),(mx+uy*h,my-ux*h)]
    p.sort(key=lambda q:math.hypot(q[0]-cx,q[1]-cy))  # [inner, outer]
    return p
# Borromean-style alternation: each pair crosses over once and under once
over=[('A','B','B','A'),('B','C','C','B'),('C','A','A','C')]  # pair, top at inner, top at outer
defs=[];tops=''
for i,(a,b,ti,to) in enumerate(over):
    pin,pout=inter(a,b)
    for j,(p,t) in enumerate([(pin,ti),(pout,to)]):
        cid=f'x{i}{j}'
        defs.append(f'<clipPath id="{cid}"><circle cx="{p[0]:.2f}" cy="{p[1]:.2f}" r="{W+10}"/></clipPath>')
        tops+=ring(t,cid)
def at(k,off):
    a=math.radians(ang[k]); return cx+(d+off)*math.cos(a), cy+(d+off)*math.sin(a)
ex,ey=at('A',22); dx,dy=at('B',26); lx,ly=at('C',26)
eye=f'''<g transform="translate({ex:.1f},{ey:.1f}) scale(0.92)">
<path d="M0,-40 L42,30 L-42,30Z" fill="none" stroke="{WH}" stroke-width="8" stroke-linejoin="round"/>
<path d="M-24,10 Q0,-10 24,10 Q0,30 -24,10Z" fill="{WH}"/><circle cx="0" cy="10" r="7.5" fill="{BLUE}"/></g>'''
dove=f'''<g transform="translate({dx:.1f},{dy:.1f}) scale(0.95)" fill="{WH}">
<path d="M-40,8 Q-22,0 -4,4 Q10,-8 24,-6 Q34,-4 36,2 L46,4 L36,8 Q30,22 8,26 Q-12,28 -24,22 L-44,30 L-38,16Z"/>
<path d="M-8,6 Q-30,-24 -14,-46 Q-6,-30 2,-26 Q0,-40 12,-48 Q18,-22 14,0Z"/>
<path d="M44,6 Q50,14 50,24" fill="none" stroke="{WH}" stroke-width="3.5" stroke-linecap="round"/>
<ellipse cx="48" cy="12" rx="5.5" ry="3" transform="rotate(50 48 12)"/><ellipse cx="51" cy="22" rx="5.5" ry="3" transform="rotate(-40 51 22)"/>
<circle cx="27" cy="0" r="2.8" fill="{BLUE}"/></g>'''
lamb=f'''<g transform="translate({lx:.1f},{ly:.1f}) scale(0.95)" fill="{WH}">
<path d="M-28,12 L-28,36 M-12,14 L-12,38 M8,14 L8,38 M22,12 L22,36" stroke="{WH}" stroke-width="8" stroke-linecap="round"/>
<circle cx="-30" cy="0" r="14"/><circle cx="-16" cy="-10" r="15"/><circle cx="2" cy="-10" r="15"/><circle cx="18" cy="-2" r="14"/>
<circle cx="-8" cy="10" r="15"/><circle cx="12" cy="10" r="13"/><circle cx="-26" cy="12" r="11"/>
<ellipse cx="38" cy="-18" rx="11" ry="15" transform="rotate(-25 38 -18)"/>
<ellipse cx="27" cy="-25" rx="9" ry="4" transform="rotate(25 27 -25)"/>
<circle cx="40" cy="-21" r="2.6" fill="{BLUE}"/></g>'''
discs=''.join(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{R}" fill="{BLUE}"/>' for x,y in C.values())
# white field centred on the cross intersection, sized to clear the furthest ring edge
reach=max(math.hypot(x-X0,y-Y0) for x,y in C.values())+R+W/2+4+14
svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="{FW}" height="{FH}" viewBox="0 0 {FW} {FH}"><defs>{''.join(defs)}</defs>
<rect width="{FW}" height="{FH}" fill="{RED}"/>
<rect x="{6*U}" width="{4*U}" height="{FH}" fill="{WH}"/><rect y="{6*U}" width="{FW}" height="{4*U}" fill="{WH}"/>
<rect x="{7*U}" width="{2*U}" height="{FH}" fill="{BLUE}"/><rect y="{7*U}" width="{FW}" height="{2*U}" fill="{BLUE}"/>

{discs}{eye}{dove}{lamb}
{ring('A')}{ring('B')}{ring('C')}{tops}</svg>'''
open('C.svg','w').write(svg)
im=Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=svg)))).convert('RGB'); im.save('C.png')
s=im.resize((82,52),Image.LANCZOS); s.save('C_82.png'); s.resize((410,260),Image.NEAREST).save('C_82_zoom.png')
print('reach',reach, 'oy',oy)
