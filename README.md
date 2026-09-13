# 飞机大战游戏

这是一个基于Pygame开发的飞机大战手机游戏。

## 功能特性

- **专业游戏资源**：使用高质量的星际基地背景、飞机和敌机图片
- **爆炸效果**：飞机中弹时的爆炸起火动画
- **背景音乐**：电子游戏专用音乐
- **游戏机制**：
  - 方向键控制飞机移动
  - 空格键发射子弹
  - 击中敌人获得分数
  - 玩家有生命值系统
  - 敌人随机出现并移动

## 运行游戏

### 安装依赖

```bash
python -m pip install pygame
```

### 运行游戏

```bash
python plane_war_pro.py
```

## 打包为手机APP

要将游戏打包为手机APP，您可以使用Buildozer工具。以下是基本步骤：

### 1. 安装Buildozer

```bash
pip install buildozer
```

### 2. 初始化Buildozer配置

在游戏目录中运行：

```bash
buildozer init
```

### 3. 修改buildozer.spec文件

编辑生成的buildozer.spec文件，设置以下内容：

```ini
[app]
title = 飞机大战
package.name = planewar
package.domain = org.test
source.dir = .
source.include_exts = py,png,jpg,mp3
version = 1.0
requirements = python3,kivy,pygame
orientation = portrait
osx.python_version = 3
fullscreen = 0
android.api = 28
android.sdk = 24
android.ndk = 17
android.arch = armeabi-v7a
```

### 4. 打包APK

```bash
buildozer android debug
```

### 5. 安装到手机

打包完成后，您可以在`bin`目录中找到生成的APK文件，将其安装到手机上。

## 游戏控制

- **方向键**：控制飞机移动
- **空格键**：发射子弹
- **ESC键**：退出游戏

## 游戏资源

游戏会自动下载以下资源：
- 星际基地背景图片
- 玩家飞机图片
- 敌人飞机图片
- 子弹图片
- 爆炸效果图片

如果下载失败，游戏会使用默认的几何图形代替。

## 注意事项

- 游戏窗口大小为480x800像素，适合手机屏幕比例
- 首次运行时会下载游戏资源，可能需要一些时间
- 背景音乐需要单独下载，您可以将喜欢的MP3文件命名为`bgm.mp3`并放在`resources`目录中