"""Place the approved winter-lake glyph blueprint into desktop character grids.

Runtime reads explicit printable glyphs, inks and materials only. It never reads
or paints the reference image. Portrait framing uses the same-size typography.
"""
import json
import math
from pathlib import Path


def load_blueprint(path=None):
    path=Path(path) if path else Path(__file__).parent/'assets/winter-lake-glyphs.json'
    data=json.loads(path.read_text())
    cols,rows=data['columns'],data['rows']
    if cols<1 or rows<1:raise ValueError('Glyph blueprint dimensions must be positive')
    for key in ('glyph_rows','ink_rows','material_rows'):
        if len(data[key])!=rows or any(len(row)!=cols for row in data[key]):
            raise ValueError('Invalid glyph blueprint row geometry: '+key)
    if any(not 32<=ord(c)<=126 for row in data['glyph_rows'] for c in row):
        raise ValueError('Scenery must contain only printable ASCII')
    return data


def cell_noise(col,row,salt=0):
    """Stable cell-local randomness without translating or wrapping scene fragments."""
    value=((col+71)*374761393 ^ (row+317)*668265263 ^ salt)&0xffffffff
    value=((value^(value>>13))*1274126177)&0xffffffff
    return ((value^(value>>16))&0xffffffff)/4294967296


def portrait_sky(col,row,rows,paper):
    """Faint native glyph grain and sparse stars, never a copied sky strip."""
    noise=cell_noise(col,row)
    chars="....,,,::;''++*"
    char=' ' if noise<.28 else chars[int(cell_noise(col,row,0x45d9f3b)*len(chars))]
    strength=(.35+.65*cell_noise(col,row,0x119de1f3))*(.70+.30*row/max(1,rows-1))
    if noise>.9985:
        char='+' if noise>.99925 else '*'
        strength=2.5+1.5*cell_noise(col,row,0x27d4eb2d)
    elif noise>.989:
        char='.'
        strength=1+cell_noise(col,row,0x165667b1)
    ink=tuple(p+d*strength for p,d in zip(paper,(.060,.075,.095)))
    return (char,ink,'sky',sum(ink)/3)


def build_landscape(cols,rows,portrait=False,blueprint=None):
    data=blueprint or load_blueprint();width,height=data['columns'],data['rows']
    paper=tuple(int(data['paper'][i:i+2],16)/255 for i in (1,3,5))
    def sample(x,y):
        x=max(0,min(width-1,int(x)));y=max(0,min(height-1,int(y)))
        char=data['glyph_rows'][y][x];ink=data['ink_rows'][y][x]
        rgb=tuple(int(ink[i:i+2],16)/255 for i in (1,3,5))
        return (char,rgb,data['material_rows'][y][x],sum(rgb)/3)
    def resample(x,y,col,row):
        # Interpolate ink; dither between the neighbouring native glyphs rather
        # than duplicating whole source rows when the lower scene grows taller.
        x0,y0=math.floor(x),math.floor(y);fx,fy=x-x0,y-y0
        neighbours=[(sample(x0,y0),(1-fx)*(1-fy)),(sample(x0+1,y0),fx*(1-fy)),
                    (sample(x0,y0+1),(1-fx)*fy),(sample(x0+1,y0+1),fx*fy)]
        ink=tuple(sum(cell[1][k]*weight for cell,weight in neighbours) for k in range(3))
        pick=cell_noise(col,row,0x85ebca6b)
        chosen=neighbours[-1][0]
        for cell,weight in neighbours:
            pick-=weight
            if pick<0:
                chosen=cell;break
        kind=sample(round(x),round(y))[2]
        return (chosen[0],ink,kind,sum(ink)/3)
    cells=[]
    shore=rows*.735
    start=shore-height*.70
    x_start=width*.16
    x_span=min(max(0,cols-1),max(0,width-1-x_start))
    for row in range(rows):
        for col in range(cols):
            if not portrait:
                cells.append(sample(col+(width-cols)/2,row+(height-rows)/2))
                continue
            # Preserve the lake's shore and the character layout. Each source
            # foreground row is traversed once; there is no bottom-strip tiling.
            x=x_start+col*x_span/max(1,cols-1)
            if row>=shore:
                progress=(row-shore)/max(1,rows-1-shore)
                y=(height-1)*.70+progress*(height-1)*.30
                cell=resample(x,y,col,row)
            else:
                y=row-start
                cell=sample(x,y) if y>=0 else None
            if cell is None or cell[2]=='sky':
                cell=portrait_sky(col,row,rows,paper)
            cells.append(cell)
    return cells
