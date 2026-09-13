import pygame
import random
import sys

# 初始化Pygame
pygame.init()

# 游戏常量
SCREEN_WIDTH = 480
SCREEN_HEIGHT = 800
FPS = 60

# 颜色定义
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)

# 创建游戏窗口
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("飞机大战")

# 时钟对象
clock = pygame.time.Clock()

# 直接使用简单图形作为游戏元素
bg_img = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
bg_img.fill((0, 100, 150))

# 添加星星背景
for _ in range(100):
    x = random.randint(0, SCREEN_WIDTH)
    y = random.randint(0, SCREEN_HEIGHT)
    pygame.draw.circle(bg_img, WHITE, (x, y), 1)

enemy_img = pygame.Surface((50, 50))
enemy_img.fill(RED)
# 绘制敌人形状
pygame.draw.polygon(enemy_img, BLACK, [(25, 0), (50, 50), (0, 50)])

player_img = pygame.Surface((50, 50))
player_img.fill(BLUE)
# 绘制玩家形状
pygame.draw.polygon(player_img, WHITE, [(25, 0), (50, 50), (25, 40), (0, 50)])

bullet_img = pygame.Surface((10, 20))
bullet_img.fill(WHITE)

# 调整图片大小
enemy_img = pygame.transform.scale(enemy_img, (50, 50))
player_img = pygame.transform.scale(player_img, (50, 50))
bullet_img = pygame.transform.scale(bullet_img, (10, 20))

# 玩家类
class Player(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.image = player_img
        self.rect = self.image.get_rect()
        self.rect.centerx = SCREEN_WIDTH // 2
        self.rect.bottom = SCREEN_HEIGHT - 10
        self.speed = 5
        self.shoot_delay = 250
        self.last_shot = pygame.time.get_ticks()
    
    def update(self):
        # 处理键盘事件
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] and self.rect.left > 0:
            self.rect.x -= self.speed
        if keys[pygame.K_RIGHT] and self.rect.right < SCREEN_WIDTH:
            self.rect.x += self.speed
        if keys[pygame.K_UP] and self.rect.top > 0:
            self.rect.y -= self.speed
        if keys[pygame.K_DOWN] and self.rect.bottom < SCREEN_HEIGHT:
            self.rect.y += self.speed
        if keys[pygame.K_SPACE]:
            self.shoot()
    
    def shoot(self):
        now = pygame.time.get_ticks()
        if now - self.last_shot > self.shoot_delay:
            self.last_shot = now
            bullet = Bullet(self.rect.centerx, self.rect.top)
            all_sprites.add(bullet)
            bullets.add(bullet)

# 敌人类
class Enemy(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.image = enemy_img
        self.rect = self.image.get_rect()
        self.rect.x = random.randrange(SCREEN_WIDTH - self.rect.width)
        self.rect.y = random.randrange(-100, -40)
        self.speed_y = random.randrange(1, 4)
        self.speed_x = random.randrange(-2, 3)
    
    def update(self):
        self.rect.y += self.speed_y
        self.rect.x += self.speed_x
        # 边界检查
        if self.rect.top > SCREEN_HEIGHT + 10 or self.rect.left < -25 or self.rect.right > SCREEN_WIDTH + 25:
            self.rect.x = random.randrange(SCREEN_WIDTH - self.rect.width)
            self.rect.y = random.randrange(-100, -40)
            self.speed_y = random.randrange(1, 4)
            self.speed_x = random.randrange(-2, 3)

# 子弹类
class Bullet(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = bullet_img
        self.rect = self.image.get_rect()
        self.rect.centerx = x
        self.rect.bottom = y
        self.speed_y = -10
    
    def update(self):
        self.rect.y += self.speed_y
        # 边界检查
        if self.rect.bottom < 0:
            self.kill()

# 创建精灵组
all_sprites = pygame.sprite.Group()
enemies = pygame.sprite.Group()
bullets = pygame.sprite.Group()

# 创建玩家
player = Player()
all_sprites.add(player)

# 创建敌人
for i in range(8):
    enemy = Enemy()
    all_sprites.add(enemy)
    enemies.add(enemy)

# 分数
score = 0
font = pygame.font.Font(None, 36)

# 游戏循环
running = True
while running:
    # 保持帧率
    clock.tick(FPS)
    
    # 事件处理
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
    
    # 更新精灵
    all_sprites.update()
    
    # 碰撞检测：子弹击中敌人
    hits = pygame.sprite.groupcollide(enemies, bullets, True, True)
    for hit in hits:
        score += 10
        enemy = Enemy()
        all_sprites.add(enemy)
        enemies.add(enemy)
    
    # 碰撞检测：敌人击中玩家
    hits = pygame.sprite.spritecollide(player, enemies, False)
    if hits:
        running = False
    
    # 绘制背景
    screen.blit(bg_img, (0, 0))
    
    # 绘制精灵
    all_sprites.draw(screen)
    
    # 绘制分数
    score_text = font.render(f"分数: {score}", True, WHITE)
    screen.blit(score_text, (10, 10))
    
    # 更新显示
    pygame.display.flip()

# 游戏结束
pygame.quit()
sys.exit()