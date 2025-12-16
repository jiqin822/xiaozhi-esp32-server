<template>
  <div class="welcome">
    <el-container style="height: 100%">
      <el-header class="login-header">
        <div class="header-logo-container">
          <img loading="lazy" alt="" src="@/assets/xiaozhi-logo.png" class="header-logo-img" />
          <img loading="lazy" alt="" src="@/assets/xiaozhi-ai.png" class="header-brand-img" />
        </div>
      </el-header>
      <el-main style="position: relative">
        <div class="login-box" @keyup.enter="login">
          <div style="
              display: flex;
              align-items: center;
              gap: 20px;
              margin-bottom: 39px;
              padding: 0 30px;
            ">
            <img loading="lazy" alt="" src="@/assets/login/hi.png" style="width: 34px; height: 34px" />
            <div class="login-text">{{ $t("login.title") }}</div>

            <div class="login-welcome">
              {{ $t("login.welcome") }}
            </div>

            <!-- 语言切换下拉菜单 -->
            <el-dropdown trigger="click" class="title-language-dropdown"
              @visible-change="handleLanguageDropdownVisibleChange">
              <span class="el-dropdown-link">
                <span class="current-language-text">{{ currentLanguageText }}</span>
                <i class="el-icon-arrow-down el-icon--right" :class="{ 'rotate-down': languageDropdownVisible }"></i>
              </span>
              <el-dropdown-menu slot="dropdown">
                <el-dropdown-item @click.native="changeLanguage('zh_CN')">
                  {{ $t("language.zhCN") }}
                </el-dropdown-item>
                <el-dropdown-item @click.native="changeLanguage('zh_TW')">
                  {{ $t("language.zhTW") }}
                </el-dropdown-item>
                <el-dropdown-item @click.native="changeLanguage('en')">
                  {{ $t("language.en") }}
                </el-dropdown-item>
                <el-dropdown-item @click.native="changeLanguage('de')">
                  {{ $t("language.de") }}
                </el-dropdown-item>
                <el-dropdown-item @click.native="changeLanguage('vi')">
                  {{ $t("language.vi") }}
                </el-dropdown-item>
              </el-dropdown-menu>
            </el-dropdown>
          </div>
          <div style="padding: 0 30px">
            <!-- Username login -->
            <div class="input-box">
              <img loading="lazy" alt="" class="input-icon" src="@/assets/login/username.png" />
              <el-input v-model="form.username" :placeholder="$t('login.usernamePlaceholder')" />
            </div>

            <div class="input-box">
              <img loading="lazy" alt="" class="input-icon" src="@/assets/login/password.png" />
              <el-input v-model="form.password" :placeholder="$t('login.passwordPlaceholder')" type="password"
                show-password />
            </div>
            <div style="
                display: flex;
                align-items: center;
                margin-top: 20px;
                width: 100%;
                gap: 10px;
              ">
              <div class="input-box" style="width: calc(100% - 130px); margin-top: 0">
                <img loading="lazy" alt="" class="input-icon" src="@/assets/login/shield.png" />
                <el-input v-model="form.captcha" :placeholder="$t('login.captchaPlaceholder')" style="flex: 1" />
              </div>
              <img loading="lazy" v-if="captchaUrl" :src="captchaUrl" alt="验证码"
                style="width: 150px; height: 40px; cursor: pointer" @click="fetchCaptcha" />
            </div>
            <div style="
                font-weight: 400;
                font-size: 14px;
                text-align: left;
                color: #5778ff;
                display: flex;
                justify-content: space-between;
                margin-top: 20px;
              ">
              <div v-if="allowUserRegister" style="cursor: pointer; font-weight: 600; text-decoration: underline; font-size: 15px; color: #409EFF;" @click="goToRegister">
                👉 {{ $t("login.register") }} {{ $t("login.orCreateAccount") || "(Create your first account)" }}
              </div>
              <div style="cursor: pointer" @click="goToForgetPassword">
                {{ $t("login.forgetPassword") }}
              </div>
            </div>
          </div>
          <div class="login-btn" @click="login">{{ $t("login.login") }}</div>
          <div style="font-size: 14px; color: #979db1">
            {{ $t("login.agreeTo") }}
            <div style="display: inline-block; color: #5778ff; cursor: pointer">
              {{ $t("login.userAgreement") }}
            </div>
            {{ $t("login.and") }}
            <div style="display: inline-block; color: #5778ff; cursor: pointer">
              {{ $t("login.privacyPolicy") }}
            </div>
          </div>
        </div>
      </el-main>
      <el-footer>
        <version-footer />
      </el-footer>
    </el-container>
  </div>
</template>

<script>
import Api from "@/apis/api";
import VersionFooter from "@/components/VersionFooter.vue";
import i18n, { changeLanguage } from "@/i18n";
import { getUUID, goToPage, showDanger, showSuccess, sm2Encrypt } from "@/utils";
import { mapState } from "vuex";

export default {
  name: "login",
  components: {
    VersionFooter,
  },
  computed: {
    ...mapState({
      allowUserRegister: (state) => state.pubConfig.allowUserRegister,
      sm2PublicKey: (state) => state.pubConfig.sm2PublicKey,
    }),
    // Get current language
    currentLanguage() {
      return i18n.locale || "zh_CN";
    },
    // Get current language display text
    currentLanguageText() {
      const currentLang = this.currentLanguage;
      switch (currentLang) {
        case "zh_CN":
          return this.$t("language.zhCN");
        case "zh_TW":
          return this.$t("language.zhTW");
        case "en":
          return this.$t("language.en");
        case "de":
          return this.$t("language.de");
        case "vi":
          return this.$t("language.vi");
        default:
          return this.$t("language.zhCN");
      }
    },
  },
  data() {
    return {
      form: {
        username: "",
        password: "",
        captcha: "",
        captchaId: "",
      },
      captchaUuid: "",
      captchaUrl: "",
      languageDropdownVisible: false,
    };
  },
  mounted() {
    // First get configuration, then decide whether to redirect
    this.$store.dispatch("fetchPubConfig").then(() => {
      console.log('PubConfig loaded:', {
        allowUserRegister: this.allowUserRegister,
        currentPath: this.$route.path
      });
      
      // Only auto-redirect to registration if:
      // 1. Registration is allowed
      // 2. User is on the root path (first visit), not explicitly on /login
      // 3. User is not already logged in (no token)
      const hasToken = localStorage.getItem('token');
      if (this.allowUserRegister && this.$route.path === '/' && !hasToken) {
        // Redirect to registration page only on first visit to root path
        console.log('First visit, redirecting to register page...');
        this.$nextTick(() => {
          this.$router.replace('/register');
        });
        return; // Do not continue execution, avoid loading captcha etc.
      }
      
      // Only fetch captcha when no redirection is needed
      this.fetchCaptcha();
    }).catch((error) => {
      console.error('Failed to load pubConfig:', error);
      // If fetching configuration fails, still try to fetch captcha
      this.fetchCaptcha();
    });
  },
  methods: {
    fetchCaptcha() {
      if (this.$store.getters.getToken) {
        if (this.$route.path !== "/home") {
          this.$router.push("/home");
        }
      } else {
        this.captchaUuid = getUUID();

        Api.user.getCaptcha(this.captchaUuid, (res) => {
          if (res.status === 200) {
            const blob = new Blob([res.data], { type: res.data.type });
            this.captchaUrl = URL.createObjectURL(blob);
          } else {
            showDanger("Captcha loading failed, click to refresh");
          }
        });
      }
    },

    // Handle language dropdown visibility change
    handleLanguageDropdownVisibleChange(visible) {
      this.languageDropdownVisible = visible;
    },

    // Change language
    changeLanguage(lang) {
      changeLanguage(lang);
      this.languageDropdownVisible = false;
      this.$message.success({
        message: this.$t("message.success"),
        showClose: true,
      });
    },

    // Input validation helper
    validateInput(input, messageKey) {
      if (!input.trim()) {
        showDanger(this.$t(messageKey));
        return false;
      }
      return true;
    },

    async login() {
      // Username validation
      if (!this.validateInput(this.form.username, 'login.requiredUsername')) {
        return;
      }

      // 验证密码
      if (!this.validateInput(this.form.password, 'login.requiredPassword')) {
        return;
      }
      // 验证验证码
      if (!this.validateInput(this.form.captcha, 'login.requiredCaptcha')) {
        return;
      }
      // 加密密码
      let encryptedPassword;
      try {
        // 拼接验证码和密码
        const captchaAndPassword = this.form.captcha + this.form.password;
        encryptedPassword = sm2Encrypt(this.sm2PublicKey, captchaAndPassword);
      } catch (error) {
        console.error("密码加密失败:", error);
        showDanger(this.$t('sm2.encryptionFailed'));
        return;
      }

      const plainUsername = this.form.username;

      this.form.captchaId = this.captchaUuid;

      // 加密
      const loginData = {
        username: plainUsername,
        password: encryptedPassword,
        captchaId: this.form.captchaId
      };

      Api.user.login(
        loginData,
        ({ data }) => {
          showSuccess(this.$t('login.loginSuccess'));
          this.$store.commit("setToken", JSON.stringify(data.data));
          goToPage("/home");
        },
        (err) => {
          // 直接使用后端返回的国际化消息
          let errorMessage = err.data.msg || "登录失败";

          showDanger(errorMessage);
          if (
            err.data != null &&
            err.data.msg != null &&
            err.data.msg.indexOf("图形验证码") > -1 || err.data.msg.indexOf("Captcha") > -1
          ) {
            this.fetchCaptcha();
          }
        }
      );

      // Re-fetch captcha
      setTimeout(() => {
        this.fetchCaptcha();
      }, 1000);
    },

    goToRegister() {
      goToPage("/register");
    },
    goToForgetPassword() {
      goToPage("/retrieve-password");
    }
  },
};
</script>
<style lang="scss" scoped>
@import "./auth.scss";

.title-language-dropdown {
  margin-left: auto;
}

.current-language-text {
  margin-left: 4px;
  margin-right: 4px;
  font-size: 12px;
  color: #3d4566;
}

.language-dropdown {
  margin-left: auto;
}

.rotate-down {
  transform: rotate(180deg);
  transition: transform 0.3s ease;
}

.el-icon-arrow-down {
  transition: transform 0.3s ease;
}

@import '../styles/theme.scss';

:deep(.el-button--primary) {
  @include material-button($pen-blue);
  background-color: $pen-blue !important;
  border-color: $pen-blue !important;

  &:hover,
  &:focus {
    background-color: $pen-blue-dark !important;
    border-color: $pen-blue-dark !important;
    box-shadow: $elevation-3 !important;
  }

  &:active {
    background-color: darken($pen-blue, 10%) !important;
    border-color: darken($pen-blue, 10%) !important;
    box-shadow: $elevation-1 !important;
  }
}
</style>
