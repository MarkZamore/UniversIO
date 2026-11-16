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

  // On this Forge version mods can add x()/y() alongside the mapped fields.
  // Rhino 284 then exposes overloaded field/method objects instead of numbers.
  const widgetClass = Widget.__javaObject__
  const xField = widgetClass.getField('f_93620_')
  const yField = widgetClass.getField('f_93621_')
  const visibleField = widgetClass.getField('f_93624_')

  function bounds(widget) {
    return { x: xField.getInt(widget), y: yField.getInt(widget),
      width: widget.getWidth(), height: widget.getHeight() }
  }

  function overlaps(a, b) {
    return a.x < b.x + b.width && a.x + a.width > b.x &&
      a.y < b.y + b.height && a.y + a.height > b.y
  }

  // FancyMenu's render-pre listener can reapply layout changes on a resize.
  function alignReports(screen) {
    if (!(screen instanceof PauseScreen)) return
    const widgets = []
    let reports = null
    let options = null
    let stats = null
    const children = screen.children().iterator()
    while (children.hasNext()) {
      let widget = children.next()
      if (!(widget instanceof Widget) || !visibleField.getBoolean(widget)) continue
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
    if (reports == null || options == null || stats == null) return
    const original = bounds(reports)
    const target = { x: xField.getInt(stats), y: yField.getInt(options),
      width: original.width, height: original.height }
    if (target.x <= xField.getInt(options) || yField.getInt(stats) >= target.y) return
    const others = widgets.filter(widget => widget !== reports).map(bounds)
    if (!others.some(widget => overlaps(original, widget))) return
    if (others.some(widget => overlaps(target, widget))) return
    xField.setInt(reports, target.x)
    yField.setInt(reports, target.y)
  }

  let disabled = false
  Forge.EVENT_BUS.addListener(Priority.LOWEST, false, RenderPre, event => {
    if (disabled) return
    try {
      alignReports(event.getScreen())
    } catch (error) {
      disabled = true
      console.warn('UniversIO pause layout disabled: ' + error)
    }
  })
})()
