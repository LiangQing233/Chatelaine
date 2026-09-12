# -*- coding: utf-8 -*-
from mod.common.mod import Mod
import mod.server.extraServerApi as serverApi


@Mod.Binding(name="ChatelaineProviderBetaMod", version="1.0.0")
class ChatelaineProviderBetaMod(object):

    @Mod.InitServer()
    def serverInit(self):
        serverApi.RegisterSystem(
            "chatelaine_provider_beta",
            "ChatelaineProviderBetaServerSystem",
            "chatelaine_provider_beta.server_system.ChatelaineProviderBetaServerSystem",
        )

    @Mod.DestroyServer()
    def serverDestroy(self):
        pass
