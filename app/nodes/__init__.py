import logging
import os
from typing import Dict, Any, Optional

import httpx

from app.nodes.base import BaseNodeExecutor, render_template
from app.nodes.message import MessageNodeExecutor
from app.nodes.buttons import ButtonsNodeExecutor
from app.nodes.input import InputNodeExecutor
from app.nodes.condition import ConditionNodeExecutor
from app.nodes.end import EndNodeExecutor
from app.nodes.switch import SwitchNodeExecutor
from app.storage.credentials import get_credential

logger = logging.getLogger("flow_engine.nodes.ai")

logger = logging.getLogger("flow_engine.nodes.ai")


class StartNodeExecutor(BaseNodeExecutor):

    def execute(
        self,
        node_config: Dict[str, Any],
        state: Dict[str, Any],
    ) -> Dict[str, Any]:

        config = node_config.get("config") or node_config.get("data") or {}
        explicit_next = (
            node_config.get("next_node")
            or config.get("next_node")
        )
        if explicit_next:
            state["current_node"] = explicit_next

        state["status"] = "running"
        return state


class AIResponseNodeExecutor(BaseNodeExecutor):
    """Generic LLM executor with built-in provider adapters.

    Supported out of the box:
      * OpenAI
      * Groq (OpenAI-compatible)
      * Anthropic
      * Google Gemini
      * Any OpenAI-compatible endpoint via ``provider=custom`` + ``api_url``

<<<<<<< HEAD
    Credentials are referenced by credential_id. Legacy per-node api_key values are
    still accepted for migration, but workflow storage strips them after migration.
=======
    Credentials can be supplied per node (api_key) or through environment
    variables. Node settings always win over environment settings.
>>>>>>> 00c7d9e (llm connection)
    """

    PROVIDER_DEFAULTS = {
        "openai": {
            "api_url": "https://api.openai.com/v1/chat/completions",
            "env_keys": ("OPENAI_API_KEY", "AI_API_KEY"),
            "model": "gpt-4o-mini",
            "protocol": "openai",
        },
        "groq": {
            "api_url": "https://api.groq.com/openai/v1/chat/completions",
            "env_keys": ("GROQ_API_KEY", "AI_API_KEY"),
            "model": "openai/gpt-oss-120b",
            "protocol": "openai",
        },
        "anthropic": {
            "api_url": "https://api.anthropic.com/v1/messages",
            "env_keys": ("ANTHROPIC_API_KEY", "AI_API_KEY"),
            "model": "claude-sonnet-4-6",
            "protocol": "anthropic",
        },
        "gemini": {
            "api_url": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            "env_keys": ("GEMINI_API_KEY", "GOOGLE_API_KEY", "AI_API_KEY"),
            "model": "gemini-2.0-flash",
            "protocol": "gemini",
        },
        "google": {
            "api_url": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            "env_keys": ("GEMINI_API_KEY", "GOOGLE_API_KEY", "AI_API_KEY"),
            "model": "gemini-2.0-flash",
            "protocol": "gemini",
        },
        "custom": {
            "api_url": "",
            "env_keys": ("AI_API_KEY",),
            "model": "",
            "protocol": "openai",
        },
    }

    PROVIDER_ALIASES = {
        "google_gemini": "gemini",
        "google": "gemini",
        "claude": "anthropic",
        "grok": "custom",
        "openai_compatible": "custom",
        "openai-compatible": "custom",
    }

    def _provider_info(self, provider: str) -> Dict[str, Any]:
        provider = self.PROVIDER_ALIASES.get(provider, provider)
        if provider in self.PROVIDER_DEFAULTS:
            return self.PROVIDER_DEFAULTS[provider]
        # Unknown providers are treated as OpenAI-compatible so the engine
        # remains generic rather than requiring a code change for every vendor.
        return self.PROVIDER_DEFAULTS["custom"]

    def _env_api_key(self, provider: str) -> Optional[str]:
        info = self._provider_info(provider)
        for name in info["env_keys"]:
            value = os.getenv(name)
            if value:
                return value
        return None

    def _call_openai_style(self, api_url: str, api_key: Optional[str], model: str, prompt: str) -> str:
        """Call an OpenAI-compatible chat-completions endpoint."""
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {"model": model, "messages": [{"role": "user", "content": prompt}]}
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            resp = client.post(api_url, json=payload, headers=headers)
            if resp.status_code >= 400:
                # Keep the provider response body: it is dramatically more useful
                # than a bare `404 Not Found` when debugging a provider config.
                try:
                    detail = resp.json()
                except Exception:
                    detail = resp.text[:1000]
                raise RuntimeError(
                    f"HTTP {resp.status_code} from AI provider at {api_url}: {detail}"
                )
            data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") for part in content
                if isinstance(part, dict)
            )
        return str(content).strip()

    def _groq_list_models(self, api_key: Optional[str]) -> list[str]:
        """Return active Groq model IDs. Used to recover from retired/invalid model IDs."""
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        models_url = "https://api.groq.com/openai/v1/models"
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            resp = client.get(models_url, headers=headers)
            if resp.status_code >= 400:
                return []
            data = resp.json()
        return [
            str(item.get("id"))
            for item in data.get("data", [])
            if isinstance(item, dict) and item.get("id")
        ]

    def _call_groq(self, api_url: str, api_key: Optional[str], model: str, prompt: str) -> str:
        """Call Groq and automatically recover from retired model IDs.

        Groq is OpenAI-compatible, but model IDs are provider-owned and can be
        retired. If Groq returns ``model_not_found``/``model_not_found``-style
        404, discover the active model list and retry with a safe current model.
        This keeps old saved flows working without requiring users to edit every
        AI node after a provider model retirement.
        """
        try:
            return self._call_openai_style(api_url, api_key, model, prompt)
        except RuntimeError as exc:
            message = str(exc)
            if "HTTP 404" not in message or "/chat/completions" not in api_url:
                raise

            # A 404 can be either an endpoint/proxy problem or a retired model.
            # If the provider body says model_not_found, recover automatically.
            is_model_error = (
                "model_not_found" in message
                or "does not exist" in message
                or "do not have access" in message
            )
            if is_model_error:
                active_models = self._groq_list_models(api_key)
                preferred = [
                    "openai/gpt-oss-120b",
                    "qwen/qwen3.6-27b",
                    "openai/gpt-oss-20b",
                ]
                replacement = next(
                    (candidate for candidate in preferred if candidate in active_models),
                    None,
                )
                if replacement and replacement != model:
                    logger.warning(
                        "Groq model '%s' is unavailable; retrying with active model '%s'",
                        model, replacement,
                    )
                    return self._call_openai_style(api_url, api_key, replacement, prompt)

            # Keep Responses API as an endpoint compatibility fallback.
            responses_url = api_url.replace("/chat/completions", "/responses")
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            payload = {"model": model, "input": prompt}

            with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                resp = client.post(responses_url, json=payload, headers=headers)
                if resp.status_code >= 400:
                    try:
                        detail = resp.json()
                    except Exception:
                        detail = resp.text[:1000]
                    raise RuntimeError(
                        f"Groq request failed after fallback (chat HTTP 404; "
                        f"responses HTTP {resp.status_code}): {detail}"
                    ) from exc
                data = resp.json()

            if data.get("output_text"):
                return str(data["output_text"]).strip()
            parts = []
            for item in data.get("output", []):
                for content in item.get("content", []) if isinstance(item, dict) else []:
                    if isinstance(content, dict) and content.get("text"):
                        parts.append(str(content["text"]))
            return "".join(parts).strip()

    def _call_anthropic(self, api_url: str, api_key: Optional[str], model: str, prompt: str) -> str:
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        if api_key:
            headers["x-api-key"] = api_key
        payload = {
            "model": model,
            "max_tokens": 1000,
            "messages": [{"role": "user", "content": prompt}],
        }
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(api_url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return "".join(
            block.get("text", "")
            for block in data.get("content", [])
            if isinstance(block, dict) and block.get("type") == "text"
        ).strip()

    def _call_gemini(self, api_url: str, api_key: Optional[str], model: str, prompt: str) -> str:
        if not api_key:
            raise ValueError("Gemini requires GEMINI_API_KEY/GOOGLE_API_KEY or an API key in the AI node")
        url = api_url.format(model=model) if "{model}" in api_url else api_url
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}key={api_key}"
        payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, json=payload, headers={"Content-Type": "application/json"})
            resp.raise_for_status()
            data = resp.json()
        parts = []
        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                if isinstance(part, dict) and part.get("text"):
                    parts.append(str(part["text"]))
        return "".join(parts).strip()

    def execute(self, node_config: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        config = node_config.get("config") or node_config.get("data") or {}

        prompt = (
            config.get("prompt") or config.get("text") or config.get("message")
            or node_config.get("prompt") or node_config.get("message") or ""
        )
        rendered_prompt = render_template(str(prompt), state.get("variables", {}))

        provider_raw = str(
            config.get("provider") or node_config.get("provider")
            or os.getenv("AI_PROVIDER") or "openai"
        ).lower().strip()
        provider = self.PROVIDER_ALIASES.get(provider_raw, provider_raw)
        info = self._provider_info(provider)

        model_env = {
            "openai": "OPENAI_MODEL",
            "groq": "GROQ_MODEL",
            "anthropic": "ANTHROPIC_MODEL",
            "gemini": "GEMINI_MODEL",
        }.get(provider)
        model = (
            config.get("model") or node_config.get("model")
            or (os.getenv(model_env) if model_env else None)
            or os.getenv("AI_MODEL") or info["model"]
        )
        if not model:
            raise ValueError(f"No model configured for provider '{provider_raw}'")

        node_api_url = (
            config.get("api_url") or config.get("apiUrl") or config.get("endpoint")
            or node_config.get("api_url")
        )
        # AI_API_URL is a legacy/custom global endpoint. Never let it override
        # a built-in provider's native endpoint.
        api_url = node_api_url or (
            os.getenv("AI_API_URL") if provider == "custom" else info["api_url"]
        )
        if not api_url:
            raise ValueError(
                f"Provider '{provider_raw}' needs an API URL. Set it in the AI node or use a supported provider."
            )

<<<<<<< HEAD
        credential_id = (
            config.get("credential_id")
            or node_config.get("credential_id")
        )
        credential = get_credential(str(credential_id)) if credential_id else None
        api_key = (
            (credential or {}).get("api_key")
            or config.get("api_key") or config.get("apiKey")
            or node_config.get("api_key") or self._env_api_key(provider)
        )
        if credential and credential.get("api_url") and provider == "custom" and not api_url:
            api_url = credential["api_url"]
=======
        api_key = (
            config.get("api_key") or config.get("apiKey")
            or node_config.get("api_key") or self._env_api_key(provider)
        )
>>>>>>> 00c7d9e (llm connection)

        try:
            protocol = info["protocol"]
            if provider == "gemini":
                ai_text = self._call_gemini(api_url, api_key, str(model), rendered_prompt)
            elif protocol == "anthropic":
                ai_text = self._call_anthropic(api_url, api_key, str(model), rendered_prompt)
            elif provider == "groq":
                ai_text = self._call_groq(api_url, api_key, str(model), rendered_prompt)
            else:
                ai_text = self._call_openai_style(api_url, api_key, str(model), rendered_prompt)
            if not ai_text:
                ai_text = "[AI response was empty.]"
        except Exception as exc:
            logger.exception("AI node '%s' (%s) call failed: %s", node_config.get("id"), provider_raw, exc)
<<<<<<< HEAD
            error_next = node_config.get("error_next_node") or config.get("error_next_node")
            state.setdefault("variables", {})["error"] = {
                "node_id": node_config.get("id"),
                "message": str(exc),
                "type": exc.__class__.__name__,
            }
            state["variables"]["error_message"] = str(exc)
            if error_next:
                state["current_node"] = error_next
                state["status"] = "running"
                state["response"] = f"[AI error: {exc}]"
                return state
=======
>>>>>>> 00c7d9e (llm connection)
            ai_text = f"[AI request failed: {exc}]"

        if state.get("response"):
            state["response"] += "\n\n" + ai_text
        else:
            state["response"] = ai_text

        state.setdefault("conversation_history", []).append({
            "role": "assistant", "type": "ai_response", "content": ai_text,
        })

        explicit_next = node_config.get("next_node") or config.get("next_node")
        if explicit_next:
            state["current_node"] = explicit_next
        state["status"] = "running"
        return state


_start_exec = StartNodeExecutor()
_msg_exec = MessageNodeExecutor()
_btn_exec = ButtonsNodeExecutor()
_inp_exec = InputNodeExecutor()
_cond_exec = ConditionNodeExecutor()
_end_exec = EndNodeExecutor()
_switch_exec = SwitchNodeExecutor()
_ai_exec = AIResponseNodeExecutor()

_registry: Dict[str, BaseNodeExecutor] = {
    "start": _start_exec,
    "message": _msg_exec,
    "buttons": _btn_exec,
    "button": _btn_exec,
    "choice": _btn_exec,
    "input": _inp_exec,
    "input_message": _inp_exec,
    "condition": _cond_exec,
    "end": _end_exec,
    "switch": _switch_exec,
    "ai_response": _ai_exec,
    "ai": _ai_exec,
    "llm": _ai_exec,
}


def get_node_executor(
    node_type: str,
) -> Optional[BaseNodeExecutor]:

    if not node_type:
        return None

    return _registry.get(
        node_type.lower().strip()
    )