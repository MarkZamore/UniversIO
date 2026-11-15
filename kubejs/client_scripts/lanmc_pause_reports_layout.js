// FancyMenu 2.x places the LAN button, but has no identifier for the
// reporting button that replaces it after the host publishes the world.
(() => {
  const PauseScreen = Java.loadClass('net.minecraft.client.gui.screens.PauseScreen')
  const Widget = Java.loadClass('net.minecraft.client.gui.components.AbstractWidget')
  const Button = Java.loadClass('net.minecraft.client.gui.components.Button')
  const Translatable = Java.loadClass('net.minecraft.network.chat.contents.TranslatableContents')
  const Forge = Java.loadClass('net.minecraftforge.common.MinecraftForge')
  const Priority = Java.loadClass('net.minecraftforge.eventbus.api.EventPriority')
  const RenderPre = Java.loadClass('net.minecraftforge.client.event.ScreenEvent$Render$Pre')

  function overlaps(x, y, width, height, widget) {
    return x < widget.x + widget.getWidth() && x + width > widget.x &&
      y < widget.y + widget.getHeight() && y + height > widget.y
  }

  // FancyMenu's render-pre listener can reapply layout changes on a resize.
  Forge.EVENT_BUS.addListener(Priority.LOWEST, false, RenderPre, event => {
    const screen = event.getScreen()
    if (!(screen instanceof PauseScreen)) return
    const widgets = []
    let reports = null
    let options = null
    let stats = null
    const children = screen.children().iterator()
    while (children.hasNext()) {
      let widget = children.next()
      if (!(widget instanceof Widget) || !widget.visible) continue
      widgets.push(widget)
      if (!(widget instanceof Button)) continue
      let contents = widget.getMessage().getContents()
      if (!(contents instanceof Translatable)) continue
      switch (String(contents.getKey())) {
        case 'menu.playerReporting': reports = widget; break
        case 'menu.options': options = widget; break
        case 'gui.stats': stats = widget; break
      }
    }
    if (reports == null || options == null || stats == null || stats.x <= options.x || stats.y >= options.y) return
    const width = reports.getWidth()
    const height = reports.getHeight()
    const others = widgets.filter(widget => widget !== reports)
    if (!others.some(widget => overlaps(reports.x, reports.y, width, height, widget))) return
    if (others.some(widget => overlaps(stats.x, options.y, width, height, widget))) return
    reports.x = stats.x
    reports.y = options.y
  })
})()
