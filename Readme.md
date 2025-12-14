# TypeF

## 简介

**LyricsFlow** 的服务端核心。

**TypeF** 是一个 **歌词聚合**与**解密网关**，旨在解决跨平台歌词格式混乱的问题。

服务端负责接收标准化的元数据请求，并发搜索多个上游音乐平台，将加密或非标准的歌词格式（如 QRC、KRC、LRC）清洗并转换为统一的 **LyricsFlow Standard JSON** 格式返回给客户端。

## 核心特性

- #### **多源聚合**
   - 支持并发请求 QQ 音乐（QRC）、网易云音乐（LRC）、酷狗音乐（KRC）、Musixmatch。
   - 内置 `songmid`、`media_mid` 及 `FileHash` 的映射与处理逻辑。
   - **Meting 引擎**: 采用 [Meting](https://github.com/metowolf/Meting) 的 Python 移植实现，提供统一 API 接口。
- #### **歌词解密**
   - 支持 **QRC** 解密（TripleDES + Zlib）。
   - 支持 **KRC** 解密（XOR + Zlib）。
   - 支持网易云 API 参数加密（AES-128-ECB EAPI）。
   - 支持 Base64 解码（Tencent/Kugou via Meting）。
- #### **智能匹配**
   - **时长过滤**：自动剔除时长误差超过 ±2000ms 的结果。
   - **模糊匹配**：基于 `rapidfuzz` (Levenshtein Distance) 计算歌名、艺人、专辑的加权相似度。
   - **翻译回落**：支持英文名转中文后的二次匹配。
   - **纯音乐回避**：
      - **不中止**: 遭遇纯音乐/空歌词结果时，继续搜索后续匹配项。
      - **优先歌词**: 优先返回包含歌词的结果，仅在无其他选择时回退至纯音乐版本。
- #### **标准化输出**
   - 所有歌词统一转换为包含**逐字 (Syllable)** 时间戳的 JSON 格式，供客户端直接渲染。
   - **智能清洗**
      - 自动识别并剥离“作词/作曲/编曲/制作人”等元数据行，将其移入 `credits` 字段。
      - 采用 **安全窗口** 策略，仅扫描首尾 12 行，确保正文中包含类似“Producer”的歌词不被误删。
      - 对时间戳为 `00:00.00` 的行进行更激进的元数据清理。
- #### **本地缓存**
   - 文件级 JSON 缓存，避免重复计算与下载，显著提升响应速度。
- #### **AI 增强**
   - **歌词补全**: 补全缺失的**翻译**、**罗马音 (Romaji)** 及**脏标 (Explicit)**。
   - **BYOK (Bring Your Own Key)**: 支持客户端传入 API Key/BaseURL，实现私有化或中继调用。
   - **个性化翻译**: 支持用户自定义翻译风格，且非标准结果不污染本地缓存。
   - **众包缓存**: 若用户进行标准翻译，结果将保留至缓存。

---

## 技术栈

- **Language**: Python 3.11+ (利用异步特性与类型提示)
- **Web Framework**: FastAPI
- **Server**: Uvicorn (ASGI)
- **Key Libraries**:
   - `httpx`: 异步 HTTP 请求
   - `pycryptodome`: 加密与解密核心
   - `rapidfuzz`: 高性能字符串匹配
   - `beautifulsoup4`: 网页解析辅助

---

## 快速开始

#### 使用 Docker 部署（推荐）

TypeF 专为容器化环境设计，建议使用 Docker Compose 启动。

1. **拉取代码**

   Bash

```other
git clone https://github.com/liuhaoultra/lyricsflow-typef.git
cd lyricsflow-typef
```

2. **构建并启动**

   Bash

```other
docker-compose up -d --build
```

3. 验证服务

   访问 `http://localhost:8000/v1/health` ，若返回 {"status": "ok"} 说明服务正常。

#### 使用 Dockge 部署

1. 进入 Dockge 管理的 Stacks 目录（例如 `/opt/stacks`）。
2. 克隆本项目：
   ```bash
   git clone https://github.com/liuhaoultra/lyricsflow-typef.git lyricsflow-typef
   ```
3. 回到 Dockge Web 面板，点击右上角 `扫描堆栈文件夹`。
4. 在列表中找到 `lyricsflow-typef`，点击进入。
5. 点击 `编辑` 按钮，并配置 `.env` 变量。
6. 点击 `部署` 按钮，Dockge 将自动构建并启动服务。

---

## API 文档

#### 获取歌词 (Meting)

- **Endpoint**: `POST /v1/match`
- **描述**: 使用 Meting 统一 API 搜索并获取歌词，优先使用 `{lyric, tlyric}` 格式。若 Meting 失败则自动回退到传统 Provider。

#### 获取歌词 (Legacy)

- **Endpoint**: `POST /v1/match_legacy`
- **描述**: 使用传统 Provider 实现（直接调用各平台加密 API）。

JSON

```other
{
  "title": "Anti-Hero",
  "artist": "Taylor Swift",
  "album": "Midnights",
  "duration": 200.5
}
```

#### 响应示例

返回标准的 **LyricsFlow JSON**：

JSON

```other
{
  "type": "syllable",
  "source": "qq_music",
  "match_score": 98,
  "lines": [
    {
      "st": 12.5,
      "et": 15.2,
      "txt": "It's me, hi, I'm the problem, it's me",
      "words": [
        {"txt": "It's", "st": 12.5, "et": 12.8},
        {"txt": " me,", "st": 12.8, "et": 13.1},
        ...
      ]
    }
  ]
}
```

---

## 配置

支持通过 `.env` 文件或环境变量进行配置：

| 变量名               | 描述                 | 默认值   |
| ----------------- | ------------------ | ----- |
| PORT              | 服务监听端口             | 8000  |
| LOG_LEVEL         | 日志等级               | INFO  |
| PROXY_URL         | 上游请求代理 (可选)        | None  |
| ENABLE_QQ         | 启用 QQ 音乐源          | True  |
| ENABLE_NETEASE    | 启用网易云源             | True  |
| ENABLE_KUGOU      | 启用酷狗音乐源            | True  |
| ENABLE_MUSIXMATCH | 启用 Musixmatch 源    | True  |
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

**Meting Engine**: TypeF 的统一 API 层基于 [`Meting`](https://github.com/metowolf/Meting) (Node.js) 的 Python 移植实现。感谢 [`@metowolf`](https://github.com/metowolf) 提供的优雅的音乐 API 框架。

**Legacy Decryption**: 解密与聚合逻辑参考并移植自 [`Lyricify-Lyrics-Helper`](https://github.com/WXRIW/Lyricify-Lyrics-Helper)。特别感谢 [`@WXRIW`](https://github.com/WXRIW) 及其上游开源社区的贡献。

---

## 许可证

本项目基于 **Apache-2.0** 许可证。

## 免责声明

本项目仅供技术研究与教育目的使用。

1. 本项目**不提供**任何受版权保护的音频文件。
2. 所有歌词数据均来自第三方公开 API，项目开发者不对第三方内容的**准确性**或**合法性**负责。
3. 请在下载后的 24 小时内删除相关数据，支持正版。