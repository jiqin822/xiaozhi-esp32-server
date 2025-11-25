package pingping.modules.config.init;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.DependsOn;

import jakarta.annotation.PostConstruct;
import pingping.common.constant.Constant;
import pingping.common.redis.RedisKeys;
import pingping.common.redis.RedisUtils;
import pingping.modules.config.service.ConfigService;
import pingping.modules.sys.service.SysParamsService;

@Configuration
@DependsOn("liquibase")
public class SystemInitConfig {

    @Autowired
    private SysParamsService sysParamsService;

    @Autowired
    private ConfigService configService;

    @Autowired
    private RedisUtils redisUtils;

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
    }
}