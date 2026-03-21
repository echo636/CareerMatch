package candidate

// CandidateStructData 描述从 Dify Workflow 返回的候选人结构化信息。
// 字段保持相对宽松，具体结构由 Dify 工作流的输出约定决定。
type CandidateStructData struct {
	IsResume *bool `json:"is_resume,omitempty"`

	BasicInfo struct {
		Name            string  `json:"name"`
		Gender          *string `json:"gender,omitempty"`
		Age             *int    `json:"age,omitempty"`
		WorkYears       *int    `json:"work_years,omitempty"`
		CurrentCity     *string `json:"current_city,omitempty"`
		CurrentTitle    *string `json:"current_title,omitempty"`
		CurrentCompany  *string `json:"current_company,omitempty"`
		Status          *string `json:"status,omitempty"`
		Email           *string `json:"email,omitempty"`
		Phone           *string `json:"phone,omitempty"`
		Wechat          *string `json:"wechat,omitempty"`
		Ethnicity       *string `json:"ethnicity,omitempty"`
		BirthDate       *string `json:"birth_date,omitempty"`
		NativePlace     *string `json:"native_place,omitempty"`
		Residence       *string `json:"residence,omitempty"`
		PoliticalStatus *string `json:"political_status,omitempty"`
		IDNumber        *string `json:"id_number,omitempty"`
		MaritalStatus   *string `json:"marital_status,omitempty"`
		Summary         *string `json:"summary,omitempty"`
		SelfEvaluation  *string `json:"self_evaluation,omitempty"`
		FirstDegree     *string `json:"first_degree,omitempty"`
		Avator          *string `json:"avator,omitempty"`
	} `json:"basic_info"`

	Educations []struct {
		School    string  `json:"school"`
		Degree    *string `json:"degree,omitempty"`
		Major     *string `json:"major,omitempty"`
		StartYear *string `json:"start_year,omitempty"`
		EndYear   *string `json:"end_year,omitempty"`
	} `json:"educations"`

	WorkExperiences []struct {
		CompanyName      string   `json:"company_name"`
		Industry         *string  `json:"industry,omitempty"`
		Title            string   `json:"title"`
		Level            *string  `json:"level,omitempty"`
		Location         *string  `json:"location,omitempty"`
		StartDate        *string  `json:"start_date,omitempty"`
		EndDate          *string  `json:"end_date,omitempty"`
		Responsibilities []string `json:"responsibilities,omitempty"`
		Achievements     []string `json:"achievements,omitempty"`
		TechStack        []string `json:"tech_stack,omitempty"`
	} `json:"work_experiences"`

	Projects []struct {
		Name             string   `json:"name"`
		Role             *string  `json:"role,omitempty"`
		Domain           *string  `json:"domain,omitempty"`
		Description      *string  `json:"description,omitempty"`
		Responsibilities []string `json:"responsibilities,omitempty"`
		Achievements     []string `json:"achievements,omitempty"`
		TechStack        []string `json:"tech_stack,omitempty"`
	} `json:"projects"`

	Skills []struct {
		Name         string  `json:"name"`
		Level        *string `json:"level,omitempty"`
		Years        *int    `json:"years,omitempty"`
		LastUsedYear *int    `json:"last_used_year,omitempty"`
	} `json:"skills"`

	Tags []struct {
		Name     string  `json:"name"`
		Category *string `json:"category,omitempty"`
	} `json:"tags"`
}
