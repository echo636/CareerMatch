按当前代码的真实实现，匹配不是“把整份简历和 JD 丢给大模型直接判断”，而是 4 步：
                                                                                                                                                                
  1. 先把简历和岗位结构化。                                                                                                                                     
  2. 用结构化后的文本做向量召回。                                                                                                                               
  3. 用硬条件和薪资做过滤。                                                                                                                                     
  4. 用加权公式精排。                                                                                                                                           
                                                                                                                                                                
  核心代码在 backend/app/services/matching.py:22。                                                                                                              
                                                                                                                                                                
  1. 简历是怎么转成可匹配信息的                                                                                                                                 
  简历上传后，会先抽取文本，再生成一个 ResumeProfile，字段包括：摘要、技能、项目关键词、工作年限、期望薪资等，见 backend/app/services/resume_pipeline.py:29 和  
  backend/app/domain/models.py:15。                                                                                                                             
                                                                                                                                                                
  当前“解析”其实是 mock 规则，不是真 LLM：                                                                                                                      
                                                                                                                                                                
  - summary：取简历前 200 个字符                                                                                                                                
  - skills：只从预设技能词表里做包含匹配                                                                                                                        
  - project_keywords：只从预设项目词表里做包含匹配                                                                                                              
  - years_experience：正则抓 “3年 / 5 years” 这类文本                                                                                                           
  - salary_min/max：从文本里抓前两个 4~5 位数字                                                                                                                 
                                                                                                                                                                
  实现见 backend/app/clients/llm.py:41。                                                                                                                        
                                                                                                                                                                
  2. 岗位是怎么转成可匹配信息的                                                                                                                                 
  岗位导入时会生成 JobProfile，字段包括：技能、项目关键词、硬性要求、薪资区间、经验年限等，见 backend/app/services/job_pipeline.py:25 和 backend/app/domain/    
  models.py:30。                                                                                                                                                
                                                                                                                                                                
  当前岗位解析规则：                                                                                                                                            
                                                                                                                                                                
  - 如果导入数据里已经有 skills/project_keywords/hard_requirements，就直接用                                                                                    
  - 如果没有，就从岗位 summary/raw_text 里按关键词表提取                                                                                                        
  - hard_requirements 如果没传，默认取前两个技能                                                                                                                
                                                                                                                                                                
  实现见 backend/app/clients/llm.py:58。                                                                                                                        
                                                                                                                                                                
  3. 简历和岗位如何召回匹配                                                                                                                                     
  简历和岗位都会拼成一段文本：                                                                                                                                  
                                                                                                                                                                
  - 简历：summary + skills + project_keywords                                                                                                                   
  - 岗位：summary + skills + project_keywords                                                                                                                   
                                                                                                                                                                
  然后做 embedding，存到向量库里，见 backend/app/services/resume_pipeline.py:84 和 backend/app/services/job_pipeline.py:54。                                    
                                                                                                                                                                
  但要注意，当前 embedding 不是语义模型，而是一个基于 sha256 的 16 维伪向量，见 backend/app/clients/embedding.py:6。                                            
  向量检索也是本地内存版，按余弦相似度取前 top_k * 3 个候选，见 backend/app/clients/vector_store.py:13 和 backend/app/services/matching.py:27。                 
                                                                                                                                                                
  所以“形式上”是语义召回，“实际上”目前还是原型级实现，不是真正语义理解。                                                                                        
                                                                                                                                                                
  4. 召回后如何过滤和打分                                                                                                                                       
  过滤条件在 backend/app/services/matching.py:52：                                                                                                              
                                                                                                                                                                
  - 硬性要求必须命中                                                                                                                                            
  - 候选人的最低期望薪资，不能比岗位最高薪资高出 8000 以上                                                                                                      
                                                                                                                                                                
  这里还有个细节：带空格的 requirement 或长度小于等于 2 的 requirement，会被直接放过，不算严格校验。                                                            
                                                                                                                                                                
  打分公式在 backend/app/services/matching.py:62：                                                                                                              
                                                                                                                                                                
  total =                                                                                                                                                       
  0.35 * vector_similarity +                                                                                                                                    
  0.35 * skill_match +                                                                                                                                          
  0.20 * project_match +                                                                                                                                        
  0.10 * salary_match                                                                                                                                           
                                                                                                                                                                
  各项含义：                                                                                                                                                    
                                                                                                                                                                
  - vector_similarity：向量余弦相似度                                                                                                                           
  - skill_match：简历技能与岗位技能的重合率 = 交集数 / 岗位技能数                                                                                               
  - project_match：简历项目关键词与岗位项目关键词的重合率                                                                                                       
  - salary_match：薪资区间交并比                                                                                                                                
                                                                                                                                                                
  最后按 total 从高到低排序，返回 Top K，见 backend/app/services/matching.py:49。                                                                               
                                                                                                                                                                
  5. 当前真正参与匹配的字段                                                                                                                                     
  主要是这些：                                                                                                                                                  
                                                                                                                                                                
  - summary                                                                                                                                                     
  - skills                                                                                                                                                      
  - project_keywords                                                                                                                                            
  - hard_requirements                                                                                                                                           
  - salary_range / expected_salary                                                                                                                              
                                                                                                                                                                
  目前这些字段基本不参与匹配主分：                                                                                                                              
                                                                                                                                                                
  - candidate_name                                                                                                                                              
  - company                                                                                                                                                     
  - location                                                                                                                                                    
  - experience_years / years_experience 目前只在 Gap 分析里用，没有进匹配主评分，见 backend/app/services/gap_analysis.py:20                                     
                                                                                                                                                                
  一句话总结：当前系统是“关键词抽取后的结构化匹配 + 伪向量召回 + 规则精排”，不是完整的真实 LLM/Embedding 生产版。 