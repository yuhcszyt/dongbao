"""Live test driver: python e2e.py prepare|query|repeat|cleanup|purge. No credentials."""
import json
import sys
from urllib.request import Request, urlopen

BASE = 'http://100.91.158.117:8888'
GLOBAL = 'global'
A = 'gm-e2e-project-a'
B = 'gm-e2e-project-b'
DOC = 'gm-e2e-docker-dns'
TEXT = '''测试项目 A 完成了一次 Docker DNS 排错，已验证修复：容器内 curl 报 Could not resolve host，宿主机解析正常。检查容器 /etc/resolv.conf 和 Docker 网络配置，发现容器 DNS 指向不可达的解析器。修正 Docker daemon 的 DNS 配置为该网络中可达的 DNS，重建受影响容器，然后分别验证容器域名解析和 HTTPS 请求恢复。经验适用于 Docker 容器内 DNS 解析失败而宿主正常的情形；修改前需备份 daemon.json 并确认变更影响，避免把所有网络错误都当成 DNS 故障。'''


def http(method, path, data=None, headers=None):
    req = Request(BASE + path, data=None if data is None else json.dumps(data).encode(),
                  method=method, headers={'Content-Type': 'application/json', **(headers or {})})
    with urlopen(req, timeout=300) as r:
        raw = r.read().decode()
        events = [line[6:] for line in raw.splitlines() if line.startswith('data: ')]
        if events:
            raw = events[-1]
        if not raw.strip():
            raise RuntimeError('empty HTTP response')
        return json.loads(raw), dict(r.headers)


SESSION = None
SEQ = 0


def rpc(method, params):
    global SESSION, SEQ
    headers = {'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2024-11-05'}
    if SESSION:
        headers['Mcp-Session-Id'] = SESSION
    SEQ += 1
    out, hs = http('POST', '/mcp/', {'jsonrpc': '2.0', 'id': SEQ, 'method': method, 'params': params}, headers)
    SESSION = hs.get('mcp-session-id', hs.get('Mcp-Session-Id', SESSION))
    if 'error' in out:
        raise RuntimeError(out['error'])
    return out['result']


def call(name, arguments):
    out = rpc('tools/call', {'name': name, 'arguments': arguments})
    if out.get('isError'):
        raise RuntimeError(out)
    value = out.get('structuredContent') or json.loads(out['content'][0]['text'])
    if isinstance(value, dict) and set(value) == {'result'}:
        value = value['result']
    return json.loads(value) if isinstance(value, str) else value


def main():
    rpc('initialize', {'protocolVersion': '2024-11-05', 'capabilities': {}, 'clientInfo': {'name': 'global-memory-e2e', 'version': '1'}})
    tools = rpc('tools/list', {})['tools']
    assert len(tools) == 39, len(tools)
    print('tool_count=39', flush=True)
    mode = sys.argv[1]
    if mode == 'prepare':
        call('create_bank', {'bank_id': B})
        print(call('retain', {'bank_id': A, 'document_id': DOC, 'content': TEXT}), flush=True)
    elif mode == 'query':
        # Cross-project read is a client action: recall the shared bank explicitly.
        result = call('recall', {'bank_id': GLOBAL, 'query': 'Docker container DNS could not resolve host，宿主机正常，怎么排查修复？', 'max_tokens': 2000})
        assert result.get('results'), list(result)
        blob = json.dumps(result, ensure_ascii=False)
        assert 'DNS' in blob or 'Docker' in blob, blob[:600]
        print(json.dumps(result, ensure_ascii=False)[:2500], flush=True)
    elif mode == 'repeat':
        print(call('retain', {'bank_id': A, 'document_id': DOC, 'content': TEXT}), flush=True)
    elif mode == 'cleanup':
        for bank in [A, B]:
            print(call('delete_bank', {'bank_id': bank}), flush=True)
    elif mode == 'purge':
        # DANGER: wipes the shared bank. Only right after an e2e run.
        print(call('clear_memories', {'bank_id': GLOBAL}), flush=True)


if __name__ == '__main__':
    main()
