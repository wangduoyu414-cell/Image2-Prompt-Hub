# GPT Image 2 提示词案例库 · 总目录索引

本目录是为 `gpt-image-2` Skill 编写的**典型提示词案例库**：每个 `references/` 下的模板都对应 `prompts/<category>/<template-name>/` 下的一个目录，目录里给出 1–3 条可直接交给图像模型出图的真实提示词案例（每条一个独立 JSON 文件）。

**说明：** 本目录不是模板本身，而是模板的「已填好参数、可直接复用」版本，可作为：

- 文章配图素材（每条提示词 → 一张文章配图）
- 模板效果对照（用于评估与回归）
- 团队内部 prompt benchmark

索引底部还附带机器可读的 [`_mapping.json`](./_mapping.json)，记录「模板 ↔ JSON 文件」的完整映射，可被脚本直接消费。

---

## 总览

| 分类 | 模板数 | 案例数 | 图片进度 |
|---|---|---|---|
| ui-mockups | 5 | 13 | ✅ 13 / 13 |
| product-visuals | 5 | 10 | ✅ 10 / 10 |
| maps | 4 | 8 | ✅ 8 / 8 |
| slides-and-visual-docs | 4 | 8 | ✅ 8 / 8 |
| poster-and-campaigns | 4 | 8 | ✅ 8 / 8 |
| portraits-and-characters | 4 | 8 | ✅ 8 / 8 |
| scenes-and-illustrations | 4 | 8 | ✅ 8 / 8 |
| editing-workflows | 5 | 10 | ✅ 10 / 10 |
| avatars-and-profile | 5 | 10 | ✅ 10 / 10 |
| storyboards-and-sequences | 5 | 10 | ✅ 10 / 10 |
| grids-and-collages | 4 | 8 | ✅ 8 / 8 |
| branding-and-packaging | 4 | 8 | ✅ 8 / 8 |
| typography-and-text-layout | 2 | 4 | ✅ 4 / 4 |
| assets-and-props | 2 | 4 | ✅ 4 / 4 |
| academic-figures | 9 | 18 | ✅ 18 / 18 |
| infographics | 6 | 12 | ✅ 12 / 12 |
| technical-diagrams | 7 | 14 | ✅ 14 / 14 |
| **合计** | **79** | **161** | **✅ 161 / 161** |

模板根目录：`<skill>/references/`  
提示词根目录：`prompts/`  
图片根目录：`prompts/`（与提示词文件同目录、同名，仅扩展名为 `.png`）

---

## 1. UI Mockups（界面样机）

各种「界面 + 内容」的样机视觉。

### 1.1 电商直播 / 社交直播 UI 样机

- **模板简介**：电商 / 社交直播带货截图样机（主播 + 聊天区 + 礼物区 + 商品卡）。
- **模板路径**：[`references/ui-mockups/live-commerce-ui.md`](../references/ui-mockups/live-commerce-ui.md)
- **提示词目录**：[`prompts/ui-mockups/live-commerce-ui/`](./ui-mockups/live-commerce-ui/)
- **图片进度**：✅ 2 / 2
- **案例**：

  | # | 提示词 | 图片 | 案例标题 | 简介 |
  |---|---|---|---|---|
  | 1 | [`1.json`](./ui-mockups/live-commerce-ui/1.json) | [`1.png`](./ui-mockups/live-commerce-ui/1.png) | Elon Musk 直播带 Cybertruck（科技带货旗舰场景） | 典型的"科技公司创始人本人下场带货"场景，主播是 Elon Musk，商品是 Tesla Cybertruck，整体氛围既像真实直播截图，又有发布会主视觉的高级感。是该模板最具代表性的旗舰用例。 |
  | 2 | [`2.json`](./ui-mockups/live-commerce-ui/2.json) | [`2.png`](./ui-mockups/live-commerce-ui/2.png) | Taylor Swift 直播开箱限定香水（明星个人 IP 带货） | 明星个人 IP 跨界美妆带货的典型场景。商品紧扣明星人设、聊天与礼物文案围绕粉丝向语言展开，是该模板"明星 + 美妆 / 文创"方向的代表用例。 |

### 1.2 社交平台界面样机

- **模板简介**：社交平台动态详情页样机（Twitter/X、小红书、微博、Threads 等）。
- **模板路径**：[`references/ui-mockups/social-interface-mockup.md`](../references/ui-mockups/social-interface-mockup.md)
- **提示词目录**：[`prompts/ui-mockups/social-interface-mockup/`](./ui-mockups/social-interface-mockup/)
- **图片进度**：✅ 3 / 3
- **案例**：

  | # | 提示词 | 图片 | 案例标题 | 简介 |
  |---|---|---|---|---|
  | 1 | [`1.json`](./ui-mockups/social-interface-mockup/1.json) | [`1.png`](./ui-mockups/social-interface-mockup/1.png) | Elon Musk 在 X 上发火星殖民推文（Twitter / X 暗色模式） | 典型的"知名科技人物在 X 上发布一条带配图的高互动推文"场景，深色模式 + 中文界面 + 多图九宫格，是该模板最具传播力的代表案例。 |
  | 2 | [`2.json`](./ui-mockups/social-interface-mockup/2.json) | [`2.png`](./ui-mockups/social-interface-mockup/2.png) | 小红书风格上海 City Walk 笔记（浅色模式） | 典型小红书图文笔记详情页，亲切、生活化、带 4 张可滑动配图。是该模板"内容创作者 + 生活方式"方向的代表案例。 |
  | 3 | [`3.json`](./ui-mockups/social-interface-mockup/3.json) | [`3.png`](./ui-mockups/social-interface-mockup/3.png) | Anthropic 官方账号在 X 上发布 Claude Opus 4.7（品牌官方公告） | 科技品牌账号在 X 上发布产品更新公告的典型场景，浅色模式 + 高互动量级 + 单图发布主视觉，是该模板"品牌官方账号"方向的代表案例。 |

### 1.3 商品卡叠加样机

- **模板简介**：落地页 hero / 详情页主图（人物 + 商品 + 卖点 + 价格）。
- **模板路径**：[`references/ui-mockups/product-card-overlay.md`](../references/ui-mockups/product-card-overlay.md)
- **提示词目录**：[`prompts/ui-mockups/product-card-overlay/`](./ui-mockups/product-card-overlay/)
- **图片进度**：✅ 2 / 2
- **案例**：

  | # | 提示词 | 图片 | 案例标题 | 简介 |
  |---|---|---|---|---|
  | 1 | [`1.json`](./ui-mockups/product-card-overlay/1.json) | [`1.png`](./ui-mockups/product-card-overlay/1.png) | DERMA CALM 敏感肌精华 — 临床感落地页 hero（女性向护肤） | 典型的"敏感肌护肤品牌"电商详情页主视觉，三栏结构 + 临床感配色 + 模特 + 产品 + 卖点徽章，是该模板最具代表性的女性向护肤用例。 |
  | 2 | [`2.json`](./ui-mockups/product-card-overlay/2.json) | [`2.png`](./ui-mockups/product-card-overlay/2.png) | NEX SKIN 男士护肤暗色科技款落地页（男性向数码感） | 男士护肤品牌的暗色科技感 hero 主视觉，硬朗、专业、可信赖，底部带销量条。是该模板"男性向 / 数码感"方向的代表用例。 |

### 1.4 聊天界面 / 对话气泡场景

- **模板简介**：聊天 / 对话界面样机（微信、AI 助手、群聊）。
- **模板路径**：[`references/ui-mockups/chat-interface-scene.md`](../references/ui-mockups/chat-interface-scene.md)
- **提示词目录**：[`prompts/ui-mockups/chat-interface-scene/`](./ui-mockups/chat-interface-scene/)
- **图片进度**：✅ 3 / 3
- **案例**：

  | # | 提示词 | 图片 | 案例标题 | 简介 |
  |---|---|---|---|---|
  | 1 | [`1.json`](./ui-mockups/chat-interface-scene/1.json) | [`1.png`](./ui-mockups/chat-interface-scene/1.png) | 微信双人聊天 — Elon Musk × Mark Zuckerberg "八角笼约架"对话 | 复刻 2023 年硅谷顶流梗——Elon 提出和 Zuck 在八角笼里 cage match，Zuck 回复 "send location"。这里把它搬到中文微信场景：Elon Musk 用中英混合发挑衅，Zuck 一本正经技术宅式接招，包含文字、语音条、Cybertruck 自拍、定位卡片、表情包等典型微信元素。… |
  | 2 | [`2.json`](./ui-mockups/chat-interface-scene/2.json) | [`2.png`](./ui-mockups/chat-interface-scene/2.png) | 硅谷 CEO 微信群聊 — 「Tech CEO 互助会 (8)」深夜吐槽现场 | 把"产品组日常"升级成顶配名人群聊——Tim Cook、Sundar Pichai、Sam Altman、Jensen Huang、Mark Zuckerberg、Satya Nadella、Jeff Bezos 都在群里，本机视角是 Elon Musk。内容是周五深夜大家互相吐槽：GPU 不够用、Vision P… |
  | 3 | [`3.json`](./ui-mockups/chat-interface-scene/3.json) | [`3.png`](./ui-mockups/chat-interface-scene/3.png) | Claude Opus 4.7 AI 助手对话 — 帮 Elon Musk 整理"硅谷 CEO 群"周报 | 典型的 AI 助手桌面产品截图，用户视角是 Elon Musk，把案例 2 的群聊上下文丢给 Claude，让它帮整理成"硅谷 drama 周报"。包含用户提问、Claude 结构化回答、再次追问让 Claude 改写成 Twitter / X 推文。是该模板"AI 产品演示 + 名人使用场景"方向的代表案例。 |

### 1.5 短视频封面 / Stream 缩略图 UI

- **模板简介**：短视频封面 / 直播缩略图（YouTube、抖音、B 站、VTuber stream）。
- **模板路径**：[`references/ui-mockups/short-video-cover-ui.md`](../references/ui-mockups/short-video-cover-ui.md)
- **提示词目录**：[`prompts/ui-mockups/short-video-cover-ui/`](./ui-mockups/short-video-cover-ui/)
- **图片进度**：✅ 3 / 3
- **案例**：

  | # | 提示词 | 图片 | 案例标题 | 简介 |
  |---|---|---|---|---|
  | 1 | [`1.json`](./ui-mockups/short-video-cover-ui/1.json) | [`1.png`](./ui-mockups/short-video-cover-ui/1.png) | 知识科普封面 — 「99% 的人都不知道的 Claude 用法」（高对比醒目风） | 典型的"知识科普 / 工具教程"短视频封面，深色渐变 + 高亮黄标题 + 主体人物 + 三条要点，是该模板最具代表性的"高点击率知识号"用例。 |
  | 2 | [`2.json`](./ui-mockups/short-video-cover-ui/2.json) | [`2.png`](./ui-mockups/short-video-cover-ui/2.png) | 可爱风 VTuber 直播预告封面 — 「樱粉杂谈直播」 | 典型的女性 VTuber 直播开播预告封面，粉色主调 + 卡通主播 + 多层文字丝带，是该模板"VTuber / 主播预告"方向的代表案例。 |
  | 3 | [`3.json`](./ui-mockups/short-video-cover-ui/3.json) | [`3.png`](./ui-mockups/short-video-cover-ui/3.png) | 开箱评测封面 — 「我把 Vision Pro 2 拆了」（强诱因） | 典型的 YouTube 数码博主开箱评测视频封面，主体半身 + 神秘包装盒 + 强好奇感标题。是该模板"开箱评测"方向的代表案例。 |

---

## 2. Product Visuals（产品视觉）

以商品为视觉中心的图。

### 2.1 产品爆炸视图海报

- **模板简介**：产品爆炸视图海报（主体垂直堆叠 + callout + 顶部 logo + 底部品牌区）。
- **模板路径**：[`references/product-visuals/exploded-view-poster.md`](../references/product-visuals/exploded-view-poster.md)
- **提示词目录**：[`prompts/product-visuals/exploded-view-poster/`](./product-visuals/exploded-view-poster/)
- **图片进度**：✅ 2 / 2
- **案例**：

  | # | 提示词 | 图片 | 案例标题 | 简介 |
  |---|---|---|---|---|
  | 1 | [`1.json`](./product-visuals/exploded-view-poster/1.json) | [`1.png`](./product-visuals/exploded-view-poster/1.png) | Tesla Cybertruck 工程结构爆炸主视觉 | 电动皮卡品类里最具辨识度的不锈钢蒙皮与线控架构，适合作为「硬核工程 + 发布会主视觉」的代表；九层垂直展开、左右双语式技术标注，突出结构进化与品牌叙事。 |
  | 2 | [`2.json`](./product-visuals/exploded-view-poster/2.json) | [`2.png`](./product-visuals/exploded-view-poster/2.png) | Apple Vision Pro 2 头显光机与算力模块爆炸主视觉 | 空间计算品类的代表形态；Pancake 光路、眼动与透视传感器、M 系列系留算力等分层，适合作为「近眼显示 + 工程拆解」主视觉，与深紫极光背景形成科技仪式感。 |

### 2.2 白底产品图

- **模板简介**：电商纯白底主图（单品 / 多角度 / 极简营销叠层）。
- **模板路径**：[`references/product-visuals/white-background-product.md`](../references/product-visuals/white-background-product.md)
- **提示词目录**：[`prompts/product-visuals/white-background-product/`](./product-visuals/white-background-product/)
- **图片进度**：✅ 2 / 2
- **案例**：

  | # | 提示词 | 图片 | 案例标题 | 简介 |
  |---|---|---|---|---|
  | 1 | [`1.json`](./product-visuals/white-background-product/1.json) | [`1.png`](./product-visuals/white-background-product/1.png) | AirPods Pro 3 单品白底主图（数码耳机典型） | TWS 降噪耳机类目里最常见的上架主图需求：充电盒与耳机本体的材质、合模线、闪电口与耳塞细节需清晰可辨，白底无道具，适合作为 Apple 系配件店与平台首图规范参考。 |
  | 2 | [`2.json`](./product-visuals/white-background-product/2.json) | [`2.png`](./product-visuals/white-background-product/2.png) | Dyson Supersonic Nural 吹风机白底主图（小家电典型） | 高端小家电常需「科技灰 + 金属环 + 进风口细节」在同一张白底里交代清楚；本案例强调主机 + 磁吸风嘴组合，适合品牌旗舰店与京东家电首图。 |

### 2.3 高级影棚商业产品图

- **模板简介**：高级影棚商业产品图（杂志广告级氛围）。
- **模板路径**：[`references/product-visuals/premium-studio-product.md`](../references/product-visuals/premium-studio-product.md)
- **提示词目录**：[`prompts/product-visuals/premium-studio-product/`](./product-visuals/premium-studio-product/)
- **图片进度**：✅ 2 / 2
- **案例**：

  | # | 提示词 | 图片 | 案例标题 | 简介 |
  |---|---|---|---|---|
  | 1 | [`1.json`](./product-visuals/premium-studio-product/1.json) | [`1.png`](./product-visuals/premium-studio-product/1.png) | 海蓝之谜（La Mer）经典面霜单页主视觉 | 高端护肤面霜品类里最具符号性的瓷瓶、薄荷绿与烫银字，配合丝绒与暗角暖光，呈现「可上杂志跨页」的 luxury still life，强调质地叙事而非白底平铺。 |
  | 2 | [`2.json`](./product-visuals/premium-studio-product/2.json) | [`2.png`](./product-visuals/premium-studio-product/2.png) | Rolex 星期日历型 40 暗调金表影棚主视觉 | 奢侈品腕表在暗调高反差下的金壳、总统链与表盘细节，是「影棚 + 无 lifestyle」的教科书级用例；适合官网 hero、平面投放与经销商灯箱。 |

### 2.4 礼盒 / 包装展示图

- **模板简介**：礼盒 / 包装展示图（外盒 + 内容物展示）。
- **模板路径**：[`references/product-visuals/packaging-showcase.md`](../references/product-visuals/packaging-showcase.md)
- **提示词目录**：[`prompts/product-visuals/packaging-showcase/`](./product-visuals/packaging-showcase/)
- **图片进度**：✅ 2 / 2
- **案例**：

  | # | 提示词 | 图片 | 案例标题 | 简介 |
  |---|---|---|---|---|
  | 1 | [`1.json`](./product-visuals/packaging-showcase/1.json) | [`1.png`](./product-visuals/packaging-showcase/1.png) | iPhone 16 Pro 首发套装式包装展示 | 数码旗舰常见「黑底白字 + 撕膜体验」的礼盒叙事；本案例以深空黑硬盒、开盖泡棉位与主机、线缆、说明卡同屏呈现，适合电商首屏与开箱活动主视觉。 |
  | 2 | [`2.json`](./product-visuals/packaging-showcase/2.json) | [`2.png`](./product-visuals/packaging-showcase/2.png) | 星巴克中国「冬悦」节日礼盒 | 食品零售节日档典型「中国红 + 咖啡绿 + 烫金」组合；本案例为双杯装咖啡豆 + 马克杯 + 星礼卡，适合门店橱窗与礼赠电商页。 |

### 2.5 生活方式产品场景图

- **模板简介**：生活方式产品场景图（商品出现在真实场景中）。
- **模板路径**：[`references/product-visuals/lifestyle-product-scene.md`](../references/product-visuals/lifestyle-product-scene.md)
- **提示词目录**：[`prompts/product-visuals/lifestyle-product-scene/`](./product-visuals/lifestyle-product-scene/)
- **图片进度**：✅ 2 / 2
- **案例**：

  | # | 提示词 | 图片 | 案例标题 | 简介 |
  |---|---|---|---|---|
  | 1 | [`1.json`](./product-visuals/lifestyle-product-scene/1.json) | [`1.png`](./product-visuals/lifestyle-product-scene/1.png) | 便携意式机与露营木桌（户外咖啡季） | 户外生活电器典型用法：晨间湖边营地、手冲级仪式感但设备为电动便携机；无具体名人入画，以器具与光营造「可上小红书封面」的克制杂志感。 |
  | 2 | [`2.json`](./product-visuals/lifestyle-product-scene/2.json) | [`2.png`](./product-visuals/lifestyle-product-scene/2.png) | Apple Watch Ultra 2 与晨跑（LeBron James 运动背影） | 运动穿戴典型「跑道 + 腕部特写可联想」的构图：以 LeBron James 晨跑中的背影与抬腕看表动作为主叙事，表盘朝读者，品牌可读，无正脸，符合运动社交传播习惯。 |

---

## 3. Maps（地图）

信息密度较高的「地图风」图像。

### 3.1 城市美食手绘地图

- **模板简介**：城市美食手绘地图（编号点位 + 图例 + 中心吉祥物）。
- **模板路径**：[`references/maps/food-map.md`](../references/maps/food-map.md)
- **提示词目录**：[`prompts/maps/food-map/`](./maps/food-map/)
- **图片进度**：✅ 2 / 2
- **案例**：

  | # | 提示词 | 图片 | 案例标题 | 简介 |
  |---|---|---|---|---|
  | 1 | [`1.json`](./maps/food-map/1.json) | [`1.png`](./maps/food-map/1.png) | 上海武康路·梧桐区周末探吃地图 | 法租界街区尺度小、店密、网感强，适合作为「单街区美食地图片」的标杆：地标与轻食/咖啡/烘焙组合，配梧桐叶与武康大楼剪影，主标题突出 City Walk + 好味。 |
  | 2 | [`2.json`](./maps/food-map/2.json) | [`2.png`](./maps/food-map/2.png) | 东京新宿·深夜拉面与居酒屋巷地图 | 高密度夜间餐饮街区：以歌舞伎町与东口拉面横丁为精神原型，用「蒸汽、红灯笼、丼、拉面、烧鸟」为符号，配日式复古羊皮纸，适合日料自媒体与赴日攻略封面。 |

### 3.2 旅行路线图

- **模板简介**：旅行路线图（多日行程 / 单日 city walk / 户外路线）。
- **模板路径**：[`references/maps/travel-route-map.md`](../references/maps/travel-route-map.md)
- **提示词目录**：[`prompts/maps/travel-route-map/`](./maps/travel-route-map/)
- **图片进度**：✅ 2 / 2
- **案例**：

  | # | 提示词 | 图片 | 案例标题 | 简介 |
  |---|---|---|---|---|
  | 1 | [`1.json`](./maps/travel-route-map/1.json) | [`1.png`](./maps/travel-route-map/1.png) | 京都三日古典慢走（机铁 + 步行为主） | 关西最经典的「少城市跳点、多点寺庙庭园与町家」的三天节奏；东西向动线不回头，适合作为旅行路线图模板的代表：手绘羊皮纸、站点小插画、侧栏条列。 |
  | 2 | [`2.json`](./maps/travel-route-map/2.json) | [`2.png`](./maps/travel-route-map/2.png) | 美国 66 号公路七日西部段（公路片气质） | 长距离自驾线模板代表：以芝加哥方向感为起点、洛杉矶方向感为收束的「中段西部七日」选段，强调路边小镇、汽旅文化与国家公园节点，用沙漠色与路牌符号强化识别。 |

### 3.3 城市风貌插画地图

- **模板简介**：城市风貌插画地图（地标 + 江山 + 文化元素）。
- **模板路径**：[`references/maps/illustrated-city-map.md`](../references/maps/illustrated-city-map.md)
- **提示词目录**：[`prompts/maps/illustrated-city-map/`](./maps/illustrated-city-map/)
- **图片进度**：✅ 2 / 2
- **案例**：

  | # | 提示词 | 图片 | 案例标题 | 简介 |
  |---|---|---|---|---|
  | 1 | [`1.json`](./maps/illustrated-city-map/1.json) | [`1.png`](./maps/illustrated-city-map/1.png) | 北京中轴线·从永定门到钟鼓楼 | 以世界遗产中轴线为叙事主轴，突出故宫、天坛、钟鼓楼与景山万春亭的南北对位，国潮与 watercolor 可并存；是「单城文化推广主视觉」的典型命题。 |
  | 2 | [`2.json`](./maps/illustrated-city-map/2.json) | [`2.png`](./maps/illustrated-city-map/2.png) | 成都·巷陌与烟火市井文化…23271 tokens truncated…rizontal double-stranded DNA duplex (3′–5′ on top, 5′–3′ bottom) in deep blue; a single guide RNA (red-orange) hybridized to the target protospacer, with a short PAM (NGG) region highlighted; Cas9 (large gray/lavender ovoid) docked to the RNP–DNA ternary complex with a wedge at the HNH and RuvC nuclease sites.

SUPPORTING ELEMENTS
(1) A magnified insert (panel b) showing phosphodiester cleavage at positions −3 and +3 relative to the PAM, with small scissor marks.
(2) A dashed branch: left path labeled “NHEJ: indels, frameshift, knockout”; right path labeled “HDR: donor template, precise knock-in (low efficiency in G1)”.
(3) A tiny 20 nt spacer + tracr repeat cartoon above Cas9, connected by thin leader lines.

ANNOTATIONS
- Use leader lines (thin black, 0.8–1.0pt) to label: target DNA, protospacer, PAM, sgRNA, Cas9, HNH, RuvC, cut sites.
- Each label 11pt sans-serif (Helvetica / Inter / Arial), sentence case, no all-caps.
- 5–6 main labels; subparts (a)(b) in 10pt bold at top-left of each panel.

EQUATIONS
- Optional one-line: none required; or small grey note “ΔG_hybrid kcal/mol (qualitative)”.
- If showing knock-in, small italic: “P_HDR ∝ f(cell cycle, exogenous donor)” in margin.

COLOR PALETTE
- 3–4 muted academic colors:
  - deep blue #1E3A8A — target DNA
  - warm orange #C2410C — gRNA
  - medium gray #475569 — Cas9 and annotation lines
  - pale yellow #FEF9C3 — PAM and donor DNA outline
- White background; print-safe grayscale.

LAYOUT
- single panel ~60% width to central cleavage; right 40% split between two repair fates, aligned to grid.
- Aspect ratio: 4:3.
- 25% whitespace, invisible alignment grid, no decorative texture.

STYLE ENFORCEMENT
- Crisp vector lines; no drop shadow, no gradient, no 3D extrusion, no stock photo.
- All text typeset, never hand-lettered.
- NO cartoon characters, NO emoji, NO “science fair” clip art.
- Read like TikZ + Illustrator, peer-review quality.

CAPTION (optional, drawn below figure)
Figure. CRISPR-Cas9 (spCas9) RNP cleaves a genomic target 3′ of the PAM, enabling indel formation via NHEJ or precise editing via HDR when a homologous donor is supplied.（中文注：PAM 依赖性的靶向切割是 Cas9 编辑的核心约束。）

