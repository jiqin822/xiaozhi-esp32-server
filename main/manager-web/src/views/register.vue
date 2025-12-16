<template>
  <div class="welcome" @keyup.enter="register">
    <el-container style="height: 100%;">
      <!-- Keep the same header -->
      <el-header class="login-header">
        <div class="header-logo-container">
          <img loading="lazy" alt="" src="@/assets/xiaozhi-logo.png" class="header-logo-img" />
          <img loading="lazy" alt="" src="@/assets/xiaozhi-ai.png" class="header-brand-img" />
        </div>
      </el-header>
      <el-main style="position: relative;">
        <div class="login-box">
          <!-- Modified title section -->
          <div style="display: flex;align-items: center;gap: 20px;margin-bottom: 39px;padding: 0 30px;">
            <img loading="lazy" alt="" src="@/assets/login/hi.png" style="width: 34px;height: 34px;" />
            <div class="login-text">{{ $t('register.title') }}</div>
            <div class="login-welcome">
              {{ $t('register.welcome') }}
            </div>
          </div>

          <div style="padding: 0 30px;">
            <form @submit.prevent="register">
              <!-- Username input field -->
              <div class="input-box">
                <img loading="lazy" alt="" class="input-icon" src="@/assets/login/username.png" />
                <el-input v-model="form.username" :placeholder="$t('register.usernamePlaceholder')" />
              </div>

              <!-- Password input field -->
              <div class="input-box">
                <img loading="lazy" alt="" class="input-icon" src="@/assets/login/password.png" />
                <el-input v-model="form.password" :placeholder="$t('register.passwordPlaceholder')" type="password"
                  show-password />
              </div>

              <!-- Added confirm password field -->
              <div class="input-box">
                <img loading="lazy" alt="" class="input-icon" src="@/assets/login/password.png" />
                <el-input v-model="form.confirmPassword" :placeholder="$t('register.confirmPasswordPlaceholder')"
                  type="password" show-password />
              </div>

              <!-- Captcha section is disabled -->

              <!-- Modified bottom link -->
              <div style="font-weight: 400;font-size: 14px;text-align: left;color: #5778ff;margin-top: 20px;">
                <div style="cursor: pointer;" @click="goToLogin">{{ $t('register.goToLogin') }}</div>
              </div>
            </form>
          </div>

          <!-- Modified button text -->
          <div class="login-btn" @click="register">{{ $t('register.registerButton') }}</div>

          <!-- Keep the same agreement statement -->
          <div style="font-size: 14px;color: #979db1;">
            {{ $t('register.agreeTo') }}
            <div style="display: inline-block;color: #5778FF;cursor: pointer;">{{ $t('register.userAgreement') }}</div>
            {{ $t('register.and') }}
            <div style="display: inline-block;color: #5778FF;cursor: pointer;">{{ $t('register.privacyPolicy') }}</div>
          </div>
        </div>
      </el-main>

      <!-- Keep the same footer -->
      <el-footer>
        <version-footer />
      </el-footer>
    </el-container>
  </div>
</template>

<script>
import Api from '@/apis/api';
import VersionFooter from '@/components/VersionFooter.vue';
import { getUUID, goToPage, showDanger, showSuccess, sm2Encrypt } from '@/utils';
import { mapState } from 'vuex';

// Import language switching functionality

export default {
  name: 'register',
  components: {
    VersionFooter
  },
  computed: {
    ...mapState({
      allowUserRegister: state => state.pubConfig.allowUserRegister,
      sm2PublicKey: state => state.pubConfig.sm2PublicKey,
    })
  },
  data() {
    return {
      form: {
        username: '',
        password: '',
        confirmPassword: '',
        captcha: '',
        captchaId: ''
      },
      captchaUrl: '',
    }
  },
  mounted() {
    this.$store.dispatch('fetchPubConfig').then(() => {
      if (!this.allowUserRegister) {
        showDanger(this.$t('register.notAllowRegister'));
        setTimeout(() => {
          goToPage('/login');
        }, 1500);
        return;
      }
      
      // Check if SM2 public key is loaded
      if (!this.sm2PublicKey) {
        console.error('SM2 public key not loaded');
        showDanger('SM2 public key configuration not loaded, please refresh the page and try again');
      }
    }).catch((error) => {
      console.error('Failed to fetch public configuration:', error);
      showDanger('Unable to connect to server, please check if the backend service is running');
    });
    // Captcha is disabled, no longer fetch captcha
    // this.fetchCaptcha();
  },
  methods: {
    // Reuse captcha fetching method
    fetchCaptcha() {
      this.form.captchaId = getUUID();
      Api.user.getCaptcha(this.form.captchaId, (res) => {
        try {
          // Handle blob response
        if (res.status === 200) {
            // If res.data is already a Blob, use it directly; otherwise create a new Blob
            let blob;
            if (res.data instanceof Blob) {
              blob = res.data;
            } else {
              blob = new Blob([res.data], { type: 'image/gif' });
            }
            // Release old URL object to avoid memory leak
            if (this.captchaUrl) {
              URL.revokeObjectURL(this.captchaUrl);
            }
          this.captchaUrl = URL.createObjectURL(blob);
        } else {
            console.error('Captcha loading error, status code:', res.status);
            showDanger(this.$t('register.captchaLoadFailed'));
          }
        } catch (error) {
          console.error('Captcha processing error:', error);
          showDanger(this.$t('register.captchaLoadFailed'));
        }
      }, (err) => {
        console.error('Failed to get captcha:', err);
        showDanger(this.$t('register.captchaLoadFailed') || 'Captcha loading failed, please refresh the page and try again');
      });
    },

    // Encapsulate input validation logic
    validateInput(input, message) {
      if (!input.trim()) {
        showDanger(message);
        return false;
      }
      return true;
    },

    // Registration logic
    async register() {
      // Username registration validation
      if (!this.validateInput(this.form.username, this.$t('register.requiredUsername'))) {
        return;
      }

      // Validate password
      if (!this.validateInput(this.form.password, this.$t('register.requiredPassword'))) {
        return;
      }
      if (this.form.password !== this.form.confirmPassword) {
        showDanger(this.$t('register.passwordsNotMatch'))
        return
      }
      // Check if SM2 public key is loaded
      if (!this.sm2PublicKey) {
        console.error("SM2 public key not loaded, please wait for configuration to load");
        showDanger(this.$t('sm2.encryptionFailed') || 'SM2 public key not loaded. Please wait and try again.');
        // Try to fetch configuration again
        this.$store.dispatch('fetchPubConfig').then(() => {
          if (this.sm2PublicKey) {
            showDanger('Configuration loaded, please retry registration');
          }
        });
        return;
      }
      
      // Encrypt (captcha is disabled, encrypt password directly)
      let encryptedPassword;
      try {
        encryptedPassword = sm2Encrypt(this.sm2PublicKey, this.form.password);
      } catch (error) {
        console.error("Password encryption failed:", error);
        console.error("SM2 public key:", this.sm2PublicKey);
        showDanger(this.$t('sm2.encryptionFailed') || 'Password encryption failed: ' + error.message);
        return;
      }

      // Prepare registration data
      const registerData = {
        username: this.form.username,
        password: encryptedPassword
        // Captcha is disabled, do not send captchaId field
      };

      Api.user.register(registerData, ({ data }) => {
        showSuccess(this.$t('register.registerSuccess'))
        goToPage('/login')
      }, (err) => {
        showDanger(err.data.msg || this.$t('register.registerFailed'))
        // Captcha is disabled, no longer handle captcha-related errors
      })
    },

    goToLogin() {
      goToPage('/login')
    }
  }
}
</script>

<style lang="scss" scoped>
@import './auth.scss';

.send-captcha-btn {
  margin-right: -5px;
  min-width: 100px;
  height: 40px;
  line-height: 40px;
  border-radius: 4px;
  font-size: 14px;
  background: rgb(87, 120, 255);
  border: none;
  padding: 0px;

  &:disabled {
    background: #c0c4cc;
    cursor: not-allowed;
  }
}
</style>
