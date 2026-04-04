# 匹配算法与配置说明

本文档说明当前 CareerMatch 的岗位匹配流程、关键评分逻辑，以及已经抽成配置的关键参数。

## 配置入口

- 统一配置定义：`backend/app/core/config.py`
- 运行时读取：`Settings.matching_algorithm`
- 使用位置：`backend/app/services/matching.py`

所有关键参数都提供了默认值，同时支持通过环境变量覆盖。

## 当前匹配流程

### 1. 简历结构化与索引准备

匹配前，系统会先把简历整理成几个结构化来源：

- `resume.skills`
- 工作经历里的 `tech_stack`
- 项目里的 `tech_stack`
- `resume.tags` 中 `category == tech` 的标签

系统会把这些内容合并成 `candidate_skill_index`，用于技能打分。同时还会准备简历整体向量，用于岗位召回。

### 2. 向量召回

系统先使用简历向量到岗位向量库中查询候选岗位，再根据岗位库规模动态决定召回数量。

当前召回数量受以下参数控制：

- `MATCH_RECALL_SMALL_JOB_POOL_MAX`
- `MATCH_RECALL_MEDIUM_JOB_POOL_MAX`
- `MATCH_RECALL_LARGE_JOB_POOL_MAX`
- `MATCH_RECALL_MULTIPLIER_SMALL`
- `MATCH_RECALL_MULTIPLIER_MEDIUM`
- `MATCH_RECALL_MULTIPLIER_LARGE`
- `MATCH_RECALL_MULTIPLIER_XLARGE`
- `MATCH_FILTERED_RECALL_SCALE`
- `MATCH_FILTERED_RECALL_MIN_MULTIPLIER`

如果用户启用了岗位筛选，系统会自动放大召回量，避免过滤后候选不足。

### 3. 过滤

召回后的岗位会先经过两层过滤：

1. 用户筛选条件
- 岗位方向
- 工作方式
- 是否实习
- 发布时间
- 经验年限区间

2. 系统硬过滤
- 最低学历门槛不足
- 候选人最低薪资期望远高于岗位预算
- 简历与岗位方向标签完全不相交

相关参数：

- `MATCH_MIN_DEGREE_FILTER_THRESHOLD`
- `MATCH_SALARY_FAR_ABOVE_BUDGET_RATIO`
- `MATCH_DIRECTION_MISMATCH_MIN_TAG_COUNT`

### 4. 结构化打分

每个通过过滤的岗位会计算 4 个主要分项：

- `vector_similarity`
- `skill_match`
- `experience_match`
- `education_match`

薪资不进入总分，只用于岗位分层 `reach / match / safety`。

### 5. Skill 打分

`skill_match` 由三部分组成：

- 必需技能 `required`
- 可选技能组 `optional_groups`
- 加分技能 `bonus`

对应参数：

- `MATCH_SKILL_REQUIRED_WEIGHT`
- `MATCH_SKILL_OPTIONAL_WEIGHT`
- `MATCH_SKILL_BONUS_WEIGHT`

#### 5.1 精确匹配优先

系统先做技能名归一化和别名对齐，例如：

- `React.js -> react`
- `PostgreSQL -> postgresql`

如果归一化后能直接命中，就按规则分数计算。

#### 5.2 语义匹配补分

如果精确匹配没有命中，系统才会对技能名做 embedding 相似度比较，作为补充命中：

- 语义匹配只作为 fallback，不替代精确匹配
- 命中后给的是部分分，不会直接给满分
- 结果也会影响前端的 `matched_skills / missing_skills`

相关参数：

- `MATCH_SEMANTIC_SKILL_MIN_SIMILARITY`
- `MATCH_SEMANTIC_SKILL_BASE_SCORE`
- `MATCH_SEMANTIC_SKILL_SCORE_SCALE`
- `MATCH_SEMANTIC_SKILL_MAX_SCORE`

这样做的目标是：

- 保留硬技能判断的稳定性
- 补偿不同技能写法、相近术语、解析标签不一致造成的漏判
- 避免把“相关但不等价”的技能直接当成强命中

### 6. Experience 打分

`experience_match` 由三部分组成：

- 核心经验项 `core`
- 加分经验项 `bonus`
- 总年限匹配 `min_total_years`

对应参数：

- `MATCH_EXPERIENCE_CORE_WEIGHT`
- `MATCH_EXPERIENCE_BONUS_WEIGHT`
- `MATCH_EXPERIENCE_TOTAL_YEARS_WEIGHT`

### 7. Education 打分

`education_match` 由四部分组成：

- 最低学历
- 偏好学历
- 必需专业
- 偏好专业

对应参数：

- `MATCH_EDUCATION_MIN_DEGREE_WEIGHT`
- `MATCH_EDUCATION_PREFER_DEGREE_WEIGHT`
- `MATCH_EDUCATION_REQUIRED_MAJOR_WEIGHT`
- `MATCH_EDUCATION_PREFERRED_MAJOR_WEIGHT`

### 8. 总分排序

当前总分由以下部分加权组成：

- `vector_similarity`
- `skill_match`
- `experience_match`
- `education_match`

对应参数：

- `MATCH_TOTAL_WEIGHT_VECTOR`
- `MATCH_TOTAL_WEIGHT_SKILL`
- `MATCH_TOTAL_WEIGHT_EXPERIENCE`
- `MATCH_TOTAL_WEIGHT_EDUCATION`

当前默认策略是降低 `skill_match` 在总分中的占比，把更多权重交给经验与整体召回相似度。

### 9. 岗位分层

排序完成后，系统会根据岗位薪资与候选人期望薪资的关系，把岗位标为：

- `reach`
- `match`
- `safety`

相关参数：

- `MATCH_TIER_REACH_RATIO`
- `MATCH_TIER_SAFETY_RATIO`

### 10. 岗位级 Gap 分析

前端结果页不再展示一个总览式 gap 区块，而是为每个岗位单独生成 gap 分析，并放在岗位详情展开区域中。当前岗位级 gap 分析基于：

- 命中技能与缺口技能
- 简历总年限与岗位要求年限
- 候选人期望薪资与岗位薪资区间

这部分主要是展示层逻辑，不直接影响匹配排序。

## 默认参数一览

### 总分权重

- `MATCH_TOTAL_WEIGHT_VECTOR=0.30`
- `MATCH_TOTAL_WEIGHT_SKILL=0.15`
- `MATCH_TOTAL_WEIGHT_EXPERIENCE=0.40`
- `MATCH_TOTAL_WEIGHT_EDUCATION=0.15`

### Skill 子权重

- `MATCH_SKILL_REQUIRED_WEIGHT=0.60`
- `MATCH_SKILL_OPTIONAL_WEIGHT=0.25`
- `MATCH_SKILL_BONUS_WEIGHT=0.15`

### Experience 子权重

- `MATCH_EXPERIENCE_CORE_WEIGHT=0.60`
- `MATCH_EXPERIENCE_BONUS_WEIGHT=0.15`
- `MATCH_EXPERIENCE_TOTAL_YEARS_WEIGHT=0.25`

### Education 子权重

- `MATCH_EDUCATION_MIN_DEGREE_WEIGHT=0.50`
- `MATCH_EDUCATION_PREFER_DEGREE_WEIGHT=0.20`
- `MATCH_EDUCATION_REQUIRED_MAJOR_WEIGHT=0.20`
- `MATCH_EDUCATION_PREFERRED_MAJOR_WEIGHT=0.10`

### 过滤与分层阈值

- `MATCH_MIN_DEGREE_FILTER_THRESHOLD=0.50`
- `MATCH_SALARY_FAR_ABOVE_BUDGET_RATIO=1.50`
- `MATCH_TIER_REACH_RATIO=1.20`
- `MATCH_TIER_SAFETY_RATIO=0.85`
- `MATCH_DIRECTION_MISMATCH_MIN_TAG_COUNT=3`

### 召回参数

- `MATCH_RECALL_SMALL_JOB_POOL_MAX=50`
- `MATCH_RECALL_MEDIUM_JOB_POOL_MAX=200`
- `MATCH_RECALL_LARGE_JOB_POOL_MAX=1000`
- `MATCH_RECALL_MULTIPLIER_SMALL=3`
- `MATCH_RECALL_MULTIPLIER_MEDIUM=5`
- `MATCH_RECALL_MULTIPLIER_LARGE=8`
- `MATCH_RECALL_MULTIPLIER_XLARGE=10`
- `MATCH_FILTERED_RECALL_SCALE=2`
- `MATCH_FILTERED_RECALL_MIN_MULTIPLIER=8`

### Skill 语义匹配参数

- `MATCH_SEMANTIC_SKILL_MIN_SIMILARITY=0.88`
- `MATCH_SEMANTIC_SKILL_BASE_SCORE=0.55`
- `MATCH_SEMANTIC_SKILL_SCORE_SCALE=2.5`
- `MATCH_SEMANTIC_SKILL_MAX_SCORE=0.85`

## 调参建议

### 如果误匹配太多

- 提高 `MATCH_SEMANTIC_SKILL_MIN_SIMILARITY`
- 降低 `MATCH_SEMANTIC_SKILL_MAX_SCORE`
- 降低 `MATCH_TOTAL_WEIGHT_VECTOR`
- 提高 `MATCH_DIRECTION_MISMATCH_MIN_TAG_COUNT`

### 如果感觉技能要求太松

- 提高 `MATCH_SKILL_REQUIRED_WEIGHT`
- 降低 `MATCH_SEMANTIC_SKILL_MAX_SCORE`
- 提高 `MATCH_TOTAL_WEIGHT_SKILL`

### 如果感觉经验应该更重要

- 提高 `MATCH_TOTAL_WEIGHT_EXPERIENCE`
- 提高 `MATCH_EXPERIENCE_CORE_WEIGHT`
- 提高 `MATCH_EXPERIENCE_TOTAL_YEARS_WEIGHT`

### 如果筛选后结果太少

- 提高 `MATCH_FILTERED_RECALL_SCALE`
- 提高 `MATCH_FILTERED_RECALL_MIN_MULTIPLIER`
- 或适当放宽用户筛选条件

## 当前实现边界

- Skill 语义匹配只在精确匹配失败时触发
- 语义匹配只用于 skill 维度，不直接进入 experience 或 education
- 岗位级 gap 分析当前是规则生成，不参与排序
- 前端目前不展示“语义命中”与“精确命中”的区别
