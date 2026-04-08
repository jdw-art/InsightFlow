"""
Multi-Agent RAG 行业决策助手，一个基于 Multi-Agent + RAG 的智能行业分析系统，能够自动拆解复杂问题、检索多源信息并生成结构化决策报告。

基于 LangGraph 实现的技术博客自动生成系统，包含以下 Agent:
- Researcher: 联网搜索收集背景资料
- Planner: 大纲规划
- Writer: 内容撰写
- Coder: 代码示例生成
- Artist: 配图生成
- Questioner: 追问深化
- Reviewer: 质量审核
- Assembler: 文档组装
"""