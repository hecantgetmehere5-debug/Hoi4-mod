import io,resvg_py
from PIL import Image,ImageDraw,ImageFont
R,B,W,G='#BA0C2F','#00205B','#FFFFFF','#F4C430'; GD='#C8961E'
U=50; WID,HEI=22*U,16*U  # true 22:16, square cross units
def base():
    return (f'<rect width="{WID}" height="{HEI}" fill="{R}"/>'
     f'<rect x="{6*U}" width="{4*U}" height="{HEI}" fill="{W}"/><rect y="{6*U}" width="{WID}" height="{4*U}" fill="{W}"/>'
     f'<rect x="{7*U}" width="{2*U}" height="{HEI}" fill="{B}"/><rect y="{7*U}" width="{WID}" height="{2*U}" fill="{B}"/>')
CX,CY=3*U,3*U
def ear(L,n=4):
    s=f'<path d="M0,0 L0,{-L*0.6}" stroke="{G}" stroke-width="14" stroke-linecap="round"/>'
    for i in range(n):
        y=-L*0.45-i*(L*0.13)
        for sg in(-1,1):
            s+=f'<ellipse cx="{sg*13}" cy="{y}" rx="12" ry="24" transform="rotate({sg*25} {sg*13} {y})" fill="{G}"/>'
    s+=f'<ellipse cx="0" cy="{-L*0.45-n*L*0.13+4}" rx="11" ry="24" fill="{G}"/>'
    return s
def A():
    s=''
    for a in(-26,0,26): s+=f'<g transform="rotate({a})">{ear(190)}</g>'
    for a in(-20,0,20): s+=f'<g transform="rotate({180+a})"><path d="M0,0 L0,-100" stroke="{G}" stroke-width="16" stroke-linecap="round"/></g>'
    s+=f'<rect x="-36" y="-22" width="72" height="40" rx="8" fill="{GD}"/>'
    return f'<g transform="translate({CX},{CY+40}) scale(0.82)">{s}</g>'
def B_():
    fork=(f'<rect x="-14" y="-90" width="28" height="300" rx="10" fill="{G}"/>'
          f'<path d="M-70,-80 L70,-80 L70,-200 L42,-200 L42,-110 L14,-110 L14,-215 L-14,-215 L-14,-110 L-42,-110 L-42,-200 L-70,-200 Z" fill="{G}"/>')
    scythe=(f'<rect x="-14" y="-200" width="28" height="410" rx="10" fill="{G}"/>'
            f'<path d="M0,-200 Q-110,-270 -220,-170 Q-110,-205 0,-140 Z" fill="{G}"/>')
    return f'<g transform="translate({CX},{CY+5}) scale(0.5)"><g transform="rotate(-30)">{fork}</g><g transform="rotate(30)">{scythe}</g></g>'
def C():
    s=''
    for sg in(-1,1):
        s+=f'<g transform="scale({sg},1)"><path d="M-8,100 Q-115,40 -95,-80" fill="none" stroke="{G}" stroke-width="16" stroke-linecap="round"/>'
        for t,ang in((0.35,-55),(0.7,-25),(0.98,0)):
            x=(1-t)**2*-8+2*(1-t)*t*-115+t*t*-95; y=(1-t)**2*100+2*(1-t)*t*40+t*t*-80
            s+=f'<g transform="translate({x},{y}) rotate({ang}) scale(0.55)">{ear(130,3)}</g>'
        s+='</g>'
    leaf=f'<path d="M0,80 C-62,30 -55,-55 0,-110 C55,-55 62,30 0,80 Z" fill="#2E9E46" stroke="{G}" stroke-width="8"/><path d="M0,70 L0,-80" stroke="{G}" stroke-width="10" stroke-linecap="round"/>'
    return f'<g transform="translate({CX},{CY+5}) scale(0.82)">{s}{leaf}</g>'
def D():
    p=(f'<path d="M-140,-120 L-30,40" stroke="{G}" stroke-width="34" stroke-linecap="round"/>'   # handle
       f'<path d="M-170,-115 L-110,-125" stroke="{G}" stroke-width="30" stroke-linecap="round"/>' # grip
       f'<rect x="-60" y="25" width="200" height="34" rx="8" fill="{G}"/>'                      # beam
       f'<path d="M-10,55 L150,55 L60,120 L-40,120 Z" fill="{G}"/>'                              # share/mouldboard
       f'<path d="M120,30 L150,-40" stroke="{G}" stroke-width="26" stroke-linecap="round"/>')    # hitch
    return f'<g transform="translate({CX-12},{CY+12}) scale(0.68)">{p}</g>'
SNAP={(82,52):(19,22,28,31),(41,26):(10,11,14,15)}
def pbase(w,h,a,b,c,d):
    return (f'<rect width="{w}" height="{h}" fill="{R}"/><rect x="{a}" width="{d-a}" height="{h}" fill="{W}"/><rect y="{a}" width="{w}" height="{d-a}" fill="{W}"/>'
            f'<rect x="{b}" width="{c-b}" height="{h}" fill="{B}"/><rect y="{b}" width="{w}" height="{c-b}" fill="{B}"/>')
def svg(sym,w=WID,h=HEI):
    if (w,h) in SNAP:
        a,b,c,d=SNAP[(w,h)]; cw=a  # canton is a x a px
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" shape-rendering="crispEdges">{pbase(w,h,a,b,c,d)}<g shape-rendering="geometricPrecision" transform="scale({cw/(6*U)})">{sym}</g></svg>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {WID} {HEI}">{base()}{sym}</svg>'
def png(s): return Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=s)))).convert('RGB')
F={'A':A,'B':B_,'C':C,'D':D}
names={'A':'A  Wheat sheaf (recommended)','B':'B  Scythe & pitchfork','C':'C  Wheat wreath & leaf','D':'D  Plough'}
tiles=[]
for k,f in F.items():
    big=png(svg(f())); big.save(f'ncl_{k}.png')
    for w,h in((82,52),(41,26)):
        png(svg(f(),w,h)).save(f'ncl_{k}_{w}x{h}.png')
    sm=Image.open(f'ncl_{k}_82x52.png').resize((410,260),Image.NEAREST); sm.save(f's_{k}.png')
    tiles.append((k,big,sm))
try: fnt=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',34)
except: fnt=ImageFont.load_default()
tw,th=550,400; sheet=Image.new('RGB',(2*tw+60,2*(th+60+140)+20),'#ECECEC'); d=ImageDraw.Draw(sheet)
for i,(k,big,sm) in enumerate(tiles):
    x=20+(i%2)*(tw+20); y=10+(i//2)*(th+200)
    d.text((x,y),names[k],fill='#222',font=fnt)
    sheet.paste(big.resize((tw,th),Image.LANCZOS),(x,y+48))
    sheet.paste(sm.resize((205,130),Image.NEAREST),(x,y+48+th+10))
    sheet.paste(Image.open(f'ncl_{k}_41x26.png').resize((164,104),Image.NEAREST),(x+225,y+48+th+10))
sheet.save('all.png')
