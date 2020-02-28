import pygame,sys
from pygame.locals import *

RED=(255,0,0)
BLACK=(0,0,0)


def main():
    pygame.init()
    screen=pygame.display.set_mode((600,400))

    x=20
    y=20
    r=255
    g=1
    b=1
    color=(r,g,b)
    
    pygame.draw.rect(screen,BLACK,(0,0,600,400))
    pygame.draw.circle(screen,color,(x,y),10)
    pygame.display.update()

    while True:

        for event in pygame.event.get():
            if event.type==QUIT:
                sys.exit()
            if event.type==KEYDOWN:
                if event.key==K_LEFT:
                    x-=5
                elif event.key==K_RIGHT:
                    x+=5
                elif event.key==K_UP:
                    y-=5
                elif event.key==K_DOWN:
                    y+=5
            r-=1
            b+=1
            g+=1
            if r==0:
                r=255
            if b==255:
                b=0
            if g==255:
                g=0
                
            color=(r,g,b)
            
            pygame.draw.rect(screen,BLACK,(0,0,600,400))
            pygame.draw.circle(screen,color,(x,y),10)
            pygame.display.update()
            
 
main()
