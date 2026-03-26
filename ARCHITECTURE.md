# OpenGlass 项目架构分析

## 系统概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        OpenGlass 系统架构                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐     BLE 蓝牙      ┌──────────────────────┐   │
│  │  XIAO ESP32  │ ◄──────────────► │   React Native App   │   │
│  │   S3 Sense   │   (低功耗蓝牙)     │    (Expo Go/Web)     │   │
│  │   硬件固件   │                   │                      │   │
│  └──────────────┘                   └──────────────────────┘   │
│        │                                    │                   │
│        │                                    ▼                   │
│  - 摄像头拍照                          ┌──────────────────┐    │
│  - 麦克风录音                         │     Agent        │    │
│  - BLE 传输                          │   (AI 处理器)    │    │
│  - 电池供电                          └──────────────────┘    │
│                                              │                 │
│                                    ┌─────────┴─────────┐       │
│                                    ▼                   ▼       │
│                            ┌─────────────┐     ┌───────────┐   │
│                            │  Moondream │     │  Groq/    │   │
│                            │  (本地)    │     │  Ollama   │   │
│                            │   图像识别  │     │  LLM问答  │   │
│                            └─────────────┘     └───────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## 硬件部分 (firmware/)

| 文件 | 功能 |
|------|------|
| `firmware.ino` | 主程序：摄像头拍照、麦克风录音、BLE 通信 |
| `camera_pins.h` | 摄像头引脚配置 |
| `mulaw.h` | 音频编码 |

**BLE 服务 UUID:**
- `19B10000-E8F2-537E-4F6C-D104768A1214` - 主服务
- `19B10001` - 音频数据
- `19B10005` - 照片数据
- `19B10006` - 照片控制（触发拍照）

## 软件部分 (sources/)

```
sources/
├── app/
│   ├── Main.tsx           # 主界面：连接设备按钮
│   ├── DeviceView.tsx     # 设备连接后的界面
│   └── components/
│       ├── RoundButton.tsx # 圆形按钮组件
│       └── theme.ts        # 主题样式
├── modules/
│   ├── useDevice.ts       # 蓝牙连接管理
│   ├── openai.ts          # OpenAI API (GPT-4, TTS)
│   ├── ollama.ts          # 本地 Ollama (Moondream)
│   └── groq-llama3.ts     # Groq API (Llama3)
├── agent/
│   ├── Agent.ts           # AI Agent 核心逻辑
│   ├── imageDescription.ts # 图像描述 + 问答
│   └── imageBlurry.ts      # 模糊检测
└── utils/
    ├── base64.ts          # 图片 Base64 转换
    ├── lock.ts            # 异步锁
    └── ...
```

## 工作流程

1. **连接设备**: 手机通过蓝牙连接到 OpenGlass 眼镜
2. **自动拍照**: 眼镜每 5 秒自动拍摄照片，通过 BLE 传输到手机
3. **图像识别**: 
   - 本地使用 **Moondream** (Ollama) 生成图像描述
   - 或者使用 **Groq/Llama3** API
4. **用户提问**: 用户输入问题
5. **AI 问答**: 
   - 将所有图像描述发送给 LLM
   - LLM 根据描述回答问题
6. **语音回复**: 使用 **OpenAI TTS** 将答案转为语音播放

## 支持的 AI 模式

| 模式 | 图像描述 | 问答 | TTS |
|------|---------|------|-----|
| Ollama (本地) | ✅ Moondream | ❌ | ❌ |
| Groq API | ✅ | ✅ Llama3 | ❌ |
| OpenAI API | ✅ | ✅ GPT-4o | ✅ |

## 技术说明

### 原始设计问题

原始代码使用 **Web Bluetooth API** (`navigator.bluetooth.requestDevice`)，这个 API 只在以下环境可用：
- Chrome/Edge 桌面浏览器
- Android Chrome 浏览器

因此原项目设计为在 **电脑浏览器上运行 web 版本**，不是手机 Expo Go。

### 如何在手机上使用

需要使用 `react-native-ble-plx` 替代 Web Bluetooth API，并构建原生 APK：

```bash
npx expo prebuild    # 生成 native 项目
npx expo run:android # 构建 APK
```
