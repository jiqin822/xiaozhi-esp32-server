package pingping.modules.security.dto;

import java.io.Serializable;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * 短信验证码请求DTO
 */
@Data
@Schema(description = "短信验证码请求")
public class SmsVerificationDTO implements Serializable {
    private static final long serialVersionUID = 1L;

    @Schema(description = "手机号码")
    @NotBlank(message = "{sysuser.username.require}")
    private String phone;

    @Schema(description = "验证码")
    // 验证码已禁用，不再要求
    private String captcha;

    @Schema(description = "唯一标识")
    // 验证码已禁用，不再要求
    private String captchaId;
}