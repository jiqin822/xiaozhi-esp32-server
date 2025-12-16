package pingping.modules.agent.controller;

import java.util.List;

import org.apache.commons.lang3.StringUtils;
import org.apache.shiro.authz.annotation.RequiresPermissions;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.Parameters;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.AllArgsConstructor;
import pingping.common.exception.ErrorCode;
import pingping.common.exception.RenException;
import pingping.common.utils.Result;
import pingping.modules.agent.dto.AgentVoicePrintSaveDTO;
import pingping.modules.agent.dto.AgentVoicePrintUpdateDTO;
import pingping.modules.agent.service.AgentVoicePrintService;
import pingping.modules.agent.vo.AgentVoicePrintVO;
import pingping.modules.security.user.SecurityUser;
import pingping.modules.sys.service.SysParamsService;

@Tag(name = "智能体声纹管理")
@AllArgsConstructor
@RestController
@RequestMapping("/agent/voice-print")
public class AgentVoicePrintController {
    private final AgentVoicePrintService agentVoicePrintService;
    private final SysParamsService sysParamsService;

    @PostMapping
    @Operation(summary = "创建智能体的声纹")
    @RequiresPermissions("sys:role:normal")
    public Result<Void> save(@RequestBody @Valid AgentVoicePrintSaveDTO dto) {
        boolean b = agentVoicePrintService.insert(dto);
        if (b) {
            return new Result<>();
        }
        return new Result<Void>().error(ErrorCode.AGENT_VOICEPRINT_CREATE_FAILED);
    }

    @PutMapping
    @Operation(summary = "更新智能体的对应声纹")
    @RequiresPermissions("sys:role:normal")
    public Result<Void> update(@RequestBody @Valid AgentVoicePrintUpdateDTO dto) {
        Long userId = SecurityUser.getUserId();
        boolean b = agentVoicePrintService.update(userId, dto);
        if (b) {
            return new Result<>();
        }
        return new Result<Void>().error(ErrorCode.AGENT_VOICEPRINT_UPDATE_FAILED);
    }

    @DeleteMapping("/{id}")
    @Operation(summary = "删除智能体对应声纹")
    @RequiresPermissions("sys:role:normal")
    public Result<Void> delete(@PathVariable String id) {
        Long userId = SecurityUser.getUserId();
        // 先删除关联的设备
        boolean delete = agentVoicePrintService.delete(userId, id);
        if (delete) {
            return new Result<>();
        }
        return new Result<Void>().error(ErrorCode.AGENT_VOICEPRINT_DELETE_FAILED);
    }

    @GetMapping("/list/{id}")
    @Operation(summary = "获取用户指定智能体声纹列表")
    @RequiresPermissions("sys:role:normal")
    public Result<List<AgentVoicePrintVO>> list(@PathVariable String id) {
        String voiceprintUrl = sysParamsService.getValue("server.voice_print", true);
        if (StringUtils.isBlank(voiceprintUrl) || "null".equals(voiceprintUrl)) {
            throw new RenException(ErrorCode.VOICEPRINT_API_NOT_CONFIGURED);
        }
        Long userId = SecurityUser.getUserId();
        List<AgentVoicePrintVO> list = agentVoicePrintService.list(userId, id);
        return new Result<List<AgentVoicePrintVO>>().ok(list);
    }

    @PostMapping(value = "/upload-audio", consumes = "multipart/form-data")
    @Operation(summary = "上传音频文件用于声纹注册")
    @Parameters({
            @Parameter(name = "agentId", description = "智能体ID", required = true),
            @Parameter(name = "audioFile", description = "音频文件", required = true)
    })
    @RequiresPermissions("sys:role:normal")
    public Result<String> uploadAudio(
            @RequestParam("agentId") String agentId,
            @RequestParam("audioFile") MultipartFile audioFile) {
        try {
            // 验证文件
            if (audioFile == null || audioFile.isEmpty()) {
                return new Result<String>().error(ErrorCode.VOICEPRINT_AUDIO_EMPTY);
            }

            // 验证文件类型
            String contentType = audioFile.getContentType();
            if (contentType == null || !contentType.startsWith("audio/")) {
                return new Result<String>().error(ErrorCode.VOICE_CLONE_NOT_AUDIO_FILE);
            }

            // 验证文件大小 (最大10MB)
            if (audioFile.getSize() > 10 * 1024 * 1024) {
                return new Result<String>().error(ErrorCode.VOICE_CLONE_AUDIO_TOO_LARGE);
            }

            // 上传音频并获取audioId
            String audioId = agentVoicePrintService.uploadAudioForVoicePrint(agentId, audioFile);
            return new Result<String>().ok(audioId);
        } catch (RenException e) {
            return new Result<String>().error(e.getCode(), e.getMsg());
        } catch (Exception e) {
            return new Result<String>().error(ErrorCode.VOICEPRINT_AUDIO_UPLOAD_FAILED, e.getMessage());
        }
    }

}
