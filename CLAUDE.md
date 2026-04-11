# CLAUDE 配置
## 项目简介
项目描述
设计并实现一个基于 Multi-Agent + RAG + 动态路由机制 的行业分析系统，支持复杂问题拆解、多源知识检索与结构化决策报告生成，在保证结果可靠性的同时提升系统性能与可扩展性。
技术亮点
1. Multi-Agent 推理框架
构建 Planner / Research / Analysis / Writer 多Agent协作架构，实现复杂问题自动拆解与多步推理，通过任务分解驱动信息检索与分析流程，并设计Agent间上下文传递机制提升整体推理连贯性与完整性。
2. RAG 检索优化体系
构建领域知识库并实现 Hybrid Retrieval（向量检索 + BM25），结合 Chunk 切分策略与 LLM Rerank 优化上下文质量，有效提升信息召回率与生成结果的准确性。
3. 动态路由 + Web Search 增强
设计 Query Router，根据问题类型动态选择 RAG 或 Web Search，实现“RAG为主 + 实时信息增强”的多源融合策略，并通过去重与 rerank 提升上下文一致性与可靠性。
4. Semantic Cache 语义缓存
引入基于 embedding 相似度的 Semantic Cache，在 RAG 前置缓存层实现语义级查询复用，减少重复检索与生成开销，并结合相似度阈值与 LRU 策略优化系统响应延迟与吞吐性能。
5. 可评估的 RAG 系统
构建检索与生成评估体系（Recall@K / MRR / LLM-as-a-Judge），并通过消融实验验证 Hybrid Retrieval 与 Rerank 等模块对系统性能的提升，实现可量化优化与系统迭代。

## 项目架构

### 系统架构
```
用户问题
   ↓
任务拆解 Agent（Planner）
   ↓
子任务（行业趋势 / 公司分析 / 政策分析）
   ↓
检索 Agent（RAG）
   ↓
多源数据（PDF / Web / DB）
   ↓
Rerank + Context构建
   ↓
生成 Agent（Writer）
   ↓
结构化报告（带引用）
```

```
Frontend（Streamlit / Web）
        ↓
Backend API（FastAPI）
        ↓
Agent Orchestrator
        ↓
-------------------------
| Planner Agent         |
| Research Agent        |
| Analysis Agent        |
| Writer Agent          |
-------------------------
        ↓
RAG Pipeline
        ↓
-------------------------
| Vector DB (FAISS)     |
| BM25 Index            |
| Document Store        |
-------------------------
        ↓
LLM（GPT / Claude / 本地模型）
```

### 技术栈
- 前端：React + TypeScript + Node.js
- 后端：Python + Langchain + LangGraph + Flask + Langfuse
- 数据库：FAISS + ChromaDB + SQLite
- 模型：GPT / Claude / 本地模型

### 核心模块
1. Planner Agent（任务拆解）
2. RAG检索模块（核心技术点）
    - 数据来源（必须多源）
        - PDF报告（行业报告） 
        - 网页（新闻/分析） 
        - 结构化数据（可选） 
    - 检索优化
        - Chunk优化
            -  固定长度 vs 语义切分 
            -   overlap策略 
    - 混合检索
        - 向量检索（semantic） 
        - BM25（keyword） 
    - Rerank（拉开差距关键）
        -  用 cross-encoder rerank 
        -  或 LLM rerank
3. 多 Agent 协作
4. 报告生成（体现产品力）
5. 评估体系
    - 检索评估
    - 生成评估
    - 消融实验


### 解决痛点
传统 LLM：
 ❌ 回答泛泛
 ❌ 无依据（hallucination）
 ❌ 不会拆解复杂问题
你的系统：
 ✅ 自动拆问题（Agent）
 ✅ 基于真实数据（RAG）
 ✅ 输出“像咨询公司一样”的报告
## 参考资料

[语义缓存：优化高频查询场景](https://huggingface.co/learn/cookbook/semantic_cache_chroma_vector_database)
[从数据解析到多路由器检索的工程实践](https://mp.weixin.qq.com/s/ryzaGd7xrMNisd0d0Ak-GQ)
[跟着企业 RAG 竞赛冠军学习 RAG 最佳实践](https://hustyichi.github.io/2025/07/03/rag-complete/)
- [代码](https://github.com/IlyaRice/RAG-Challenge-2/tree/main)
[vibe-blog-基于Multi-Agent 架构的万字长文技术博客生成AI助手](https://github.com/datawhalechina/vibe-blog)

## 开发目标
1. 完善前端页面
2. 完善后端接口
3. 结合vibe-blog和RAG-Challenge-2，完善系统功能
    - rag部分复用RAG-Challenge-2的设计思路，根据实际项目进行调整
    - 多 Agent 协作部分根据vibe-blog的设计思路，完善Agent协作机制
    - 报告生成部分根据vibe-blog的设计思路，完善报告生成机制
    - 评估体系根据vibe-blog的设计思路，完善评估体系
4. 完整的系统架构与设计文档
5. 前端设计风格借鉴[Anthropic官网](https://www.anthropic.com/)的UI和设计风格
    - 前端页面布局参考Anthropic官网的布局
    - 前端页面交互设计参考Anthropic官网的交互设计
    - 具体的页面可以参考vibe-blog的前端页面
6. 开发事项
    - UI/UX设计合理使用ui ux pro max的skill
    - 前端开发合理使用frontend-design的skill
