"""Bounded diagnostics; credentials are used only in memory for redaction."""
import json
import os
from pathlib import PureWindowsPath
import re
import subprocess
import urllib.error
from urllib.parse import quote, quote_plus

LIMIT = 600
DIAGNOSTIC_FIELDS = ('error_detail', 'http_status', 'provider_message')


def _secret_forms(secrets):
    values = [*secrets, os.environ.get('GRSAI_API_KEY', '')]
    forms = set()
    for value in values:
        if isinstance(value, str) and value:
            forms.update((value, quote(value, safe=''), quote_plus(value, safe=''),
                          json.dumps(value, ensure_ascii=False)[1:-1]))
    return sorted(forms, key=len, reverse=True)


def redact(text, secrets=()):
    text = str(text)
    for value in _secret_forms(secrets):
        text = text.replace(value, '***')
    text = re.sub(r'(?i)\bBearer\s+[^\s"\'<>,;]+', 'Bearer ***', text)
    text = re.sub(r'\bsk-[A-Za-z0-9_-]+', '***', text)
    text = re.sub(
        r'''(?ix)(\b(?:authorization|api[-_]?key|access[-_]?token|refresh[-_]?token|token|password|secret)\b["']?\s*[:=]\s*)'''
        r'''(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s,;&}\]]+)''',
        r'\1***', text)
    return text if len(text) <= LIMIT else text[:LIMIT - 3] + '...'


def describe(exc, secrets=()):
    if isinstance(exc, json.JSONDecodeError):
        message = f'JSON 格式错误：第 {exc.lineno} 行第 {exc.colno} 列（{exc.msg}）'
    elif isinstance(exc, KeyError):
        message = '缺少字段：' + str(exc)
    elif isinstance(exc, PermissionError):
        message = '没有权限或文件被占用：' + str(exc.filename or exc)
    elif isinstance(exc, FileNotFoundError):
        message = '找不到文件：' + str(exc.filename or exc)
    elif isinstance(exc, subprocess.TimeoutExpired):
        # String commands cannot be safely split into a program and secret-bearing arguments.
        program = PureWindowsPath(str(exc.cmd[0])).name if isinstance(exc.cmd, (list, tuple)) and exc.cmd else '外部程序'
        message = f'外部程序超时：{program}，超过 {exc.timeout} 秒'
    elif isinstance(exc, urllib.error.HTTPError):
        message = f'HTTP 请求失败（状态码 {exc.code}）；按原任务状态处理'
    elif isinstance(exc, TimeoutError):
        message = '网络或外部操作超时；按原任务状态处理'
    elif isinstance(exc, (urllib.error.URLError, ConnectionError)):
        message = '网络连接失败；未输出原始请求信息，按原任务状态处理'
    else:
        message = type(exc).__name__ + ': ' + str(exc)
    return redact(message, secrets)


def details(exc, secrets=()):
    result = {'error_detail': describe(exc, secrets)}
    if not isinstance(exc, urllib.error.HTTPError):
        return result
    result['http_status'] = exc.code
    try:
        raw = exc.read(2048).decode('utf-8')
        data = json.loads(raw)
    except (OSError, ValueError, TypeError, AttributeError):
        return result
    # Check the complete inspected object, including fields that will not be displayed.
    decoded = json.dumps(data, ensure_ascii=False)
    if any(value in raw or value in decoded for value in _secret_forms(secrets)):
        return result
    if isinstance(data, dict):
        message = data.get('message') or data.get('msg') or data.get('error')
        if isinstance(message, dict):
            message = message.get('message') or message.get('msg')
        if isinstance(message, str) and message.strip():
            result['provider_message'] = redact(message, secrets)
    return result
