# 简历岗位匹配优化报告

## 1. 背景

本次优化聚焦于“系统排序结果与 LLM 招聘判断存在明显偏差”的问题。

在优化前的对比报告中：

- `Spearman Rho = 0.293706`
- `Top-5 Overlap = 2`
- 8 年 Java 后端候选人仍被系统高位推荐到 `初级 / 校招 / 实习` 岗位
- 邻近技术栈岗位（如 Go 后端、游戏服务端）被系统压分过重

对应报告：

- 优化前：[resume_algorithm_llm_compare_20260409_095218.md](/D:/constructing_projects/CareerMatch/backend/test/reports/resume_algorithm_llm_compare/2026-04-09/resume_algorithm_llm_compare_20260409_095218.md)
- 优化后：[resume_algorithm_llm_compare_20260409_150432.md](/D:/constructing_projects/CareerMatch/backend/test/reports/resume_algorithm_llm_compare/2026-04-09/resume_algorithm_llm_compare_20260409_150432.md)


## 2. 核心问题

### 2.1 职级错配没有被有效处理

原算法更关注“技能像不像、文本像不像”，但缺少“岗位级别是否真实适合”的约束。

直接表现为：

- `360 初级服务端岗` 在优化前算法排第 1，但 LLM 排第 7
- `携程 Java 实习` 在优化前算法排第 3，但 LLM 排第 9
- `快手 Java 实习` 也进入了靠前候选集

这类岗位在技术关键词上和候选人有交集，但从招聘落地角度看，属于明显的过度资深错配。

### 2.2 邻近技术栈迁移被惩罚过重

原算法对主语言不一致比较敏感，容易把“Java 高并发 / 分布式 / TCP 服务端经验”与“Go 后端 / 游戏服务端 / 底层网络服务端”切得过开。

直接表现为：

- `高级 Go 后端` 优化前算法排第 12，LLM 排第 4
- `游戏服务器工程师` 优化前算法排第 6，LLM 排第 3

说明系统对“能力迁移”的刻画偏弱，对“语言字面不一致”的惩罚偏强。

### 2.3 报告解释能力不足

原对比报告只展示：

- `vec / skill / exp / edu / salary`

但实际总分还受到以下因素影响：

- `domain`
- `location`
- 标题主技能对齐
- 技术栈迁移得分
- 各类 penalty

结果是当排序出现偏差时，报告无法直接说明“为什么这个岗位被压下去了”。


## 3. 优化目标

本次优化目标不是“让算法完全复刻 LLM”，而是让算法更接近真实招聘逻辑：

- 减少明显不合理的 `实习 / 校招 / 初级岗` 高排位
- 保留对邻近后端技术栈的合理迁移评分
- 提升排序与 LLM 判断的一致性
- 提升报告可解释性，方便后续继续调参


## 4. 方案设计

### 4.1 增加职级匹配维度

新增岗位经验带宽和职级适配逻辑：

- 识别 `internship / campus / entry / senior` 类型岗位
- 计算 `role_level_fit`
- 对明显过度资深的 entry-level 岗位追加 `role_level_penalty`

同时新增默认过滤：

- 当候选人年限明显较高时，默认过滤不适合的 `实习 / 校招` 岗位

这样可以在排序前就剔除一部分低价值噪声候选项。

### 4.2 放宽邻近技术栈迁移惩罚

对 `Go / Java / 后端分布式 / 网络服务端` 这类岗位：

- 保留标题主技能检查
- 但 penalty 不再只看“标题主语言是否完全命中”
- 引入 `transition_score` 参与 `title_skill_penalty` 和 `specialized_role_penalty`

目的是把“主语言不同但底层能力明显相近”的岗位，从“重罚”调整为“中等降权”。

### 4.3 增强报告解释能力

在 `MatchBreakdown` 和对比报告中补充以下字段：

- `domain_match`
- `location_match`
- `role_level_fit`
- `title_skill_alignment`
- `transition_score`
- `base_total`
- `penalty_multiplier`

这样后续看报告时，可以直接拆出：

- 基础匹配是不是高
- 是哪一层 penalty 把分数压下来了
- 是职级问题还是技术栈问题


## 5. 实施内容

### 5.1 代码改动

主要改动文件：

- [matching.py](/D:/constructing_projects/CareerMatch/backend/app/services/matching.py)
- [models.py](/D:/constructing_projects/CareerMatch/backend/app/domain/models.py)
- [test_resume_algorithm_llm_compare.py](/D:/constructing_projects/CareerMatch/backend/test/test_resume_algorithm_llm_compare.py)
- [test_uploaded_resume_matching.py](/D:/constructing_projects/CareerMatch/backend/test/test_uploaded_resume_matching.py)
- [domain.ts](/D:/constructing_projects/CareerMatch/frontend/types/domain.ts)

关键实现点：

- [matching.py#L470](/D:/constructing_projects/CareerMatch/backend/app/services/matching.py#L470)
  默认过滤明显不适合的实习 / 校招岗位
- [matching.py#L563](/D:/constructing_projects/CareerMatch/backend/app/services/matching.py#L563)
  构建岗位经验带宽
- [matching.py#L594](/D:/constructing_projects/CareerMatch/backend/app/services/matching.py#L594)
  计算 `role_level_fit`
- [matching.py#L652](/D:/constructing_projects/CareerMatch/backend/app/services/matching.py#L652)
  计算 `role_level_penalty`
- [matching.py#L853](/D:/constructing_projects/CareerMatch/backend/app/services/matching.py#L853)
  计算 `base_total`
- [matching.py#L934](/D:/constructing_projects/CareerMatch/backend/app/services/matching.py#L934)
  输出 `penalty_multiplier`
- [matching.py#L1149](/D:/constructing_projects/CareerMatch/backend/app/services/matching.py#L1149)
  调整 hard skill penalty
- [matching.py#L1169](/D:/constructing_projects/CareerMatch/backend/app/services/matching.py#L1169)
  让 `title_skill_penalty` 引入 `transition_score`
- [matching.py#L1197](/D:/constructing_projects/CareerMatch/backend/app/services/matching.py#L1197)
  让 specialized role penalty 参考迁移能力

### 5.2 测试补充

新增和调整的回归测试：

- [test_matching_filters.py#L544](/D:/constructing_projects/CareerMatch/backend/test/test_matching_filters.py#L544)
  验证高年限候选人默认过滤实习 / 校招岗
- [test_matching_filters.py#L618](/D:/constructing_projects/CareerMatch/backend/test/test_matching_filters.py#L618)
  验证职级惩罚会拉低 entry-level 岗位得分
- [test_matching_filters.py#L692](/D:/constructing_projects/CareerMatch/backend/test/test_matching_filters.py#L692)
  验证邻近后端技术栈仍保留迁移得分，不会被过度压制


## 6. 效果对比

### 6.1 指标变化

优化前：

- `Filtered Candidate Count = 88`
- `Filtered Out Count = 8`
- `Spearman Rho = 0.293706`
- `Top-5 Overlap = 2`

优化后：

- `Filtered Candidate Count = 27`
- `Filtered Out Count = 69`
- `Spearman Rho = 0.839161`
- `Top-5 Overlap = 4`

结论：

- 候选池噪声显著下降
- 系统排序与 LLM 的一致性显著提升
- 主要偏差从“大面积结构性错位”缩小到“局部排序先后差异”

### 6.2 排名现象变化

优化前：

- `360 初级服务端岗` 算法第 1，LLM 第 7
- `携程 Java 实习` 算法第 3，LLM 第 9
- `高级 Go 后端` 算法第 12，LLM 第 4

优化后：

- 实习 / 校招类岗位大部分已被默认过滤出候选池
- `360 初级服务端岗` 降到算法第 6，且 `role_level_fit = 0.18`
- `游戏服务器工程师` 升到算法第 4，与 LLM 更接近
- 邻近技术栈岗位仍然会被降权，但不会再出现极端低估


## 7. 当前结论

本次优化已经解决了最关键的结构性问题：

- 系统不再大规模把高年限候选人推向实习 / 校招 / 初级岗
- 系统对后端邻近技术栈的迁移理解更接近招聘判断
- 报告维度更完整，后续调参成本明显降低

从工作汇报角度，这次优化可以定义为：

> 从“基于结构化相似度的匹配排序”，向“兼顾招聘可落地性和技术迁移能力的排序”推进了一步。


## 8. 仍然存在的不足

虽然整体一致性已经明显提升，但仍有两个残留问题：

### 8.1 个别强匹配岗位仍被压分

例如：

- `阿里云 Java研发工程师` 在新报告里算法第 5，LLM 第 1

从报告拆解看，这类岗位的问题已不再是职级错配，而更可能是：

- 某些 required skill 被当成过强约束
- `base_total` 尚可，但 penalty 仍然偏重

### 8.2 安全 / Go 等跨语言跨领域岗位仍有分歧

例如：

- `安全开发初级工程师` 仍存在一定偏差
- `golang开发工程师` 仍被明显压低

这说明当前“迁移能力”已经比之前好，但还不够细：

- 对语言迁移的可接受程度没有区分岗位上下文
- 对“领域迁移”和“语言迁移”仍然混在一起处罚


## 9. 后续方向

建议下一阶段继续做 3 件事。

### 9.1 做 required skill 分层

把 JD 要求拆成：

- 核心必备
- 次核心必备
- 可迁移必备

避免把“列在要求里但实际可迁移”的技能也按强约束处理。

### 9.2 强化岗位级别识别

进一步补充：

- 级别关键词词典
- 年限区间推断
- title + summary 联合判断

把 `role_level_fit` 做得更稳定。

### 9.3 建立持续评估基线

建议固定一组代表性样本：

- 高年限候选人 vs 初级 / 校招岗
- 同语言强匹配岗
- 邻近语言迁移岗
- 跨领域但同架构类型岗

每次调参都自动对比：

- `Spearman`
- `Top-k overlap`
- 关键岗位 rank shift

避免后续优化顾此失彼。


## 10. 验证记录

本次已执行：

```powershell
python -m unittest backend.test.test_matching_filters
python -m py_compile backend\app\services\matching.py backend\app\domain\models.py backend\test\test_resume_algorithm_llm_compare.py backend\test\test_uploaded_resume_matching.py backend\test\test_matching_filters.py
python backend\test\test_resume_algorithm_llm_compare.py
```

结果：

- 单元测试通过
- 相关文件编译通过
- 新的对比报告已生成并验证效果改善
