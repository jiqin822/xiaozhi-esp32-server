-- 添加Chatterbox TTS供应器
delete from `ai_model_provider` where id = 'SYSTEM_TTS_ChatterboxTTS';
INSERT INTO `ai_model_provider` (`id`, `model_type`, `provider_code`, `name`, `fields`, `sort`, `creator`, `create_date`, `updater`, `update_date`) VALUES
('SYSTEM_TTS_ChatterboxTTS', 'TTS', 'chatterbox', 'Chatterbox TTS', '[{"key":"device","label":"设备","type":"string","editable":true},{"key":"model_type","label":"模型类型","type":"string","editable":true},{"key":"language_id","label":"语言ID","type":"string","editable":true},{"key":"audio_prompt_path","label":"参考音频路径(零样本语音克隆)","type":"string","editable":true},{"key":"exaggeration","label":"情感夸张度(0.0-1.0)","type":"number","editable":true},{"key":"cfg_weight","label":"CFG权重(0.0-1.0)","type":"number","editable":true},{"key":"sample_rate","label":"采样率","type":"number","editable":true},{"key":"output_dir","label":"输出目录","type":"string","editable":true}]', 21, 1, NOW(), 1, NOW());

-- 添加Chatterbox TTS模型配置
delete from `ai_model_config` where id = 'TTS_ChatterboxTTS';
INSERT INTO `ai_model_config` VALUES ('TTS_ChatterboxTTS', 'TTS', 'ChatterboxTTS', 'Chatterbox TTS', 0, 1, '{\"type\": \"chatterbox\", \"device\": \"cuda\", \"model_type\": \"multilingual\", \"language_id\": \"en\", \"exaggeration\": 0.5, \"cfg_weight\": 0.5, \"sample_rate\": 24000, \"output_dir\": \"tmp/\"}', NULL, NULL, 24, NULL, NULL, NULL, NULL);

-- 更新Chatterbox TTS配置说明
UPDATE `ai_model_config` SET 
`doc_link` = 'https://github.com/resemble-ai/chatterbox',
`remark` = 'Chatterbox TTS说明：
1. Resemble AI开源的SoTA TTS模型，支持23种语言
2. 支持零样本语音克隆（zero-shot voice cloning）
3. 支持情感/夸张度控制（emotion/exaggeration control）
4. 安装：pip install chatterbox-tts
5. 模型类型：english（仅英文）或 multilingual（23种语言）
6. 支持的语言：ar, da, de, el, en, es, fi, fr, he, hi, it, ja, ko, ms, nl, no, pl, pt, ru, sv, sw, tr, zh
7. 设备：cuda（GPU）或 cpu（CPU）
8. 情感夸张度：0.0-1.0，默认0.5
9. CFG权重：0.0-1.0，默认0.5，用于控制生成质量
10. 参考音频路径：可选，用于零样本语音克隆
' WHERE `id` = 'TTS_ChatterboxTTS';

