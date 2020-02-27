import pygame,sys
from pygame.locals import *
pygame.init()

width=1000
height=800
                           
RED=(255,0,0)
BLACK=(0,0,0)
GRAY=(128,128,128)
r=250
g=10
b=10
dr=-1
dg=1
db=3
color=(r,g,b)

x=163
y=120
dx=1
dy=1

cr=5
dcr=1

screen=pygame.display.set_mode((width,height))
pygame.display.set_caption("小球自弹跳")

while True:
    for event in pygame.event.get():
        if event.type==pygame.QUIT:
            sys.exit()
    x+=dx
    y+=dy
    if x<cr+1 or (x+cr+1)>width:
        dx=-dx
    if y<cr+1 or (y+cr+1)>height:
        dy=-dy
    screen.fill(GRAY)
    pygame.draw.circle(screen,color,(x,y),cr)

    r+=dr
    b+=db
    g+=dg
   
    if r<10 or r>250:
        dr=-dr
    if b<10 or b>250:
        db=-db
    if g<10 or g>250:
        dg=-dg
                
    color=(r,g,b)

    cr+=dcr
    if cr>20 or cr<10:
        dcr=-dcr
                           
    pygame.display.update()

 
