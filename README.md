# 🔮 API 余额桌面小组件

Windows 桌面小组件，实时显示 **DeepSeek** 和**通义千问 (DashScope)** 的 API 余额与状态。

![screenshot](https://github.com/3120647866-code/balance-widget/raw/main/screenshot.png)

## ✨ 特性

- 🪟 **白色磨玻璃质感** — Windows 11 Mica/Acrylic 背景模糊，20px 圆角
- 📍 **桌面右上角** — 自动定位，可拖拽移动
- 📥 **最下层显示** — 始终在应用窗口之下，不遮挡工作
- 🔤 **清晰美观字体** — Microsoft YaHei UI，层级分明
- 🚀 **开机自启** — 一键安装到 Startup 文件夹
- 🔄 **自动刷新** — 每 10 分钟更新余额数据

## 📦 安装

```bash
# 1. 安装依赖
pip install PyQt6 requests pywin32

# 2. 克隆项目
git clone git@github.com:3120647866-code/balance-widget.git
cd balance-widget

# 3. 运行
python balance_widget.py

# 4. (可选) 开机自启
install_startup.bat
```

## 📋 依赖

| 包 | 用途 |
|---|------|
| `PyQt6` | GUI 窗口与渲染 |
| `requests` | API 余额查询 |
| `pywin32` | Windows 原生 API 调用 |
| `pillow` | 可选，截图调试用 |

## 🔑 API 密钥配置

小组件自动从以下位置读取密钥：

1. 环境变量：`ANTHROPIC_AUTH_TOKEN`（DeepSeek）和 `DASHSCOPE_API_KEY`（千问）
2. Claude Code 配置：`~/.claude/settings.json` 中的 `env` 字段

## 🖱️ 使用

| 操作 | 方法 |
|------|------|
| 刷新数据 | 右键 → `立即刷新` |
| 移动位置 | 左键拖拽 |
| 退出组件 | 右键 → `退出` |
| 手动启动 | 双击 `start_widget.vbs` |

## 🛠️ 技术实现

- **磨玻璃效果**：Windows 11 `DwmSetWindowAttribute` (Mica/Acrylic) + Qt 半透明白色背景
- **圆角**：`DWMWA_WINDOW_CORNER_PREFERENCE` 原生圆角 + CSS `border-radius`
- **置底**：`WindowStaysOnBottomHint` + `SetWindowPos(HWND_BOTTOM)`
- **静默启动**：VBS 调用 `pythonw.exe`，无控制台窗口
