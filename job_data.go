package job

// =====================================================
// JD 结构化数据模型定义
// =====================================================

// SkillRequirementType 技能需求类型
type SkillRequirementType string

const (
	SkillTypeRequired SkillRequirementType = "required" // 必备技能（必须全部满足）
	SkillTypeOptional SkillRequirementType = "optional" // 可选技能组（组内至少满足一个）
	SkillTypeBonus    SkillRequirementType = "bonus"    // 加分技能（有就加分，没有也不扣）
)

// ExperienceRequirementType 经验需求类型
type ExperienceRequirementType string

const (
	ExperienceTypeCore  ExperienceRequirementType = "core"  // 核心经验需求
	ExperienceTypeBonus ExperienceRequirementType = "bonus" // 加分经历
)

// =====================================================
// JD 结构化信息（从 Dify Workflow 返回）
// =====================================================

// JobStructData 描述从 Dify Workflow 返回的 JD 结构化信息。
// 将 JD 解析为「基础信息 + 技能需求 + 经验需求 + 教育/其他约束 + 标签」几大块。
type JobStructData struct {
	// 基础信息
	BasicInfo JobBasicInfo `json:"basic_info"`

	// 技能需求（分为必备、可选组、加分三类）
	SkillRequirements JobSkillRequirements `json:"skill_requirements"`

	// 经验需求（分为核心经验和加分经历）
	ExperienceRequirements JobExperienceRequirements `json:"experience_requirements"`

	// 教育及其他约束条件
	EducationConstraints JobEducationConstraints `json:"education_constraints"`

	// 标签（用于快速筛选和分类）
	Tags []JobTag `json:"tags"`
}

// JobBasicInfo 岗位基础信息
type JobBasicInfo struct {
	Title       string  `json:"title"`                  // 岗位名称
	Department  *string `json:"department,omitempty"`   // 所属部门
	Location    *string `json:"location,omitempty"`     // 工作地点
	JobType     *string `json:"job_type,omitempty"`     // 工作类型：fulltime / intern / parttime
	SalaryNegotiable   *bool   `json:"salary_negotiable,omitempty"`    // 薪资面议
	SalaryMin          *int    `json:"salary_min,omitempty"`           // 月薪下限
	SalaryMax          *int    `json:"salary_max,omitempty"`           // 月薪上限
	SalaryMonthsMin    *int    `json:"salary_months_min,omitempty"`    // 年薪月数下限
	SalaryMonthsMax    *int    `json:"salary_months_max,omitempty"`    // 年薪月数上限
	InternSalaryAmount *int    `json:"intern_salary_amount,omitempty"` // 实习薪资金额
	InternSalaryUnit   *string `json:"intern_salary_unit,omitempty"`   // 实习薪资周期(日/月)
	Currency           *string `json:"currency,omitempty"`             // 薪资币种
	Summary            *string `json:"summary,omitempty"`              // 一句话岗位摘要，用于粗排匹配

	// 岗位职责概述
	Responsibilities []string `json:"responsibilities,omitempty"`
	// 岗位亮点/福利
	Highlights []string `json:"highlights,omitempty"`
}

// =====================================================
// 技能需求结构
// =====================================================

// JobSkillRequirements 技能需求汇总
type JobSkillRequirements struct {
	// 必备技能（必须全部满足）
	Required []RequiredSkill `json:"required"`

	// 可选技能组（一个组里至少会一个，如 React / Vue / Angular 三选一）
	OptionalGroups []OptionalSkillGroup `json:"optional_groups"`

	// 加分技能（有就加分，没有也不扣）
	Bonus []BonusSkill `json:"bonus"`
}

// RequiredSkill 必备技能
type RequiredSkill struct {
	Name        string  `json:"name"`                  // 技能名称
	Level       *string `json:"level,omitempty"`       // 期望熟练度：basic / intermediate / advanced / expert
	MinYears    *float64 `json:"min_years,omitempty"`  // 最低使用年限（允许小数，如 0.5）
	Description *string `json:"description,omitempty"` // 详细描述
}

// OptionalSkillGroup 可选技能组（组内技能至少满足一个）
type OptionalSkillGroup struct {
	GroupName   string          `json:"group_name"`            // 组名（如"前端框架"）
	Description *string         `json:"description,omitempty"` // 组描述
	MinRequired int             `json:"min_required"`          // 组内最少需要满足的技能数（默认为1）
	Skills      []OptionalSkill `json:"skills"`                // 组内可选技能列表
}

// OptionalSkill 可选技能组内的单个技能
type OptionalSkill struct {
	Name        string  `json:"name"`
	Level       *string `json:"level,omitempty"`
	Description *string `json:"description,omitempty"`
}

// BonusSkill 加分技能
type BonusSkill struct {
	Name        string  `json:"name"`
	Weight      *int    `json:"weight,omitempty"` // 加分权重（1-10）
	Description *string `json:"description,omitempty"`
}

// =====================================================
// 经验需求结构
// =====================================================

// JobExperienceRequirements 经验需求汇总
type JobExperienceRequirements struct {
	// 核心经验需求（必须满足）
	Core []CoreExperience `json:"core"`

	// 加分经历（有就加分）
	Bonus []BonusExperience `json:"bonus"`

	// 总工作年限要求
	MinTotalYears *float64 `json:"min_total_years,omitempty"`
	MaxTotalYears *float64 `json:"max_total_years,omitempty"`
}

// CoreExperience 核心经验需求
type CoreExperience struct {
	Type        string   `json:"type"`                  // 经验类型：industry / domain / project / tech
	Name        string   `json:"name"`                  // 经验名称/领域
	MinYears    *float64 `json:"min_years,omitempty"`   // 最低年限（允许小数）
	Description *string  `json:"description,omitempty"` // 详细描述
	Keywords    []string `json:"keywords,omitempty"`    // 相关关键词（用于匹配）
}

// BonusExperience 加分经历
type BonusExperience struct {
	Type        string   `json:"type"`
	Name        string   `json:"name"`
	Weight      *int     `json:"weight,omitempty"` // 加分权重（1-10）
	Description *string  `json:"description,omitempty"`
	Keywords    []string `json:"keywords,omitempty"`
}

// =====================================================
// 教育及其他约束
// =====================================================

// JobEducationConstraints 教育及其他约束条件
type JobEducationConstraints struct {
	// 学历要求
	MinDegree     *string  `json:"min_degree,omitempty"`     // 最低学历：high_school / bachelor / master / phd
	PreferDegrees []string `json:"prefer_degrees,omitempty"` // 优选学历

	// 专业要求
	RequiredMajors  []string `json:"required_majors,omitempty"`  // 必须专业
	PreferredMajors []string `json:"preferred_majors,omitempty"` // 优选专业

	// 语言要求
	Languages []LanguageRequirement `json:"languages,omitempty"`

	// 其他约束
	Certifications []string `json:"certifications,omitempty"` // 证书要求
	AgeRange       *string  `json:"age_range,omitempty"`      // 年龄范围
	Other          []string `json:"other,omitempty"`          // 其他约束条件
}

// LanguageRequirement 语言要求
type LanguageRequirement struct {
	Language string  `json:"language"`        // 语言名称
	Level    *string `json:"level,omitempty"` // 水平要求：basic / fluent / native
	Required bool    `json:"required"`        // 是否必须
}

// =====================================================
// 岗位标签
// =====================================================

// JobTag 岗位标签（结构化数据使用）
type JobTag struct {
	Name     string  `json:"name"`
	Category *string `json:"category,omitempty"` // 标签分类：industry / domain / tech / culture
	Weight   *int    `json:"weight,omitempty"`   // 权重（用于匹配排序）
}
