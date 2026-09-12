# Chatelaine（垂佩）公开接口文档

本文说明注册数据、服务端接口和事件。首次接入请阅读[注册者接入教程](Chatelaine注册者接入教程.md)。

本开发版本直接采用 `chatelaine_api`／`chatelaine:`，接入方同步更新；不提供旧 ID 兼容、别名或存档迁移。方法中的 `Curio` 与标准类型 `chatelaine:curio` 表示通用饰品，不是原版 Curios 的运行时命名空间。

## 获取服务

适用端：服务端。接口面向受信任的行为包；客户端不直接写入装备。

```python
import mod.server.extraServerApi as serverApi

chatelaine = serverApi.GetSystem("chatelaine_api", "ChatelaineServerSystem")
if chatelaine is not None:
    status = chatelaine.GetRegistryStatus()
```

在 `LoadServerAddonScriptsAfter` 回调中同步注册。注册窗口结束后的下一 tick 冻结；收到 `ChatelaineRegistryReadyServerEvent` 或查询到 `ready=True` 后，再使用槽位数据。注册成功不等于最终注册表就绪。

| 项目 | 值 |
| --- | --- |
| System 命名空间／名称 | `chatelaine_api`／`ChatelaineServerSystem` |
| contractName／contractVersion | `chatelaine:slot_provider`／`1` |
| 注册数据 schemaVersion | `1` |

当前为未发布的开发版本，核心与接入方按同一开发版本使用。获取核心后直接注册，需要共用按压时绑定快捷装备门控；注册表就绪后使用实体装备和外观接口。

## 注册接口

### RegisterContribution

`RegisterContribution(contractName, contractVersion, providerId, payload)`

描述：提交一个提供方的完整注册数据；同一提供方再次提交会替换原贡献。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| contractName | str | 固定为 `chatelaine:slot_provider` |
| contractVersion | int | 固定为 `1` |
| providerId | str | 匹配 `^[a-z][a-z0-9_]{0,31}$`，不能使用 `chatelaine` |
| payload | dict | 下文的注册数据 |

返回值：dict。成功含 `accepted=True`、`contractVersion`、`idempotent`；失败含 `accepted=False` 和 `reason`。冻结后仅允许完全相同的幂等提交，其他变更返回 `registry_frozen`。

### 注册查询与撤回

| 接口 | 返回值与说明 |
| --- | --- |
| `UnregisterContribution(providerId)` | bool；仅可在冻结前撤回已有贡献 |
| `GetRegistryStatus()` | dict；包含 `contractName/contractVersion/providerCount/registryRevision/dirty/frozen/ready/errors/budgetUsage/budgetLimits` |
| `GetChatelaineRegistrySnapshot()` | dict；返回最终注册表的副本，使用前先检查 ready |
| `GetContributions()` | dict；按 providerId 返回规范化贡献的副本 |
| `GetEventDeliveryStatus()` | dict；包含 attempts、failureCount、failuresByEvent；每个失败事件记录 count、lastErrorType、lastError |

最终快照包含 `schemaVersion/registryRevision/typesById/pages/slotsById/itemTypesByItemId/itemsById/visualsById/attachableEntities/attachableEntitySources`。页面的 `slotIds` 指向 `slotsById`；物品的 `equippedVisualId` 指向 `visualsById`。修改副本不会修改注册表。

## 注册数据

```python
payload = {
    "schemaVersion": 1,
    "types": [],
    "pages": [],
    "items": [{
        "itemId": "your_mod:test_ring",
        "types": ["chatelaine:ring"],
        "equipOnUse": True
    }],
    "attachableEntities": []
}
```

`schemaVersion/types/pages/items` 必填；`attachableEntities` 可省略。数据只接受 JSON 可表达的值；Python 中使用 `True/False`，不能传字符串代替布尔值。未定义字段会被拒绝。

### 标准槽

直接引用标准类型即可，不要重新声明它们。只有被有效物品映射使用的标准类型才会激活对应槽位；标准页面为 `chatelaine:standard`，每槽容量为 1。

| typeId | slotId |
| --- | --- |
| `chatelaine:head` | `chatelaine:head` |
| `chatelaine:necklace` | `chatelaine:necklace` |
| `chatelaine:back` | `chatelaine:back` |
| `chatelaine:body` | `chatelaine:body` |
| `chatelaine:hands` | `chatelaine:hands_1`、`chatelaine:hands_2` |
| `chatelaine:bracelet` | `chatelaine:bracelet` |
| `chatelaine:ring` | `chatelaine:ring_1`、`chatelaine:ring_2` |
| `chatelaine:belt` | `chatelaine:belt` |
| `chatelaine:charm` | `chatelaine:charm` |
| `chatelaine:curio` | `chatelaine:curio` |

### 自定义类型、页面与槽

| 对象 | 必填字段 | 可选字段 |
| --- | --- | --- |
| types 元素 | `typeId`、`label` | 无 |
| pages 元素 | `pageId`、`label`、`slots` | `order=0` |
| slots 元素 | `slotId`、`label`、`acceptedTypes` | `order=0`、`maxStack=1`、`emptyTexture=""` |

自建的 typeId、pageId、slotId 必须以 `providerId:` 开头。label 最长 64 字符；order 为非负整数，页面和槽分别按 `(order, ID)` 排序。每页 1～16 槽，maxStack 为 1～64；实际容量还受物品原生堆叠上限限制。

`acceptedTypes` 为无重复的非空类型列表。物品 types 与槽 acceptedTypes 有交集即可佩戴。emptyTexture 使用资源包内 `textures/...` 路径，不带 `.png`；使用自己的纹理路径，避免覆盖其他包。

### 物品映射

| 字段 | 类型／默认值 | 说明 |
| --- | --- | --- |
| itemId | str，必填 | 已存在的物品 identifier，可映射其他命名空间物品 |
| types | list，必填 | 无重复的非空类型列表 |
| equipOnUse | bool，False | 玩家使用物品时尝试快捷装备一件 |
| quickEquipDecision | bool，False | 启用同步资格裁决；同时要求 equipOnUse=True |
| equipSound | str 或 dict | 玩家普通装备成功时的声音 |
| quickEquipSound | str 或 dict | 玩家快捷装备声音；与 equipSound 独立，省略时不播放 |
| equippedVisual | dict | 佩戴外观，可省略 |

声音可写 `"armor.equip_leather"` 或 `{"sound": "armor.equip_leather", "volume": 1.0, "pitch": 1.0}`。volume 为 0～4，pitch 为 0.01～4。玩家背包放入、槽间转移或快捷装备成功且装备栈改变时播放；单纯同类堆叠数量变化不播放。实体佩戴接口不播放这些声音。

多个提供方映射同一物品时，types 取并集，equipOnUse 取逻辑或，资格裁决汇总所有声明方。相互冲突的声音、外观或资源别名会使最终化失败，不按加载顺序覆盖。

### 数量与大小限制

| 范围 | 上限 |
| --- | --- |
| 提供方数量 | 32 |
| 每提供方的类型／页面／槽／物品 | 64／16／128／256 |
| 全部类型／页面／槽／物品／外观 | 256／64／512／2048／256 |
| 单外观兼容槽／全部玩家外观槽组合 | 32／512 |
| 单外观实体类型覆盖／全部实体模型槽组合 | 32／512 |
| 每提供方追加附着类型／最终附着类型 | 64／256 |
| 单贡献／完整注册表 | 128 KiB／512 KiB |
| 玩家或实体外观注册数据 | 各 384 KiB |

大小按 UTF-8 JSON 计算；更多实时占用可查询 GetRegistryStatus。资源标识和路径最长 160 字符；不能使用路径穿越、空路径段或纹理文件扩展名。

## 玩家装备接口

下列 playerId 是在线玩家运行时 ID；slotId 是完整槽 ID。物品参数为网易完整物品字典，如 `{"newItemName": "your_mod:test_ring", "count": 1, "newAuxValue": 0}`。更新已有物品时保留其余字段，空物品为 `{}`。

### 读取与准入

| 接口 | 返回值与说明 |
| --- | --- |
| `GetPlayerChatelaineSnapshot(playerId)` | dict；`schemaVersion=2/revision/slots/mouseCursor` |
| `GetPlayerChatelaineSlots(playerId)` | dict；`{slotId: itemDict}`，空槽为 `{}` |
| `GetPlayerCurioItem(playerId, slotId)` | dict；指定槽物品副本，空槽或不可读时为 `{}` |
| `GetPlayerCurioItemsByType(playerId, typeId)` | dict；返回 acceptedTypes 包含 typeId 的槽内非空物品，键为 slotId；筛选的是槽接受类型 |
| `CanEquipCurio(slotId, itemDictOrItemId)` | bool；检查注册类型是否兼容，不检查某个实例是否已初始化或槽是否为空 |
| `GetCurioSlotCapacity(slotId, itemDictOrItemId)` | int；有效容量，不兼容返回 0 |
| `GetNativeItemMaxStack(itemDictOrItemId)` | int；物品原生堆叠上限 |

getter 不初始化玩家或实体，返回值均为副本。玩家尚未就绪时快照的 slots、mouseCursor 为空；实体尚未初始化时快照为 `{}`。System 已销毁时不要继续使用旧引用。

### 转移与更新

```python
TransferInventoryToCurio(playerId, inventorySlot, slotId, takeCount)
TransferCurioToInventory(playerId, slotId, inventorySlot, takeCount)
TransferCurioToCurio(playerId, sourceSlotId, targetSlotId, takeCount)
```

描述：在玩家背包和饰品槽之间转移，或在两个饰品槽之间转移。inventorySlot 为 0～35，takeCount 为正整数；槽容量、堆叠兼容性和锁定属性均参与校验。

返回值：成功为字符串 `"ok"`，失败为原因字符串；已销毁 System 返回 False。必须用 `result == "ok"` 判断，不能直接判断字符串真假。空槽和同类堆叠按可容纳数量转移；异类交换要求完整源堆叠和反向准入均满足条件。

| 接口 | 返回值与说明 |
| --- | --- |
| `ReplacePlayerCurioItemData(playerId, slotId, itemDict)` | bool；非空更新须保持物品 ID 和数量；允许用 `{}` 清空（lock_in_slot 除外），不负责退还 |
| `ClearPlayerChatelaine(playerId, itemId=None, auxValue=None, maxCount=None)` | int 或 None；返回实际清除件数，参数错误或保存失败为 None；maxCount、auxValue 只能为非负整数，None 不限制 |
| `SyncPlayerChatelaineInventory(playerId, result="external_change")` | 无业务返回值；刷新已打开的饰品背包界面，不保存装备，也不替代转移接口 |

ClearPlayerChatelaine 清理饰品槽，不清理鼠标持有物；0 表示没有清除任何物品，不能当作调用失败。玩家死亡按 keepInventory 处理饰品槽及鼠标持有物。移除提供方前应取出物品或完成迁移，当前玩家失效槽不会自动退还。

也可使用 `game_directors` 权限的自定义命令；target 必填，仅处理在线玩家，后三项省略时不限制，auxvalue 和 maxcount 必须非负：

```text
/chatelaine_clear <target> [newitemname] [auxvalue] [maxcount]
/chatelaine_clear @s your_mod:test_ring 0 1
```

### 物品图标

Chatelaine 背包支持网易物品 Layer 图标，覆盖经典／触屏格子、鼠标持有物和快捷移动动画。图层由物品渲染数据决定，无需另行注册 Chatelaine 字段；其他模组的界面需自行适配，原生飞行图标不因 Chatelaine 支持而自动改变。

## 非玩家装备接口

适用对象：存活且引擎类型含 `Mob` 的非玩家实体。所有实体不会自动获得槽位，也不需要先注册实体类型佩戴白名单；由服务端选定具体实例并初始化。模型名单只决定外观回退，不决定佩戴资格。

| 接口 | 返回值与说明 |
| --- | --- |
| `InitializeEntityChatelaine(entityId, slotIds)` | bool；slotIds 为无重复的已注册槽 ID 列表，可为空。首次建立记录；已有记录则恢复它，忽略所传槽布局，不覆盖物品 |
| `GetEntityChatelaineSnapshot(entityId)` | dict；`schemaVersion=1/revision/slots`；不可读时为 `{}` |
| `GetEntityCurioItem(entityId, slotId)` | dict；只返回当前准入有效的物品；未知槽或失效物品返回 `{}` |
| `ConfigureEntityChatelaineSlots(entityId, slotIds, expectedRevision)` | 结果 dict；修改实例槽集合；不允许删除仍有物品的槽 |
| `ExchangeEntityCurioItem(entityId, slotId, itemDict, expectedRevision)` | 结果 dict；放入、换装或传 `{}` 取下；受锁定规则约束 |
| `ReplaceEntityCurioItemData(entityId, slotId, itemDict, expectedRevision)` | 结果 dict；更新已有物品数据，必须保持非空、同 ID、同数量 |

expectedRevision 为刚读到的快照 revision 整数。三个写接口均返回 `{"success": bool, "reason": str, "revision": int或None}`；成功 Exchange 和 Replace 另含 `previousItem`。销毁后的旧 System 返回 `{}`，调用方用 `result.get("success") is True` 判断。

常见 reason：`ok`、`unchanged`、`revision_conflict`、`not_ready`、`invalid_slots`、`occupied_slot`、`unknown_slot`、`invalid_item`、`item_rejected`、`identity_changed`、`item_locked`、`save_failed`。修订冲突时重新读取并重新决定动作，不能直接重复交付物品。

已有记录随实体加载恢复；新生实体仍需显式初始化。完整快照保留失效槽和物品以便回收，但准入读取及外观不使用失效物品。不要通过反复 Initialize 修改布局，它会重新采用记录并重置临时外观状态。

Exchange 不扣除玩家背包，也不自动投递旧物品；提供方负责物品来源和交接。Replace 的 previousItem 仅用于比较，`unchanged` 也没有产生可退还的新物品。Chatelaine 不提供实体装备 UI、出生配装、死亡掉落、AI 或饰品效果。

## 外观配置

将 equippedVisual 放在物品映射中。Chatelaine 读取声明并挂接提供方资源，不生成模型，也不自动匹配骨骼。

### 玩家第三人称与第一人称

| 字段 | 必填／默认值 | 说明 |
| --- | --- | --- |
| visualId | 必填 | `providerId:名称` |
| geometry | 必填 | `{"key": "your_mod_relic_geo", "resource": "geometry.your_mod.relic"}` |
| textures | 必填，非空 list | 元素为 key/resource，resource 使用 `textures/...` |
| materials | 必填，非空 list | 元素为 key/resource，如 `entity_alphatest` |
| renderController | 必填 | `controller.render.*` 资源名 |
| animations | 默认 [] | 元素必含 key/resource/state/layer；resource 为 `animation.*` |
| animationControllers | 默认 [] | 元素必含 key/resource/attach；resource 为 `controller.animation.*` |
| firstPerson | 默认 False | False 或独立资源对象；不能写 True |
| nativeSlotBlock | 默认无 | 玩家原生装备遮挡规则 |
| entity | 默认启用 | 非玩家设置，见下一节 |

key 是宿主上的资源别名，必须以 `providerId_` 开头；同一有效模型内不得冲突，不同外观也不能占用同类别别名。提供方 RP 中的 geometry、控制器等应引用对应别名。

动画控制器的 attach 支持 `{"mode": "state", "controller": "root", "state": "default"}` 或 `{"mode": "script_animate", "autoReplace": False}`。state/layer 和资源需由提供方保证有效。

firstPerson 对象必含 geometry/textures/materials/renderController，可选 animations/animationControllers；同类别 key 与第三人称不得重复。基础资源仅用于第三人称，独立对象用于第一人称。

nativeSlotBlock 格式为 `{"slots": ["chest"], "operator": "or"}`。slots 允许 `mainhand/offhand/head/chest/legs/feet`；or 表示任一槽有物品即隐藏，and 表示所有所列槽都有物品才隐藏。空列表不遮挡。

### 实体模型与附着类型

`equippedVisual.entity` 可含：

| 字段 | 默认值 | 说明 |
| --- | --- | --- |
| enabled | True | False 禁用该外观的非玩家显示 |
| modelsByEntity | {} | 按 `namespace:实体类型` 指定模型，不是运行时 entityId |
| renderControllersBySlot | 无 | 按完整 slotId 指定独立 render controller |

模型选择顺序：

1. entity.enabled 为 False 时不显示。
2. 命中 modelsByEntity 的精确类型时使用该模型，无需加入附着名单。
3. 未命中且类型在注册表 attachableEntities 中时，使用玩家第三人称基础资源。
4. 其余情况不显示；佩戴数据仍保留。显隐开关不能绕过模型条件。

modelsByEntity 的每个值可覆盖 geometry/textures/materials/animations/animationControllers/renderController/renderControllersBySlot。省略字段继承基础资源，数组整体替换。实体动画及动画控制器元素只接受 key/resource/可选 condition，condition 默认为 `"1.0"`；不使用玩家的 state/layer/attach。基础资源回退也不继承这些玩家挂接字段、第一人称或 nativeSlotBlock。**非玩家不支持原生盔甲遮挡**。

默认同外观的多个槽合并显示一个模型，任一槽可见即显示。需要独立多模型时，renderControllersBySlot 必须覆盖该模型全部兼容槽，且控制器资源名互异；可在 entity 层统一声明，或在某个类型模型中覆盖。玩家链仍按槽显示独立实例。

顶层 `attachableEntities` 是提供方对资源包中 `enable_attachables=True` 的声明，只追加默认模型回退资格，不修改实体 JSON。允许声明其他命名空间类型；禁止玩家、通配符和重复项。最终名单取并集，来源记录在 `attachableEntitySources`，原版来源为 `chatelaine`。

当前内置以下 20 个非玩家类型，均以 `minecraft:` 为前缀：

```text
allay、armor_stand、bogged、copper_golem、drowned、happy_ghast、
husk、piglin、piglin_brute、pillager、skeleton、stray、vindicator、
warden、wither_skeleton、wolf、zombie、zombie_pigman、
zombie_villager、zombie_villager_v2
```

该目录不保证目标客户端可生成每种生物；也不会因其他资源包改写 enable_attachables 而自动更新。以最终快照名单和实际资源为准。

### 运行时显隐

| 玩家接口 | 非玩家接口 |
| --- | --- |
| `SetCurioSlotVisualEnabled(playerId, slotId, enabled)` | `SetEntityCurioSlotVisualEnabled(entityId, slotId, enabled)` |
| `ResetCurioSlotVisualEnabled(playerId, slotId)` | `ResetEntityCurioSlotVisualEnabled(entityId, slotId)` |
| `GetCurioSlotVisualState(playerId, slotId)` | `GetEntityCurioSlotVisualState(entityId, slotId)` |
| `RefreshPlayerCurioVisuals(playerId, nativeOverrides=None)` | `RefreshEntityCurioVisuals(entityId)` |

Set／Reset 返回 bool，enabled 必须为 bool；Reset 恢复默认显示。非玩家须已初始化且拥有该槽。开关不持久化，隐藏不取下物品、不停止效果。非玩家空槽保留开关，删除槽或重新采用实例后重置；玩家重新加入后由提供方重设需要的开关。

Get 返回状态 dict：通用字段 `itemId/visualId/visible/slotDisplayEnabled/slotId/visualRevision`；玩家另含 playerId、blockedByNativeSlots；实体另含 entityId、modelKey、coreEpoch、entityGeneration、equipmentRevision。非玩家不可读时返回 `{}`。

Refresh 重算外观。玩家返回是否发出更新；状态未改变也可返回 False。nativeOverrides 是 `{原生槽名: itemDict}`，只用于本次占用判断。实体返回是否完成刷新；外部改变实体类型或维度后可主动调用。状态 visible 表示服务端允许显示，不证明客户端资源已加载或模型已正确贴合。

## 快捷装备裁决

`SetQuickEquipDecision(requestId, providerId, itemId, allowed)`

描述：在 ChatelaineQuickEquipDecisionServerEvent 的当前回调内同步提交 bool 裁决。返回 bool 表示裁决是否被接收。所有 decisionProviders 必须明确允许；缺回复、否决或事件分发失败均不装备。已提交 False 不能在本请求中改回 True。

快捷装备优先叠加，再使用空槽，最后尝试交换；成功才取消本次原生使用。该裁决不自动限制背包手动转移和服务端写入。

### 共用按压门控

`SetQuickEquipPressGate(gateId, claim, shouldCancel, markCancel, yieldClaim)`、`ClearQuickEquipPressGate(gateId)` 均返回 bool。仅在宿主需要多个功能共用一次按压时使用；Chatelaine 不替宿主管理输入生命周期。

四个回调均接收 `(playerId, owner)`，owner 固定为 `chatelaine_quick_equip`：

| 回调 | 用途 |
| --- | --- |
| claim | 先记录尝试，再返回是否允许，避免同步重入重复执行 |
| shouldCancel | claim 失败时返回是否仍应取消原生使用 |
| markCancel | 所有提供方允许后、装备事务前，记录取消标记 |
| yieldClaim | 否决或装备失败时让出动作所有权、清除取消标记，保留本按压的尝试记录 |

同一时刻仅一个 gateId 可绑定，同 ID 可重绑，其他 ID 返回 False。宿主销毁时 Clear；ID 不匹配不能清除他人的绑定。

## 服务端事件

统一监听来源：`chatelaine_api`／`ChatelaineServerSystem`。

| 事件名 | 参数 | 触发时机 |
| --- | --- | --- |
| ChatelaineRegistryReadyServerEvent | registryRevision、providerCount | 注册表最终化成功 |
| ChatelainePlayerSlotChangedServerEvent | playerId、slotId、oldItem、newItem、revision、reason | 玩家槽变更提交后 |
| ChatelainePlayerSlotsReconciledServerEvent | playerId、revision、slots | 玩家加载协调改变槽数据后 |
| ChatelaineQuickEquipDecisionServerEvent | requestId、playerId、itemId、itemDict、decisionProviders | 快捷装备前同步裁决 |
| ChatelaineEntitySlotsChangedServerEvent | entityId、revision、slots、reason | 实体采用记录或变更提交后；reason 为 adopt/configure/exchange/item_data |

除同步裁决外，事件用于通知已发生的结果，不是可取消事件。多个槽变更可共享同一个 revision。监听器失败不会撤销已提交装备；需要恢复业务状态时重新读取快照，并用 GetEventDeliveryStatus 查看通知失败情况。
