---
name: beautiful_html_templates
description: "生成精美的单文件 HTML 横向翻页演示文稿，视觉风格为编辑杂志 × 电子墨水"
metadata: {"nanobot":{"always":false}}
---

# Beautiful HTML Templates Skill

将提示词生成单文件 HTML 横向翻页演示文稿，视觉风格是"编辑杂志 × 电子墨水"，就像 Monocle 杂志缝上了代码。

## 两套视觉系统

### Style A - 电子杂志 × 电子墨水风格
适合叙事、观点、分享、个人风格表达。特点：
- 电子墨水质感
- 编辑杂志排版
- 个人叙事风格

### Style B - 瑞士国际主义风格
适合事实、产品、分析、方法论表达。特点：
- 网格至上
- 单一高饱和锚点色
- 直角、丝线
- 极致字号对比

## 使用方法

1. **准备内容**：整理好要展示的内容（文字、图片、数据等）
2. **选择风格**：根据内容类型选择 Style A 或 Style B
3. **生成 HTML**：创建单文件 HTML 演示文稿
4. **本地预览**：在浏览器中打开 HTML 文件预览
5. **分享发布**：可直接分享 HTML 文件或部署到网站

## 技术要求

- 单文件 HTML（所有 CSS 和 JS 内联）
- 横向翻页（左右箭头或滑动）
- 响应式设计（支持桌面和移动设备）
- 无外部依赖（可离线运行）

## HTML 结构示例

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>演示文稿</title>
    <style>
        /* Style A 样式 */
        :root {
            --bg-color: #f5f5f5;
            --text-color: #1a1a1a;
            --accent-color: #0066cc;
        }

        body {
            margin: 0;
            padding: 0;
            background: var(--bg-color);
            color: var(--text-color);
            font-family: 'Georgia', serif;
            overflow-x: hidden;
        }

        .slide-container {
            display: flex;
            transition: transform 0.5s ease;
        }

        .slide {
            min-width: 100vw;
            height: 100vh;
            padding: 5rem;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .slide-content {
            max-width: 800px;
        }

        h1 {
            font-size: 4rem;
            margin-bottom: 1rem;
            font-weight: 300;
        }

        h2 {
            font-size: 2.5rem;
            margin-bottom: 1rem;
            font-weight: 400;
        }

        p {
            font-size: 1.2rem;
            line-height: 1.8;
            margin-bottom: 1.5rem;
        }

        .accent {
            color: var(--accent-color);
        }

        /* Style B 样式变体 */
        .style-b {
            --bg-color: #ffffff;
            --text-color: #000000;
            --accent-color: #ff3366;
            font-family: 'Helvetica Neue', sans-serif;
        }

        .style-b h1 {
            font-size: 8rem;
            font-weight: 700;
        }

        .style-b .grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 2rem;
        }
    </style>
</head>
<body>
    <div class="slide-container" id="slides">
        <div class="slide">
            <div class="slide-content">
                <h1 class="accent">标题页面</h1>
                <p>演示文稿的起始页</p>
            </div>
        </div>

        <div class="slide">
            <div class="slide-content">
                <h2>内容页面</h2>
                <p>详细的展示内容...</p>
            </div>
        </div>

        <!-- 更多页面... -->
    </div>

    <script>
        let currentSlide = 0;
        const slides = document.querySelectorAll('.slide');
        const totalSlides = slides.length;

        function goToSlide(index) {
            if (index < 0) index = 0;
            if (index >= totalSlides) index = totalSlides - 1;
            currentSlide = index;
            document.getElementById('slides').style.transform =
                `translateX(-${currentSlide * 100}vw)`;
        }

        // 键盘导航
        document.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowRight') goToSlide(currentSlide + 1);
            if (e.key === 'ArrowLeft') goToSlide(currentSlide - 1);
        });

        // 触摸滑动
        let startX = 0;
        document.addEventListener('touchstart', (e) => {
            startX = e.touches[0].clientX;
        });

        document.addEventListener('touchend', (e) => {
            const endX = e.changedTouches[0].clientX;
            const diff = startX - endX;
            if (Math.abs(diff) > 50) {
                if (diff > 0) goToSlide(currentSlide + 1);
                else goToSlide(currentSlide - 1);
            }
        });
    </script>
</body>
</html>
```

## 内容生成流程

### 步骤 1: 收集素材
从用户提供的内容中提取：
- 标题和副标题
- 主要段落文本
- 图片路径或 URL
- 数据图表信息
- 重点标注内容

### 步骤 2: 设计页面结构
根据内容类型规划：
- 封面页（标题 + 简介）
- 目录页（可选）
- 内容页（分段展示）
- 结束页（总结或联系方式）

### 步骤 3: 应用视觉风格
根据内容性质选择：
- **Style A**: 适合故事、观点、个人分享
  - 使用 Georgia/serif 字体
  - 柔和的背景色
  - 大字号标题，优雅排版

- **Style B**: 适合数据、产品、分析
  - 使用 Helvetica Neue/sans-serif
  - 白色背景，强对比色
  - 网格布局，极简设计

### 步骤 4: 添加交互功能
基础功能：
- 左右箭头键盘导航
- 触摸屏滑动支持
- 页码指示器（可选）
- 进度条（可选）

高级功能：
- 动画过渡效果
- 自动播放模式
- 嵌入视频/音频
- 外部链接按钮

## 最佳实践

1. **单文件原则**: 所有资源内联，确保离线可用
2. **性能优化**: 压缩 CSS/JS，优化图片大小
3. **响应式设计**: 适配桌面、平板、手机
4. **可访问性**: 提供键盘导航，清晰字体
5. **品牌一致性**: 保持配色和字体风格统一

## 同类产品参考

- guizang-ppt-skill
- frontend-slides-editable
- reveal.js

## 输出格式

生成完整的 HTML 文件，包含：
- `<!DOCTYPE html>` 声明
- 完整的 `<head>` 标签（meta, title, style）
- `<body>` 标签内的幻灯片内容
- 内联 JavaScript 交互逻辑
- 注释说明各部分功能

文件命名建议：`presentation-[主题]-[日期].html`