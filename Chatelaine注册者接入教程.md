# Chatelaine（垂佩）注册者接入教程

本教程使用网易 ModSDK，为 `your_mod:test_ring` 添加两个标准戒指槽，再介绍自定义槽、实体佩戴和外观。完整字段和返回值请查阅[公开接口文档](Chatelaine公开接口文档.md)。

## 1. 准备行为包和资源包

按 [README](README.md) 启用 Chatelaine 的行为包、资源包。在编辑器中创建自己的行为包和资源包，保留编辑器生成的四个不同 UUID；自己的 BP 依赖自己的 RP。不要复制 Chatelaine 的 UUID。

创建以下文件：

```text
你的行为包/
  manifest.json
  netease_items_beh/test_ring.json
  your_mod/
    __init__.py
    modMain.py
    server_system.py
你的资源包/
  manifest.json
  netease_items_res/test_ring.json
  texts/zh_CN.lang
```

Chatelaine 通过 GetSystem 提供服务，无需跨包 import。物品定义、贴图、模型和语言文件放在自己的包中。

## 2. 创建测试物品

行为包 `netease_items_beh/test_ring.json`：

```json
{
  "format_version": "1.10",
  "minecraft:item": {
    "description": {
      "identifier": "your_mod:test_ring",
      "category": "equipment"
    },
    "components": {
      "minecraft:max_stack_size": 1,
      "netease:allow_offhand": {"value": false}
    }
  }
}
```

资源包 `netease_items_res/test_ring.json`：

```json
{
  "format_version": "1.10",
  "minecraft:item": {
    "description": {
      "identifier": "your_mod:test_ring",
      "category": "equipment"
    },
    "components": {
      "minecraft:icon": "emerald",
      "minecraft:hover_text_color": "green"
    }
  }
}
```

示例复用原版绿宝石图标。资源包 `texts/zh_CN.lang` 添加：

```properties
item.your_mod:test_ring.name=测试戒指
```

## 3. 注册物品到标准槽

创建空的 `your_mod/__init__.py`。在 `your_mod/modMain.py` 中注册服务端 System：

```python
# -*- coding: utf-8 -*-
from mod.common.mod import Mod
import mod.server.extraServerApi as serverApi


@Mod.Binding(name="YourModChatelaineProvider", version="1.0.0")
class YourModChatelaineProvider(object):
    @Mod.InitServer()
    def InitServer(self):
        serverApi.RegisterSystem(
            "your_mod", "YourModServerSystem",
            "your_mod.server_system.YourModServerSystem"
        )

    @Mod.DestroyServer()
    def DestroyServer(self):
        system = serverApi.GetSystem("your_mod", "YourModServerSystem")
        if system is not None:
            system.Destroy()
```

在 `your_mod/server_system.py` 中提交注册数据：

```python
# -*- coding: utf-8 -*-
import mod.server.extraServerApi as serverApi

ServerSystem = serverApi.GetServerSystemCls()


class YourModServerSystem(ServerSystem):
    def __init__(self, namespace, systemName):
        ServerSystem.__init__(self, namespace, systemName)
        self._destroyed = False
        self.ListenForEvent(
            serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
            "LoadServerAddonScriptsAfter", self, self.OnLoaded
        )

    def OnLoaded(self, args):
        if self._destroyed:
            return
        chatelaine = serverApi.GetSystem("chatelaine_api", "ChatelaineServerSystem")
        if chatelaine is None:
            print("[YourMod] Chatelaine is not enabled")
            return
        payload = {
            "schemaVersion": 1,
            "types": [],
            "pages": [],
            "items": [{
                "itemId": "your_mod:test_ring",
                "types": ["chatelaine:ring"],
                "equipOnUse": True
            }]
        }
        result = chatelaine.RegisterContribution(
            "chatelaine:slot_provider", 1, "your_mod", payload
        )
        print("[YourMod] Chatelaine register: %s" % result)

    def Destroy(self):
        if self._destroyed:
            return
        self._destroyed = True
        self.UnListenAllEvents()
```

请在 LoadServerAddonScriptsAfter 回调内同步提交，不要延迟到定时器。注册表冻结后不能修改配置；修改代码或资源后完整重载 Addon，或退出世界重新进入。

这里引用核心的 `chatelaine:ring`，不需要在 types 中重复声明，也不需要自建页面。单独启用此示例时，就绪后应有两个槽：`chatelaine:ring_1` 和 `chatelaine:ring_2`。

## 4. 在游戏中查看结果

1. 执行 `/give @s your_mod:test_ring 1`。
2. 打开背包，通过 Chatelaine 按钮切换到饰品页，应看到两个戒指槽。
3. 将戒指放入槽内，再取回背包；手持戒指使用时应尝试快捷装备。
4. 服务端查询 GetRegistryStatus，确认 ready=True；查询 GetPlayerCurioItem 确认佩戴数据。

以上戒指示例仅提供佩戴，不附加属性或模型。需要本地运行的双包示例，可使用 [Provider Beta](provider_beta/README.md) 的[行为包](provider_beta/behavior_pack_chatelaine_provider_beta)和[资源包](provider_beta/resource_pack_chatelaine_provider_beta)；其物品 ID 为 `chatelaine_provider_beta:test_ring`，图标引用内置 `emerald`。构建分别生成核心与 Beta 两个 ZIP，每个 ZIP 根目录直接包含行为包和资源包。

## 5. 添加自己的类型和页面

需要标准槽以外的槽位时，将 OnLoaded 中的 payload 替换为以下内容。示例把同一个测试物品改为“遗物”类型：

```python
payload = {
    "schemaVersion": 1,
    "types": [{"typeId": "your_mod:relic", "label": u"遗物"}],
    "pages": [{
        "pageId": "your_mod:equipment",
        "label": u"特殊装备",
        "order": 10,
        "slots": [{
            "slotId": "your_mod:relic",
            "label": u"遗物",
            "acceptedTypes": ["your_mod:relic"],
            "maxStack": 1
        }]
    }],
    "items": [{
        "itemId": "your_mod:test_ring",
        "types": ["your_mod:relic"],
        "equipOnUse": True
    }]
}
```

自定义 ID 使用 providerId 前缀。物品 types 与槽 acceptedTypes 至少一个类型相同才能放入。每页最多 16 槽；需要空槽图标时增加 `emptyTexture: "textures/ui/your_mod/relic"` 并提供对应 PNG。

后续示例继续使用第 3 步的标准戒指槽配置。

## 6. 读取装备并接入物品效果

在自己的 System 中监听装备事件。下面的方法放入 YourModServerSystem，并在构造函数中调用一次 `ListenChatelaineChanges()`：

```python
def ListenChatelaineChanges(self):
    self.ListenForEvent(
        "chatelaine_api", "ChatelaineServerSystem",
        "ChatelainePlayerSlotChangedServerEvent", self, self.OnCurioChanged
    )

def OnCurioChanged(self, args):
    if self._destroyed:
        return
    chatelaine = serverApi.GetSystem("chatelaine_api", "ChatelaineServerSystem")
    if chatelaine is None:
        return
    item = chatelaine.GetPlayerCurioItem(args["playerId"], args["slotId"])
    print("[YourMod] equipped item: %s" % item)
    # 在这里根据当前装备更新自己的物品效果
```

玩家加载和注册表就绪时也应读取当前装备，建立效果状态；不要只依赖换装事件。实体使用 ChatelaineEntitySlotsChangedServerEvent 和 GetEntityCurioItem，效果是否支持非玩家由提供方决定。

需要从玩家背包装备时，使用核心转移接口，不要先自行删物品：

```python
result = chatelaine.TransferInventoryToCurio(player_id, inventory_slot, "chatelaine:ring_1", 1)
if result != "ok":
    print("[YourMod] equip failed: %s" % result)
```

需要修改耐久或物品自定义数据时，先读取完整物品字典，保留 ID、数量和无关字段，再调用 ReplacePlayerCurioItemData。隐藏外观不等于关闭物品效果。

## 7. 为具体实体添加槽位并佩戴

当前核心与接入方使用同一开发版本，沿用第 3 步直接注册。收到 ChatelaineRegistryReadyServerEvent，或查询 GetRegistryStatus 的 ready=True 后，再初始化实体槽位并佩戴。

以下函数给一只存活的非玩家 Mob 发放测试戒指。物品由服务端生成，不从玩家背包扣除；请仅在自己的生成或奖励流程中调用：

```python
def EquipTestRing(chatelaine, entity_id):
    snapshot = chatelaine.GetEntityChatelaineSnapshot(entity_id)
    if not snapshot:
        if not chatelaine.InitializeEntityChatelaine(entity_id, ["chatelaine:ring_1"]):
            return False
        snapshot = chatelaine.GetEntityChatelaineSnapshot(entity_id)
    slots = snapshot.get("slots", {})
    if "chatelaine:ring_1" not in slots or slots["chatelaine:ring_1"]:
        return False
    result = chatelaine.ExchangeEntityCurioItem(
        entity_id, "chatelaine:ring_1",
        {"newItemName": "your_mod:test_ring", "count": 1, "newAuxValue": 0},
        snapshot["revision"]
    )
    return result.get("success") is True
```

新实例需要初始化；已有记录会在实体加载时恢复。getter 不创建槽位，Initialize 也不修改已有布局。需要增减槽时，读取最新 revision，再调用 ConfigureEntityChatelaineSlots；删除有物品的槽前先取下。

取下时向 ExchangeEntityCurioItem 传 `{}`；确认 success=True 且 reason 为 ok 后，由提供方接管 previousItem。保存失败或修订冲突时不得发放旧物品。数据更新接口 ReplaceEntityCurioItemData 不代表取下，其 previousItem 只能用于比较。

## 8. 配置佩戴外观

先在自己的 RP 准备模型、贴图及 render controller，再在第 3 步的物品映射中增加 equippedVisual。例如：

```python
payload["items"][0]["equippedVisual"] = {
    "visualId": "your_mod:relic",
    "geometry": {
        "key": "your_mod_relic_geo", "resource": "geometry.your_mod.relic"
    },
    "textures": [{
        "key": "your_mod_relic_tex", "resource": "textures/entity/your_mod/relic"
    }],
    "materials": [{
        "key": "your_mod_relic_mat", "resource": "entity_alphatest"
    }],
    "renderController": "controller.render.your_mod.relic",
    "nativeSlotBlock": {"slots": ["chest"], "operator": "or"},
    "entity": {
        "modelsByEntity": {
            "minecraft:pig": {
                "geometry": {
                    "key": "your_mod_relic_geo",
                    "resource": "geometry.your_mod.pig_relic"
                }
            }
        }
    }
}
```

此例中，玩家穿胸甲时隐藏外观；猪替换 geometry 资源并沿用同一 key，因此可继承基础纹理、材质和控制器。若改用不同 key，也需让控制器引用新别名。其他实体只有位于附着物名单时才使用基础模型。非玩家不使用 nativeSlotBlock，穿戴原生盔甲不会遮挡饰品。

若自己的 `your_mod:guard` 客户端实体定义已设置 `enable_attachables=True`，可在注册数据顶层追加：

```python
payload["attachableEntities"] = ["your_mod:guard"]
```

该声明不会修改 guard 的 JSON。指定类型模型优先于名单回退；不在名单的类型也可通过 modelsByEntity 提供专用模型。省略的模型字段继承，数组则整体替换。

同外观在非玩家多个槽中默认合并显示；如需两个独立模型，额外声明不同的控制器资源：

```python
payload["items"][0]["equippedVisual"]["entity"]["renderControllersBySlot"] = {
    "chatelaine:ring_1": "controller.render.your_mod.relic_left",
    "chatelaine:ring_2": "controller.render.your_mod.relic_right"
}
```

映射必须覆盖全部兼容槽，两个控制器也必须存在于 RP。资源中的骨骼、动画和 Molang 表达式需要适合目标实体；Chatelaine 不自动改造模型。第一人称需要独立资源对象，详细格式见[外观配置](Chatelaine公开接口文档.md#外观配置)。

临时隐藏某只实体的一个槽：

```python
chatelaine.SetEntityCurioSlotVisualEnabled(entity_id, "chatelaine:ring_1", False)
chatelaine.ResetEntityCurioSlotVisualEnabled(entity_id, "chatelaine:ring_1")
state = chatelaine.GetEntityCurioSlotVisualState(entity_id, "chatelaine:ring_1")
```

开关不保存到存档，隐藏不取下物品。visible=True 只说明服务端允许显示，还需确认客户端模型实际呈现。

## 9. 排查接入问题

| 现象 | 检查方法 |
| --- | --- |
| GetSystem 返回 None | 检查核心 BP 是否启用，是否在所有服务端脚本加载后获取 |
| registry_frozen | 将注册移回 LoadServerAddonScriptsAfter 同步回调，完整重载 |
| unknown_item | 核对 BP 物品 identifier 和载入日志，先保证物品存在 |
| accepted=True 但 ready=False | 查看 GetRegistryStatus 的 errors，检查类型引用、资源别名及冲突 |
| 槽不显示或无法放入 | 检查最终快照、类型交集、数量、原生堆叠上限和锁定属性 |
| 实体快照为空 | 检查是否为存活非玩家 Mob、注册表是否就绪、是否已初始化 |
| revision_conflict | 重新读快照并重新决定动作，不盲目重试交付 |
| 实体有装备但无模型 | 检查 entity.enabled、类型模型、最终附着名单、槽开关及 RP 资源 |
| 模型存在但位置不对 | 在目标实体上调整 geometry、骨骼、动画和控制器 |
| 装备变更后效果未更新 | 读取当前快照并检查 GetEventDeliveryStatus，修正自己的监听器 |

发布自己的接入包前，在经典／触屏界面检查放入、取下、快捷装备和重进恢复；有外观时再检查不同实体、同类型多实例、双槽和多观察者。移除提供方前先取出玩家槽物品；分发沿用的素材时保留[来源及许可证](THIRD_PARTY_LICENSES/curios-9.5.1/SOURCE.md)。
