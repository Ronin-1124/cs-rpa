# 真实咚咚前端采集记录

采集日期：2026-09-07。来源：Codex 内置浏览器已登录的 https://dongdong.jd.com/。
采集方式：只读 DOM 与 computed style，后续经授权切换历史客户。未填写、发送或修改接待状态。
当前账号挂起，正在咨询和留言均为 0；不保存客户姓名、正文、头像地址或登录凭据。

## 已确认结构

```text
.root > .windows > .container
  header#t-body_header.theme-back-img
  .panel-content
    .ulist-wrap
      #t-ulist_search.search-wrap
      #t-alluser-wrap.alluser-wrap
        .c_tabs.c_tabs-pos_top
          .c_tabs-bar > .c_tabs-nav-container > .c_tabs-tab
          .c_tabs-content
            .c_tabs-tabpane
              .list-compatible > .c_stream > .c_stream-content
                .c_cas-head
            .c_tabs-tabpane.c_tabs-tab_inactive
              .recent-user-w > div > .c_stream > .c_stream-content
                .c_stream-item-w > .alluser-item-content > .alluser-item
    .panel-content-left
      .chat-wrap
        .chat-head
        .chat-content-w
          #t-chat-scroll.chat-scroll-wrap
            .sc-kEYyzF.geuhpn > .c-wrap > .c-c
          .editor-hori-divider
          .chat-foot > .EditorWrapper
            ul.quick-emoji-w.t-quick-emoji
            .chat-foot-tool
            .pell-editor-wrapper > .EditorContent[contenteditable=true]
            .EditorFoot > .SendButtonGroup
              span.send-button
              span.SendButton-icon
              .set-key-w
    .phrase-wrap
  .plugin-wrap
```

`.sc-kEYyzF.geuhpn` 是本次观察值，不能假定为稳定定位属性。
页面有一个无 src 属性的 iframe；当前编辑器在主文档中。

## 与现有模拟页的重要差异

- 真实编辑器为 `<div class="EditorContent " contenteditable="true"><br></div>`，没有 id 或 textbox role。
- 真实发送元素为 `span.send-button`，没有 button role。按钮组另有发送快捷键菜单。
- 真实导航项为 `.c_tabs-tab`，没有 tab role；当前项带 `.c_tabs-tab_check`。
- 非当前面板带 `.c_tabs-tab_inactive`，其内容仍在 DOM 中。不可无条件遍历全部 `.c_stream-content`。
- 最近联系人节点为 `.c_stream-item-w > .alluser-item-content > .alluser-item`，并非模拟页的 `.c_stream-item`。
- 最近联系人姓名在 `.alluser-item-name`，日期在 `.alluser-item-date-w`，预览在 `.alluser-item-breifdesc`。保留原拼写 breif。
- 正文容器有多层包装，不是模拟页的 `#wrap > div`。
- 模拟页专用的 `#header`、`#editor`、`#send` 及人为添加的 ARIA role 不能作为真实适配依据。

## 本次布局测量

视口为 1146 x 958；尺寸只表示当前布局，不代表所有分辨率下的规则。

| 区域 | x | 宽度 | 高度 |
| --- | ---: | ---: | ---: |
| 左导航 | 0 | 70 | 958 |
| 会话栏 | 70 | 300 | 958 |
| 聊天栏 | 370 | 400 | 958 |
| 快捷话术栏 | 770 | 250 | 958 |
| 插件栏 | 1020 | 126 | 958 |

聊天头部高 81，编辑区域高 200；输入框在 y=833，高 85。
左导航背景 rgb(0, 131, 255)，聊天正文背景 rgb(243, 244, 244)。
字体为 Segoe WPC / Segoe UI / sans-serif，主要文本 14px，话术栏 12px。

## 尚未采集

- 当前咨询和留言中有客户时的节点结构、未读标记及分组展开行为。
- 独立图片消息的完整节点（已看到的非头像图片属于商品卡片错误占位，不能当作图片消息样本）。
- 消息更新、历史加载、输入和发送过程中的 DOM 变化。
- 完整样式、图标资源及不同窗口尺寸下的布局规则。

以上未采集部分不能从空会话状态推断，也不代表已经完成一比一复刻。

## 历史咨询实测补充

同日通过 Codex 内置浏览器点击“历史咨询”，再依次打开三个历史联系人。只查看，没有填写编辑器或发送消息。以下仅记录结构，不保存客户身份、消息正文或资源地址。

- 历史导航使用 `#t-alluser-wrap .c_tabs-nav-container > .c_tabs-tab[title="历史咨询"]`，可以直接用 Playwright DOM 点击。
- 列表显示最近联系人；可见行当前宽 299、高 60。当前项包含 `alluser-item_check t-item-ck alluser-current`。隐藏面板也有联系人节点，测量和定位必须限定可见面板。
- 点击联系人后 `.chat-head-name` 先改变；第一次即时快照消息区仍为空，后续快照才出现消息。标题变化不能独立证明消息加载完成。
- 标题位于 `.chat-head-title > .chat-head-name`，内有 `.consult-type` 和 `.chatHead-entering`。商品栏为 `.chat-product`，含 `.name` 和 `.copy-link`。
- 消息所在结构是 `#t-chat-scroll > div > .c-wrap > .c-c > .message`。实际滚动元素为 `.c-wrap`，一次测得 clientHeight=677、scrollHeight=1041、scrollTop=364。
- 每个 `.message` 中的方向节点为 `.message_left`（客户）或 `.message_right`（客服），带 `s_` 前缀消息 id，可作为候选去重键，但其跨会话及重载稳定性仍需验证。
- 方向节点包含 `.message__nickname > .message__time_str`、`img.message__avatar` 以及正文包装层。
- 文字为 `pre.message__text > span.message__content`，按方向另带 `.message__text_left` 或 `.message__text_right`。读取整个气泡会混入姓名、时间、已读，正文应定位 `.message__content`。
- 客服气泡内 `.message__read_status.read` 表示已读。链接在正文内为 `a.msg-link.editor-text`。
- 中间分隔记录为 `.message_center > .message_componet-center`，包含 `.last-chat-divider`。系统记录也可能使用独立 `.message__system_wrap > .message__system_box`，不能只按 `.message_center` 识别系统消息；另见 `.message__system`、`.message__clickable` 和 `.message__system_custom`。
- 商品卡片为 `.message_componet-left > .CardWrapper.ProductCard`。有卡片出现 `.Error` 及占位图片，须保留加载失败场景。
- 样式中的 `sc-*` 和随机短类名属于生成类名；自动化优先使用上述语义类名。

消息气泡当前样式：左右正文 padding=5px 10px、圆角 4px；客户背景 rgb(255,255,255)，客服背景 rgb(208,233,255)。头像 36x36、圆形。姓名与时间为 12px 灰色。商品卡片 padding=10px、底部 margin=10px、圆角 4px。

本次已证实真实页面支持通过 DOM 切换历史会话、读取文字正文并识别方向、时间和消息类型。尚未验证真实发送、新消息监听、未读清除和历史翻页，也未完成前端复刻。
