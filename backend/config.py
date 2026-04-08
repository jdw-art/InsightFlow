"""
InsightFlow 后端配置文件
行业分析报告生成系统
"""
import os
from datetime import timedelta

# 基础路径配置
_current_file = os.path.realpath(__file__)
BASE_DIR = os.path.dirname(_current_file)
PROJECT_ROOT = os.path.dirname(BASE_DIR)


class Config:
    """基础配置"""

    # Flask 配置
    SECRET_KEY = os.getenv('SECRET_KEY', 'insightflow-secret-key')

    # 文件存储配置
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    OUTPUT_FOLDER = os.path.join(BASE_DIR, 'outputs')
    DATA_FOLDER = os.path.join(BASE_DIR, 'data')
    CACHE_FOLDER = os.path.join(BASE_DIR, 'cache')
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB

    # AI 配置（从 .env 读取）
    AI_PROVIDER_FORMAT = os.getenv('AI_PROVIDER_FORMAT', 'openai')
    TEXT_MODEL = os.getenv('TEXT_MODEL', 'qwen3-max-preview')

    # OpenAI 兼容 API（用于文本生成）
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    OPENAI_API_BASE = os.getenv('OPENAI_API_BASE', 'https://dashscope.aliyuncs.com/compatible-mode/v1')

    # 日志配置
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()

    # CORS 配置
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*').split(',')

    # Prompt 模板目录
    PROMPTS_DIR = os.path.join(BASE_DIR, 'infrastructure', 'prompts')

    # RAG 配置
    # 向量数据库
    VECTOR_DB_TYPE = os.getenv('VECTOR_DB_TYPE', 'faiss')  # faiss | chromadb
    VECTOR_DB_PATH = os.path.join(DATA_FOLDER, 'vector_db')

    # BM25 索引配置
    BM25_INDEX_PATH = os.path.join(DATA_FOLDER, 'bm25_index')

    # 文档存储路径
    DOCUMENTS_PATH = os.path.join(DATA_FOLDER, 'documents')

    # 检索配置
    RAG_TOP_K = int(os.getenv('RAG_TOP_K', '10'))
    RAG_RERANK_TOP_K = int(os.getenv('RAG_RERANK_TOP_K', '5'))
    RAG_CHUNK_SIZE = int(os.getenv('RAG_CHUNK_SIZE', '1000'))
    RAG_CHUNK_OVERLAP = int(os.getenv('RAG_CHUNK_OVERLAP', '200'))

    # Semantic Cache 配置
    SEMANTIC_CACHE_ENABLED = os.getenv('SEMANTIC_CACHE_ENABLED', 'true').lower() == 'true'
    SEMANTIC_CACHE_THRESHOLD = float(os.getenv('SEMANTIC_CACHE_THRESHOLD', '0.85'))
    SEMANTIC_CACHE_PATH = os.path.join(CACHE_FOLDER, 'semantic_cache')

    # LLM 弹性调用配置
    LLM_CALL_TIMEOUT = int(os.getenv('LLM_CALL_TIMEOUT', '600'))
    LLM_MAX_RETRIES = int(os.getenv('LLM_MAX_RETRIES', '5'))
    LLM_RETRY_BASE_WAIT = float(os.getenv('LLM_RETRY_BASE_WAIT', '5'))
    LLM_RETRY_MAX_WAIT = float(os.getenv('LLM_RETRY_MAX_WAIT', '60'))
    LLM_TRUNCATION_EXPAND_RATIO = float(os.getenv('LLM_TRUNCATION_EXPAND_RATIO', '1.1'))

    # 上下文长度守卫配置
    CONTEXT_GUARD_ENABLED = os.getenv('CONTEXT_GUARD_ENABLED', 'true').lower() == 'true'
    CONTEXT_SAFETY_MARGIN = float(os.getenv('CONTEXT_SAFETY_MARGIN', '0.85'))
    CONTEXT_ESTIMATION_METHOD = os.getenv('CONTEXT_ESTIMATION_METHOD', 'auto')

    # Token 追踪与成本分析
    TOKEN_TRACKING_ENABLED = os.getenv('TOKEN_TRACKING_ENABLED', 'true').lower() == 'true'
    TOKEN_COST_ESTIMATION = os.getenv('TOKEN_COST_ESTIMATION', 'false').lower() == 'true'
    TOKEN_TOTAL_BUDGET = int(os.getenv('TOKEN_TOTAL_BUDGET', '500000'))

    # 结构化任务日志
    TASK_LOG_ENABLED = os.getenv('TASK_LOG_ENABLED', 'true').lower() == 'true'
    TASK_LOGS_DIR = os.getenv('TASK_LOGS_DIR', 'logs/tasks')

    # SSE 流式事件配置
    SSE_LLM_EVENTS_ENABLED = os.getenv('SSE_LLM_EVENTS_ENABLED', 'true').lower() == 'true'
    SSE_TOKEN_SUMMARY_ENABLED = os.getenv('SSE_TOKEN_SUMMARY_ENABLED', 'true').lower() == 'true'

    # 统一 ToolManager
    TOOL_BLACKLIST = os.getenv('TOOL_BLACKLIST', '')
    TOOL_DEFAULT_TIMEOUT = int(os.getenv('TOOL_DEFAULT_TIMEOUT', '300'))

    # Web Search 配置
    SERPER_API_KEY = os.getenv('SERPER_API_KEY', '')
    SERPER_TIMEOUT = int(os.getenv('SERPER_TIMEOUT', '10'))
    SERPER_MAX_RESULTS = int(os.getenv('SERPER_MAX_RESULTS', '10'))

    # Jina 深度抓取
    JINA_API_KEY = os.getenv('JINA_API_KEY', '')
    DEEP_SCRAPE_ENABLED = os.getenv('DEEP_SCRAPE_ENABLED', 'true').lower() == 'true'
    DEEP_SCRAPE_TOP_N = int(os.getenv('DEEP_SCRAPE_TOP_N', '3'))
    DEEP_SCRAPE_TIMEOUT = int(os.getenv('DEEP_SCRAPE_TIMEOUT', '30'))

    # 搜狗搜索配置
    TENCENTCLOUD_SECRET_ID = os.getenv('TENCENTCLOUD_SECRET_ID', '')
    TENCENTCLOUD_SECRET_KEY = os.getenv('TENCENTCLOUD_SECRET_KEY', '')
    SOGOU_SEARCH_TIMEOUT = int(os.getenv('SOGOU_SEARCH_TIMEOUT', '10'))
    SOGOU_MAX_RESULTS = int(os.getenv('SOGOU_MAX_RESULTS', '10'))

    # 多提供商 LLM 客户端工厂
    DEFAULT_LLM_PROVIDER = os.getenv('DEFAULT_LLM_PROVIDER', 'openai')
    DEFAULT_LLM_MODEL = os.getenv('DEFAULT_LLM_MODEL', '')

    # 三级 LLM 模型策略
    LLM_FAST = os.getenv('LLM_FAST', '')
    LLM_SMART = os.getenv('LLM_SMART', '')
    LLM_STRATEGIC = os.getenv('LLM_STRATEGIC', '')
    LLM_FAST_MAX_TOKENS = int(os.getenv('LLM_FAST_MAX_TOKENS', '3000'))
    LLM_SMART_MAX_TOKENS = int(os.getenv('LLM_SMART_MAX_TOKENS', '8192'))
    LLM_STRATEGIC_MAX_TOKENS = int(os.getenv('LLM_STRATEGIC_MAX_TOKENS', '16000'))

    # 推理引擎 Extended Thinking
    THINKING_ENABLED = os.getenv('THINKING_ENABLED', 'false').lower() == 'true'
    THINKING_BUDGET_TOKENS = int(os.getenv('THINKING_BUDGET_TOKENS', '19000'))

    # 评估配置
    EVALUATION_ENABLED = os.getenv('EVALUATION_ENABLED', 'true').lower() == 'true'
    EVALUATION_RECALL_K = int(os.getenv('EVALUATION_RECALL_K', '10'))
    EVALUATION_RESULTS_DIR = os.path.join(OUTPUT_FOLDER, 'evaluations')


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False


config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config():
    """根据环境变量获取配置"""
    env = os.getenv('FLASK_ENV', 'development')
    return config_map.get(env, DevelopmentConfig)