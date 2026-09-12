# -*- coding: utf-8 -*-
import mod.server.extraServerApi as serverApi


ServerSystem = serverApi.GetServerSystemCls()


class ChatelaineProviderBetaServerSystem(ServerSystem):

    def __init__(self, namespace, systemName):
        ServerSystem.__init__(self, namespace, systemName)
        self.ListenForEvent(
            serverApi.GetEngineNamespace(),
            serverApi.GetEngineSystemName(),
            "LoadServerAddonScriptsAfter",
            self,
            self.OnAllServerAddonsLoaded,
        )

    def OnAllServerAddonsLoaded(self, args=None):
        registry = serverApi.GetSystem("chatelaine_api", "ChatelaineServerSystem")
        if registry is None:
            print "[Chatelaine][ProviderBeta] REGISTER registry_missing"
            return
        result = registry.RegisterContribution(
            "chatelaine:slot_provider",
            1,
            "chatelaine_provider_beta",
            {
                "schemaVersion": 1,
                "types": [],
                "pages": [],
                "items": [
                    {
                        "itemId": "chatelaine_provider_beta:test_ring",
                        "types": ["chatelaine:ring"],
                        "equipOnUse": True,
                    },
                ],
            },
        )
        print "[Chatelaine][ProviderBeta] REGISTER result=%s" % result
