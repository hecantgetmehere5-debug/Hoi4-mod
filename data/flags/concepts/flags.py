import re,io,sys,resvg_py,arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image,ImageDraw,ImageFont
D='/private/tmp/claude-501/-Users-filip67-Documents-GitHub-Hoi4-mod/5a8001ff-df39-4f0d-9f94-62b2706ffaa2/scratchpad/jnp_flags/'
s=open(D+'src/coa.svg').read()
els=[m.group(0) for m in re.finditer(r'<(path|polygon|rect|circle)\b[^>]*>',s)]
G='#008543'
LION=''.join(els[i] for i in range(21,42))
AXE=''.join(els[i] for i in [20,42,43,44])
SHIELD=els[18]+els[19]
PAW=(76,276)
def sword(tr,blade=260):
    b=blade
    return f'''<g transform="{tr}" stroke="#1a1a1a" stroke-width="3" stroke-linejoin="round">
<path d="M-10,-34 L-10,{-b+34} L0,{-b} L10,{-b+34} L10,-34 Z" fill="#ffffff"/>
<path d="M0,-34 L0,{-b} L10,{-b+34} L10,-34 Z" fill="#cfd6dc" stroke="none"/>
<path d="M-10,-34 L-10,{-b+34} L0,{-b} L10,{-b+34} L10,-34 Z" fill="none"/>
<line x1="0" y1="-40" x2="0" y2="{-b+44}" stroke="#9aa5ad" stroke-width="2"/>
<path d="M-42,-26 Q-46,-34 -38,-38 L38,-38 Q46,-34 42,-26 Z" fill="#ffffff"/>
<rect x="-6" y="-26" width="12" height="52" rx="3" fill="#e6e9ec"/>
<circle cx="0" cy="34" r="10" fill="#ffffff"/></g>'''
def lion(tr,weapon='sword',sw_tr=None):
    w=''
    if weapon=='sword': w=sword(sw_tr or f'translate({PAW[0]},{PAW[1]}) scale(0.55)')
    if weapon=='axe': w=AXE
    return f'<g transform="{tr}">{w}{LION}</g>'
def crescent(cx,cy,R,dy,r,col=G):
    return f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="#fff"/><circle cx="{cx}" cy="{cy-dy}" r="{r}" fill="{col}"/>'
def place(cx,cy,sc,bx=172,by=395):
    return f'translate({cx},{cy}) scale({sc}) translate({-bx},{-by})'
def concept(k):
    if k=='A':
        return crescent(600,330,290,72,252)+lion(place(600,350,1.3))
    if k=='B':
        return crescent(600,360,270,100,240)+lion(place(612,345,1.3),sw_tr=f'translate({PAW[0]},{PAW[1]}) rotate(-20) scale(0.5)')
    if k=='C':
        sw=''.join(sword(f'translate(600,340) rotate({a}) translate(0,175) scale(1.2)',320) for a in (-38,38))
        return '<circle cx="600" cy="335" r="290" fill="#fff"/><circle cx="608" cy="340" r="245" fill="'+G+'"/><path d="M600,335 L470,0 L730,0 Z" fill="'+G+'"/>'+sw+lion(place(600,350,1.1),weapon=None)
    if k=='D':
        sh=f'<g transform="{place(600,352,1.12,160,398)}">{SHIELD}{LION}{AXE}</g>'
        return crescent(600,66,54,20,47)+sh+sword('translate(600,585) rotate(-90) translate(0,0) scale(0.9)',300).replace('translate(600,585) rotate(-90) translate(0,0)','translate(465,598) rotate(90)')
def text(img,y,size):
    t=get_display(arabic_reshaper.reshape('النرويج للأمة'))
    f=ImageFont.truetype('/System/Library/Fonts/GeezaPro.ttc',size,index=1)
    d=ImageDraw.Draw(img); w=d.textlength(t,font=f)
    d.text((600-w/2,y),t,font=f,fill='white')
for k in 'ABCD':
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 800" width="1200" height="800"><rect width="1200" height="800" fill="{G}"/>{concept(k)}</svg>'
    im=Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=svg,width=1200)))).convert('RGB')
    text(im,655,78)
    im.save(D+f'concept_{k}.png')
ims=[Image.open(D+f'concept_{k}.png') for k in 'ABCD']
S=Image.new('RGB',(1240,880),'#1e1e1e');d=ImageDraw.Draw(S)
lf=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf',30)
for i,(k,im) in enumerate(zip('ABCD',ims)):
    x,y=20+(i%2)*610,20+(i//2)*430
    S.paste(im.resize((590,393),Image.LANCZOS),(x,y+25)); d.text((x,y-8),k,font=lf,fill='white')
S.save(D+'all.png')
