-- 添加Coqui TTS供应器
delete from `ai_model_provider` where id = 'SYSTEM_TTS_CoquiTTS';
INSERT INTO `ai_model_provider` (`id`, `model_type`, `provider_code`, `name`, `fields`, `sort`, `creator`, `create_date`, `updater`, `update_date`) VALUES
('SYSTEM_TTS_CoquiTTS', 'TTS', 'coqui', 'Coqui TTS', '[{"key":"device","label":"设备","type":"string","editable":true},{"key":"model_name","label":"模型名称","type":"string","editable":true},{"key":"speaker_id","label":"说话人ID(多说话人模型)","type":"string","editable":true},{"key":"language","label":"语言代码(多语言模型)","type":"string","editable":true},{"key":"sample_rate","label":"采样率","type":"number","editable":true},{"key":"output_dir","label":"输出目录","type":"string","editable":true}]', 22, 1, NOW(), 1, NOW());

-- 添加Coqui TTS模型配置
delete from `ai_model_config` where id = 'TTS_CoquiTTS';
INSERT INTO `ai_model_config` VALUES ('TTS_CoquiTTS', 'TTS', 'CoquiTTS', 'Coqui TTS', 0, 1, '{\"type\": \"coqui\", \"device\": \"cuda\", \"model_name\": \"tts_models/en/ljspeech/tacotron2-DDC\", \"sample_rate\": 22050, \"output_dir\": \"tmp/\"}', NULL, NULL, 25, NULL, NULL, NULL, NULL);

-- 更新Coqui TTS配置说明
UPDATE `ai_model_config` SET 
`doc_link` = 'https://github.com/coqui-ai/TTS',
`remark` = 'Coqui TTS说明：
1. Coqui TTS是一个开源的文本转语音库，提供多种预训练模型
2. 安装：pip install TTS
3. 查看可用模型：tts --list_models
4. 支持单说话人和多说话人模型
5. 支持多语言模型（英语、中文、德语、法语、西班牙语、日语等）
6. 设备：cuda（GPU）或 cpu（CPU）
7. 常用模型示例：
   - tts_models/en/ljspeech/tacotron2-DDC (英语，单说话人)
   - tts_models/en/vctk/vits (英语，多说话人)
   - tts_models/multilingual/multi-dataset/your_tts (多语言，多说话人)
   - tts_models/zh-CN/baker/tacotron2-DDC-GST (中文)
   - tts_models/de/thorsten/tacotron2-DDC (德语)
   - tts_models/fr/mai/tacotron2-DDC (法语)
   - tts_models/es/mai/tacotron2-DDC (西班牙语)
   - tts_models/ja/kokoro/tacotron2-DDC (日语)
8. 对于多说话人模型，可以设置speaker_id参数（如"p225", "p226"）
9. 对于多语言模型，可以设置language参数（如"en", "zh", "de", "fr", "es", "ja"）
10. 采样率默认为22050，但取决于具体模型
' WHERE `id` = 'TTS_CoquiTTS';

