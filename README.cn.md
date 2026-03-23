# personal-kb-curator

一个用于**整理、去重、沉淀并持续维护个人知识库/资料库**的 skill 仓库。

它适合处理这类场景：

- 文件夹里堆满了笔记、截图、PDF、草稿、重复版本，想整理成可维护的知识库。
- 已经有一套知识库结构，但会持续接收新资料，需要做**增量归档与合并**。
- 希望 assistant 在回答问题时，**优先检索规范化后的 canonical
  资产**，而不是全仓乱扫。
- 希望 agent 在发现新论文、新仓库或新文章时，先读轻量索引层而不是把
  整个知识库重新读一遍。
- 想把“保留 / 归档 / 回收 / 合并 / 标注冲突”的规则固定下来，避免每次重新判断。

## 仓库目标

这个 skill 的核心目标不是“把文件挪一挪”，而是把一批杂乱资料转成：

1. **可复用的 canonical knowledge assets**
2. **有明确状态和动作的 inventory**
3. **支持后续增量更新的仓库规则层**
4. **面向检索与问答的受控读取流程**

换句话说，它强调的是：

- 先结构化，再摘要
- 先分类，再合并
- 不静默吞掉冲突
- 不默认全量重建
- 让未来的 assistant 能继续接手，而不是一次性整理完就失控

## 适用场景

### 0. 研究发现与候选更新

当仓库已经沉淀了你的主题和结构后，这个 skill 也适合支持一个
`research-curator` agent：

- 先从 `AGENTS.md`、`docs/`、`00_index/` 这类轻量锚点推断当前关注点
- 在不全仓扫描的前提下发现相关的新论文、新仓库、新文章或新 benchmark
- 先按相关性与新颖性做候选分组
- 再把最终落库动作交给 `commands/kb-update.md`


### 1. 仓库冷启动 / 初次整理

当资料还没有稳定结构时，这个 skill 会帮助你：

- 盘点所有内容项
- 识别重复、近重复、补充材料、版本链和冲突
- 选择或合成 canonical note / canonical asset
- 建立 `AGENTS.md` 与 `docs/` 规则文件
- 产出索引、变更日志、归档决策等基础设施

### 2. 增量维护

当知识库已经成型，又有新文件进入时，这个 skill 会帮助你：

- 仅处理新增材料
- 分类其与已有 canonical 资产的关系
- 只更新受影响的资产
- 记录本轮更新和未解决问题

### 3. 问答检索

当用户基于整理后的仓库提问时，这个 skill 倡导：

- 先读规则文件
- 先从索引定位
- 首轮只读取少量高相关 canonical 资产
- 证据不足时再逐步扩展
- 明确标注来源与不确定性

## 核心方法论

该仓库内置了一套面向知识整理的判断框架。

### 分类标签

新资料或已有资料在聚类时，通常会落入以下关系之一：

- `duplicate`：本质相同，仅有微小差异
- `near_duplicate`：主体相同，但有可吸收增量
- `version_chain`：同一材料的版本演进
- `supplement`：补充信息，不替代主体
- `conflict`：存在不能静默合并的实质冲突
- `new_topic`：尚无对应主题或 canonical 资产

### 行动原则

- **duplicate**：归档或回收，不进入活跃内容
- **near_duplicate**：仅把有效增量合并进 canonical 资产
- **version_chain**：保留最新强版本为活跃资产，旧版归档
- **supplement**：作为 supporting material 关联到 canonical 资产
- **conflict**：保留冲突并显式标注待审查
- **new_topic**：创建新的 canonical note 或主题资产

### 默认价值观

- 保留信号，压缩噪声
- 不确定时优先 archive，而不是 delete
- 合成内容时保留来源映射
- 冲突必须显式处理
- 每个 item 都应有明确状态与动作

## 仓库结构

```text
.
├── commands/
│   └── kb-update.md               # 增量更新命令说明
└── skills/
    ├── SKILL.md                   # skill 主入口与触发说明
    ├── references/
    │   ├── decision-model.md      # 分类与 canonical 选择规则
    │   ├── repo-bootstrap.md      # 知识库规则层初始化指南
    │   └── schemas.md             # inventory / asset 字段规范
    └── templates/
        ├── canonical-note.md      # canonical note 模板
        ├── change-log.md          # change log 模板
        ├── intake-manifest.json   # intake manifest 模板
        └── repo/                  # 仓库规则层模板
```

## 关键文件说明

### `skills/SKILL.md`

这是 skill 的主说明文件，定义了：

- 什么时候应触发这个 skill
- 仓库 bootstrap、增量维护、问答检索三种模式
- 标准输出契约
- 推荐读取顺序与工作风格

### `skills/references/decision-model.md`

提供分类标签、canonical 选择优先级、动作映射与安全规则。

### `skills/references/schemas.md`

提供 inventory item 与 canonical asset 的推荐字段，方便输出结构统一。

### `skills/references/repo-bootstrap.md`

用于冷启动整理时生成仓库规则层，包括：

- `AGENTS.md`
- `docs/kb-policy.md`
- `docs/kb-structure.md`
- `docs/kb-update-policy.md`
- `docs/kb-dedup-rules.md`
- `docs/kb-query-policy.md`

### `skills/templates/`

提供常见产物模板，例如：

- canonical note
- change log
- intake manifest
- 仓库规则文件模板

### `commands/kb-update.md`

定义增量更新命令的预期行为：

- 先读取规则层
- 仅处理指定输入
- 对每个条目做分类
- 更新受影响资产、索引与变更日志
- 输出本次处理摘要

## 推荐工作流

### 冷启动整理

1. 盘点当前资料集合
2. 按主题与关系做聚类
3. 为高价值主题创建或合成 canonical assets
4. 将其余材料区分为 supporting / archive / recycle
5. 初始化仓库规则层与索引
6. 记录 change log，方便以后增量维护

### 日常增量更新

1. 读取 `AGENTS.md` 与 `docs/` 规则文件
2. 仅处理新进入的文件或目录
3. 判断其属于 duplicate / supplement / conflict 等哪一类
4. 仅更新受影响的 canonical assets
5. 同步更新索引、source mapping 与 change log

### 面向问答的检索

1. 先读仓库规则层
2. 先从索引路由
3. 首轮只打开少量高度相关的 canonical 内容
4. 不足时再扩展读取
5. 回答时显式引用来源并标明冲突或不确定性

## 典型输出物

使用本 skill 整理知识库时，通常会产出：

- **Inventory**：记录每个输入项的状态与动作
- **Canonical Notes / Assets**：沉淀后的主资产
- **Reorganization Map**：说明文件如何迁移或归类
- **Change Log**：记录本轮整理或更新
- **Repository Rule Layer**：让未来更新和问答可持续进行

## 如何使用

### 作为 skill 使用

如果你的 agent 环境支持本地 skill 仓库，可以让 assistant 在以下任务中触发它：

- “帮我把这个资料文件夹整理成知识库”
- “这些笔记有很多重复版本，帮我做 canonical 整理”
- “把新加入的这批 PDF 增量合并进现有知识库”
- “基于这个已经整理好的知识库回答问题，但不要全库扫描”

### 作为方法论参考

即使你不直接把它作为 skill 加载，也可以把它当作一套知识库整理标准来复用：

- 直接参考 `references/` 中的分类和 schema
- 直接复用 `templates/` 中的模板
- 参考 `commands/kb-update.md` 设计自己的增量更新流程

## 设计特点

这个仓库的设计重点包括：

- **可维护性优先**：为未来增量维护服务，而不是一次性清洗
- **检索边界明确**：问答时限制读取范围，避免高成本全量扫描
- **冲突可见**：不把冲突悄悄融合进总结
- **模板化输出**：便于不同仓库之间复用同一种整理方法
- **面向 agent 协作**：通过规则层让后续 assistant 接续工作

## 后续可扩展方向

如果你准备继续完善这个 skill，可以考虑补充：

- 更具体的示例输入 / 输出目录
- 面向不同资料类型（PDF、网页摘录、会议纪要、研究笔记）的细化策略
- 自动生成 inventory 或 source mapping 的脚本
- 更丰富的 query-time citation 规范

## License

当前仓库未包含单独的许可证文件；如需公开分发，建议补充明确的 LICENSE。


## Commands

- `kb-ask`：基于知识库进行有界问答
- `kb-update`：把指定新材料增量合并进知识库
- `kb-curate`：利用轻量索引发现、筛选、暂存，并可按协议写入新的外部研究信息
