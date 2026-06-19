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

1. **不要泄露凭证文件**
   - `userinfo.db` 和 `quick_snippets_v2.json` 分别存储了加密后的 SSH 凭证和快捷命令配置，**已加入 `.gitignore`**，请勿提交。

2. **密钥安全与 Keyring 集成**
   - 本项目现在默认将**用于对称加密的主密钥**存储在操作系统的原生安全凭证管理库中（例如 macOS 的 Keychain、Windows 的 Credential Manager）。
   - 这大大提升了本地数据的安全性。如果您在无桌面的纯命令行环境运行，程序会自动降级并在本地生成 `.secret.key` 密钥文件。
   - 如果您使用的是旧版本的 `.secret.key`，程序首次启动时会自动将其迁移至 Keyring，并将原文件重命名为 `.secret.key.bak`。请勿提交此备份文件。

3. **重新生成密钥的后果**
   - 无论是重置 Keyring 中的密钥，还是删除了本地的 `.secret.key` 文件，程序会自动生成新密钥。但这会导致**之前保存的所有站点凭证解密失败失效**，需要重新添加站点。
