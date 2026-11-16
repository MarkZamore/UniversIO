// Inventory HUD+ 3.4.7 installs a separate listener for its update message.
(() => {
  const Forge = Java.loadClass('net.minecraftforge.common.MinecraftForge')
  const EventBus = Java.loadClass('net.minecraftforge.eventbus.EventBus')
  const Priority = Java.loadClass('net.minecraftforge.eventbus.api.EventPriority')
  const ScreenInitPost = Java.loadClass('net.minecraftforge.client.event.ScreenEvent$Init$Post')
  const TitleScreen = Java.loadClass('net.minecraft.client.gui.screens.TitleScreen')
  const Notice = Java.loadClass('dlovin.inventoryhud.events.UpdateNotificationEvent')
  const bus = Forge.EVENT_BUS
  let attempted = false

  function removeNotice() {
    const registry = EventBus.__javaObject__.getDeclaredField('listeners')
    if (!registry.trySetAccessible()) throw new Error('Forge listener registry is inaccessible')
    const targets = registry.get(bus).keySet().iterator()
    while (targets.hasNext()) {
      let target = targets.next()
      if (target instanceof Notice) bus.unregister(target)
    }
  }

  // Client setup has registered the listener by the time the title screen opens.
  bus.addListener(Priority.LOWEST, false, ScreenInitPost, event => {
    if (attempted || !(event.getScreen() instanceof TitleScreen)) return
    attempted = true
    try {
      removeNotice()
    } catch (error) {
      console.warn('UniversIO could not remove the Inventory HUD+ update notice: ' + error)
    }
  })
})()
