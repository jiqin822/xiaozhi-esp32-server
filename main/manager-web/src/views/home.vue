<template>
  <div class="welcome">
    <!-- Common header -->
    <HeaderBar :devices="devices" @search="handleSearch" @search-reset="handleSearchReset" />
    <el-main style="padding: 20px;display: flex;flex-direction: column;">
      <div>
        <!-- Home page content -->
        <div class="add-device">
          <div class="add-device-bg">
            <div class="hellow-text" style="margin-top: 30px;">
              {{ $t('home.greeting') }}
            </div>
            <div class="add-device-btn">
              <div class="left-add" @click="showAddDialog">
                {{ $t('home.addAgent') }}
              </div>
              <div class="right-add" @click="showAddDialog">
                <i class="el-icon-right" style="font-size: 20px;color: #fff;" />
              </div>
            </div>
          </div>
        </div>
        <div class="device-list-container">
          <template v-if="isLoading">
            <div v-for="i in skeletonCount" :key="'skeleton-' + i" class="skeleton-item">
              <div class="skeleton-image"></div>
              <div class="skeleton-content">
                <div class="skeleton-line"></div>
                <div class="skeleton-line-short"></div>
              </div>
            </div>
          </template>

          <template v-else>
            <DeviceItem v-for="(item, index) in devices" :key="index" :device="item" @configure="goToRoleConfig"
              @deviceManage="handleDeviceManage" @delete="handleDeleteAgent" @chat-history="handleShowChatHistory" />
          </template>
        </div>
      </div>
      <AddWisdomBodyDialog :visible.sync="addDeviceDialogVisible" @confirm="handleWisdomBodyAdded" />
    </el-main>
    <el-footer>
      <version-footer />
    </el-footer>
    <chat-history-dialog :visible.sync="showChatHistory" :agent-id="currentAgentId" :agent-name="currentAgentName" />
  </div>

</template>

<script>
import Api from '@/apis/api';
import AddWisdomBodyDialog from '@/components/AddWisdomBodyDialog.vue';
import ChatHistoryDialog from '@/components/ChatHistoryDialog.vue';
import DeviceItem from '@/components/DeviceItem.vue';
import HeaderBar from '@/components/HeaderBar.vue';
import VersionFooter from '@/components/VersionFooter.vue';

export default {
  name: 'HomePage',
  components: { DeviceItem, AddWisdomBodyDialog, HeaderBar, VersionFooter, ChatHistoryDialog },
  data() {
    return {
      addDeviceDialogVisible: false,
      devices: [],
      originalDevices: [],
      isSearching: false,
      searchRegex: null,
      isLoading: true,
      skeletonCount: localStorage.getItem('skeletonCount') || 8,
      showChatHistory: false,
      currentAgentId: '',
      currentAgentName: ''
    }
  },

  mounted() {
    this.fetchAgentList();
  },

  methods: {
    showAddDialog() {
      this.addDeviceDialogVisible = true
    },
    goToRoleConfig() {
      // Navigate to role configuration page after clicking configure role
      this.$router.push('/role-config')
    },
    handleWisdomBodyAdded(res) {
      this.fetchAgentList();
      this.addDeviceDialogVisible = false;
    },
    handleDeviceManage() {
      this.$router.push('/device-management');
    },
    handleSearch(regex) {
      this.isSearching = true;
      this.searchRegex = regex;
      this.applySearchFilter();
    },
    handleSearchReset() {
      this.isSearching = false;
      this.searchRegex = null;
      this.devices = [...this.originalDevices];
    },
    applySearchFilter() {
      if (!this.isSearching || !this.searchRegex) {
        this.devices = [...this.originalDevices];
        return;
      }

      this.devices = this.originalDevices.filter(device => {
        return this.searchRegex.test(device.agentName);
      });
    },
    // Update agent list based on search
    handleSearchResult(filteredList) {
      this.devices = filteredList; // Update device list
    },
    // Fetch agent list
    fetchAgentList() {
      this.isLoading = true;
      Api.agent.getAgentList(({ data }) => {
        if (data?.data) {
          this.originalDevices = data.data.map(item => ({
            ...item,
            agentId: item.id
          }));

          // Dynamically set skeleton screen count (optional)
          this.skeletonCount = Math.min(
            Math.max(this.originalDevices.length, 3), // Minimum 3
            10 // Maximum 10
          );

          this.handleSearchReset();
        }
        this.isLoading = false;
      }, (error) => {
        console.error('Failed to fetch agent list:', error);
        this.isLoading = false;
      });
    },
    // Delete agent
    handleDeleteAgent(agentId) {
      // Prevent deletion of default agent
      if (agentId === 'DEFAULT_AGENT') {
        this.$message.warning({
          message: 'Default agent cannot be deleted',
          showClose: true
        });
        return;
      }
      this.$confirm(this.$t('home.confirmDeleteAgent'), 'Notice', {
        confirmButtonText: this.$t('button.ok'),
        cancelButtonText: this.$t('button.cancel'),
        type: 'warning'
      }).then(() => {
        Api.agent.deleteAgent(agentId, (res) => {
          if (res.data.code === 0) {
            this.$message.success({
              message: this.$t('home.deleteSuccess'),
              showClose: true
            });
            this.fetchAgentList(); // Refresh list
          } else {
            this.$message.error({
              message: res.data.msg || this.$t('home.deleteFailed'),
              showClose: true
            });
          }
        }, (error) => {
          this.$message.error({
            message: error?.response?.data?.msg || this.$t('home.deleteFailed'),
            showClose: true
          });
        });
      }).catch(() => {
        // User cancelled
      });
    },
    handleShowChatHistory({ agentId, agentName }) {
      this.currentAgentId = agentId;
      this.currentAgentName = agentName;
      this.showChatHistory = true;
    }
  }
}
</script>

<style lang="scss" scoped>
@import '../styles/theme.scss';

.welcome {
  min-width: 900px;
  min-height: 506px;
  height: 100vh;
  display: flex;
  flex-direction: column;
  @include paper-texture;
  position: relative;
  
  &::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    @include notebook-lines;
    opacity: 0.2;
    pointer-events: none;
  }
}

.add-device {
  height: 195px;
  border-radius: 0;
  position: relative;
  overflow: visible;
  @include notebook-cover;
  background: #FFFFFF !important;
  margin-bottom: 24px;
}

.add-device-bg {
  width: 100%;
  height: 100%;
  text-align: left;
  overflow: visible;
  box-sizing: border-box;
  background: transparent;
  padding: 25px 30px 20px 50px; // Extra left padding for spiral binding
  position: relative;
  
  .hellow-text {
    margin-left: 0;
    color: $pen-black;
    font-size: 36px;
    font-weight: 400;
    font-family: 'Caveat', 'Kalam', cursive;
    letter-spacing: 1px;
    position: relative;
    z-index: 1;
    text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.05);
    transform: rotate(-0.5deg); // Slight handwritten tilt
    display: inline-block;
    line-height: 1.2;
    
    &:first-child {
      margin-top: 0;
      font-size: 42px;
      font-weight: 600;
      color: $pen-blue;
      transform: rotate(0.3deg);
    }
  }

  .hi-hint {
    font-weight: 400;
    font-size: 20px;
    font-family: 'Caveat', 'Kalam', cursive;
    text-align: left;
    color: $text-secondary;
    margin-left: 0;
    margin-top: 8px;
    font-style: normal;
    position: relative;
    z-index: 1;
    transform: rotate(-0.2deg);
    display: inline-block;
    text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.05);
  }
}

.add-device-btn {
  display: flex;
  align-items: center;
  margin-left: 0; // Aligned with notebook margin
  margin-top: 20px;
  cursor: pointer;
  position: relative;
  z-index: 10; // Above the notebook lines and margin
  width: fit-content;

  .left-add {
    background: $pen-blue !important;
    width: 140px;
    height: 40px;
    border-radius: 20px;
    color: #fff !important;
    font-size: 16px;
    font-family: 'Caveat', 'Kalam', cursive;
    font-weight: 600;
    text-align: center;
    line-height: 40px;
    text-transform: none;
    letter-spacing: 0.5px;
    border: none;
    box-shadow: $elevation-2;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    cursor: pointer;
    position: relative;
    z-index: 11;
    
    &:hover {
      background: $pen-blue-dark !important;
      box-shadow: $elevation-3;
      transform: translateY(-1px);
    }
    
    &:active {
      box-shadow: $elevation-1;
      transform: translateY(1px);
    }
  }

  .right-add {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: $pen-blue !important;
    margin-left: -6px;
    display: flex;
    justify-content: center;
    align-items: center;
    box-shadow: $elevation-2;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    cursor: pointer;
    position: relative;
    z-index: 11;
    
    &:hover {
      background: $pen-blue-dark !important;
      box-shadow: $elevation-3;
      transform: scale(1.05);
    }
  }
}

.device-list-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 30px;
  padding: 30px 0;
}

/* Styles in DeviceItem.vue */
.device-item {
  margin: 0 !important;
  /* Avoid conflicts */
  width: auto !important;
}

.footer {
  font-size: 12px;
  font-weight: 400;
  margin-top: auto;
  padding-top: 30px;
  color: #979db1;
  text-align: center;
  /* Center display */
}

/* Skeleton screen animation */
@keyframes shimmer {
  100% {
    transform: translateX(100%);
  }
}

.skeleton-item {
  @include material-card(1);
  background: $paper-cream !important;
  border-radius: 8px;
  padding: 20px;
  height: 120px;
  position: relative;
  overflow: hidden;
  margin-bottom: 20px;
  border: 1px solid rgba(0, 0, 0, 0.08);
}

.skeleton-image {
  width: 80px;
  height: 80px;
  background: #f0f2f5;
  border-radius: 4px;
  float: left;
  position: relative;
  overflow: hidden;
}

.skeleton-content {
  margin-left: 100px;
}

.skeleton-line {
  height: 16px;
  background: #f0f2f5;
  border-radius: 4px;
  margin-bottom: 12px;
  width: 70%;
  position: relative;
  overflow: hidden;
}

.skeleton-line-short {
  height: 12px;
  background: #f0f2f5;
  border-radius: 4px;
  width: 50%;
}

.skeleton-item::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 50%;
  height: 100%;
  background: linear-gradient(90deg,
      rgba(255, 255, 255, 0),
      rgba(255, 255, 255, 0.3),
      rgba(255, 255, 255, 0));
  animation: shimmer 1.5s infinite;
}
</style>