"""Place the approved winter-lake glyph blueprint into desktop character grids.

Runtime reads explicit printable glyphs, inks and materials only. It never reads
or paints the reference image. Portrait framing uses the same-size typography.
"""
import json
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


def build_landscape(cols,rows,portrait=False,blueprint=None):
    data=blueprint or load_blueprint();width,height=data['columns'],data['rows']
    def sample(x,y):
        x=max(0,min(width-1,int(x)));y=max(0,min(height-1,int(y)))
        char=data['glyph_rows'][y][x];ink=data['ink_rows'][y][x]
        rgb=tuple(int(ink[i:i+2],16)/255 for i in (1,3,5))
        return (char,rgb,data['material_rows'][y][x],sum(rgb)/3)
    cells=[]
    for row in range(rows):
        for col in range(cols):
            if not portrait:
                x=col+(width-cols)/2;y=row+(height-rows)/2
                cells.append(sample(x,y))
            else:
                # Crop the left/central lake into the narrow output, retaining
                # glyph pitch. Place the original shore around 73.5% height.
                x=width*.16+col
                y=row-(rows*.735-height*.70)
                if y<0:
                    # Extend the reference's faint sky rather than stretching
                    # the mountain ridge vertically into artificial towers.
                    sky_y=(row*.43+col*.07)%max(1,int(height*.24))
                    char,ink,_,value=sample((x+row*.11)%width,sky_y)
                    cells.append((char,ink,'sky',value))
                elif y>=height:
                    # Continue the low foreground's open mesh and snow texture.
                    char,ink,_,value=sample(x,height-5+(row%5))
                    cells.append((char,ink,'foreground',value))
                else:cells.append(sample(x,y))
    return cells
