# -*- coding: utf-8 -*-
from mod.common.mod import Mod
import mod.client.extraClientApi as clientApi
import mod.server.extraServerApi as serverApi


@Mod.Binding(name="ChatelaineCoreMod", version="1.0.0")
class ChatelaineCoreMod(object):

    @Mod.InitServer()
    def serverInit(self):
        serverApi.RegisterSystem(
            "chatelaine_api",
            "ChatelaineServerSystem",
            "chatelaine_aggregator.server_system.ChatelaineServerSystem",
        )

    @Mod.DestroyServer()
    def serverDestroy(self):
        system = serverApi.GetSystem("chatelaine_api", "ChatelaineServerSystem")
        if system is not None:
            system.destroy()

    @Mod.InitClient()
    def clientInit(self):
        clientApi.RegisterSystem(
            "chatelaine_api",
            "ChatelaineClientSystem",
            "chatelaine_aggregator.client_system.ChatelaineClientSystem",
        )

    @Mod.DestroyClient()
    def clientDestroy(self):
        system = clientApi.GetSystem("chatelaine_api", "ChatelaineClientSystem")
        if system is not None:
            system.Destroy()
