package pingping;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.ComponentScan;

@SpringBootApplication
@ComponentScan(basePackages = {"pingping", "xiaozhi"})
@MapperScan(basePackages = {"pingping.modules.*.dao", "pingping.modules.*.dao", "pingping.common.dao", "pingping.common.dao"})
public class AdminApplication {

    public static void main(String[] args) {
        SpringApplication.run(AdminApplication.class, args);
        System.out.println("http://localhost:8002/pingping/doc.html");
    }
}