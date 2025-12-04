package pingping.modules.device.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class DeviceManualAddDTO {
    @NotBlank(message = "智能体ID不能为空")
    private String agentId;
    
    @NotBlank(message = "设备型号不能为空")
    private String board;        // 设备型号
    
    @NotBlank(message = "固件版本不能为空")
    private String appVersion;   // 固件版本
    
    @NotBlank(message = "Mac地址不能为空")
    private String macAddress;   // Mac地址
} 