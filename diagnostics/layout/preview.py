"""Render bounds emitted by the production-method harness; not a game screenshot."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
here=Path(__file__).resolve().parent
data=json.loads((here/'beta5-geometry.json').read_text())
image=Image.new('RGB',(800,660),'#101721')
draw=ImageDraw.Draw(image)
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',16)
draw.text((30,16),'Beta 5 layout diagram - not a native game render',font=font,fill='white')
draw.rectangle((50,70,750,620),fill='#191919',outline='#8794a8',width=2)
labels={'Title':'Friendlies','Host':'HOST','Room code':'Room Code','Input':'Select to enter room code...',
 'Keyboard hint':'Select the field, then press STEAM+X to type','Paste':'PASTE CODE','Join':'JOIN',
 'Status':'Reserved status message (wrap / ellipsis)','Back':'BACK',
 'Controls':'Stick: move   A: select   B: back   STEAM+X: keyboard'}
for key,(left,bottom,right,top) in data['boxes'].items():
 rect=(400+left,345-top,400+right,345-bottom)
 fill='#343b49' if key in ('Host','Paste','Join','Back') else '#292930' if key=='Input' else '#191919'
 draw.rectangle(rect,fill=fill,outline='#607185' if key!='Status' else '#8b7755')
 draw.text(((rect[0]+rect[2])/2,(rect[1]+rect[3])/2),labels[key],font=small if key in ('Controls','Keyboard hint','Status') else font,anchor='mm',fill='#e3e8ee')
draw.text((50,630),'Bounds from executed production setup; font/artwork are placeholders.',font=small,fill='#bdc6d3')
image.save(here/'beta5-layout-diagram.png')
print(here/'beta5-layout-diagram.png')
