// ProjectE PE1.0.1B sends its own update message when the local player joins.
// That subscriber only posts this notice. Forge's version check can still run.
(() => {
  const Forge = Java.loadClass('net.minecraftforge.common.MinecraftForge')
  const Notifier = Java.loadClass('moze_intel.projecte.network.ThreadCheckUpdate')
  Forge.EVENT_BUS.unregister(Notifier.__javaObject__)
})()
