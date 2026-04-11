"""
数据库服务 - 管理文档元数据和知识块
使用 SQLite 存储
"""
import sqlite3
import uuid
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DatabaseService:
    """SQLite 数据库服务"""
    
    def __init__(self, db_path: str = None):
        """
        初始化数据库服务
        
        Args:
            db_path: 数据库文件路径，默认为 backend/data/banana_blog.db
                    在 Vercel 等只读环境中，自动使用内存数据库
        """
        if db_path is None:
            # 默认路径: backend/data/banana_blog.db
            base_dir = Path(__file__).parent.parent
            db_path = str(base_dir / "data" / "banana_blog.db")
        
        self.db_path = db_path
        
        # 尝试创建目录，如果失败则使用内存数据库
        try:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        except (OSError, IOError):
            # Vercel 环境是只读的，使用内存数据库
            logger.warning(f"无法创建数据库目录，使用内存数据库")
            self.db_path = ":memory:"
        
        # 初始化表
        self._init_tables()
        logger.info(f"数据库服务已初始化: {self.db_path}")
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 返回字典形式的结果
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _init_tables(self):
        """初始化数据库表"""
        with self.get_connection() as conn:
            conn.executescript('''
                -- 文档表：存储上传的文档元数据
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    file_type TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    markdown_content TEXT,
                    markdown_length INTEGER DEFAULT 0,
                    summary TEXT,
                    mineru_folder TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    parsed_at TIMESTAMP
                );
                
                -- 知识分块表：存储文档的分块内容（二期新增）
                CREATE TABLE IF NOT EXISTS knowledge_chunks (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    chunk_type TEXT DEFAULT 'text',
                    title TEXT,
                    content TEXT NOT NULL,
                    start_pos INTEGER,
                    end_pos INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
                );
                
                -- 文档图片表：存储 PDF 中提取的图片及摘要（二期新增）
                CREATE TABLE IF NOT EXISTS document_images (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    image_index INTEGER NOT NULL,
                    image_path TEXT NOT NULL,
                    caption TEXT,
                    page_num INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
                );
                
                -- 历史记录表：存储问答历史快照
                CREATE TABLE IF NOT EXISTS history_records (
                    id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    article_type TEXT DEFAULT 'tutorial',
                    target_length TEXT DEFAULT 'medium',
                    markdown_content TEXT,
                    outline TEXT,
                    sections_count INTEGER DEFAULT 0,
                    code_blocks_count INTEGER DEFAULT 0,
                    images_count INTEGER DEFAULT 0,
                    review_score INTEGER DEFAULT 0,
                    cover_image TEXT,
                    target_sections_count INTEGER,
                    target_images_count INTEGER,
                    target_code_blocks_count INTEGER,
                    target_word_count INTEGER,
                    citations TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                -- 创建索引
                CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
                CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at);
                CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON knowledge_chunks(document_id);
                CREATE INDEX IF NOT EXISTS idx_chunks_type ON knowledge_chunks(chunk_type);
                CREATE INDEX IF NOT EXISTS idx_images_document_id ON document_images(document_id);
                CREATE INDEX IF NOT EXISTS idx_history_created_at ON history_records(created_at);
            ''')
        logger.info("数据库表初始化完成")
        
        # 执行数据库迁移
        self._migrate_tables()
    
    def _migrate_tables(self):
        """数据库迁移：检查并添加新字段"""
        with self.get_connection() as conn:
            # 迁移 history_records 表
            cursor = conn.execute("PRAGMA table_info(history_records)")
            columns = [row[1] for row in cursor.fetchall()]
            
            new_columns = {
                'target_sections_count': 'INTEGER',
                'target_images_count': 'INTEGER',
                'target_code_blocks_count': 'INTEGER',
                'target_word_count': 'INTEGER',
                'book_id': 'TEXT',
                'summary': 'TEXT',  # 博客摘要
                'citations': 'TEXT',  # 引用来源（JSON）
            }
            
            for col_name, col_type in new_columns.items():
                if col_name not in columns:
                    logger.info(f"迁移数据库：添加 history_records.{col_name} 列")
                    conn.execute(f"ALTER TABLE history_records ADD COLUMN {col_name} {col_type}")

            # ========== 小红书支持迁移 ==========
            xhs_columns = {
                # 内容类型区分
                'content_type': "TEXT DEFAULT 'blog'",      # 'blog' | 'xhs'
                
                # 记录关联
                'source_id': 'TEXT',                        # 来源记录ID（小红书来源于哪个博客）
                'derived_ids': 'TEXT',                      # 衍生记录ID（JSON数组，博客衍生了哪些小红书）
                
                # 小红书专属字段
                'xhs_style': 'TEXT',                        # hand_drawn | claymation
                'xhs_layout_type': 'TEXT',                  # 布局类型
                'xhs_image_urls': 'TEXT',                   # 图片URL列表（JSON）
                'xhs_copy_text': 'TEXT',                    # 小红书文案
                'xhs_hashtags': 'TEXT',                     # 话题标签（JSON）
                'xhs_publish_url': 'TEXT',                  # 小红书发布链接
                
                # 多平台发布状态
                'publish_platforms': 'TEXT'                 # JSON格式
            }
            
            for col_name, col_type in xhs_columns.items():
                if col_name not in columns:
                    logger.info(f"迁移数据库：添加 history_records.{col_name} 列")
                    conn.execute(f"ALTER TABLE history_records ADD COLUMN {col_name} {col_type}")
            
            # 创建小红书相关索引
            conn.execute('CREATE INDEX IF NOT EXISTS idx_history_content_type ON history_records(content_type)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_history_source_id ON history_records(source_id)')
    
    # ========== 文档操作 ==========
    
    def create_document(
        self, 
        doc_id: str, 
        filename: str, 
        file_path: str, 
        file_size: int, 
        file_type: str
    ) -> Dict[str, Any]:
        """
        创建文档记录
        
        Args:
            doc_id: 文档 ID
            filename: 原始文件名
            file_path: 存储路径
            file_size: 文件大小（字节）
            file_type: 文件类型 (pdf/md/txt)
        
        Returns:
            创建的文档记录
        """
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO documents (id, filename, file_path, file_size, file_type, status)
                VALUES (?, ?, ?, ?, ?, 'pending')
            ''', (doc_id, filename, file_path, file_size, file_type))
        
        logger.info(f"创建文档记录: {doc_id}, {filename}")
        return self.get_document(doc_id)
    
    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        获取文档记录
        
        Args:
            doc_id: 文档 ID
        
        Returns:
            文档记录字典，不存在返回 None
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                'SELECT * FROM documents WHERE id = ?', 
                (doc_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None
    
    def update_document_status(
        self, 
        doc_id: str, 
        status: str, 
        error_message: str = None
    ):
        """
        更新文档状态
        
        Args:
            doc_id: 文档 ID
            status: 新状态 (pending/parsing/ready/error)
            error_message: 错误信息（可选）
        """
        with self.get_connection() as conn:
            conn.execute('''
                UPDATE documents 
                SET status = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (status, error_message, doc_id))
        
        logger.info(f"更新文档状态: {doc_id} -> {status}")
    
    def save_parse_result(
        self, 
        doc_id: str, 
        markdown: str, 
        mineru_folder: str = None
    ):
        """
        保存解析结果
        
        Args:
            doc_id: 文档 ID
            markdown: 解析后的 Markdown 内容
            mineru_folder: MinerU 解析结果目录（PDF 专用）
        """
        with self.get_connection() as conn:
            conn.execute('''
                UPDATE documents 
                SET status = 'ready', 
                    markdown_content = ?, 
                    markdown_length = ?,
                    mineru_folder = ?, 
                    parsed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (markdown, len(markdown), mineru_folder, doc_id))
        
        logger.info(f"保存解析结果: {doc_id}, 长度={len(markdown)}")
    
    def get_documents_by_ids(self, doc_ids: List[str]) -> List[Dict[str, Any]]:
        """
        批量获取文档
        
        Args:
            doc_ids: 文档 ID 列表
        
        Returns:
            文档记录列表
        """
        if not doc_ids:
            return []
        
        placeholders = ','.join(['?' for _ in doc_ids])
        with self.get_connection() as conn:
            cursor = conn.execute(
                f'SELECT * FROM documents WHERE id IN ({placeholders}) AND status = "ready"',
                doc_ids
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def delete_document(self, doc_id: str) -> bool:
        """
        删除文档记录
        
        Args:
            doc_id: 文档 ID
        
        Returns:
            是否删除成功
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                'DELETE FROM documents WHERE id = ?',
                (doc_id,)
            )
            deleted = cursor.rowcount > 0
        
        if deleted:
            logger.info(f"删除文档: {doc_id}")
        return deleted
    
    def list_documents(
        self, 
        status: str = None, 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        列出文档
        
        Args:
            status: 筛选状态（可选）
            limit: 返回数量限制
        
        Returns:
            文档记录列表
        """
        with self.get_connection() as conn:
            if status:
                cursor = conn.execute(
                    'SELECT * FROM documents WHERE status = ? ORDER BY created_at DESC LIMIT ?',
                    (status, limit)
                )
            else:
                cursor = conn.execute(
                    'SELECT * FROM documents ORDER BY created_at DESC LIMIT ?',
                    (limit,)
                )
            return [dict(row) for row in cursor.fetchall()]
    
    def update_document_summary(self, doc_id: str, summary: str):
        """
        更新文档摘要（二期新增）
        
        Args:
            doc_id: 文档 ID
            summary: 文档摘要
        """
        with self.get_connection() as conn:
            conn.execute('''
                UPDATE documents 
                SET summary = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (summary, doc_id))
        logger.info(f"更新文档摘要: {doc_id}")
    
    # ========== 知识分块操作（二期新增） ==========
    
    def save_chunks(self, doc_id: str, chunks: List[Dict[str, Any]]):
        """
        保存文档的知识分块
        
        Args:
            doc_id: 文档 ID
            chunks: 分块列表，每个分块包含 {chunk_type, title, content, start_pos, end_pos}
        """
        with self.get_connection() as conn:
            # 先删除旧分块
            conn.execute('DELETE FROM knowledge_chunks WHERE document_id = ?', (doc_id,))
            
            # 插入新分块
            for idx, chunk in enumerate(chunks):
                chunk_id = f"chunk_{doc_id}_{idx}"
                conn.execute('''
                    INSERT INTO knowledge_chunks 
                    (id, document_id, chunk_index, chunk_type, title, content, start_pos, end_pos)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    chunk_id,
                    doc_id,
                    idx,
                    chunk.get('chunk_type', 'text'),
                    chunk.get('title', ''),
                    chunk.get('content', ''),
                    chunk.get('start_pos', 0),
                    chunk.get('end_pos', 0)
                ))
        
        logger.info(f"保存知识分块: {doc_id}, 共 {len(chunks)} 块")
    
    def get_chunks_by_document(self, doc_id: str) -> List[Dict[str, Any]]:
        """
        获取文档的所有分块
        
        Args:
            doc_id: 文档 ID
        
        Returns:
            分块列表
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                'SELECT * FROM knowledge_chunks WHERE document_id = ? ORDER BY chunk_index',
                (doc_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_chunks_by_documents(self, doc_ids: List[str]) -> List[Dict[str, Any]]:
        """
        批量获取多个文档的分块
        
        Args:
            doc_ids: 文档 ID 列表
        
        Returns:
            分块列表
        """
        if not doc_ids:
            return []
        
        placeholders = ','.join(['?' for _ in doc_ids])
        with self.get_connection() as conn:
            cursor = conn.execute(
                f'SELECT * FROM knowledge_chunks WHERE document_id IN ({placeholders}) ORDER BY document_id, chunk_index',
                doc_ids
            )
            return [dict(row) for row in cursor.fetchall()]
    
    # ========== 文档图片操作（二期新增） ==========
    
    def save_images(self, doc_id: str, images: List[Dict[str, Any]]):
        """
        保存文档的图片信息
        
        Args:
            doc_id: 文档 ID
            images: 图片列表，每个图片包含 {image_path, caption, page_num}
        """
        with self.get_connection() as conn:
            # 先删除旧图片记录
            conn.execute('DELETE FROM document_images WHERE document_id = ?', (doc_id,))
            
            # 插入新图片
            for idx, img in enumerate(images):
                img_id = f"img_{doc_id}_{idx}"
                conn.execute('''
                    INSERT INTO document_images 
                    (id, document_id, image_index, image_path, caption, page_num)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    img_id,
                    doc_id,
                    idx,
                    img.get('image_path', ''),
                    img.get('caption', ''),
                    img.get('page_num', 0)
                ))
        
        logger.info(f"保存文档图片: {doc_id}, 共 {len(images)} 张")
    
    def get_images_by_document(self, doc_id: str) -> List[Dict[str, Any]]:
        """
        获取文档的所有图片
        
        Args:
            doc_id: 文档 ID
        
        Returns:
            图片列表
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                'SELECT * FROM document_images WHERE document_id = ? ORDER BY image_index',
                (doc_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    # ========== 历史记录操作 ==========
    
    def save_history(
        self,
        history_id: str,
        topic: str,
        article_type: str,
        target_length: str,
        markdown_content: str,
        outline: str,
        sections_count: int = 0,
        code_blocks_count: int = 0,
        images_count: int = 0,
        review_score: int = 0,
        cover_image: str = None,
        target_sections_count: int = None,
        target_images_count: int = None,
        target_code_blocks_count: int = None,
        target_word_count: int = None,
        citations: str = None
    ) -> Dict[str, Any]:
        """保存历史记录"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO history_records
                (id, topic, article_type, target_length, markdown_content, outline,
                 sections_count, code_blocks_count, images_count, review_score, cover_image,
                 target_sections_count, target_images_count, target_code_blocks_count, target_word_count, citations)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                history_id, topic, article_type, target_length, markdown_content, outline,
                sections_count, code_blocks_count, images_count, review_score, cover_image,
                target_sections_count, target_images_count, target_code_blocks_count, target_word_count, citations
            ))
        
        logger.info(f"保存历史记录: {history_id}, 主题: {topic}")
        return self.get_history(history_id)
    
    def get_history(self, history_id: str) -> Optional[Dict[str, Any]]:
        """获取单条历史记录"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                'SELECT * FROM history_records WHERE id = ?',
                (history_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None
    
    def list_history(self, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """列出历史记录（按时间倒序，支持分页）"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                '''SELECT hr.id, hr.topic, hr.article_type, hr.target_length, hr.sections_count,
                   hr.code_blocks_count, hr.images_count, hr.review_score, hr.cover_image,
                   hr.target_sections_count, hr.target_images_count, hr.target_code_blocks_count, hr.target_word_count,
                   hr.created_at
                   FROM history_records hr
                   ORDER BY hr.created_at DESC LIMIT ? OFFSET ?''',
                (limit, offset)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def count_history(self) -> int:
        """获取历史记录总数"""
        with self.get_connection() as conn:
            cursor = conn.execute('SELECT COUNT(*) FROM history_records')
            return cursor.fetchone()[0]

    def delete_history(self, history_id: str) -> bool:
        """删除历史记录"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                'DELETE FROM history_records WHERE id = ?',
                (history_id,)
            )
            deleted = cursor.rowcount > 0
        
        if deleted:
            logger.info(f"删除历史记录: {history_id}")
        return deleted
    
    # ========== 小红书记录操作 ==========
    
    def list_history_by_type(
        self, 
        content_type: str = None, 
        limit: int = 20, 
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        按类型列出历史记录
        
        Args:
            content_type: 内容类型 ('blog' | 'xhs' | None表示全部)
            limit: 返回数量限制
            offset: 偏移量
        
        Returns:
            历史记录列表
        """
        with self.get_connection() as conn:
            if content_type and content_type != 'all':
                cursor = conn.execute(
                    '''SELECT hr.id, hr.topic, hr.article_type, hr.target_length, hr.sections_count,
                       hr.code_blocks_count, hr.images_count, hr.review_score, hr.cover_image,
                       hr.target_sections_count, hr.target_images_count, hr.target_code_blocks_count, hr.target_word_count,
                       hr.created_at, hr.content_type, hr.source_id, hr.derived_ids,
                       hr.xhs_style, hr.xhs_image_urls, hr.xhs_copy_text, hr.xhs_hashtags, hr.xhs_publish_url,
                       hr.publish_platforms
                       FROM history_records hr
                       WHERE hr.content_type = ? OR (hr.content_type IS NULL AND ? = 'blog')
                       ORDER BY hr.created_at DESC LIMIT ? OFFSET ?''',
                    (content_type, content_type, limit, offset)
                )
            else:
                cursor = conn.execute(
                    '''SELECT hr.id, hr.topic, hr.article_type, hr.target_length, hr.sections_count,
                       hr.code_blocks_count, hr.images_count, hr.review_score, hr.cover_image,
                       hr.target_sections_count, hr.target_images_count, hr.target_code_blocks_count, hr.target_word_count,
                       hr.created_at, hr.content_type, hr.source_id, hr.derived_ids,
                       hr.xhs_style, hr.xhs_image_urls, hr.xhs_copy_text, hr.xhs_hashtags, hr.xhs_publish_url,
                       hr.publish_platforms
                       FROM history_records hr
                       ORDER BY hr.created_at DESC LIMIT ? OFFSET ?''',
                    (limit, offset)
                )
            return [dict(row) for row in cursor.fetchall()]
    
    def count_history_by_type(self, content_type: str = None) -> int:
        """
        按类型统计历史记录数量
        
        Args:
            content_type: 内容类型 ('blog' | 'xhs' | None表示全部)
        
        Returns:
            记录数量
        """
        with self.get_connection() as conn:
            if content_type and content_type != 'all':
                cursor = conn.execute(
                    '''SELECT COUNT(*) FROM history_records 
                       WHERE content_type = ? OR (content_type IS NULL AND ? = 'blog')''',
                    (content_type, content_type)
                )
            else:
                cursor = conn.execute('SELECT COUNT(*) FROM history_records')
            return cursor.fetchone()[0]
    
    def save_xhs_record(
        self,
        history_id: str,
        topic: str,
        style: str = "hand_drawn",
        layout_type: str = "list",
        image_urls: list = None,
        copy_text: str = "",
        hashtags: list = None,
        cover_image: str = None,
        source_id: str = None
    ) -> Dict[str, Any]:
        """
        保存小红书记录

        Args:
            history_id: 记录ID
            topic: 主题
            style: 风格 (hand_drawn | claymation)
            layout_type: 布局类型
            image_urls: 图片URL列表
            copy_text: 小红书文案
            hashtags: 话题标签列表
            cover_image: 封面图
            source_id: 来源博客ID（如果是从博客转换的）

        Returns:
            创建的记录
        """
        import json
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO history_records
                (id, topic, content_type, xhs_style, xhs_layout_type,
                 xhs_image_urls, xhs_copy_text, xhs_hashtags,
                 cover_image, source_id, images_count)
                VALUES (?, ?, 'xhs', ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                history_id, topic, style, layout_type,
                json.dumps(image_urls or [], ensure_ascii=False),
                copy_text,
                json.dumps(hashtags or [], ensure_ascii=False),
                cover_image, source_id,
                len(image_urls or [])
            ))
        
        # 如果有来源记录，更新其 derived_ids
        if source_id:
            self._add_derived_id(source_id, history_id)
        
        logger.info(f"保存小红书记录: {history_id}, 主题: {topic}")
        return self.get_history(history_id)
    
    def _add_derived_id(self, source_id: str, derived_id: str):
        """添加衍生记录ID到来源记录"""
        import json
        record = self.get_history(source_id)
        if record:
            derived_ids = json.loads(record.get('derived_ids') or '[]')
            if derived_id not in derived_ids:
                derived_ids.append(derived_id)
                with self.get_connection() as conn:
                    conn.execute('''
                        UPDATE history_records 
                        SET derived_ids = ?
                        WHERE id = ?
                    ''', (json.dumps(derived_ids), source_id))
    
    def update_publish_platforms(self, history_id: str, platform: str, status: dict) -> bool:
        """
        更新多平台发布状态
        
        Args:
            history_id: 记录ID
            platform: 平台名称 (csdn | zhihu | juejin | xiaohongshu)
            status: 状态信息 {status, url, published_at}
        
        Returns:
            是否更新成功
        """
        import json
        record = self.get_history(history_id)
        if record:
            platforms = json.loads(record.get('publish_platforms') or '{}')
            platforms[platform] = status
            with self.get_connection() as conn:
                cursor = conn.execute('''
                    UPDATE history_records 
                    SET publish_platforms = ?
                    WHERE id = ?
                ''', (json.dumps(platforms, ensure_ascii=False), history_id))
                return cursor.rowcount > 0
        return False
    
    def update_xhs_publish_url(self, history_id: str, publish_url: str) -> bool:
        """更新小红书发布链接"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                UPDATE history_records 
                SET xhs_publish_url = ?
                WHERE id = ?
            ''', (publish_url, history_id))
            return cursor.rowcount > 0
    
    def update_history_summary(self, history_id: str, summary: str) -> bool:
        """
        更新博客摘要
        
        Args:
            history_id: 博客 ID
            summary: 博客摘要
        """
        with self.get_connection() as conn:
            cursor = conn.execute('''
                UPDATE history_records 
                SET summary = ?
                WHERE id = ?
            ''', (summary, history_id))
            updated = cursor.rowcount > 0
        
        if updated:
            logger.info(f"更新博客摘要: {history_id}")
        return updated


# 全局单例
_db_service: Optional[DatabaseService] = None


def get_db_service() -> DatabaseService:
    """获取数据库服务单例"""
    global _db_service
    if _db_service is None:
        _db_service = DatabaseService()
    return _db_service


def init_db_service(db_path: str = None) -> DatabaseService:
    """初始化数据库服务"""
    global _db_service
    _db_service = DatabaseService(db_path)
    return _db_service
