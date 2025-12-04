-- Add Whisper ASR model provider and configuration
-- Whisper ASR uses local Hugging Face transformers model

-- Add Whisper ASR model provider
DELETE FROM `ai_model_provider` WHERE `id` = 'SYSTEM_ASR_Whisper';
INSERT INTO `ai_model_provider` (`id`, `model_type`, `provider_code`, `name`, `fields`, `sort`, `creator`, `create_date`, `updater`, `update_date`) VALUES
('SYSTEM_ASR_Whisper', 'ASR', 'whisper', 'Whisper语音识别', '[{"key": "model_id", "type": "string", "label": "模型ID", "default": "openai/whisper-large-v3"}, {"key": "output_dir", "type": "string", "label": "输出目录", "default": "tmp/"}, {"key": "device", "type": "string", "label": "设备", "default": null, "description": "null=自动检测, cpu=CPU, cuda:0=GPU, mps=Apple Silicon"}, {"key": "torch_dtype", "type": "string", "label": "数据类型", "default": null, "description": "null=自动检测, float16=GPU, float32=CPU/MPS"}, {"key": "language", "type": "string", "label": "语言", "default": null, "description": "null=自动检测, en=英语, zh=中文"}, {"key": "task", "type": "string", "label": "任务", "default": "transcribe", "description": "transcribe=转录, translate=翻译"}, {"key": "max_new_tokens", "type": "number", "label": "最大新令牌数", "default": null, "description": "null=自动调整"}]', 15, 1, NOW(), 1, NOW());

-- Add Whisper ASR model configuration
DELETE FROM `ai_model_config` WHERE `id` = 'ASR_Whisper';
INSERT INTO `ai_model_config` VALUES ('ASR_Whisper', 'ASR', 'Whisper', 'Whisper语音识别', 0, 1, '{\"type\": \"whisper\", \"model_id\": \"openai/whisper-large-v3\", \"output_dir\": \"tmp/\", \"device\": null, \"torch_dtype\": null, \"language\": null, \"task\": \"transcribe\", \"max_new_tokens\": null}', NULL, NULL, 15, NULL, NULL, NULL, NULL);

-- Update Whisper ASR configuration documentation
UPDATE `ai_model_config` SET 
`doc_link` = 'https://huggingface.co/openai/whisper-large-v3',
`remark` = 'Whisper ASR配置说明：
1. 使用OpenAI开源的Whisper模型，通过Hugging Face Transformers运行
2. 支持本地部署，无需API密钥
3. 支持多语言自动检测
4. 需要安装transformers库：pip install transformers accelerate datasets[audio]
5. 设备自动检测：优先使用CUDA（GPU），其次CPU，MPS（Apple Silicon）由于兼容性问题优先使用CPU
6. 模型ID：默认使用openai/whisper-large-v3，可在Hugging Face选择其他模型
7. 输出文件保存在tmp/目录
8. 详细配置参考：pingping-server/config.yaml中的ASR.Whisper配置项' WHERE `id` = 'ASR_Whisper';

