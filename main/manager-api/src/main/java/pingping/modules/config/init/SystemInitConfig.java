package pingping.modules.config.init;

import java.util.ArrayList;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.DependsOn;

import jakarta.annotation.PostConstruct;
import pingping.common.constant.Constant;
import pingping.common.redis.RedisKeys;
import pingping.common.redis.RedisUtils;
import pingping.common.utils.JsonUtils;
import pingping.modules.agent.entity.AgentEntity;
import pingping.modules.agent.entity.AgentPluginMapping;
import pingping.modules.agent.entity.AgentTemplateEntity;
import pingping.modules.agent.service.AgentPluginMappingService;
import pingping.modules.agent.service.AgentService;
import pingping.modules.agent.service.AgentTemplateService;
import pingping.modules.config.service.ConfigService;
import pingping.modules.model.dto.ModelProviderDTO;
import pingping.modules.model.entity.ModelConfigEntity;
import pingping.modules.model.service.ModelConfigService;
import pingping.modules.model.service.ModelProviderService;
import pingping.modules.sys.service.SysParamsService;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.dataformat.yaml.YAMLFactory;

@Configuration
@DependsOn("liquibase")
public class SystemInitConfig {

    @Autowired
    private SysParamsService sysParamsService;

    @Autowired
    private ConfigService configService;

    @Autowired
    private RedisUtils redisUtils;

    @Autowired
    private AgentService agentService;

    @Autowired
    private AgentTemplateService agentTemplateService;

    @Autowired
    private ModelProviderService modelProviderService;

    @Autowired
    private AgentPluginMappingService agentPluginMappingService;

    @Autowired
    private ModelConfigService modelConfigService;

    @PostConstruct
    public void init() {
        // 检查版本号
        String redisVersion = null;
        try {
            redisVersion = (String) redisUtils.get(RedisKeys.getVersionKey());
        } catch (Exception e) {
            // 如果读取版本号失败（可能是旧数据格式问题），清空Redis
            redisUtils.emptyAll();
        }
        
        if (!Constant.VERSION.equals(redisVersion)) {
            // 如果版本不一致，清空Redis
            redisUtils.emptyAll();
            // 存储新版本号
            redisUtils.set(RedisKeys.getVersionKey(), Constant.VERSION);
        }

        sysParamsService.initServerSecret();
        configService.getConfig(false);
        
        // Create default agent if it doesn't exist
        initDefaultAgent();
    }

    /**
     * Initialize default agent using default template (which should match config.yaml defaults)
     * Reads model IDs from the default template, but also syncs with config.yaml defaults
     */
    private void initDefaultAgent() {
        try {
            // Check if default agent already exists
            AgentEntity existingAgent = agentService.selectById(Constant.DEFAULT_AGENT_ID);
            if (existingAgent != null) {
                // Update existing default agent to match config.yaml defaults
                syncDefaultAgentWithConfig(existingAgent);
                return;
            }

            // Get default template (should match config.yaml defaults)
            AgentTemplateEntity template = agentTemplateService.getDefaultTemplate();
            if (template == null) {
                System.err.println("Warning: No default template found, cannot create default agent");
                return; // No template available, skip creation
            }

            // Create default agent entity
            AgentEntity defaultAgent = new AgentEntity();
            defaultAgent.setId(Constant.DEFAULT_AGENT_ID);
            defaultAgent.setAgentCode("DEFAULT_AGENT");
            defaultAgent.setAgentName("Default Agent");
            defaultAgent.setUserId(null); // System agent, not owned by any user
            defaultAgent.setCreator(null);
            defaultAgent.setCreatedAt(new Date());
            defaultAgent.setUpdater(null);
            defaultAgent.setUpdatedAt(new Date());
            defaultAgent.setSort(0);

            // Read model IDs from template, but override with config.yaml defaults if available
            // Read actual config from data/.config.yaml
            Map<String, String> selectedModules = readSelectedModulesFromConfig();
            
            // Map config.yaml selected_module values to database model IDs
            // config.yaml format: selected_module.ASR: Whisper -> database: ASR_Whisper
            defaultAgent.setAsrModelId(getModelIdFromConfigName("ASR", template.getAsrModelId(), 
                    selectedModules.getOrDefault("ASR", "FunASR")));
            defaultAgent.setVadModelId(getModelIdFromConfigName("VAD", template.getVadModelId(), 
                    selectedModules.getOrDefault("VAD", "SileroVAD")));
            defaultAgent.setLlmModelId(getModelIdFromConfigName("LLM", template.getLlmModelId(), 
                    selectedModules.getOrDefault("LLM", "ChatGLMLLM")));
            defaultAgent.setVllmModelId(getModelIdFromConfigName("VLLM", template.getVllmModelId(), 
                    selectedModules.getOrDefault("VLLM", "ChatGLMVLLM")));
            defaultAgent.setTtsModelId(getModelIdFromConfigName("TTS", template.getTtsModelId(), 
                    selectedModules.getOrDefault("TTS", "EdgeTTS")));
            // Memory model: "nomem" in config.yaml maps to "Memory_nomem" in database
            // "mem_local_short" maps to "Memory_mem_local_short", etc.
            String memConfigValue = selectedModules.getOrDefault("Memory", "nomem");
            String memModelId = getModelIdFromConfigName("Memory", template.getMemModelId(), memConfigValue);
            if (memModelId == null || memModelId.equals(template.getMemModelId())) {
                // Try the database format directly based on config value
                if ("nomem".equals(memConfigValue)) {
                    memModelId = Constant.MEMORY_NO_MEM;
                } else if ("mem_local_short".equals(memConfigValue)) {
                    memModelId = "Memory_mem_local_short";
                } else if ("mem0ai".equals(memConfigValue)) {
                    memModelId = "Memory_mem0ai";
                } else {
                    // Fallback to template value
                    memModelId = template.getMemModelId();
                }
            }
            System.out.println("  Memory from config: " + memConfigValue + " -> " + memModelId);
            defaultAgent.setMemModelId(memModelId);
            defaultAgent.setIntentModelId(getModelIdFromConfigName("Intent", template.getIntentModelId(), "function_call"));
            defaultAgent.setTtsVoiceId(template.getTtsVoiceId());
            
            // Read prompt from config file if available
            String configPrompt = readPromptFromConfig();
            if (configPrompt != null && !configPrompt.trim().isEmpty()) {
                defaultAgent.setSystemPrompt(configPrompt);
            } else {
                defaultAgent.setSystemPrompt(template.getSystemPrompt());
            }
            
            defaultAgent.setSummaryMemory(template.getSummaryMemory());
            defaultAgent.setLangCode(template.getLangCode());
            defaultAgent.setLanguage(template.getLanguage());

            // Set default chatHistoryConf value based on memory model
            // If memory is nomem, set to 0 (no recording)
            // Otherwise, set to 2 (record text and audio) for viewing purposes
            if (Constant.MEMORY_NO_MEM.equals(memModelId)) {
                defaultAgent.setChatHistoryConf(0);
            } else {
                defaultAgent.setChatHistoryConf(2); // Record text and audio for viewing
            }

            // Save default agent
            agentService.insert(defaultAgent);

            // Set default plugins
            List<AgentPluginMapping> toInsert = new ArrayList<>();
            String[] pluginIds = new String[] { "SYSTEM_PLUGIN_MUSIC", "SYSTEM_PLUGIN_WEATHER",
                    "SYSTEM_PLUGIN_NEWS_NEWSNOW" };
            for (String pluginId : pluginIds) {
                ModelProviderDTO provider = modelProviderService.getById(pluginId);
                if (provider == null) {
                    continue;
                }
                AgentPluginMapping mapping = new AgentPluginMapping();
                mapping.setPluginId(pluginId);

                Map<String, Object> paramInfo = new HashMap<>();
                @SuppressWarnings("unchecked")
                List<Map<String, Object>> fields = (List<Map<String, Object>>) JsonUtils.parseObject(provider.getFields(), List.class);
                if (fields != null) {
                    for (Map<String, Object> field : fields) {
                        paramInfo.put((String) field.get("key"), field.get("default"));
                    }
                }
                mapping.setParamInfo(JsonUtils.toJsonString(paramInfo));
                mapping.setAgentId(defaultAgent.getId());
                toInsert.add(mapping);
            }
            // Save default plugins
            if (!toInsert.isEmpty()) {
                agentPluginMappingService.saveBatch(toInsert);
            }
        } catch (Exception e) {
            // Log error but don't fail initialization
            System.err.println("Failed to initialize default agent: " + e.getMessage());
            e.printStackTrace();
        }
    }

    /**
     * Sync existing default agent with config.yaml defaults
     * This ensures the displayed information matches what's actually used
     */
    private void syncDefaultAgentWithConfig(AgentEntity agent) {
        try {
            boolean updated = false;
            
            // Read actual config from data/.config.yaml
            Map<String, String> selectedModules = readSelectedModulesFromConfig();
            System.out.println("Syncing default agent with config. Current agent values:");
            System.out.println("  ASR: " + agent.getAsrModelId());
            System.out.println("  VAD: " + agent.getVadModelId());
            System.out.println("  LLM: " + agent.getLlmModelId());
            System.out.println("  VLLM: " + agent.getVllmModelId());
            System.out.println("  TTS: " + agent.getTtsModelId());
            System.out.println("  Memory: " + agent.getMemModelId());
            System.out.println("  Intent: " + agent.getIntentModelId());
            
            // Map config.yaml selected_module values to database model IDs
            String asrConfigValue = selectedModules.getOrDefault("ASR", "Whisper");
            String asrModelId = getModelIdFromConfigName("ASR", agent.getAsrModelId(), asrConfigValue);
            System.out.println("  ASR from config: " + asrConfigValue + " -> " + asrModelId);
            if (!java.util.Objects.equals(agent.getAsrModelId(), asrModelId)) {
                agent.setAsrModelId(asrModelId);
                updated = true;
            }
            
            String vadConfigValue = selectedModules.getOrDefault("VAD", "SileroVAD");
            String vadModelId = getModelIdFromConfigName("VAD", agent.getVadModelId(), vadConfigValue);
            System.out.println("  VAD from config: " + vadConfigValue + " -> " + vadModelId);
            if (!java.util.Objects.equals(agent.getVadModelId(), vadModelId)) {
                agent.setVadModelId(vadModelId);
                updated = true;
            }
            
            String llmConfigValue = selectedModules.getOrDefault("LLM", "ChatGLMLLM");
            String llmModelId = getModelIdFromConfigName("LLM", agent.getLlmModelId(), llmConfigValue);
            System.out.println("  LLM from config: " + llmConfigValue + " -> " + llmModelId);
            if (!java.util.Objects.equals(agent.getLlmModelId(), llmModelId)) {
                agent.setLlmModelId(llmModelId);
                updated = true;
            }
            
            String vllmConfigValue = selectedModules.getOrDefault("VLLM", "ChatGLMVLLM");
            String vllmModelId = getModelIdFromConfigName("VLLM", agent.getVllmModelId(), vllmConfigValue);
            System.out.println("  VLLM from config: " + vllmConfigValue + " -> " + vllmModelId);
            if (!java.util.Objects.equals(agent.getVllmModelId(), vllmModelId)) {
                agent.setVllmModelId(vllmModelId);
                updated = true;
            }
            
            String ttsConfigValue = selectedModules.getOrDefault("TTS", "EdgeTTS");
            String ttsModelId = getModelIdFromConfigName("TTS", agent.getTtsModelId(), ttsConfigValue);
            System.out.println("  TTS from config: " + ttsConfigValue + " -> " + ttsModelId);
            if (!java.util.Objects.equals(agent.getTtsModelId(), ttsModelId)) {
                agent.setTtsModelId(ttsModelId);
                updated = true;
            }
            
            // Memory model: "nomem" in config.yaml maps to "Memory_nomem" in database
            // "mem_local_short" maps to "Memory_mem_local_short", etc.
            String memConfigValue = selectedModules.getOrDefault("Memory", "nomem");
            String memModelId = getModelIdFromConfigName("Memory", agent.getMemModelId(), memConfigValue);
            if (memModelId == null || memModelId.equals(agent.getMemModelId())) {
                // Try the database format directly based on config value
                if ("nomem".equals(memConfigValue)) {
                    memModelId = Constant.MEMORY_NO_MEM;
                } else if ("mem_local_short".equals(memConfigValue)) {
                    memModelId = "Memory_mem_local_short";
                } else if ("mem0ai".equals(memConfigValue)) {
                    memModelId = "Memory_mem0ai";
                } else {
                    // Keep current value if mapping fails
                    memModelId = agent.getMemModelId();
                }
            }
            System.out.println("  Memory from config: " + memConfigValue + " -> " + memModelId);
            if (!java.util.Objects.equals(agent.getMemModelId(), memModelId)) {
                agent.setMemModelId(memModelId);
                updated = true;
            }
            
            // Update chat_history_conf based on memory model
            if (Constant.MEMORY_NO_MEM.equals(memModelId) && agent.getChatHistoryConf() != null && agent.getChatHistoryConf() != 0) {
                agent.setChatHistoryConf(0);
                updated = true;
                System.out.println("  Updated chat_history_conf to 0 (no memory)");
            } else if (!Constant.MEMORY_NO_MEM.equals(memModelId) && (agent.getChatHistoryConf() == null || agent.getChatHistoryConf() == 0)) {
                agent.setChatHistoryConf(2);
                updated = true;
                System.out.println("  Updated chat_history_conf to 2 (with memory)");
            }
            
            String intentConfigValue = selectedModules.getOrDefault("Intent", "function_call");
            String intentModelId = getModelIdFromConfigName("Intent", agent.getIntentModelId(), intentConfigValue);
            System.out.println("  Intent from config: " + intentConfigValue + " -> " + intentModelId);
            if (!java.util.Objects.equals(agent.getIntentModelId(), intentModelId)) {
                agent.setIntentModelId(intentModelId);
                updated = true;
            }
            
            // Update system prompt from config file
            String configPrompt = readPromptFromConfig();
            if (configPrompt != null && !configPrompt.trim().isEmpty()) {
                String currentPrompt = agent.getSystemPrompt();
                if (currentPrompt == null || !currentPrompt.equals(configPrompt)) {
                    agent.setSystemPrompt(configPrompt);
                    updated = true;
                    System.out.println("  Updated system_prompt from config file");
                }
            }
            
            if (updated) {
                agent.setUpdatedAt(new Date());
                agentService.updateById(agent);
                System.out.println("Default agent updated to match config.yaml defaults");
            } else {
                System.out.println("Default agent already matches config.yaml defaults");
            }
        } catch (Exception e) {
            System.err.println("Failed to sync default agent with config: " + e.getMessage());
            e.printStackTrace();
        }
    }

    /**
     * Read selected_module values from data/.config.yaml file
     * Falls back to config.yaml if .config.yaml doesn't exist
     * 
     * @return Map of module type to module name (e.g., "ASR" -> "Whisper")
     */
    @SuppressWarnings("unchecked")
    private Map<String, String> readSelectedModulesFromConfig() {
        Map<String, String> result = new HashMap<>();
        try {
            String userDir = System.getProperty("user.dir");
            System.out.println("Current working directory: " + userDir);
            
            // Try to find the config file relative to the project root
            // The Java backend is typically in manager-api/, so we need to go up to main/ then to pingping-server/data/.config.yaml
            String[] possiblePaths = {
                "../pingping-server/data/.config.yaml",
                "../../pingping-server/data/.config.yaml",
                "pingping-server/data/.config.yaml",
                userDir + "/pingping-server/data/.config.yaml",
                userDir + "/../pingping-server/data/.config.yaml"
            };
            
            Path configPath = null;
            for (String pathStr : possiblePaths) {
                Path path = Paths.get(pathStr).toAbsolutePath().normalize();
                System.out.println("Trying config path: " + path);
                if (Files.exists(path) && Files.isRegularFile(path)) {
                    configPath = path;
                    System.out.println("Found config file at: " + configPath);
                    break;
                }
            }
            
            // If .config.yaml not found, try config.yaml
            if (configPath == null) {
                String[] configYamlPaths = {
                    "../pingping-server/config.yaml",
                    "../../pingping-server/config.yaml",
                    "pingping-server/config.yaml",
                    userDir + "/pingping-server/config.yaml",
                    userDir + "/../pingping-server/config.yaml"
                };
                for (String pathStr : configYamlPaths) {
                    Path path = Paths.get(pathStr).toAbsolutePath().normalize();
                    System.out.println("Trying config.yaml path: " + path);
                    if (Files.exists(path) && Files.isRegularFile(path)) {
                        configPath = path;
                        System.out.println("Found config.yaml file at: " + configPath);
                        break;
                    }
                }
            }
            
            if (configPath != null && Files.exists(configPath)) {
                ObjectMapper yamlMapper = new ObjectMapper(new YAMLFactory());
                Map<String, Object> config = yamlMapper.readValue(configPath.toFile(), Map.class);
                
                if (config != null && config.containsKey("selected_module")) {
                    Object selectedModuleObj = config.get("selected_module");
                    if (selectedModuleObj instanceof Map) {
                        Map<String, Object> selectedModule = (Map<String, Object>) selectedModuleObj;
                        System.out.println("Reading selected_module from config file:");
                        for (Map.Entry<String, Object> entry : selectedModule.entrySet()) {
                            if (entry.getValue() != null) {
                                String value = entry.getValue().toString();
                                result.put(entry.getKey(), value);
                                System.out.println("  " + entry.getKey() + " = " + value);
                            }
                        }
                    }
                } else {
                    System.out.println("Warning: selected_module not found in config file");
                }
            } else {
                System.out.println("Warning: Could not find config.yaml or .config.yaml file. Using defaults.");
            }
        } catch (Exception e) {
            System.err.println("Error reading config file: " + e.getMessage());
            e.printStackTrace();
        }
        return result;
    }

    /**
     * Read prompt from config.yaml file
     * 
     * @return The prompt string, or null if not found
     */
    @SuppressWarnings("unchecked")
    private String readPromptFromConfig() {
        try {
            String userDir = System.getProperty("user.dir");
            
            // Try to find the config file (same paths as readSelectedModulesFromConfig)
            String[] possiblePaths = {
                "../pingping-server/data/.config.yaml",
                "../../pingping-server/data/.config.yaml",
                "pingping-server/data/.config.yaml",
                userDir + "/pingping-server/data/.config.yaml",
                userDir + "/../pingping-server/data/.config.yaml"
            };
            
            Path configPath = null;
            for (String pathStr : possiblePaths) {
                Path path = Paths.get(pathStr).toAbsolutePath().normalize();
                if (Files.exists(path) && Files.isRegularFile(path)) {
                    configPath = path;
                    break;
                }
            }
            
            // If .config.yaml not found, try config.yaml
            if (configPath == null) {
                String[] configYamlPaths = {
                    "../pingping-server/config.yaml",
                    "../../pingping-server/config.yaml",
                    "pingping-server/config.yaml",
                    userDir + "/pingping-server/config.yaml",
                    userDir + "/../pingping-server/config.yaml"
                };
                for (String pathStr : configYamlPaths) {
                    Path path = Paths.get(pathStr).toAbsolutePath().normalize();
                    if (Files.exists(path) && Files.isRegularFile(path)) {
                        configPath = path;
                        break;
                    }
                }
            }
            
            if (configPath != null && Files.exists(configPath)) {
                ObjectMapper yamlMapper = new ObjectMapper(new YAMLFactory());
                Map<String, Object> config = yamlMapper.readValue(configPath.toFile(), Map.class);
                
                if (config != null && config.containsKey("prompt")) {
                    Object promptObj = config.get("prompt");
                    if (promptObj != null) {
                        String prompt = promptObj.toString();
                        System.out.println("Read prompt from config file (length: " + prompt.length() + " chars)");
                        return prompt;
                    }
                }
            }
        } catch (Exception e) {
            System.err.println("Error reading prompt from config file: " + e.getMessage());
            e.printStackTrace();
        }
        return null;
    }

    /**
     * Get model ID from config.yaml module name
     * Maps config.yaml format (e.g., "Whisper") to database format (e.g., "ASR_Whisper")
     * 
     * @param modelType The model type (ASR, VAD, LLM, etc.)
     * @param fallbackId Fallback model ID if config name not found
     * @param configName The name from config.yaml selected_module (e.g., "Whisper", "FunASR")
     * @return The database model ID (e.g., "ASR_Whisper")
     */
    private String getModelIdFromConfigName(String modelType, String fallbackId, String configName) {
        try {
            // Try to find model by name matching config.yaml value
            // Database model IDs follow pattern: {MODEL_TYPE}_{ModelName}
            // For example: config.yaml "Whisper" -> database "ASR_Whisper"
            String expectedModelId = modelType + "_" + configName;
            
            // Check if this model ID exists in database
            ModelConfigEntity model = modelConfigService.getModelByIdFromCache(expectedModelId);
            if (model != null && model.getIsEnabled() == 1) {
                return expectedModelId;
            }
            
            // If not found, try to find by model_name matching configName
            // Use getModelCodeList to find by name
            List<pingping.modules.model.dto.ModelBasicInfoDTO> models = modelConfigService.getModelCodeList(modelType.toUpperCase(), configName);
            if (models != null && !models.isEmpty()) {
                // Find exact match by name
                for (pingping.modules.model.dto.ModelBasicInfoDTO modelInfo : models) {
                    if (configName.equals(modelInfo.getModelName())) {
                        // Get the full model to get the ID
                        ModelConfigEntity foundModelEntity = modelConfigService.getModelByIdFromCache(modelInfo.getId());
                        if (foundModelEntity != null && foundModelEntity.getIsEnabled() == 1) {
                            return foundModelEntity.getId();
                        }
                    }
                }
            }
            
            // If still not found, use fallback
            return fallbackId;
        } catch (Exception e) {
            System.err.println("Error mapping config name to model ID: " + e.getMessage());
            return fallbackId;
        }
    }
}