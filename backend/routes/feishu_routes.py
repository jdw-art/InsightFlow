"""
飞书机器人 Webhook 路由

接收飞书事件订阅（im.message.receive_v1），解析用户消息，
路由到对话式写作 API，并通过飞书 API 回复结果。

飞书开发者后台配置：
  1. 创建企业自建应用 → 获取 App ID / App Secret
  2. 添加机器人能力
  3. 权限管理 → 开通 im:message（发消息）、im:message.receive_v1（收消息）
  4. 事件订阅 → 请求地址: https://your-domain/api/feishu/webhook
  5. 添加事件: im.message.receive_v1
"""
import hashlib
import hmac
import json
import logging
import os
import re
import time
import threading
from functools import lru_cache

import requests
from flask import Blueprint, current_app, jsonify, request

logger = logging.getLogger(__name__)

feishu_bp = Blueprint('feishu', __name__, url_prefix='/api/feishu')

# ========== 配置 ==========

FEISHU_APP_ID = os.getenv('FEISHU_APP_ID', '')
FEISHU_APP_SECRET = os.getenv('FEISHU_APP_SECRET', '')
FEISHU_VERIFICATION_TOKEN = os.getenv('FEISHU_VERIFICATION_TOKEN', '')
FEISHU_ENCRYPT_KEY = os.getenv('FEISHU_ENCRYPT_KEY', '')

FEISHU_API_BASE = 'https://open.feishu.cn/open-apis'

# 内部 API 地址（同进程调用）
VIBE_REPORT_INTERNAL = os.getenv('VIBE_REPORT_INTERNAL', 'http://localhost:5001')

# 飞书卡片模板 ID（在飞书后台卡片搭建工具中创建）
CARD_TEMPLATES = {
    'help': os.getenv('FEISHU_TPL_HELP', ''),
    'task_started': os.getenv('FEISHU_TPL_TASK_STARTED', ''),
    'progress': os.getenv('FEISHU_TPL_PROGRESS', ''),
    'completed': os.getenv('FEISHU_TPL_COMPLETED', ''),
    'failed': os.getenv('FEISHU_TPL_FAILED', ''),
    'info': os.getenv('FEISHU_TPL_INFO', ''),
}

# ========== Token 管理 ==========

_token_cache = {'token': '', 'expires_at': 0}


def _get_tenant_access_token():
    """获取飞书 tenant_access_token（带缓存）。"""
    now = time.time()
    if _token_cache['token'] and _token_cache['expires_at'] > now + 60:
        return _token_cache['token']

    resp = requests.post(
        f'{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal',
        json={'app_id': FEISHU_APP_ID, 'app_secret': FEISHU_APP_SECRET},
        timeout=10,
    )
    data = resp.json()
    if data.get('code') != 0:
        logger.error('获取飞书 token 失败: %s', data)
        return ''

    token = data['tenant_access_token']
    _token_cache['token'] = token
    _token_cache['expires_at'] = now + data.get('expire', 7200)
    return token


# ========== 飞书消息发送 ==========

def _send_feishu_message(chat_id, text, msg_type='chat_id'):
    """通过飞书 API 发送文本消息到群聊。"""
    token = _get_tenant_access_token()
    if not token:
        logger.error('无法发送飞书消息：token 为空')
        return

    resp = requests.post(
        f'{FEISHU_API_BASE}/im/v1/messages',
        params={'receive_id_type': msg_type},
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json; charset=utf-8',
        },
        json={
            'receive_id': chat_id,
            'msg_type': 'text',
            'content': json.dumps({'text': text}),
        },
        timeout=10,
    )
    data = resp.json()
    if data.get('code') != 0:
        logger.error('飞书发送消息失败: %s', data)


def _reply_feishu_message(message_id, text):
    """回复飞书消息（引用回复）。"""
    token = _get_tenant_access_token()
    if not token:
        logger.error('无法回复飞书消息：token 为空')
        return

    resp = requests.post(
        f'{FEISHU_API_BASE}/im/v1/messages/{message_id}/reply',
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json; charset=utf-8',
        },
        json={
            'msg_type': 'text',
            'content': json.dumps({'text': text}),
        },
        timeout=10,
    )
    data = resp.json()
    if data.get('code') != 0:
        logger.error('飞书回复消息失败: %s', data)


# ========== 飞书卡片消息 ==========

def _build_card(title, elements, header_color='blue'):
    """构建飞书 Interactive Card（代码构建方式，作为模板的降级方案）。"""
    return {
        'config': {'wide_screen_mode': True},
        'header': {
            'title': {'tag': 'plain_text', 'content': title},
            'template': header_color,
        },
        'elements': elements,
    }


def _build_template_content(template_key, variables=None):
    """构建飞书卡片模板内容。

    Args:
        template_key: 模板键名 (help/task_started/progress/completed/failed/info)
        variables: 模板变量字典
    Returns:
        模板内容 dict，或 None（未配置模板时）
    """
    tpl_id = CARD_TEMPLATES.get(template_key, '')
    if not tpl_id:
        return None
    return {
        'type': 'template',
        'data': {
            'template_id': tpl_id,
            'template_variable': variables or {},
        },
    }


def _md_element(content):
    """Markdown 文本元素。"""
    return {'tag': 'div', 'text': {'tag': 'lark_md', 'content': content}}


def _hr_element():
    """分割线元素。"""
    return {'tag': 'hr'}


def _note_element(content):
    """备注元素（灰色小字）。"""
    return {
        'tag': 'note',
        'elements': [{'tag': 'lark_md', 'content': content}],
    }


def _reply_card(message_id, title, elements, header_color='blue',
               template_key=None, variables=None):
    """用卡片消息回复飞书消息。模板优先，无模板时降级为代码构建。"""
    token = _get_tenant_access_token()
    if not token:
        logger.error('无法回复飞书卡片：token 为空')
        return

    tpl_content = _build_template_content(template_key, variables) if template_key else None
    if tpl_content:
        content = json.dumps(tpl_content)
    else:
        content = json.dumps(_build_card(title, elements, header_color))

    resp = requests.post(
        f'{FEISHU_API_BASE}/im/v1/messages/{message_id}/reply',
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json; charset=utf-8',
        },
        json={
            'msg_type': 'interactive',
            'content': content,
        },
        timeout=10,
    )
    data = resp.json()
    if data.get('code') != 0:
        logger.error('飞书卡片回复失败: %s', data)


def _send_card(chat_id, title, elements, header_color='blue', msg_type='chat_id',
              template_key=None, variables=None):
    """主动发送卡片消息到聊天。模板优先，无模板时降级为代码构建。"""
    token = _get_tenant_access_token()
    if not token:
        logger.error('无法发送飞书卡片：token 为空')
        return

    tpl_content = _build_template_content(template_key, variables) if template_key else None
    if tpl_content:
        content = json.dumps(tpl_content)
    else:
        content = json.dumps(_build_card(title, elements, header_color))

    resp = requests.post(
        f'{FEISHU_API_BASE}/im/v1/messages',
        params={'receive_id_type': msg_type},
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json; charset=utf-8',
        },
        json={
            'receive_id': chat_id,
            'msg_type': 'interactive',
            'content': content,
        },
        timeout=10,
    )
    data = resp.json()
    if data.get('code') != 0:
        logger.error('飞书卡片发送失败: %s', data)


# ========== 进度轮询推送 ==========

def _poll_task_progress(task_id, chat_id, user_id, topic):
    """轮询任务进度，关键节点主动推送飞书卡片通知。"""
    from services.task_service import TaskManager
    tm = TaskManager()

    last_stage = ''
    poll_interval = 5  # 秒
    max_wait = 1800    # 最多等 30 分钟
    elapsed = 0

    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval

        task = tm.get_task(task_id)
        if not task:
            break

        # 阶段变化时推送进度
        if task.current_stage and task.current_stage != last_stage:
            last_stage = task.current_stage
            stage_names = {
                'analyze': '📊 分析主题',
                'metaphor': '🎭 构思比喻',
                'outline': '📋 生成大纲',
                'research': '🔍 调研搜索',
                'content': '✍️ 撰写内容',
                'image': '🎨 生成配图',
                'review': '🔍 审阅优化',
                'assemble': '📦 组装文章',
            }
            stage_label = stage_names.get(last_stage, f'⚙️ {last_stage}')
            progress = task.overall_progress or 0
            bar = _progress_bar(progress)
            _send_card(chat_id, f'⏳ 生成中：{topic}', [
                _md_element(f'**当前阶段**：{stage_label}'),
                _md_element(f'**总体进度**：{bar} {progress}%'),
            ], header_color='blue',
               template_key='progress',
               variables={'topic': topic, 'stage': stage_label, 'progress': f'{progress}%'})

        # 完成
        if task.status == 'completed':
            outputs = task.outputs or {}
            word_count = outputs.get('word_count', 0)
            section_count = outputs.get('section_count', 0)
            _send_card(chat_id, f'✅ 写作完成：{topic}', [
                _md_element(
                    f'**字数**：~{word_count}\n'
                    f'**章节**：{section_count}\n'
                ),
                _hr_element(),
                _md_element('发送 **预览** 查看文章内容\n发送 **发布** 发布文章'),
            ], header_color='green',
               template_key='completed',
               variables={'topic': topic, 'word_count': str(word_count), 'section_count': str(section_count)})
            _user_sessions[user_id] = {
                **_user_sessions.get(user_id, {}),
                'status': 'completed',
            }
            return

        # 失败
        if task.status == 'failed':
            error_msg = task.error or '未知错误'
            _send_card(chat_id, f'❌ 生成失败：{topic}', [
                _md_element(f'**错误**：{error_msg[:200]}'),
                _hr_element(),
                _md_element('发送 **写作** 重试，或发送新主题'),
            ], header_color='red',
               template_key='failed',
               variables={'topic': topic, 'error': error_msg[:200]})
            _user_sessions[user_id] = {
                **_user_sessions.get(user_id, {}),
                'status': 'failed',
            }
            return

        # 取消
        if task.status == 'cancelled':
            _send_card(chat_id, f'🚫 已取消：{topic}', [
                _md_element('任务已取消。发送新主题重新开始。'),
            ], header_color='grey')
            return

    # 超时
    _send_card(chat_id, f'⏰ 超时：{topic}', [
        _md_element('生成时间过长，请发送 **状态** 查看进度。'),
    ], header_color='orange')


def _progress_bar(percent, length=10):
    """生成文本进度条。"""
    filled = int(length * percent / 100)
    return '█' * filled + '░' * (length - filled)


def _start_progress_watcher(task_id, chat_id, user_id, topic):
    """启动进度轮询线程。"""
    threading.Thread(
        target=_poll_task_progress,
        args=(task_id, chat_id, user_id, topic),
        daemon=True,
    ).start()


# ========== 意图识别 ==========

def _parse_intent(text):
    """解析用户消息意图，映射到对话式写作 API 操作。"""
    t = text.strip()

    # 写 <主题> — 一键生成
    m = re.match(r'^写[写作]?\s+(.+)', t)
    if m:
        return {'action': 'write_full', 'topic': m.group(1).strip()}

    # 新话题 <主题>
    m = re.match(r'^(新话题|新主题|new)\s+(.+)', t, re.IGNORECASE)
    if m:
        return {'action': 'create', 'topic': m.group(2).strip()}

    if re.match(r'^(搜索|调研|research|search)', t, re.IGNORECASE):
        return {'action': 'search'}

    if re.match(r'^(大纲|outline)', t, re.IGNORECASE):
        return {'action': 'outline'}

    if re.match(r'^(写作|开始写|生成|generate|write)', t, re.IGNORECASE):
        return {'action': 'generate'}

    if re.match(r'^(预览|preview)', t, re.IGNORECASE):
        return {'action': 'preview'}

    if re.match(r'^(发布|publish)', t, re.IGNORECASE):
        return {'action': 'publish'}

    if re.match(r'^(状态|status)', t, re.IGNORECASE):
        return {'action': 'status'}

    if re.match(r'^(帮助|help|/help|\?)', t, re.IGNORECASE):
        return {'action': 'help'}

    if re.match(r'^(列表|list|我的文章)', t, re.IGNORECASE):
        return {'action': 'list'}

    return {'action': 'auto', 'text': t}


HELP_TEXT = """📝 vibe-report 对话式写作

指令：
• 写 <主题> — 一键生成完整报告
• 新话题 <主题> — 创建写作会话
• 搜索 — 调研当前主题
• 大纲 — 生成文章大纲
• 写作 — 开始写作
• 预览 — 预览文章
• 发布 — 发布文章
• 状态 — 查看当前进度
• 列表 — 查看所有文章
• 帮助 — 显示此帮助

直接发送主题也可以开始写作！"""


# ========== 内部 API 调用 ==========

def _call_chat_api(method, path, user_id, body=None):
    """调用 vibe-report 对话式写作 API。"""
    url = f'{VIBE_REPORT_INTERNAL}{path}'
    headers = {'Content-Type': 'application/json'}
    if user_id:
        headers['X-User-Id'] = user_id

    try:
        if method == 'GET':
            resp = requests.get(url, headers=headers, timeout=120)
        else:
            resp = requests.post(url, headers=headers, json=body or {}, timeout=120)

        if not resp.ok:
            raise Exception(f'API {resp.status_code}: {resp.text[:200]}')
        return resp.json()
    except Exception as e:
        logger.error('调用对话式写作 API 失败: %s %s → %s', method, path, e)
        raise


# ========== 会话管理（内存缓存，按 user_id 隔离） ==========

# user_id → { session_id, topic, status, task_id }
# 每个飞书用户独立一个活跃会话，多用户在同一群中互不干扰
_user_sessions = {}


# ========== 消息处理核心 ==========

def _handle_message(chat_id, user_id, text, message_id):
    """处理飞书消息，路由到对话式写作 API。按 user_id 隔离会话。"""
    intent = _parse_intent(text)
    session = _user_sessions.get(user_id)

    def reply_text(msg):
        _reply_feishu_message(message_id, msg)

    def reply_card(title, elements, color='blue', tpl=None, tpl_vars=None):
        _reply_card(message_id, title, elements, color,
                    template_key=tpl, variables=tpl_vars)

    def send_card(title, elements, color='blue', tpl=None, tpl_vars=None):
        _send_card(chat_id, title, elements, color,
                   template_key=tpl, variables=tpl_vars)

    try:
        # ---- 帮助 ----
        if intent['action'] == 'help':
            reply_card('📝 vibe-report 对话式写作', [
                _md_element(
                    '**指令列表**\n'
                    '• `写 <主题>` — 一键生成完整博客\n'
                    '• `新话题 <主题>` — 创建写作会话\n'
                    '• `搜索` — 调研当前主题\n'
                    '• `大纲` — 生成文章大纲\n'
                    '• `写作` — 开始写作\n'
                    '• `预览` — 预览文章\n'
                    '• `发布` — 发布文章\n'
                    '• `状态` — 查看当前进度\n'
                    '• `列表` — 查看所有文章\n'
                    '• `帮助` — 显示此帮助'
                ),
                _hr_element(),
                _note_element('直接发送主题也可以开始写作'),
            ], color='purple', tpl='help')
            return

        # ---- 列表 ----
        if intent['action'] == 'list':
            sessions = _call_chat_api('GET', '/api/chat/sessions', user_id)
            if not sessions:
                reply_card('📭 暂无写作会话', [
                    _md_element('发送 **写 <主题>** 开始创作！'),
                ], color='grey')
                return
            lines = '\n'.join(
                f'{i+1}. **{s["topic"]}** ({s["status"]})' for i, s in enumerate(sessions)
            )
            reply_card('📋 你的写作会话', [
                _md_element(lines),
            ], color='blue')
            return

        # ---- 状态 ----
        if intent['action'] == 'status':
            if not session:
                reply_card('💡 提示', [
                    _md_element('没有活跃的写作会话。\n发送 **写 <主题>** 开始创作！'),
                ], color='grey')
                return
            detail = _call_chat_api('GET', f'/api/chat/session/{session["session_id"]}', user_id)
            section_count = len(detail.get('sections') or [])
            word_count = sum(len(s.get('content', '')) for s in (detail.get('sections') or []))
            reply_card(f'📊 {detail["topic"]}', [
                _md_element(
                    f'**状态**：{detail["status"]}\n'
                    f'**章节**：{section_count}\n'
                    f'**字数**：~{word_count}'
                ),
            ], color='blue')
            return

        # ---- 写/新话题 ----
        if intent['action'] in ('write_full', 'create'):
            topic = intent['topic']

            created = _call_chat_api('POST', '/api/chat/session', user_id, {
                'topic': topic,
                'article_type': 'problem-solution',
                'target_audience': 'beginner',
                'target_length': 'medium',
            })

            _user_sessions[user_id] = {
                'session_id': created['session_id'],
                'topic': topic,
                'status': 'created',
            }

            if intent['action'] == 'create':
                reply_card(f'✅ 会话已创建', [
                    _md_element(
                        f'**主题**：{topic}\n'
                        f'**会话 ID**：`{created["session_id"]}`'
                    ),
                    _hr_element(),
                    _md_element(
                        '接下来可以发送：\n'
                        '• **搜索** — 调研主题\n'
                        '• **大纲** — 生成大纲\n'
                        '• **写作** — 一键生成'
                    ),
                ], color='green')
                return

            # write_full: 触发一键生成
            reply_card(f'🚀 开始写作：{topic}', [
                _md_element('正在创建会话并启动生成...'),
            ], color='blue')

            gen_result = _call_chat_api(
                'POST', f'/api/chat/session/{created["session_id"]}/generate', user_id
            )
            task_id = gen_result.get('task_id')
            _user_sessions[user_id]['status'] = 'generating'
            _user_sessions[user_id]['task_id'] = task_id

            send_card(f'⏳ 一键生成已启动', [
                _md_element(
                    f'**主题**：{topic}\n'
                    f'**任务 ID**：`{task_id}`'
                ),
                _hr_element(),
                _note_element('生成过程需要几分钟，完成后会自动通知你'),
            ], color='blue',
               tpl='task_started', tpl_vars={'topic': topic, 'task_id': task_id})

            _start_progress_watcher(task_id, chat_id, user_id, topic)
            return

        # ---- 搜索 ----
        if intent['action'] == 'search':
            if not session:
                reply_card('❌ 无活跃会话', [
                    _md_element('先发送 **新话题 <主题>** 创建一个。'),
                ], color='red')
                return
            reply_card('🔍 正在调研...', [
                _md_element(f'主题：**{session["topic"]}**'),
            ], color='blue')
            result = _call_chat_api('POST', f'/api/chat/session/{session["session_id"]}/search', user_id)
            count = len(result.get('search_results') or [])
            send_card('✅ 调研完成', [
                _md_element(f'找到 **{count}** 条相关资料'),
                _hr_element(),
                _md_element('发送 **大纲** 继续'),
            ], color='green')
            _user_sessions[user_id]['status'] = 'researched'
            return

        # ---- 大纲 ----
        if intent['action'] == 'outline':
            if not session:
                reply_card('❌ 无活跃会话', [
                    _md_element('先发送 **新话题 <主题>** 创建一个。'),
                ], color='red')
                return
            reply_card('📋 正在生成大纲...', [
                _md_element(f'主题：**{session["topic"]}**'),
            ], color='blue')
            result = _call_chat_api('POST', f'/api/chat/session/{session["session_id"]}/outline', user_id)
            outline = result.get('outline')
            if outline:
                sections = '\n'.join(
                    f'{i+1}. **{s["title"]}**' for i, s in enumerate(outline.get('sections', []))
                )
                send_card(f'📋 大纲：{outline.get("title", session["topic"])}', [
                    _md_element(sections),
                    _hr_element(),
                    _md_element('发送 **写作** 开始写作'),
                ], color='green')
                _user_sessions[user_id]['status'] = 'outlined'
            else:
                send_card('⚠️ 大纲生成失败', [
                    _md_element('请重试'),
                ], color='orange')
            return

        # ---- 生成 ----
        if intent['action'] == 'generate':
            if not session:
                reply_card('❌ 无活跃会话', [
                    _md_element('先发送 **新话题 <主题>** 创建一个。'),
                ], color='red')
                return
            result = _call_chat_api('POST', f'/api/chat/session/{session["session_id"]}/generate', user_id)
            task_id = result.get('task_id')
            _user_sessions[user_id]['status'] = 'generating'
            _user_sessions[user_id]['task_id'] = task_id

            reply_card('✍️ 开始生成', [
                _md_element(
                    f'**主题**：{session["topic"]}\n'
                    f'**任务 ID**：`{task_id}`'
                ),
                _hr_element(),
                _note_element('完成后会自动通知你'),
            ], color='blue',
               tpl='task_started', tpl_vars={'topic': session['topic'], 'task_id': task_id})

            _start_progress_watcher(task_id, chat_id, user_id, session['topic'])
            return

        # ---- 预览 ----
        if intent['action'] == 'preview':
            if not session:
                reply_card('❌ 无活跃会话', [
                    _md_element('没有可预览的内容。'),
                ], color='red')
                return
            result = _call_chat_api('GET', f'/api/chat/session/{session["session_id"]}/preview', user_id)
            preview = result.get('markdown') or result.get('content') or '(暂无内容)'
            if len(preview) > 3500:
                preview = preview[:3500] + '\n\n...(已截断)'
            reply_card(f'📖 预览：{session["topic"]}', [
                _md_element(preview),
                _hr_element(),
                _md_element('发送 **发布** 发布文章'),
            ], color='indigo')
            return

        # ---- 发布 ----
        if intent['action'] == 'publish':
            if not session:
                reply_card('❌ 无活跃会话', [
                    _md_element('没有可发布的内容。'),
                ], color='red')
                return
            _call_chat_api('POST', f'/api/chat/session/{session["session_id"]}/publish', user_id)
            reply_card('🎉 文章已发布', [
                _md_element(f'**主题**：{session["topic"]}'),
            ], color='green',
               tpl='completed', tpl_vars={'topic': session['topic'], 'word_count': '0', 'section_count': '0'})
            _user_sessions[user_id]['status'] = 'completed'
            return

        # ---- 自动（直接发主题） ----
        if intent['action'] == 'auto':
            if not session:
                topic = intent['text']
                created = _call_chat_api('POST', '/api/chat/session', user_id, {'topic': topic})
                _user_sessions[user_id] = {
                    'session_id': created['session_id'],
                    'topic': topic,
                    'status': 'created',
                }
                gen_result = _call_chat_api(
                    'POST', f'/api/chat/session/{created["session_id"]}/generate', user_id
                )
                task_id = gen_result.get('task_id')
                _user_sessions[user_id]['status'] = 'generating'
                _user_sessions[user_id]['task_id'] = task_id

                reply_card(f'🚀 开始写作：{topic}', [
                    _md_element(
                        f'已创建会话并启动一键生成\n'
                        f'**任务 ID**：`{task_id}`'
                    ),
                    _hr_element(),
                    _note_element('生成过程需要几分钟，完成后会自动通知你'),
                ], color='blue',
                   tpl='task_started', tpl_vars={'topic': topic, 'task_id': task_id})

                _start_progress_watcher(task_id, chat_id, user_id, topic)
            else:
                reply_card(f'📌 当前会话', [
                    _md_element(
                        f'**主题**：{session["topic"]}\n'
                        f'**状态**：{session["status"]}'
                    ),
                    _hr_element(),
                    _md_element('发送 **帮助** 查看可用指令'),
                ], color='blue')
            return

    except Exception as e:
        logger.exception('处理飞书消息失败: chat_id=%s', chat_id)
        reply_card('❌ 操作失败', [
            _md_element(f'**错误**：{str(e)[:300]}'),
            _hr_element(),
            _md_element('请重试或发送 **帮助** 查看指令'),
        ], color='red',
           tpl='failed', tpl_vars={'topic': session['topic'] if session else '', 'error': str(e)[:300]})


# ========== Webhook 路由 ==========

@feishu_bp.route('/webhook', methods=['POST'])
def feishu_webhook():
    """飞书事件订阅 Webhook 入口。"""
    data = request.get_json(silent=True) or {}

    # 1. URL 验证（飞书首次配置事件订阅时发送）
    if 'challenge' in data:
        return jsonify({'challenge': data['challenge']})

    # 2. 验证 token（可选但推荐）
    if FEISHU_VERIFICATION_TOKEN:
        token = data.get('token') or (data.get('header') or {}).get('token', '')
        if token != FEISHU_VERIFICATION_TOKEN:
            logger.warning('飞书 webhook token 验证失败')
            return jsonify({'error': 'invalid token'}), 403

    # 3. 解析事件
    # v2.0 事件格式
    header = data.get('header', {})
    event = data.get('event', {})

    event_type = header.get('event_type', '')

    if event_type == 'im.message.receive_v1':
        message = event.get('message', {})
        msg_type = message.get('message_type', '')
        chat_id = message.get('chat_id', '')
        message_id = message.get('message_id', '')

        # 提取发送者信息作为 user_id
        sender = event.get('sender', {}).get('sender_id', {})
        user_id = sender.get('open_id', '') or sender.get('user_id', '')

        # 只处理文本消息
        if msg_type != 'text':
            _reply_feishu_message(message_id, '目前只支持文本消息哦 📝')
            return jsonify({'code': 0})

        # 解析文本内容
        try:
            content = json.loads(message.get('content', '{}'))
            text = content.get('text', '').strip()
        except (json.JSONDecodeError, TypeError):
            text = ''

        if not text:
            return jsonify({'code': 0})

        # 去掉 @机器人 的部分
        text = re.sub(r'@_user_\d+\s*', '', text).strip()
        if not text:
            return jsonify({'code': 0})

        logger.info('飞书消息: chat_id=%s, user=%s, text=%s', chat_id, user_id, text[:100])

        # 异步处理（避免飞书 webhook 超时）
        threading.Thread(
            target=_handle_message,
            args=(chat_id, user_id, text, message_id),
            daemon=True,
        ).start()

        return jsonify({'code': 0})

    # 未知事件类型
    logger.debug('飞书未处理事件: %s', event_type)
    return jsonify({'code': 0})
