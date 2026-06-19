# quicksftp

跨平台 SFTP/SSH 客户端工具。支持多标签页终端、并发文件传输与站点管理。

终端渲染基于自定义纯 Python 实现的终端小组件，底层使用 [pyte](https://github.com/selectel/pyte) 进行终端状态解析，并搭配原生 QPainter 进行高速图形绘制，摆脱了原本笨重的二进制依赖，实现了完全轻量化且无 Web 依赖。

## 主要特性

- 💼 **多标签页并发 SFTP/SSH 会话**与站点管理器
- 💻 **纯净、极速的自研终端引擎**：具备 10000 行虚拟滚动历史、平滑滚动条以及文本拷贝能力
- 🎨 **专业级暗色 / 亮色主题**：深度优化的配色方案，矢量图标随主题无缝变色，VSCode 风格无边框标签页
- ⌨️ **极简 Activity Bar 左侧导航栏**：为您提供最大化、零干扰的沉浸式终端体验
- ⚡ **底部状态联动**：全局状态栏可实时监测各个后台连接的健康状态（Ping）
- ⚙️ **全局设置中心**：支持自定义终端字体、文字大小与临时下载目录

## 安装

需要 Python **3.12+** 和 [uv](https://docs.astral.sh/uv/)。

```bash
git clone https://github.com/hanyoukuang/quicksftp.git
cd quicksftp
uv sync
```

## 运行

```bash
uv run python main.py
# 或安装后直接使用命令
uv run quickstfp
```

## 安全注意事项

**发布到 GitHub 前请确保：**

1. **`.secret.key` 文件不会被提交**
   - 该文件是用于加密 SSH 密码的 Fernet 对称密钥
   - 已加入 `.gitignore`，如果密钥文件已存在，请手动使用 `git rm --cached .secret.key` 从跟踪中移除

2. **`userinfo.db` 和 `quick_snippets_v2.json` 不会被提交**
   - 这些文件分别存储加密后的 SSH 凭证和快捷命令配置
   - 同样已加入 `.gitignore`

3. **首次运行** 时程序会自动生成新的 `.secret.key`，但之前保存的所有站点凭证将因密钥变更而失效，需要重新添加站点。
