// FancyMenu's copy-player option looks up a Mojang account by name. Load the
// local profile's texture through Minecraft instead, including launcher skins.
(() => {
  const TitleScreen = Java.loadClass('net.minecraft.client.gui.screens.TitleScreen')
  const SkinType = Java.loadClass('com.mojang.authlib.minecraft.MinecraftProfileTexture$Type').SKIN
  const Players = Java.loadClass('de.keksuccino.fancymenu.menu.fancy.item.items.playerentity.PlayerEntityCustomizationItemContainer')
  const titlePlayer = 'a378933c-23ad-4424-a48d-e77735ad8a0a1671843070430'
  let skinLocation = null
  let slim = false
  let nextLookup = 0

  ClientEvents.paintScreen(event => {
    if (!(event.screen instanceof TitleScreen)) return
    const model = Players.ELEMENT_CACHE.get(titlePlayer)
    if (model == null || !model.copyClientPlayer) return

    if (skinLocation == null) {
      const now = Date.now()
      if (now < nextLookup) return
      nextLookup = now + 1000
      const profile = event.mc.getUser().getGameProfile()
      // This reads the local texture property. Minecraft's texture manager
      // handles downloading and registering the PNG asynchronously.
      const skin = event.mc.getMinecraftSessionService().getTextures(profile, false).get(SkinType)
      if (skin == null) return
      skinLocation = event.mc.getSkinManager().registerTexture(skin, SkinType)
      slim = String(skin.getMetadata('model')) === 'slim'
    }

    model.slim = slim
    const properties = model.getActiveEntityProperties()
    if (!skinLocation.equals(properties.getSkinTextureLocation())) {
      properties.setSkinTextureLocation(skinLocation)
    }
  })
})()
