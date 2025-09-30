import json
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig

@register("astrbot_plugin_user_inject", "RC-CHN", "根据用户ID注入不同system_prompt", "1.0.0")
class UserInjecter(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.enable_private_chat = self.config.get("enable_private_chat")
        self.enabled_groups = self.config.get("enabled_groups")
        self.default_prompt = self.config.get("default_prompt")
        self.inject_mode = self.config.get("inject_mode", "system")
        self.user_prompts = {}
        user_prompts_str = self.config.get("user_prompts")
        logger.debug(f"获取到 user_prompts 配置字符串: {user_prompts_str}")

        if user_prompts_str and isinstance(user_prompts_str, str):
            try:
                user_prompts_list = json.loads(user_prompts_str)
                if isinstance(user_prompts_list, list):
                    self.user_prompts = {
                        item['user_id']: item['prompt']
                        for item in user_prompts_list
                        if isinstance(item, dict) and 'user_id' in item and 'prompt' in item
                    }
                    logger.info(f"成功解析并加载 {len(self.user_prompts)} 条用户注入规则。")
                else:
                    logger.error("user_prompts 配置解析后不是一个列表，已忽略。")
            except json.JSONDecodeError:
                logger.error("解析 user_prompts 配置字符串失败，请检查 JSON 格式。")

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
        logger.info("用户注入插件已加载。")
        logger.debug(f"私聊中启用: {self.enable_private_chat}")
        if not self.enabled_groups:
            logger.debug("配置中未指定启用的群组，插件将对所有群组生效。")
        else:
            logger.debug(f"启用的群组: {self.enabled_groups}")
        logger.debug(f"处理后的用户 Prompts 字典: {self.user_prompts}")
        if self.default_prompt:
            logger.info(f"已加载默认 Prompt: {self.default_prompt}")
    
        if self.inject_mode not in ["system", "user"]:
            logger.warning(f"无效的 inject_mode: '{self.inject_mode}'，将回退到 'system' 模式。")
            self.inject_mode = "system"
        logger.info(f"全局注入模式: {self.inject_mode}")
    
    def _log_request_details(self, event: AstrMessageEvent):
        group_id = event.get_group_id()
        sender_id = event.get_sender_id()
        session_id = event.get_session_id()
        unified_msg_origin = event.unified_msg_origin

        logger.debug("--- User Inject 插件捕获到 LLM 请求 ---")
        logger.debug(f"  - 用户 ID (Sender ID): {sender_id}")
        logger.debug(f"  - 群组 ID (Group ID): {group_id if group_id else 'N/A (私聊)'}")
        logger.debug(f"  - 会话 ID (Session ID): {session_id}")
        logger.debug(f"  - 统一会话 ID (Unified Origin): {unified_msg_origin}")
        logger.debug("-----------------------------------------")

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, req: ProviderRequest):
        """
        在 LLM 请求时触发，可以修改请求内容
        """
        self._log_request_details(event)

        group_id = event.get_group_id()
        sender_id = event.get_sender_id()

        # 根据配置决定如何处理
        if event.is_private_chat():
            if not self.enable_private_chat:
                return
        # 如果是群聊，检查是否在启用的群组中
        elif self.enabled_groups and group_id not in self.enabled_groups:
            return

        prompt_to_inject = None
        # 检查用户是否在配置的列表中
        if sender_id in self.user_prompts:
            prompt_to_inject = self.user_prompts[sender_id]
            logger.info(f"为特定用户 {sender_id} 找到注入规则。")
        # 如果特定用户未匹配到，且存在默认 prompt，则使用默认 prompt
        elif self.default_prompt:
            prompt_to_inject = self.default_prompt
            logger.info(f"为用户 {sender_id} 应用默认注入规则。")

        if prompt_to_inject:
            if self.inject_mode == "system":
                req.system_prompt += f"\n{prompt_to_inject}"
                logger.info(f"向 System Prompt 注入内容: {prompt_to_inject}")
            elif self.inject_mode == "user":
                # 在用户真实输入前插入一条 user role 的消息
                req.contexts.append({"role": "user", "content": prompt_to_inject})
                logger.info(f"向 User Context 注入内容: {prompt_to_inject}")

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
