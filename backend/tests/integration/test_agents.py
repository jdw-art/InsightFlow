"""
Agents 集成测试（简化版）
测试 Agent 基本功能和协作
"""
import logging
import os
from typing import Dict, Any

import pytest
from unittest.mock import Mock, MagicMock, patch

from backend.services import LLMService

logger = logging.getLogger(__name__)


class TestAgentInitialization:
    """测试 Agent 初始化"""

    def test_writer_agent_initialization(self):
        """测试 WriterAgent 初始化"""
        from services.blog_generator.agents.writer import WriterAgent

        mock_llm = MagicMock()
        agent = WriterAgent(llm_client=mock_llm)

        assert agent is not None
        assert agent.llm == mock_llm

    def test_reviewer_agent_initialization(self):
        """测试 ReviewerAgent 初始化"""
        from services.blog_generator.agents.reviewer import ReviewerAgent

        mock_llm = MagicMock()
        agent = ReviewerAgent(llm_client=mock_llm)

        assert agent is not None
        assert agent.llm == mock_llm

    def test_artist_agent_initialization(self):
        """测试 ArtistAgent 初始化"""
        from services.blog_generator.agents.artist import ArtistAgent

        mock_llm = MagicMock()
        agent = ArtistAgent(llm_client=mock_llm)

        assert agent is not None
        assert agent.llm == mock_llm


class TestWriterAgent:
    """测试 WriterAgent"""

    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM 客户端"""
        client = MagicMock()
        # Mock chat 方法返回 JSON 字符串
        client.chat.return_value = json.dumps({
            'content': 'Generated section content',
            'key_points': ['Point 1', 'Point 2']
        })
        return client

    @pytest.fixture
    def writer_agent(self, mock_llm_client):
        """创建 WriterAgent 实例"""
        from services.blog_generator.agents.writer import WriterAgent
        return WriterAgent(llm_client=mock_llm_client)

    def test_writer_agent_run(self, writer_agent):
        """测试 WriterAgent 运行"""
        from services.blog_generator.schemas.state import create_initial_state

        # 创建初始状态
        state = create_initial_state(
            topic='Vue 3 Composition API',
            article_type='tutorial',
            target_audience='intermediate',
            target_length='medium'
        )

        # 添加大纲
        state['outline'] = {
            'title': 'Vue 3 Composition API 深度解析',
            'sections': [
                {
                    'title': '什么是 Composition API',
                    'key_points': ['定义', '优势', '使用场景']
                }
            ]
        }

        # 运行 writer agent
        result = writer_agent.run(state)

        # 验证返回了更新的状态
        assert result is not None
        assert 'sections' in result

    def test_writer_agent_error_handling(self):
        """测试 WriterAgent 错误处理"""
        from services.blog_generator.agents.writer import WriterAgent

        mock_llm = MagicMock()
        mock_llm.chat.side_effect = Exception('LLM API error')

        agent = WriterAgent(llm_client=mock_llm)

        from services.blog_generator.schemas.state import create_initial_state
        state = create_initial_state(topic='Test', target_length='mini')
        state['outline'] = {'title': 'Test', 'sections': [{'title': 'S1', 'key_points': []}]}

        # 应该捕获错误
        try:
            result = agent.run(state)
            # 如果没有抛出异常，验证返回了合理的状态
            assert result is not None
        except Exception as e:
            # 如果抛出异常，验证是预期的错误
            assert 'LLM API error' in str(e)


class TestReviewerAgent:
    """测试 ReviewerAgent"""

    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM 客户端"""
        client = MagicMock()
        client.chat.return_value = json.dumps({
            'review_score': 85,
            'review_approved': True,
            'review_issues': []
        })
        return client

    @pytest.fixture
    def reviewer_agent(self, mock_llm_client):
        """创建 ReviewerAgent 实例"""
        from services.blog_generator.agents.reviewer import ReviewerAgent
        return ReviewerAgent(llm_client=mock_llm_client)

    def test_reviewer_agent_run(self, reviewer_agent):
        """测试 ReviewerAgent 运行"""
        from services.blog_generator.schemas.state import create_initial_state

        state = create_initial_state(topic='Test', target_length='mini')
        state['outline'] = {'title': 'Test', 'sections': []}
        state['sections'] = [
            {
                'title': 'Section 1',
                'content': 'This is the content of section 1.',
                'key_points': ['Point 1']
            }
        ]

        result = reviewer_agent.run(state)

        # 验证返回了评审结果
        assert 'review_score' in result
        assert 'review_approved' in result

    def test_reviewer_agent_error_handling(self):
        """测试 ReviewerAgent 错误处理"""
        from services.blog_generator.agents.reviewer import ReviewerAgent

        mock_llm = MagicMock()
        mock_llm.chat.side_effect = Exception('Review failed')

        agent = ReviewerAgent(llm_client=mock_llm)

        from services.blog_generator.schemas.state import create_initial_state
        state = create_initial_state(topic='Test', target_length='mini')
        state['sections'] = []

        try:
            result = agent.run(state)
            assert result is not None
        except Exception as e:
            assert 'Review failed' in str(e)


class TestArtistAgent:
    """测试 ArtistAgent"""

    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM 客户端"""
        client = MagicMock()
        client.chat.return_value = json.dumps({
            'images': []  # 简化测试，返回空列表
        })
        return client

    @pytest.fixture
    def artist_agent(self, mock_llm_client):
        """创建 ArtistAgent 实例"""
        from services.blog_generator.agents.artist import ArtistAgent
        return ArtistAgent(llm_client=mock_llm_client)

    def test_artist_agent_run(self, artist_agent):
        """测试 ArtistAgent 运行"""
        from services.blog_generator.schemas.state import create_initial_state

        state = create_initial_state(topic='Test', target_length='mini')
        state['outline'] = {'title': 'Test', 'sections': []}
        state['sections'] = [
            {'title': 'Section 1', 'content': 'Content'}
        ]
        state['images'] = []

        result = artist_agent.run(state)

        # 验证返回了状态
        assert result is not None
        assert 'images' in result

    def test_artist_agent_error_handling(self):
        """测试 ArtistAgent 错误处理"""
        from services.blog_generator.agents.artist import ArtistAgent

        mock_llm = MagicMock()
        mock_llm.chat.side_effect = Exception('Image generation failed')

        agent = ArtistAgent(llm_client=mock_llm)

        from services.blog_generator.schemas.state import create_initial_state
        state = create_initial_state(topic='Test', target_length='mini')
        state['sections'] = []
        state['images'] = []

        try:
            result = agent.run(state)
            assert result is not None
        except Exception as e:
            assert 'Image generation failed' in str(e)


class TestResearcherAgent:
    """测试 ResearcherAgent - 专注于 run 方法"""

    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM 客户端"""
        client = MagicMock()
        # 模拟生成搜索查询的响应
        client.chat.side_effect = [
            # 第一次调用：generate_search_queries 返回查询列表
            json.dumps(['RAG 教程', 'RAG 最佳实践', 'RAG 常见问题']),
            # 第二次调用：summarize 返回摘要结果
            json.dumps({
                'background_knowledge': 'RAG（检索增强生成）是一种结合信息检索和文本生成的技术。',
                'key_concepts': [
                    {'name': '检索增强生成', 'description': '结合检索和生成的技术'},
                    {'name': '向量数据库', 'description': '存储向量表示的数据库'},
                    {'name': '嵌入模型', 'description': '将文本转换为向量的模型'}
                ],
                'top_references': [
                    {'title': 'RAG 官方文档', 'url': 'https://example.com/rag'},
                    {'title': 'RAG 最佳实践指南', 'url': 'https://example.com/rag-guide'}
                ],
                'instructional_analysis': {
                    'learning_objectives': ['理解 RAG 基本概念', '掌握 RAG 实现方法'],
                    'verbatim_data': [],
                    'content_type': 'tutorial'
                }
            }),
            # 第三次调用：distill 返回提炼结果
            json.dumps({
                'sources': [
                    {
                        'url': 'https://example.com/rag',
                        'core_insight': 'RAG 通过检索增强 LLM 能力',
                        'key_facts': ['RAG 减少幻觉', 'RAG 提高准确性']
                    }
                ],
                'common_themes': ['检索增强', '向量检索', '生成优化'],
                'contradictions': [],
                'material_by_type': {
                    'concepts': ['RAG 定义', '向量嵌入'],
                    'cases': ['问答系统', '文档生成'],
                    'data': [],
                    'comparisons': []
                }
            }),
            # 第四次调用：analyze_gaps 返回缺口分析
            json.dumps({
                'content_gaps': ['缺乏代码示例', '缺少性能对比'],
                'unique_angles': ['从零实现 RAG', 'RAG 性能优化'],
                'writing_recommendations': {
                    'focus_areas': ['核心概念', '实践案例'],
                    'avoid_redundancy': True
                }
            })
        ]
        return client

    @pytest.fixture
    def mock_search_service(self):
        """Mock 搜索服务"""
        service = MagicMock()
        service.search.return_value = {
            'success': True,
            'results': [
                {
                    'title': 'RAG 入门指南',
                    'url': 'https://example.com/rag',
                    'content': 'RAG 是一种强大的技术...',
                    'snippet': 'RAG 是一种强大的技术...'
                },
                {
                    'title': 'RAG 最佳实践',
                    'url': 'https://example.com/rag-guide',
                    'content': '实现 RAG 的关键步骤...',
                    'snippet': '实现 RAG 的关键步骤...'
                }
            ]
        }
        return service

    @pytest.fixture
    def researcher_agent(self, mock_llm_client, mock_search_service):
        """创建 ResearcherAgent 实例"""
        from services.blog_generator.agents.researcher import ResearcherAgent
        return ResearcherAgent(
            llm_client=mock_llm_client,
            search_service=mock_search_service
        )

    def test_researcher_run(self):
        from services.blog_generator.agents.researcher import ResearcherAgent
        from services.blog_generator.agents.planner import PlannerAgent
        from services.blog_generator.agents.writer import WriterAgent
        from services.blog_generator.schemas.state import create_initial_state
        from services.blog_generator.services import SearchService
        from services.llm_factory import create_llm_client

        llm_client = create_llm_client(provider='openai',
                                       model_name='kimi-k2.5',
                                       api_key='sk-ApQjk77RUb9jCkWX2ASe8xetmPVMWNXUMTj3cr2pmpo59IPT',
                                       base_url='https://api.moonshot.cn/v1',
                                       temperature=1.0,
                                       max_tokens=2048)
        search_service = SearchService(api_key='a946da5f0c0640549cdfad02c31e7c2a.fSuzBHl1jOY9RucW')

        # 1. researcher 执行搜索
        researcher = ResearcherAgent(llm_client=llm_client, search_service=search_service)

        state = create_initial_state(
            topic='PPO强化学习算法原理',
            article_type='tutorial',
            target_audience='intermediate',
            target_length='medium',
            target_sections_count=4,
            target_word_count=800
        )

        # 结果：Dict[str, Any]
        researcher_result = researcher.run(state)

        logger.info(f"Researcher搜索结果: {researcher_result}")

        # 2. planner 规划大纲
        planner = PlannerAgent(llm_client=llm_client)

        planner_result = planner.run(researcher_result)

        logger.info(f"Planner规划大纲: {planner_result}")

        writer = WriterAgent(llm_client=llm_client)

        writer_result = writer.run(state=planner_result, max_workers=3)

        logger.info(f"Writer撰写内容: {writer_result}")



    def test_researcher_agent_run(self, researcher_agent, mock_search_service):
        """测试 ResearcherAgent run 方法 - 正常流程"""
        from services.blog_generator.schemas.state import create_initial_state

        # 创建初始状态
        state = create_initial_state(
            topic='RAG 检索增强生成',
            article_type='tutorial',
            target_audience='intermediate',
            target_length='medium'
        )

        # 运行 researcher agent
        result = researcher_agent.run(state)

        # 验证返回了更新的状态
        assert result is not None
        assert 'search_results' in result
        assert 'background_knowledge' in result
        assert 'key_concepts' in result
        assert 'reference_links' in result
        assert 'knowledge_source_stats' in result

        # 验证具体内容
        assert len(result['search_results']) > 0
        assert 'RAG' in result['background_knowledge'] or result['background_knowledge'] == ''
        assert isinstance(result['key_concepts'], list)
        assert isinstance(result['reference_links'], list)

        # 验证搜索服务被调用
        mock_search_service.search.assert_called()

        # 验证深度提炼相关字段
        assert 'distilled_sources' in result
        assert 'material_by_type' in result
        assert 'common_themes' in result
        assert 'content_gaps' in result
        assert 'unique_angles' in result

        # 验证教学设计相关字段
        assert 'instructional_analysis' in result
        assert 'learning_objectives' in result

    def test_researcher_agent_run_without_search_service(self, mock_llm_client):
        """测试 ResearcherAgent run 方法 - 无搜索服务"""
        from services.blog_generator.agents.researcher import ResearcherAgent
        from services.blog_generator.schemas.state import create_initial_state

        # 创建没有搜索服务的 agent
        agent = ResearcherAgent(llm_client=mock_llm_client, search_service=None)

        state = create_initial_state(
            topic='测试主题',
            article_type='tutorial',
            target_audience='intermediate',
            target_length='short'
        )

        # 运行应该正常完成（跳过搜索）
        result = agent.run(state)

        assert result is not None
        assert 'search_results' in result
        assert result['search_results'] == []

    def test_researcher_agent_run_with_document_knowledge(self, researcher_agent):
        """测试 ResearcherAgent run 方法 - 带文档知识"""
        from services.blog_generator.schemas.state import create_initial_state

        state = create_initial_state(
            topic='RAG 技术',
            article_type='tutorial',
            target_audience='intermediate',
            target_length='medium'
        )

        # 添加文档知识
        state['document_knowledge'] = [
            {
                'file_name': 'rag_intro.pdf',
                'content': 'RAG 是一种结合检索和生成的技术框架。'
            }
        ]

        # 运行 researcher
        result = researcher_agent.run(state)

        assert result is not None
        assert 'search_results' in result
        assert 'background_knowledge' in result

    def test_researcher_agent_run_error_handling(self):
        """测试 ResearcherAgent run 方法 - 错误处理"""
        from services.blog_generator.agents.researcher import ResearcherAgent
        from services.blog_generator.schemas.state import create_initial_state

        mock_llm = MagicMock()
        mock_search = MagicMock()

        # 模拟搜索抛出异常
        mock_search.search.side_effect = Exception('Search API error')

        agent = ResearcherAgent(llm_client=mock_llm, search_service=mock_search)

        state = create_initial_state(
            topic='测试主题',
            article_type='tutorial',
            target_audience='intermediate',
            target_length='short'
        )

        # 应该捕获错误并继续执行
        try:
            result = agent.run(state)
            # 验证返回了状态（即使搜索失败）
            assert result is not None
            assert 'search_results' in result
        except Exception as e:
            # 如果抛出异常，应该是预期的错误
            assert 'Search API error' in str(e) or 'search_results' in str(e)


class TestAgentCollaboration:
    """测试 Agent 协作"""

    def test_writer_reviewer_collaboration(self):
        """测试 Writer 和 Reviewer 协作"""
        from services.blog_generator.agents.writer import WriterAgent
        from services.blog_generator.agents.reviewer import ReviewerAgent
        from services.blog_generator.schemas.state import create_initial_state

        # Mock LLM 客户端
        mock_llm = MagicMock()
        mock_llm.chat.return_value = json.dumps({
            'content': 'Generated content',
            'review_score': 85,
            'review_approved': True,
            'review_issues': []
        })

        writer = WriterAgent(llm_client=mock_llm)
        reviewer = ReviewerAgent(llm_client=mock_llm)

        # 初始状态
        state = create_initial_state(topic='Test', target_length='mini')
        state['outline'] = {
            'title': 'Test',
            'sections': [{'title': 'Section 1', 'key_points': ['P1']}]
        }

        # Writer 写入内容
        state = writer.run(state)
        assert 'sections' in state

        # Reviewer 评审内容
        state = reviewer.run(state)
        assert 'review_score' in state or 'review_approved' in state


# 导入 json 模块
import json
