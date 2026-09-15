# 面试 Agent（求职者端）

面向个人求职者的 Web 应用：核心业务是 Agent 聊天（自由对话 + 模拟面试），辅助业务是面试资源上传与 RAG 知识库管理。

## 功能

- **认证**：邮箱密码登录/注册、GitHub/Google OAuth（live 模式整页跳转 + `/oauth/callback` 回调），令牌持久化，401 自动登出跳登录
- **对话工作台** `/`：左会话列表（新建/切换/删除），右聊天窗。流式输出 + 打字光标、RAG 引用来源折叠块、输入区 自由对话/模拟面试 切换、停止生成；模拟面试模式带轮次顶栏与结束按钮
- **知识库** `/knowledge`：多知识库管理，文档上传（PDF/DOCX/TXT/MD ≤20MB，前端校验 + 进度条），状态流转 解析中 → 索引中 → 就绪
- **资源** `/resources`：拖拽上传面试资源（简历/面经等），同白名单与上限校验
- **设置** `/settings`：个人资料、修改密码、外观（浅色/深色，持久化）、邮件偏好

## 运行

```bash
npm install
npm run dev        # 默认 mock 数据，无需后端
```

切真实后端：设 `VITE_API_MODE=live`（如 `.env.local`），dev 代理 `/api` → `http://localhost:8000`。

## 门禁

```bash
npm run build   # tsc + vite
npm run lint    # oxlint
npm test        # SSE 解析器纯函数单测（node:test）
```

## 约定

- 界面中文，文案集中在 `src/shared/lib/locale/zh.ts`
- v1 不做：文件在线预览、管理后台、用量统计；GSAP 已装但微动效只用 motion
