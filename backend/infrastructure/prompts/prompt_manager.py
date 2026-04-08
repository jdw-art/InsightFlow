"""
统一 Prompt 管理器 - 使用 Jinja2 模板管理所有 Prompt

基于 vibe-blog 版本改造，适配 InsightFlow 行业分析系统。
模板引用使用子目录前缀：render("rag/retriever", ...) 替代 render("retriever", ...)
"""

import os
import logging
from datetime import datetime
from typing import Any, Dict, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

# 默认模板根目录
BASE_DIR = os.path.dirname(__file__)


class PromptManager:
    """
    统一 Prompt 管理器 - 使用 Jinja2 模板渲染 Prompt

    支持从 infrastructure/prompts/ 下的子目录加载模板：
    - rag/            RAG 检索相关
    - agent/          Agent 相关
    - report/         报告生成相关
    - shared/         共享模板
    """

    _instance: Optional['PromptManager'] = None

    def __init__(self, base_dir: str = None):
        """
        初始化 Prompt 管理器

        Args:
            base_dir: 模板根目录路径，默认为 infrastructure/prompts/
        """
        self.base_dir = base_dir or BASE_DIR

        # 初始化 Jinja2 环境，加载整个目录树
        self.env = Environment(
            loader=FileSystemLoader(self.base_dir),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # 添加自定义过滤器
        self.env.filters['truncate'] = self._truncate
        self.env.filters['tojson'] = self._tojson

        logger.info(f"Prompt 管理器初始化完成，模板根目录: {self.base_dir}")

    @classmethod
    def get_instance(cls, base_dir: str = None) -> 'PromptManager':
        """
        获取单例实例

        Args:
            base_dir: 模板根目录路径

        Returns:
            PromptManager 实例
        """
        if cls._instance is None:
            cls._instance = cls(base_dir)
        return cls._instance

    def _truncate(self, text: str, length: int = 500, end: str = '...') -> str:
        """截断文本"""
        if not text:
            return ''
        if len(text) <= length:
            return text
        return text[:length] + end

    def _tojson(self, obj: Any, indent: int = None) -> str:
        """转换为 JSON 字符串"""
        import json
        return json.dumps(obj, ensure_ascii=False, indent=indent)

    def render(self, template_name: str, **kwargs) -> str:
        """
        渲染模板

        Args:
            template_name: 模板名称，支持子目录前缀 (如 "rag/retriever")，不含 .j2 后缀
            **kwargs: 模板变量

        Returns:
            渲染后的字符串
        """
        # 自动添加 .j2 后缀
        if not template_name.endswith('.j2'):
            template_name = f"{template_name}.j2"

        try:
            template = self.env.get_template(template_name)
            # 自动注入当前时间戳
            kwargs['current_time'] = datetime.now().strftime('%Y年%m月%d日')
            kwargs['current_year'] = datetime.now().year
            kwargs['current_month'] = datetime.now().month
            return template.render(**kwargs)
        except Exception as e:
            logger.error(f"模板渲染失败 [{template_name}]: {e}")
            raise

    # ========== RAG 相关 Prompt ==========

    def render_retriever(self, query: str, top_k: int = 10) -> str:
        """渲染向量检索 Prompt"""
        return self.render(
            'rag/retriever',
            query=query,
            top_k=top_k
        )

    def render_reranker(self, query: str, documents: list) -> str:
        """渲染 Rerank Prompt"""
        return self.render(
            'rag/reranker',
            query=query,
            documents=documents
        )

    def render_query_router(self, query: str) -> str:
        """渲染 Query Router Prompt"""
        return self.render(
            'rag/query_router',
            query=query
        )

    def render_hybrid_retrieval(self, query: str, top_k: int = 10) -> str:
        """渲染混合检索 Prompt"""
        return self.render(
            'rag/hybrid_retrieval',
            query=query,
            top_k=top_k
        )

    # ========== Agent 相关 Prompt ==========

    def render_planner(self, query: str, context: str = None) -> str:
        """渲染 Planner Agent Prompt"""
        return self.render(
            'agent/planner',
            query=query,
            context=context or ''
        )

    def render_researcher(self, sub_task: str, context: str = None) -> str:
        """渲染 Research Agent Prompt"""
        return self.render(
            'agent/researcher',
            sub_task=sub_task,
            context=context or ''
        )

    def render_analyst(self, data: str, analysis_type: str) -> str:
        """渲染 Analysis Agent Prompt"""
        return self.render(
            'agent/analyst',
            data=data,
            analysis_type=analysis_type
        )

    def render_writer(self, outline: dict, context: str) -> str:
        """渲染 Writer Agent Prompt"""
        return self.render(
            'agent/writer',
            outline=outline,
            context=context
        )

    # ========== 报告生成 Prompt ==========

    def render_report_header(
        self,
        title: str,
        subtitle: str = None,
        reading_time: int = None
    ) -> str:
        """渲染报告头部"""
        return self.render(
            'report/header',
            title=title,
            subtitle=subtitle or '',
            reading_time=reading_time or 0
        )

    def render_report_section(
        self,
        section_title: str,
        section_content: str
    ) -> str:
        """渲染报告章节"""
        return self.render(
            'report/section',
            section_title=section_title,
            section_content=section_content
        )

    def render_report_footer(
        self,
        summary: str,
        references: list = None
    ) -> str:
        """渲染报告尾部"""
        return self.render(
            'report/footer',
            summary=summary,
            references=references or []
        )

    def render_citation(self, source: dict) -> str:
        """渲染引用格式"""
        return self.render(
            'report/citation',
            source=source
        )

    # ========== 评估相关 Prompt ==========

    def render_retrieval_evaluator(
        self,
        query: str,
        retrieved_docs: list,
        relevant_docs: list
    ) -> str:
        """渲染检索评估 Prompt"""
        return self.render(
            'evaluation/retrieval',
            query=query,
            retrieved_docs=retrieved_docs,
            relevant_docs=relevant_docs
        )

    def render_generation_evaluator(
        self,
        question: str,
        answer: str,
        reference: str
    ) -> str:
        """渲染生成评估 Prompt (LLM-as-a-Judge)"""
        return self.render(
            'evaluation/generation',
            question=question,
            answer=answer,
            reference=reference
        )


# 全局实例
_prompt_manager: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    """获取 Prompt 管理器实例"""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager