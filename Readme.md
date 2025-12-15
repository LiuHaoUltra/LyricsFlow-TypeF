# TypeF

## 简介

**LyricsFlow** 的服务端核心。

**TypeF** 是一个 **歌词聚合**与**解密网关**，旨在解决跨平台歌词格式混乱的问题。

服务端负责接收标准化的元数据请求，并发搜索多个上游音乐平台，将加密或非标准的歌词格式（如 QRC、KRC、LRC）清洗并转换为统一的 **LyricsFlow Standard JSON** 格式返回给客户端。

## 核心特性

- #### **多源聚合**
   - 支持并发请求 QQ 音乐（QRC）、网易云音乐（LRC）、酷狗音乐（KRC）。
   - 内置 `songmid`、`media_mid` 及 `FileHash` 的映射与处理逻辑。
   - **差异化超时**: 国内源 15s 标准超时。

... (skipped parts) ...

#### 获取歌词

- **Endpoint**: `POST /v1/match`
- **描述**: 使用多源聚合搜索并获取歌词。并发请求 QQ/网易/酷狗，智能匹配最佳结果。

... (skipped parts) ...

| 变量名               | 描述                 | 默认值   |
| ----------------- | ------------------ | ----- |
| PORT              | 服务监听端口             | 9000  |
| LOG_LEVEL         | 日志等级               | INFO  |
| PROXY_URL         | 上游请求代理 (可选)        | None  |
| ENABLE_QQ         | 启用 QQ 音乐源          | True  |
| ENABLE_NETEASE    | 启用网易云源             | True  |
| ENABLE_KUGOU      | 启用酷狗音乐源            | True  |
| ENABLE_ENRICH     | 启用 AI 增强服务（Server） | False |
| ENRICH_URL        | AI 增强服务 URL        | None  |
| ENRICH_KEY        | AI 增强服务 Key        | None  |

#### 双端API策略

   **ENABLE_ENRICH** 控制 **LyricsFlow 服务器**（TypeF）的AI API，配置后任何人都可以调用！

   如果正在使用 **LyricsFlow 客户端**（TypeL），设置页面中提供选项，开启并配置 **AI 增强服务（Client）** 后，请求AI功能时向服务器发送 **客户端AI API** 配置，由服务器代请求，该状态下，使用 **客户端配置** 请求。

---

## 贡献

欢迎提交 PR 改进解密算法或增加新的歌词源。

在提交代码前，请确保：

1. 所有新的解密逻辑均有单元测试覆盖。
2. 遵循 PEP 8 编码规范。

---

## **致谢**

**Legacy Decryption**: 解密与聚合逻辑参考并移植自 [`Lyricify-Lyrics-Helper`](https://github.com/WXRIW/Lyricify-Lyrics-Helper)。特别感谢 [`@WXRIW`](https://github.com/WXRIW) 及其上游开源社区的贡献。

---

## 许可证

本项目基于 **Apache-2.0** 许可证。

## 免责声明

本项目仅供技术研究与教育目的使用。

1. 本项目**不提供**任何受版权保护的音频文件。
2. 所有歌词数据均来自第三方公开 API，项目开发者不对第三方内容的**准确性**或**合法性**负责。
3. 请在下载后的 24 小时内删除相关数据，支持正版。