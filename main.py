from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig

@register("astrbot_plugin_user_inject", "RC-CHN", "根据用户ID注入不同system_prompt", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.enabled_groups = self.config.get("enabled_groups", [])
        self.user_prompts = {item['user_id']: item['prompt'] for item in self.config.get("user_prompts", [])}

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
        logger.info("用户注入插件已加载。")
        if not self.enabled_groups:
            logger.info("配置中未指定启用的群组，插件将对所有群组和私聊生效。")
        else:
            logger.info(f"启用的群组: {self.enabled_groups}")
        logger.info(f"用户 Prompts: {self.user_prompts}")
    
    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, req: ProviderRequest):
        """
        在 LLM 请求时触发，可以修改请求内容
        """
        group_id = event.get_group_id()
        sender_id = event.get_sender_id()

        # 如果是私聊，则不进行群组检查
        if event.is_private_chat():
            pass
        # 检查是否在启用的群组中，如果 enabled_groups 为空，则对所有群组生效
        elif self.enabled_groups and group_id not in self.enabled_groups:
            return

        # 检查用户是否在配置的列表中
        if sender_id in self.user_prompts:
            prompt_to_inject = self.user_prompts[sender_id]
            req.system_prompt += f"\n{prompt_to_inject}"
            logger.info(f"为用户 {sender_id} 注入了 System Prompt: {prompt_to_inject}")

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
