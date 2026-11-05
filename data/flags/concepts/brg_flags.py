import io,re,sys,resvg_py
from PIL import Image,ImageDraw,ImageFont,ImageFilter
d=sys.argv[1]
raw=open(d+'/src/bergen.svg').read()
inner=raw[raw.index('<g\n     id="g10"'):raw.rindex('</svg>')]; inner=re.sub(r'\s(inkscape|sodipodi):[a-z-]+="[^"]*"','',inner)
R,W,G,K,DR='#DE2537','#FFFFFF','#CD9217','#231f20','#7A0E1A'
W0,H0=1200,800
def seal(cx,cy,size):
    k=size/471.486
    return (f'<circle cx="{cx}" cy="{cy}" r="{size/2+6}" fill="{DR}"/>'
            f'<g transform="translate({cx-size/2},{cy-size/2}) scale({k})"><circle cx="235.74" cy="235.74" r="234" fill="{G}"/>{inner}</g>')
def castle():
    s=''
    def tower(x0,x1,top,n):
        w=(x1-x0)/(2*n-1);t=f'<rect x="{x0}" y="{top+5}" width="{x1-x0}" height="{40-top}" fill="{W}"/>'
        for i in range(n): t+=f'<rect x="{x0+2*i*w}" y="{top}" width="{w}" height="6" fill="{W}"/>'
        return t
    s+=tower(-31,-15,-26,3)+tower(15,31,-26,3)+tower(-11,11,-38,3)
    s+=f'<rect x="-33" y="-6" width="66" height="34" fill="{W}"/>'
    for i in range(6): s+=f'<rect x="{-33+i*12.4}" y="-11" width="6" height="6" fill="{W}"/>'
    s+=f'<path d="M-8,28 L-8,12 A8,8 0 0 1 8,12 L8,28 Z" fill="{K}"/>'
    for x,y in [(-25,-18),(21,-18),(-2,-30),(-22,6),(18,6)]: s+=f'<rect x="{x}" y="{y}" width="4" height="7" rx="2" fill="{K}"/>'
    return s
def emblem(cx,cy,size,ring=True):
    k=size/100
    s=f'<clipPath id="c"><circle r="44"/></clipPath>'
    s+=f'<circle r="{50 if ring else 44}" fill="{DR}"/>' if ring else ''
    if ring: s+=f'<circle r="47.5" fill="{G}"/>'
    s+=f'<circle r="43" fill="{R}"/><g clip-path="url(#c)">{castle()}'
    s+=f'<path d="M-50,50 L-50,30 Q-30,22 -15,29 Q0,21 15,29 Q30,22 50,30 L50,50 Z" fill="{G}"/></g>'
    return f'<g transform="translate({cx},{cy}) scale({k})">{s}</g>'
def tinycastle(cx,cy,size):
    return f'<g transform="translate({cx},{cy}) scale({size/100})">{castle()}</g>'
def cog(cx,cy,w,col=G):
    k=w/200
    p=(f'<path d="M-100,10 L100,10 L80,50 L-80,50 Z"/><rect x="-4" y="-100" width="8" height="112"/>'
       f'<path d="M-58,-88 Q-46,-42 -58,0 L58,0 Q70,-42 58,-88 Z"/><path d="M4,-100 L34,-108 L4,-116 Z"/>'
       f'<path d="M-100,10 L-112,-16 L-78,10 Z M100,10 L114,-18 L78,10 Z"/>')
    return f'<g transform="translate({cx},{cy}) scale({k})" fill="{col}">{p}</g>'
def body(k,mode):  # mode: big|game|tiny
    E=(lambda x,y,s: seal(x,y,s)) if mode=='big' else (lambda x,y,s: emblem(x,y,s*1.0)) if mode=='game' else (lambda x,y,s: tinycastle(x,y,s*1.15))
    if k=='A': return f'<rect width="{W0}" height="{H0}" fill="{R}"/><rect y="400" width="{W0}" height="400" fill="{W}"/>'+E(600,400,500)
    if k=='B': return f'<rect width="{W0}" height="{H0}" fill="{R}"/>'+E(380,400,480)+('' if mode=='tiny' else cog(900,470,330))
    if k=='C':
        z=' '.join(f'L{x},{690 if (x//100)%2 else 610}' for x in range(0,1201,100))
        return f'<rect width="{W0}" height="{H0}" fill="{R}"/><path d="M0,800 {z} L1200,800 Z" fill="{G}"/>'+E(600,330,460)
    if k=='D':
        return (f'<rect width="{W0}" height="{H0}" fill="{W}"/><rect x="330" width="160" height="{H0}" fill="{R}"/>'
                f'<rect y="320" width="{W0}" height="160" fill="{R}"/>'+(E(410,400,380) if mode!='tiny' else ''))
def svg(b): return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W0}" height="{H0}" viewBox="0 0 {W0} {H0}">{b}</svg>'
def rend(b,w,h):
    s=svg(b).replace(f'width="{W0}" height="{H0}" viewBox',f'width="{w}" height="{h}" viewBox',1)
    return Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=s)))).convert('RGB')
def small(k,mode,w,h):
    im=rend(body(k,mode),w*4,h*4).resize((w,h),Image.LANCZOS)
    return im.filter(ImageFilter.UnsharpMask(radius=0.6,percent=60,threshold=0))
names={'A':'A  Hanseatic bicolour','B':'B  Arms + cog in fly','C':'C  Gonfalon (dancetty)','D':'D  Nordic cross'}
font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',26)
sheet=Image.new('RGB',(1300,1120),'#2b2b2b');dr=ImageDraw.Draw(sheet)
for i,k in enumerate('ABCD'):
    big=rend(body(k,'big'),1200,800);big.save(f'{d}/brg_{k}.png')
    m=small(k,'game',82,52);m.save(f'{d}/brg_{k}_82.png')
    s2=small(k,'game',41,26);s2.save(f'{d}/brg_{k}_41.png')
    t=small(k,'tiny',10,7);t.save(f'{d}/brg_{k}_10.png')
    x=20+(i%2)*640;y=20+(i//2)*550
    sheet.paste(big.resize((600,400),Image.LANCZOS),(x,y))
    dr.text((x,y+408),names[k],fill='white',font=font)
    sheet.paste(m,(x,y+445));sheet.paste(s2,(x+100,y+445));sheet.paste(t,(x+160,y+445))
    sheet.paste(m.resize((164,104),Image.NEAREST),(x+200,y+440))
sheet.save(d+'/all.png')
