# 前端架构与设计

## 分层

`features/<模块>/{ui,app,services}` + `shared/{ui,app,services,lib}`。

- `ui`：展示与交互（组件、页面）
- `app`：Zustand store + 薄 hook（`useAuth`/`useChat`/…），UI 经选择器订阅
- `services`：数据访问；接口集中在 `shared/services/types.ts`，各模块按 `VITE_API_MODE` 选 `mockAdapter`（内存 fixtures + 模拟流式）或 `httpClient` 实现，后端就绪只换适配器

模块间只经 `shared` 交互。shadcn 基件实际位于 `src/components/ui/`（CLI 默认路径，与 `components.json` 别名绑定，视为 shared 层，未挪动以免破坏 `shadcn add`）。

## 关键机制

- **流式**：`shared/services/sseParser.ts` 纯函数（跨块半行、flush、坏 JSON → error 事件），`chat/services/sseClient.ts` 用 fetch `ReadableStream` 消费 live 字节流；mock 直接产 `SSEChunk` 异步迭代。`chatStore.sendMessage` 增量拼接，`AbortSignal` 中断。单测：`sseParser.test.ts`（`npm test`，Node 内置 runner）
- **请求层**：`shared/services/apiClient.ts`（axios 实例，`createClient(baseURL)` 工厂 + `/api` 单例，超时 15s，上传 60s）——拦截器注入 Bearer、401 回调、`{detail}` 归一为 `ApiError{status,message}`、204/空体安全；薄封装 `apiGet/apiPost/apiPatch/apiDelete/apiUpload`。`shared/services/authBridge.ts` 是 axios 与 fetch 流共用的令牌/401 注入点（`tokenService.initTokenService` 在 `main.tsx` 接线，避免 shared 反向依赖 feature）。弱网策略（缓存/重试/并发/离线重放）待后端联调时以拦截器形式追加
- **认证**：`authStore`（persist `ia-auth`）持有 `{user, token}`。`ponytail:` 令牌存 localStorage，接真实后端后升级 httpOnly Cookie
- **主题**：`themeStore`（persist `ia-theme`，默认浅色）→ `ThemeProvider` 同步 `<html>.dark`
- **动效**：`MotionConfig reducedMotion="user"` 全局尊重系统减动效；仅消息入场与流式光标用 motion，GSAP 备用

## 设计令牌（Tailwind v4 `@theme`，`src/index.css`）

| 令牌 | 浅色 | 深色 |
|---|---|---|
| background | `#FFFFFF` | `#0B0F17` |
| 表面 muted/secondary/accent | `#F7F8FA` | `#111827`/`#1F2937` |
| border | `#E5E7EB` | `#1F2937` |
| foreground | `#111827` | `#F9FAFB` |
| muted-foreground | `#6B7280` | `#9CA3AF` |
| primary（唯一点缀令牌） | `#2563EB` | `#3B82F6` |
| destructive / success | `#DC2626` / `#16A34A` | `#EF4444` / `#22C55E` |

`--primary-hover` 由 `color-mix` 派生，换色只改 `--primary`。字体 Geist Variable；字号 12/14/16/18/24；间距 4 阶梯；圆角 `0.625rem`。

## 布局

- AppShell：56px 顶栏（logo/导航/主题开关/用户菜单）+ 内容区
- 聊天工作台：左 256px 会话栏（<1024px 可收起，汉堡按钮）+ 右聊天窗（消息区 max-w-3xl 居中）
- 知识库：左 224px 库列表 + 右文档列表；资源/设置：max-w-3xl 单栏

## 已知取舍

- 构建单 chunk ~690KB（警告线 500KB）：路由级代码分割待做
- 会话/知识库/资源删除用 AlertDialog 确认；mock 文档状态按上传时长推导，前端轮询刷新
- 参考图流程（gpt-taste）因环境无图像生成能力而跳过，实现直接以上述令牌为准
