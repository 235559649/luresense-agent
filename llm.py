"""最小 Chat Completions 适配；仅显式 rag 模式进行真实调用。"""
import json
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler


class ModelError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ChatClient:
    def __init__(self, model, api_key, base_url="https://api.openai.com/v1", timeout=30):
        parsed = urlsplit(base_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("接口须为无凭据、无查询参数的HTTPS基础地址")
        if not model or not model.strip() or not api_key or not api_key.strip():
            raise ValueError("真实模式需要模型名称和密钥；未配置请先用mock模式")
        if not 1 <= timeout <= 60:
            raise ValueError("超时必须为1～60秒")
        self.model, self.api_key = model, api_key
        self.endpoint = base_url.rstrip("/") + "/chat/completions"
        self.timeout = timeout

    def complete(self, messages):
        payload = {"model": self.model, "messages": messages,
                   "response_format": {"type": "json_object"}, "max_completion_tokens": 1200}
        request = Request(self.endpoint, data=json.dumps(payload).encode(),
                          headers={"Authorization": "Bearer " + self.api_key,
                                   "Content-Type": "application/json"}, method="POST")
        try:
            with build_opener(NoRedirect()).open(request, timeout=self.timeout) as response:
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise ModelError("模型响应超过大小限制")
            data = json.loads(raw)
            choice = data["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise ModelError("回答可能被截断或拒绝，本次不作为有效答案")
            content = choice["message"]["content"]
            if not isinstance(content, str):
                raise ModelError("模型未返回文本JSON")
            usage = data.get("usage") or {}
            safe_usage = {k: v for k, v in usage.items()
                          if k in ("prompt_tokens", "completion_tokens", "total_tokens")
                          and isinstance(v, int) and not isinstance(v, bool) and v >= 0}
            return content, safe_usage
        except HTTPError as exc:
            raise ModelError(f"接口HTTP {exc.code}；核对模型、余额和JSON参数兼容性。未重试。") from None
        except (URLError, TimeoutError, socket.timeout):
            raise ModelError("模型网络失败或超时，未自动重试。") from None
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise ModelError("接口响应不符合Chat Completions格式") from None
