# 星语声音记忆库

[浏览声音目录](https://wangjiqing.github.io/xingyu-music-library/) · [提出核对建议](https://github.com/wangjiqing/xingyu-music-library/issues/new/choose)

整理歌曲、影视动画原声与游戏配乐，保留声音的版本、出处和记忆线索。GitHub 只托管条目与相关资料，音频由收藏者在对象存储或本地另行管理。

初始数据来自视听资料整理表 v40：提取 3,127 行来源，合并完全一致的行后得到 1,066 条目录记录和 40 个专题。数量不代表核定后的独立作品数。所有初始记录尚未逐项核验，差异记录保留供核对。

## 日常完善

1. 在网站打开一个条目，通过“提出核对建议”附上出处，或通过“编辑条目”修改对应 JSON。
2. 编辑 `data/entries/<条目ID>.json` 时保留 `id`，将 `revision` 加一，保留历史来源和未解决的问题。
3. 修改提交至主分支后，GitHub Actions 校验资料并自动重新发布网站。协作者或 Agent 建议通过 PR 提交，先检查再合并。

新增条目可运行：

```sh
python3 scripts/new_entry.py --title '曲目名称' --artist '署名待核'
```

脚本会生成稳定 ID 和待核状态，再按真实资料填写其他字段。专题成员同时记录在 `data/catalog.json` 与条目的 `collection_ids` 中，校验会检查两者一致。

## 本地预览

仅需 Python 3 和现代浏览器，不需要 npm 安装或数据库服务。

```sh
python3 scripts/build.py
python3 -m http.server 4173 --directory dist
```

打开本地 `http://localhost:4173`。构建只输出允许发布的页面和 JSON，不打包原始 Excel、私有笔记、音频或对象存储凭据。

## 数据与页面分工

- `data/entries/`：每条一份 JSON，是条目事实的编辑源。
- `data/catalog.json`：来源快照、专题和导入规则。
- `web/`：HTML、CSS 和浏览器交互。
- `scripts/`：导入、校验、构建与新增条目。
- `docs/IMPLEMENTATION.md`：部署、维护及数据库选型说明。
- `docs/AGENT_CONTRACT.md`：未来 Agent 的核对提案与音频关联约定。
- `private/`、原始 Excel 和音频均不提交 GitHub。

当前网站默认浏览完整目录，分页展示并显示总数，支持文字与别名搜索、类型／年代／语言／核对状态筛选、来源定位、稳定详情链接和资料下载。搜索无结果时，可以把关键词带入 GitHub 收录请求；请求目前由维护者处理，Agent 自动联网检索仍待配置。

## 资料使用

来源链接只表示原整理资料提供了该参考，未代表页面已检查或全部字段获证实。推荐级为原整理意见。当前尚未指定整体数据与文章的再利用许可；引用时请保留条目 ID 与原始出处，不把第三方材料视为项目自有内容。
