// FancyMenu's copy-player option looks up a Mojang account by name. Load the
// local profile's texture through Minecraft instead, including launcher skins.
(() => {
  const Minecraft = Java.loadClass('net.minecraft.client.Minecraft')
  const TitleScreen = Java.loadClass('net.minecraft.client.gui.screens.TitleScreen')
  const Forge = Java.loadClass('net.minecraftforge.common.MinecraftForge')
  const Priority = Java.loadClass('net.minecraftforge.eventbus.api.EventPriority')
  const ScreenRenderPost = Java.loadClass('net.minecraftforge.client.event.ScreenEvent$Render$Post')
  const SkinType = Java.loadClass('com.mojang.authlib.minecraft.MinecraftProfileTexture$Type').SKIN
  const Players = Java.loadClass('de.keksuccino.fancymenu.menu.fancy.item.items.playerentity.PlayerEntityCustomizationItemContainer')
  const titlePlayer = 'a378933c-23ad-4424-a48d-e77735ad8a0a1671843070430'
  let skinLocation = null
  let slim = false
  let nextLookup = 0

  // In this KubeJS release the paint and tick events require an in-world player.
  Forge.EVENT_BUS.addListener(Priority.LOWEST, false, ScreenRenderPost, event => {
    if (!(event.getScreen() instanceof TitleScreen)) return
    const model = Players.ELEMENT_CACHE.get(titlePlayer)
    if (model == null || !model.copyClientPlayer) return

    if (skinLocation == null) {
      const now = Date.now()
      if (now < nextLookup) return
      nextLookup = now + 1000
      const client = Minecraft.getInstance()
      const profile = client.getUser().getGameProfile()
      // This reads the local texture property. Minecraft's texture manager
      // handles downloading and registering the PNG asynchronously.
      const skin = client.getMinecraftSessionService().getTextures(profile, false).get(SkinType)
      if (skin == null) return
      skinLocation = client.getSkinManager().registerTexture(skin, SkinType)
      slim = String(skin.getMetadata('model')) === 'slim'
    }

    model.slim = slim
    const properties = model.getActiveEntityProperties()
    if (!skinLocation.equals(properties.getSkinTextureLocation())) {
      properties.setSkinTextureLocation(skinLocation)
    }
  })
})()
