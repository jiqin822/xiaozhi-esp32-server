import type {
  ChatHistory,
  CreateSpeakerData,
  VoicePrint,
} from './types'
import { http } from '@/http/request/alova'
import { getEnvBaseUrl } from '@/utils'

// 获取声纹列表
export function getVoicePrintList(agentId: string) {
  return http.Get<VoicePrint[]>(`/agent/voice-print/list/${agentId}`, {
    meta: {
      ignoreAuth: false,
      toast: false,
    },
    cacheFor: {
      expire: 0,
    },
  })
}

// 获取语音对话记录（用于选择声纹向量）
export function getChatHistory(agentId: string) {
  return http.Get<ChatHistory[]>(`/agent/${agentId}/chat-history/user`, {
    meta: {
      ignoreAuth: false,
      toast: false,
    },
    cacheFor: {
      expire: 0,
    },
  })
}

// 新增说话人
export function createVoicePrint(data: CreateSpeakerData) {
  return http.Post<null>('/agent/voice-print', data, {
    meta: {
      ignoreAuth: false,
      toast: true,
    },
  })
}

// 删除声纹
export function deleteVoicePrint(id: string) {
  return http.Delete<null>(`/agent/voice-print/${id}`, {
    meta: {
      ignoreAuth: false,
      toast: true,
    },
  })
}

// 更新声纹信息
export function updateVoicePrint(data: VoicePrint) {
  return http.Put<null>('/agent/voice-print', data, {
    meta: {
      ignoreAuth: false,
      toast: true,
    },
  })
}

// 上传音频文件用于声纹注册
export function uploadVoicePrintAudio(agentId: string, filePath: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const token = uni.getStorageSync('token')
    if (!token) {
      reject(new Error('未登录，请先登录'))
      return
    }

    uni.uploadFile({
      url: `${getEnvBaseUrl()}/agent/voice-print/upload-audio`,
      filePath,
      name: 'audioFile',
      formData: {
        agentId,
      },
      header: {
        Authorization: `Bearer ${token}`,
      },
      success: (res) => {
        try {
          const response = JSON.parse(res.data)
          if (response.code === 0) {
            resolve(response.data)
          } else {
            reject(new Error(response.msg || '上传失败'))
          }
        } catch (err) {
          reject(new Error('解析响应失败'))
        }
      },
      fail: (err) => {
        reject(new Error(err.errMsg || '上传失败'))
      },
    })
  })
}
