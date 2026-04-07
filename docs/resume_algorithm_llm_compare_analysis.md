# `resume_algorithm_llm_compare` 报告问题分析与改进方案

## 背景

基于当前 `backend/test/reports/resume_algorithm_llm_compare/latest.md`，算法排序和 LLM 排序出现了较大偏差：

- `Spearman Rho = -0.384615`
- `Top-5 Overlap = 2`

从报告明细看，当前算法主要有 3 个明显问题：

1. `skill` 评分过于死板。
2. `education` 评分偏高，容易把学历当成排序加分项。
3. `experience` 评分偏低，没有充分吃到项目描述和实际技术栈证据。

## 报告中暴露出的具体问题

### 1. Skill 评分过于死板

报告里候选人已经明显是 Vue 前端方向，但算法结果仍反复出现：

- `matched_skills: Vue`
- `missing_skills: HTML5, CSS3, JavaScript`

这说明当前系统存在两类问题：

1. 结构化技能如果写成 `HTML / CSS / ES6+ / JavaScript` 这种合并格式，算法会把它当成一个整体字符串，而不是拆成 4 个技能。
2. 对前端基础技能缺少桥接逻辑。现实里一个稳定做 Vue/React 的候选人，即使简历没单独写 `HTML5/CSS3/JavaScript`，也不应该直接按 0 分处理。

### 2. Education 评分偏高

当前报告中算法 Top 结果的 `edu` 基本都在 `0.94 ~ 1.00`，但很多岗位只是最低本科或普通学历要求。

这会带来两个问题：

1. 学历更像过滤条件，却被当成了排序加分项。
2. 硕士候选人会在大量普通前端岗位上获得接近满分的教育加成，放大了排序偏差。

### 3. Experience 评分偏低

报告中不少岗位的 `exp` 只有 `0.18 ~ 0.50`，但 LLM 给出的结论却认为候选人有较强项目落地经验，尤其是在：

- Vue3 / TypeScript / Vite
- 可视化大屏
- GIS / 数字孪生 / 图表平台

根因在于当前经验打分对证据的读取范围太窄：

1. 主要依赖结构化的 `project_keywords` / 简单 term hit。
2. 没有把项目描述、职责、成果中的技术证据充分纳入经验打分。
3. 经验项里出现的技术词，没有和候选人技能索引做足够的桥接。

## 本次已落实的方案

### 1. 放宽 Skill 评分

修改文件：`backend/app/services/matching.py`

已落实：

- 增加复合技能拆分。
  - 例如 `HTML / CSS / ES6+ / JavaScript` 会拆成多个技能参与匹配。
- 增加文本反抽技能。
  - 从简历 `summary`、`raw_text`、项目描述、项目职责、工作职责中补抽技能，避免只依赖结构化 `skills` 字段。
- 增加前端基础技能桥接。
  - 若候选人已有明显前端信号，如 `Vue`、`React`、`TypeScript`、`Vite`、`Webpack` 等，则对 `HTML`、`CSS`、`JavaScript` 给出低置信度补分。
- 增加 Git 工具桥接。
  - 若出现 `GitHub`、`GitLab`、`Gitee` 等平台信号，则补 `Git`。
- 推断技能带 `confidence`，不会与显式技能完全等价。

效果：

- Vue 候选人不再因为没把 `HTML5/CSS3/JavaScript` 单独列出来而被当成硬缺失。
- 合并写法的技能可以正常命中 JD 要求。

### 2. 提高 Experience 权重和证据利用率

修改文件：`backend/app/core/config.py`、`backend/app/services/matching.py`

已落实：

- 总权重调整：
  - `experience` 从 `0.10` 提升到 `0.15`
  - `education` 从 `0.10` 降到 `0.05`
- 经验评分现在会读取更多候选人证据：
  - `resume.skill_names`
  - 项目描述 / 职责 / 成果
  - 工作职责 / 成果
- 对经验项中的技术词，增加技能桥接评分。
  - 例如经验项里写了 `Vue3`、`TypeScript`、`大屏可视化`，现在会更容易从候选人的项目文本和技能索引中找到证据。

效果：

- 经验维度不再只靠几个结构化关键词。
- 有真实项目落地经历的候选人，`exp` 不会轻易掉到 `0.1 ~ 0.3`。

### 3. 给 Education 降温

修改文件：`backend/app/services/matching.py`

已落实：

- 最低学历满足后，不再轻易给到接近满分的排序加成。
- 超过最低学历要求，只给有限加分，不再把“硕士打普通本科岗”当成强优势。
- 专业缺失或未知时的默认分下调。
- 严格专业约束和偏好专业约束的上限整体收紧。

效果：

- 教育更接近“过滤 + 轻加权”的作用，而不是主导排序的高分项。
- 排序会更回到技能和项目经验本身。

## 本次修改位置

### 代码修改

- `backend/app/core/config.py`
  - 调整 `experience` / `education` 总权重。
- `backend/app/services/matching.py`
  - 复合技能拆分
  - 文本反抽技能
  - Vue 前端基础技能桥接
  - Git 桥接
  - 技能置信度
  - 经验项技能桥接
  - 教育评分降温

### 测试修改

- `backend/test/test_matching_filters.py`
  - 新增前端基础技能桥接测试
  - 新增项目文本驱动经验加分测试
  - 新增教育降温与经验权重高于教育的测试

## 验证结果

已执行：

```powershell
python -m unittest backend.test.test_matching_filters
python -m compileall backend\app\services\matching.py backend\app\core\config.py backend\test\test_matching_filters.py
```

结果：

- 单测通过
- 相关文件编译通过

## 预期收益

1. 前端候选人对 `HTML5/CSS3/JavaScript` 的命中会更合理。
2. 实际项目经验会比学历更能影响最终排序。
3. 算法排序和 LLM 排序之间的偏差应当缩小，尤其是前端岗位和项目驱动型岗位。

## 后续仍建议继续做的事

1. 重跑 `resume_algorithm_llm_compare`，确认最新报告里：
   - `matched_skills` 是否已经能命中 `HTML5/CSS3/JavaScript`
   - `edu` 是否整体下行
   - `exp` 是否整体上行
2. 如果后续还发现经验偏低，可以继续引入：
   - 项目领域词权重
   - 项目规模/复杂度信号
   - 岗位年限与候选人年限的非线性映射
3. 如果教育仍然影响过大，可以把教育维度进一步收缩为“过滤优先、排序次要”。
