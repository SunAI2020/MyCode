 import pygame
import random
import sys
import os

# 初始化Pygame
pygame.init()
pygame.mixer.init()

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
YELLOW = (255, 255, 0)

# 创建游戏窗口
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("飞机大战")

# 时钟对象
clock = pygame.time.Clock()

# 创建资源目录
if not os.path.exists("resources"):
    os.makedirs("resources")
  
# 加载游戏资源
try:
    # 加载背景图片
    bg_img = pygame.image.load("resources/bg.jpg")
    bg_img = pygame.transform.scale(bg_img, (SCREEN_WIDTH, SCREEN_HEIGHT))
    
    # 加载玩家飞机图片
    player_img = pygame.image.load("resources/player.png")
    player_img = pygame.transform.scale(player_img, (60, 60))
    
    # 加载敌人飞机图片
    enemy_img = pygame.image.load("resources/enemy.png")
    enemy_img = pygame.transform.scale(enemy_img, (60, 60))
    
    # 加载子弹图片
    bullet_img = pygame.image.load("resources/bullet.png")
    bullet_img = pygame.transform.scale(bullet_img, (15, 30))
    
    # 加载爆炸图片
    explosion_img = pygame.image.load("resources/explosion.png")
    explosion_img = pygame.transform.scale(explosion_img, (100, 100))
    
except Exception as e:
    print(f"资源加载失败: {e}")
    # 使用默认图形
    bg_img = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    bg_img.fill((0, 100, 150))
    for _ in range(100):
        x = random.randint(0, SCREEN_WIDTH)
        y = random.randint(0, SCREEN_HEIGHT)
        pygame.draw.circle(bg_img, WHITE, (x, y), 1)
    
    player_img = pygame.Surface((60, 60))
    player_img.fill(BLUE)
    pygame.draw.polygon(player_img, WHITE, [(30, 0), (60, 60), (30, 50), (0, 60)])
    
    enemy_img = pygame.Surface((60, 60))
    enemy_img.fill(RED)
    pygame.draw.polygon(enemy_img, BLACK, [(30, 0), (60, 60), (0, 60)])
    
    bullet_img = pygame.Surface((15, 30))
    bullet_img.fill(WHITE)
    
    explosion_img = pygame.Surface((100, 100))
    explosion_img.fill(YELLOW)

# 加载背景音乐
try:
    # 尝试加载背景音乐
    pygame.mixer.music.load("resources/bgm.mp3")
    pygame.mixer.music.set_volume(0.5)
    pygame.mixer.music.play(-1)
except Exception as e:
    print(f"背景音乐加载失败: {e}")
    # 如果没有背景音乐，使用内置音效
    print("使用游戏内置音效")

# 玩家类
class Player(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.image = player_img
        self.rect = self.image.get_rect()
        self.rect.centerx = SCREEN_WIDTH // 2
        self.rect.bottom = SCREEN_HEIGHT - 30
        self.speed = 8
        self.shoot_delay = 200
        self.last_shot = pygame.time.get_ticks()
        self.health = 100
    
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
        self.rect.y = random.randrange(-150, -50)
        self.speed_y = random.randrange(2, 5)
        self.speed_x = random.randrange(-3, 4)
        self.health = 20
    
    def update(self):
        self.rect.y += self.speed_y
        self.rect.x += self.speed_x
        # 边界检查
        if self.rect.top > SCREEN_HEIGHT + 10 or self.rect.left < -30 or self.rect.right > SCREEN_WIDTH + 30:
            self.rect.x = random.randrange(SCREEN_WIDTH - self.rect.width)
            self.rect.y = random.randrange(-150, -50)
            self.speed_y = random.randrange(2, 5)
            self.speed_x = random.randrange(-3, 4)

# 子弹类
class Bullet(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = bullet_img
        self.rect = self.image.get_rect()
        self.rect.centerx = x
        self.rect.bottom = y
        self.speed_y = -15
    
    def update(self):
        self.rect.y += self.speed_y
        # 边界检查
        if self.rect.bottom < 0:
            self.kill()

# 爆炸类
class Explosion(pygame.sprite.Sprite):
    def __init__(self, center):
        super().__init__()
        self.images = []
        # 创建爆炸动画帧
        for i in range(5):
            size = 100 - i * 20
            img = pygame.transform.scale(explosion_img, (size, size))
            self.images.append(img)
        self.image = self.images[0]
        self.rect = self.image.get_rect()
        self.rect.center = center
        self.frame = 0
        self.last_update = pygame.time.get_ticks()
        self.frame_rate = 50
        # 播放爆炸音效
        try:
            pygame.mixer.Sound.play(pygame.mixer.Sound("resources/explosion.wav"))
        except:
            # 如果没有音效文件，使用内置音效
            pygame.mixer.Sound.play(pygame.mixer.Sound(pygame.mixer.SND_ALARM))
    
    def update(self):
        now = pygame.time.get_ticks()
        if now - self.last_update > self.frame_rate:
            self.last_update = now
            self.frame += 1
            if self.frame >= len(self.images):
                self.kill()
            else:
                self.image = self.images[self.frame]
                self.rect = self.image.get_rect(center=self.rect.center)

# 创建精灵组
all_sprites = pygame.sprite.Group()
enemies = pygame.sprite.Group()
bullets = pygame.sprite.Group()
explosions = pygame.sprite.Group()

# 创建玩家
player = Player()
all_sprites.add(player)

# 创建敌人
for i in range(8):
    enemy = Enemy()
    all_sprites.add(enemy)
    enemies.add(enemy)

# 分数和生命值
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
    hits = pygame.sprite.groupcollide(enemies, bullets, False, True)
    for hit in hits:
        hit.health -= 10
        if hit.health <= 0:
            score += 10
            explosion = Explosion(hit.rect.center)
            all_sprites.add(explosion)
            explosions.add(explosion)
            hit.kill()
            enemy = Enemy()
            all_sprites.add(enemy)
            enemies.add(enemy)
    
    # 碰撞检测：敌人击中玩家
    hits = pygame.sprite.spritecollide(player, enemies, True)
    for hit in hits:
        player.health -= 20
        explosion = Explosion(hit.rect.center)
        all_sprites.add(explosion)
        explosions.add(explosion)
        enemy = Enemy()
        all_sprites.add(enemy)
        enemies.add(enemy)
        if player.health <= 0:
            explosion = Explosion(player.rect.center)
            all_sprites.add(explosion)
            explosions.add(explosion)
            running = False
    
    # 绘制背景
    screen.blit(bg_img, (0, 0))
    
    # 绘制精灵
    all_sprites.draw(screen)
    
    # 绘制分数
    score_text = font.render(f"分数: {score}", True, WHITE)
    screen.blit(score_text, (10, 10))
    
    # 绘制生命值
    health_text = font.render(f"生命: {player.health}", True, WHITE)
    screen.blit(health_text, (SCREEN_WIDTH - 100, 10))
    
    # 更新显示
    pygame.display.flip()

# 游戏结束
pygame.quit()
sys.exit()